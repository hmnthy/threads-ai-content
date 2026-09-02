from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MediaType(StrEnum):
    TEXT_POST = "TEXT_POST"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    CAROUSEL_ALBUM = "CAROUSEL_ALBUM"
    AUDIO = "AUDIO"
    REPOST_FACADE = "REPOST_FACADE"


class ThreadsPost(BaseModel):
    id: str
    text: str | None = None
    timestamp: datetime
    media_type: MediaType
    permalink: str | None = None
    shortcode: str | None = None
    username: str | None = None
    media_url: str | None = None
    thumbnail_url: str | None = None
    is_quote_post: bool = False
    quoted_post: dict[str, Any] | None = None
    reposted_post: dict[str, Any] | None = None
    children: list[str] = Field(default_factory=list)

    # Fields cho thread reconstruction — verify live 2026-08-30 (xem docs/claude/data-model.md
    # bảng "Fields cho thread reconstruction"). root_post/replied_to trả về edge dạng
    # {"id": "..."} giống quoted_post/reposted_post — giữ nguyên dict, không flatten, dùng
    # property root_post_id/replied_to_id bên dưới cho tiện.
    root_post: dict[str, Any] | None = None
    replied_to: dict[str, Any] | None = None
    is_reply: bool = False
    is_reply_owned_by_me: bool = False
    has_replies: bool = False
    is_spoiler_media: bool = False

    # Context field mở rộng — verify live 2026-08-30: KHÔNG lỗi nhưng 0/100 item có data
    # (test 50 post + 50 reply). Lưu schema nullable, KHÔNG dùng trong scoring tới khi có
    # post thật dùng chúng.
    text_attachment: str | None = None
    is_ghost_post: bool | None = None
    poll_attachment: dict[str, Any] | None = None
    gif_attachment: dict[str, Any] | None = None
    location_id: str | None = None
    enable_reply_approvals: bool | None = None

    @field_validator("children", mode="before")
    @classmethod
    def _flatten_children_edge(cls, value: Any) -> list[str]:
        """The Graph API returns children as an edge (`{"data": [{"id": ...}, ...]}`)."""
        if value is None:
            return []
        if isinstance(value, dict):
            return [item["id"] for item in value.get("data", [])]
        return value  # type: ignore[no-any-return]

    @field_validator("text_attachment", mode="before")
    @classmethod
    def _flatten_text_attachment_edge(cls, value: Any) -> str | None:
        """Verify live 2026-08-31: NGƯỢC với ghi chú trước (0/100 item có data lúc
        test mẫu nhỏ 2026-08-30) — trên toàn bộ 1,285 replies thật, tác giả CÓ dùng
        text_attachment. Response shape thật là `{"plaintext": "..."}`, không phải
        string phẳng như giả định ban đầu trong data-model.md — cập nhật giả định
        này tại đây, xem thêm ghi chú trong data-model.md."""
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value.get("plaintext")
        return value  # type: ignore[no-any-return]

    @property
    def root_post_id(self) -> str | None:
        return self.root_post.get("id") if self.root_post else None

    @property
    def replied_to_id(self) -> str | None:
        return self.replied_to.get("id") if self.replied_to else None


class PostInsights(BaseModel):
    post_id: str
    views: int = 0
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    quotes: int = 0

    @property
    def engagement_rate(self) -> float:
        """(likes + replies + reposts + quotes) / views * 100 — see docs/claude/data-model.md
        "Metric Architecture". SỬA 2026-08-30: công thức cũ thiếu `quotes` ở tử số."""
        if self.views == 0:
            return 0.0
        return (self.likes + self.replies + self.reposts + self.quotes) / self.views * 100


class AccountInsights(BaseModel):
    views: int = 0
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    quotes: int = 0
    clicks: int = 0
    followers_count: int = 0
    follower_demographics: dict[str, Any] | None = None


class UserInfo(BaseModel):
    id: str
    username: str
