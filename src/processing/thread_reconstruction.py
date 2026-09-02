"""Build `ContentUnit` từ `ThreadsPost` root (get_posts()) + continuations
(get_replies(), lọc is_reply_owned_by_me=True) — xem docs/claude/data-model.md
mục "ContentUnit — abstraction cho thread dài + text attachment".
"""

from __future__ import annotations

from src.api.models import MediaType, ThreadsPost
from src.models.content_unit import ContentUnit


def build_content_units(posts: list[ThreadsPost], replies: list[ThreadsPost]) -> list[ContentUnit]:
    """1 ContentUnit cho mỗi root post trong `posts`, nối với self-reply continuation
    của CHÍNH tác giả tìm thấy trong `replies`.

    Group theo `root_post_id` (verify live 2026-08-30: Threads trả `root_post` trỏ
    thẳng tới gốc của CẢ chuỗi reply bất kể độ sâu, không chỉ parent trực tiếp — nên
    không cần tự đệ quy theo `replied_to`). Audience reply (`is_reply_owned_by_me=False`)
    bị loại — đó là tín hiệu `conversation_rate`, không phải nội dung.
    """
    own_continuations = [reply for reply in replies if reply.is_reply_owned_by_me]
    continuations_by_root: dict[str, list[ThreadsPost]] = {}
    for reply in own_continuations:
        root_id = reply.root_post_id
        if root_id is None:
            continue
        continuations_by_root.setdefault(root_id, []).append(reply)

    return [
        _build_unit(
            root, sorted(continuations_by_root.get(root.id, []), key=lambda post: post.timestamp)
        )
        for root in posts
    ]


def _build_unit(root: ThreadsPost, continuations: list[ThreadsPost]) -> ContentUnit:
    chain = [root, *continuations]
    text_attachment = next((post.text_attachment for post in chain if post.text_attachment), None)
    full_text = " ".join(post.text for post in chain if post.text)
    media = [post for post in chain if post.media_type != MediaType.TEXT_POST]
    return ContentUnit(
        root=root,
        continuations=continuations,
        text_attachment=text_attachment,
        full_text=full_text,
        media=media,
    )
