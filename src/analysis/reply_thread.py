"""Layer 6 — reply-level analysis, tính trực tiếp trên graph đã có sẵn trong
bảng `posts` (`is_reply`, `replied_to_id`, `root_post_id`, `is_reply_owned_by_me`
— xem `src/db/schema.py`), phục vụ 1.285 replies đã ingest nhưng trước giờ chỉ
đóng góp dưới dạng đếm gộp trong `conversation_rate` (`replies/views*100`).

Căn cứ chính thức: Meta Transparency Center — "Instagram Threads Feed AI system"
liệt kê "engagement của descendant ở level 2 trong 1h/6h" là 1 prediction feature
THẬT trong ranking — cho phép trích dẫn nguồn official khi trình bày hạng mục này
(unique_repliers/reply_depth/early_reply_velocity), không phải tự bịa signal.

Chỉ đo tầng 1-2 "Narrative Layering Principle" (số thô + rate đơn giản, xem
docs/claude/data-model.md) — so sánh nhóm (VD post có reply sâu vs không) dùng
`src/analysis/significance.py` ở tầng gọi hàm này, không lặp lại logic thống kê
ở đây.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from src.api.models import ThreadsPost
from src.db.schema import get_post


def _replies_of_root(conn: sqlite3.Connection, root_post_id: str) -> list[sqlite3.Row]:
    """Toàn bộ row `posts` (audience VÀ self-reply) có `root_post_id` trỏ về
    `root_post_id` — Threads trả `root_post` trỏ thẳng gốc bất kể độ sâu (verify
    live 2026-08-30, xem `thread_reconstruction.py`), nên 1 câu SQL là đủ, không
    cần tự đệ quy theo `replied_to_id` để TÌM các reply thuộc thread này."""
    return conn.execute(
        "SELECT * FROM posts WHERE root_post_id = ? AND is_reply = 1",
        (root_post_id,),
    ).fetchall()


def unique_repliers(root_post_id: str, conn: sqlite3.Connection) -> int:
    """Số người reply RIÊNG BIỆT, KHÔNG tính reply của chính tác giả
    (`is_reply_owned_by_me=True` bị loại — đó là tác giả tự nối tiếp nội dung,
    không phải audience).

    Dùng `ThreadsPost.username` khi có (field thật đã verify — xem docs/claude/
    data-model.md bảng "Fields có thể lấy từ mỗi post") để gộp nhiều reply cùng 1
    người thành 1. **Hạn chế đã biết** (ghi rõ theo yêu cầu, không giấu): với
    reply thiếu `username` (`None`), dùng chính `post.id` làm proxy — nghĩa là 2
    reply thiếu `username` của CÙNG 1 người bị đếm thành 2 người khác nhau
    (over-count theo hướng an toàn — không bao giờ under-count 1 người thành 0).
    `posts` không lưu cột `username` riêng — đọc lại từ `raw_json` (archive nguyên
    vẹn lúc ingest, xem `upsert_post`).
    """
    identities: set[str] = set()
    for row in _replies_of_root(conn, root_post_id):
        if bool(row["is_reply_owned_by_me"]):
            continue
        post = ThreadsPost.model_validate_json(row["raw_json"])
        identities.add(post.username if post.username is not None else post.id)
    return len(identities)


def reply_depth(root_post_id: str, conn: sqlite3.Connection) -> int:
    """Độ sâu tối đa của chuỗi `replied_to_id` tính từ root — 0 nếu không có reply
    nào, 1 nếu chỉ có reply trực tiếp vào root, >=2 nếu có reply-to-reply.

    Tính trên TOÀN BỘ graph (cả audience lẫn self-reply) — khác `unique_repliers`/
    `early_reply_velocity` (chỉ audience) — vì độ sâu là thuộc tính CẤU TRÚC của
    cả cuộc hội thoại (audience có thể reply vào 1 self-continuation của tác giả,
    vẫn tính vào độ sâu thật của thread).
    """
    rows = _replies_of_root(conn, root_post_id)
    if not rows:
        return 0
    parent_of: dict[str, str | None] = {row["id"]: row["replied_to_id"] for row in rows}

    def _depth(post_id: str, visited: frozenset[str]) -> int:
        if post_id in visited:
            return 0  # cycle guard — không nên xảy ra với data thật, phòng hờ
        parent = parent_of.get(post_id)
        if parent is None or parent not in parent_of:
            return 1  # reply trực tiếp vào root (hoặc parent nằm ngoài thread này)
        return 1 + _depth(parent, visited | {post_id})

    return max(_depth(post_id, frozenset()) for post_id in parent_of)


def early_reply_velocity(
    root_post_id: str, conn: sqlite3.Connection, window_hours: float = 24.0
) -> float:
    """Số reply CỦA AUDIENCE / giờ trong `window_hours` đầu tiên kể từ lúc root
    post đăng — proxy cho "reply velocity" (chỉ audience, giống `unique_repliers`
    — self-continuation của tác giả không phải tín hiệu audience engagement).

    `window_hours` khớp `post_maturity_window` (0-72h, xem "Metric Architecture")
    khi cần so sánh với velocity view/amplification cùng khung thời gian. Trả
    `0.0` nếu root post không có trong DB. Raise `ValueError` nếu `window_hours <= 0`.
    """
    if window_hours <= 0:
        raise ValueError("window_hours phải > 0")
    root_row = get_post(conn, root_post_id)
    if root_row is None:
        return 0.0
    root_ts = datetime.fromisoformat(root_row["timestamp"])
    count = 0
    for row in _replies_of_root(conn, root_post_id):
        if bool(row["is_reply_owned_by_me"]):
            continue
        elapsed_hours = (datetime.fromisoformat(row["timestamp"]) - root_ts).total_seconds() / 3600
        if 0 <= elapsed_hours <= window_hours:
            count += 1
    return count / window_hours
