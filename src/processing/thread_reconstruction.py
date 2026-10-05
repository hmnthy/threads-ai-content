"""Build `ContentUnit` từ `ThreadsPost` root (get_posts()) + reply của chính tác giả
(get_replies()) — xem docs/claude/data-model.md mục "ContentUnit — abstraction cho
thread dài + text attachment" và ADR-0004 (phân vai reply).

`/me/replies` chỉ trả reply của CHÍNH chủ tài khoản, nhưng các reply đó có 3 vai rất
khác nhau — chỉ vai đầu là nội dung của bài:
- `self_continuation`: tác giả viết tiếp bài của mình (reply vào root hoặc vào đoạn
  nối chuỗi ngay trước) → gộp vào `full_text`.
- `author_answer`: tác giả trả lời bình luận của follower dưới bài của mình (kể cả
  viết tiếp bên dưới chính câu trả lời đó) → KHÔNG gộp; là nửa sau của 1 cặp hỏi-đáp.
- `outbound`: reply trên bài của người khác → không thuộc content unit nào.
"""

from __future__ import annotations

from typing import Literal

from src.api.models import MediaType, ThreadsPost
from src.models.content_unit import ContentUnit

ReplyRole = Literal["self_continuation", "author_answer", "outbound"]


def assign_reply_roles(
    posts: list[ThreadsPost], replies: list[ThreadsPost]
) -> dict[str, ReplyRole]:
    """Gán vai cho mỗi reply của tác giả (bỏ qua reply không phải của tác giả).

    Quy tắc (roadmap D0, Thy chốt 2026-10-01): reply là `self_continuation` khi đi
    ngược `replied_to` qua toàn các reply `self_continuation` của chính tác giả (cùng
    root) thì tới được root — tức `replied_to ∈ {root} ∪ {các continuation}`. Mọi reply
    khác dưới bài của tác giả — vào bình luận follower, vào câu trả lời follower của
    chính tác giả, hoặc `replied_to` rỗng (bình luận gốc đã xoá/ẩn) — là `author_answer`:
    không chứng minh được là nội dung bài thì không gộp. `root_post_id` không phải 1 root
    trong `posts` → `outbound`.

    KHÔNG dùng timestamp để suy quan hệ: các phần của 1 thread đăng bằng composer nhiều
    phần có timestamp trùng nhau (độ phân giải giây), thậm chí con sớm hơn cha vài giây
    (đo 2026-10-01: 57 reply trùng giờ cha, 12 reply sớm hơn cha). Chỉ dùng đồ thị
    `replied_to`, kết quả không phụ thuộc thứ tự đầu vào.

    Số đo trên data thật 2026-10-01: 353 self_continuation / 674 author_answer /
    342 outbound.
    """
    root_ids = {post.id for post in posts}
    own = {reply.id: reply for reply in replies if reply.is_reply_owned_by_me}
    memo: dict[str, bool] = {}

    def reaches_root(post_id: str, root_id: str) -> bool:
        """True nếu đi ngược `replied_to` từ `post_id` qua reply của tác giả (cùng
        root) tới được `root_id`. Vòng lặp (không đệ quy — chuỗi dài không chạm giới
        hạn đệ quy), memo cho cả đường đi, chặn vòng lặp trong dữ liệu."""
        path: list[str] = []
        seen: set[str] = set()
        current = post_id
        while True:
            if current in memo:
                result = memo[current]
                break
            if current in seen:
                result = False
                break
            seen.add(current)
            path.append(current)
            parent = own[current].replied_to_id
            if parent == root_id:
                result = True
                break
            if parent is None or parent not in own or own[parent].root_post_id != root_id:
                result = False
                break
            current = parent
        for visited in path:
            memo[visited] = result
        return result

    roles: dict[str, ReplyRole] = {}
    for reply_id, reply in own.items():
        root_id = reply.root_post_id
        if root_id is None or root_id not in root_ids:
            roles[reply_id] = "outbound"
        elif reaches_root(reply_id, root_id):
            roles[reply_id] = "self_continuation"
        else:
            roles[reply_id] = "author_answer"
    return roles


def build_content_units(posts: list[ThreadsPost], replies: list[ThreadsPost]) -> list[ContentUnit]:
    """1 ContentUnit cho mỗi root post trong `posts`, nối với các reply có vai
    `self_continuation` (xem `assign_reply_roles`). Câu trả lời follower và reply
    ngoài kênh KHÔNG vào `continuations`/`full_text`."""
    roles = assign_reply_roles(posts, replies)
    continuations_by_root: dict[str, list[ThreadsPost]] = {}
    for reply in replies:
        if roles.get(reply.id) != "self_continuation":
            continue
        root_id = reply.root_post_id
        if root_id is not None:
            continuations_by_root.setdefault(root_id, []).append(reply)

    return [
        _build_unit(root, _thread_order(root.id, continuations_by_root.get(root.id, [])))
        for root in posts
    ]


def _thread_order(root_id: str, continuations: list[ThreadsPost]) -> list[ThreadsPost]:
    """Thứ tự đọc của thread: duyệt theo chiều sâu (DFS) từ root theo `replied_to`;
    các nhánh con cùng cha xếp theo (timestamp, id). Không xếp thẳng theo timestamp —
    timestamp trùng/ngược giữa cha và con (xem `assign_reply_roles`)."""
    children: dict[str, list[ThreadsPost]] = {}
    for post in continuations:
        children.setdefault(post.replied_to_id or "", []).append(post)
    for siblings in children.values():
        siblings.sort(key=lambda post: (post.timestamp, post.id))
    ordered: list[ThreadsPost] = []
    stack = list(reversed(children.get(root_id, [])))
    seen: set[str] = set()
    while stack:
        post = stack.pop()
        if post.id in seen:
            continue
        seen.add(post.id)
        ordered.append(post)
        stack.extend(reversed(children.get(post.id, [])))
    return ordered


def _build_unit(root: ThreadsPost, continuations: list[ThreadsPost]) -> ContentUnit:
    chain = [root, *continuations]
    text_attachment = next((post.text_attachment for post in chain if post.text_attachment), None)
    # full_text = root + self_continuation + text_attachment (roadmap D0 bước 2) —
    # text_attachment (tới 10.000 ký tự) là nội dung bài, trước đây bị bỏ khỏi full_text
    parts = [post.text for post in chain if post.text]
    if text_attachment:
        parts.append(text_attachment)
    full_text = " ".join(parts)
    media = [post for post in chain if post.media_type != MediaType.TEXT_POST]
    return ContentUnit(
        root=root,
        continuations=continuations,
        text_attachment=text_attachment,
        full_text=full_text,
        media=media,
    )
