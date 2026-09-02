"""ContentUnit — abstraction "1 bài content" cho thread dài (self-reply chain) +
text attachment, tách khỏi `ThreadsPost` (raw ingestion layer, map 1:1 media object).

Xem docs/claude/data-model.md mục "ContentUnit — abstraction cho thread dài + text
attachment" cho lý do thiết kế đầy đủ. Được build từ `src/processing/thread_reconstruction.py`,
KHÔNG tự construct trực tiếp field `full_text` ở đây — module này chỉ là data holder bất biến.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.api.models import ThreadsPost


@dataclass(frozen=True)
class ContentUnit:
    """1 "bài content" hoàn chỉnh — root post + chuỗi self-reply continuations do
    CHÍNH tác giả đăng tiếp (is_reply_owned_by_me=True), nối theo root_post/replied_to.

    Audience replies KHÔNG gộp vào đây — chúng là tín hiệu `conversation_rate`, không
    phải nội dung. Embedding/topic detection chạy trên `full_text`, không phải riêng
    `root.text`.
    """

    root: ThreadsPost
    continuations: list[ThreadsPost] = field(default_factory=list)
    text_attachment: str | None = None
    full_text: str = ""
    media: list[ThreadsPost] = field(default_factory=list)

    @property
    def id(self) -> str:
        """ID của ContentUnit = id của root post — dùng làm khóa chính khi lưu DB."""
        return self.root.id

    @property
    def is_multi_post(self) -> bool:
        """True nếu content này là 1 thread dài (root + >=1 continuation self-reply)."""
        return len(self.continuations) > 0
