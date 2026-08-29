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

    @field_validator("children", mode="before")
    @classmethod
    def _flatten_children_edge(cls, value: Any) -> list[str]:
        """The Graph API returns children as an edge (`{"data": [{"id": ...}, ...]}`)."""
        if value is None:
            return []
        if isinstance(value, dict):
            return [item["id"] for item in value.get("data", [])]
        return value  # type: ignore[no-any-return]


class PostInsights(BaseModel):
    post_id: str
    views: int = 0
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    quotes: int = 0

    @property
    def engagement_rate(self) -> float:
        """(likes + replies + reposts) / views * 100 — see docs/claude/data-model.md."""
        if self.views == 0:
            return 0.0
        return (self.likes + self.replies + self.reposts) / self.views * 100


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
