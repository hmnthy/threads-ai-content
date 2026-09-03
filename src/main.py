"""FastAPI app — đọc kết quả ĐÃ TÍNH SẴN từ SQLite (`data/threads.db`, seed bằng
`src/pipeline/ingest.py` + `src/pipeline/snapshot.py`, topic label bằng
`src/nlp/topics.py`). KHÔNG load model transformer / chạy lại embedding+clustering
mỗi request — đây là nguyên tắc kiến trúc đã chốt (batch compute tách khỏi serving
layer), xem docs/claude/architecture.md quyết định "Batch pipeline tách riêng khỏi
FastAPI serving layer".

Chạy: `uv run uvicorn src.main:app --reload --port 8000` (hoặc
`.venv/Scripts/python.exe -m uvicorn src.main:app --reload --port 8000`).
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date as date_cls
from typing import Final
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.analysis.conversation import conversation_rate
from src.analysis.engagement import (
    EngagementBucketStats,
    average_engagement_rate,
    engagement_by_hour,
    engagement_by_weekday,
    top_posts_by_engagement,
)
from src.analysis.popularity import popularity_index
from src.analysis.stats import DistributionStats, window_stats
from src.analysis.virality import virality_index
from src.api.models import PostInsights, ThreadsPost
from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    get_post,
    get_post_topic_label,
    latest_insight_snapshot,
    list_content_units,
    list_daily_views,
    list_root_posts,
    list_root_posts_in_range,
    snapshot_row_to_post_insights,
)

app = FastAPI(
    title="Threads AI Content API",
    description="Internal analytics API cho kênh Threads 'thydilammuon' — Phase 1.",
    version="0.1.0",
)

# Dashboard Next.js chạy local trên :3000. Cho phép thêm origin qua env
# CORS_ALLOW_ORIGINS (phân cách bằng dấu phẩy) — dùng khi deploy tạm frontend
# lên Vercel + backend qua ngrok tunnel, không hardcode domain tạm vào code.
_cors_env = os.environ.get("CORS_ALLOW_ORIGINS", "")
_extra_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", *_extra_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def _db() -> Generator[sqlite3.Connection]:
    conn = connect(DEFAULT_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


class ContentUnitMetrics(BaseModel):
    """6-index architecture (Bước 4) — chỉ 3 base index tính được ngay từ 1 snapshot
    insights (popularity/virality/conversation) + engagement_rate đã sửa (thêm
    quotes). velocity/longevity cần nhiều snapshot theo thời gian — chưa tính tối nay
    (Bước 5 phần tính toán, Bước 6 — deferred)."""

    popularity_index: int
    engagement_rate: float
    virality_index: float
    conversation_rate: float


class TopicLabel(BaseModel):
    topic_id: str
    method: str
    confidence: float | None


class ContentUnitOut(BaseModel):
    id: str
    text: str | None
    full_text: str
    is_multi_post: bool
    continuation_count: int
    timestamp: str | None
    metrics: ContentUnitMetrics | None
    topic: TopicLabel | None
    umap: list[float] | None  # [x, y, z] — null tới khi src/nlp/topics.py chạy


class TopicOut(BaseModel):
    id: str
    label_en: str
    description_en: str | None
    method: str
    post_count: int


# Audience trải cả Pháp và Việt Nam (verify live 2026-08-31 qua
# get_follower_demographics(breakdown="country"): 71.5% VN, 19.3% FR trên 1,423
# follower có dữ liệu country — xem report cuối). So sánh song song 2 timezone thay
# vì chọn 1, đúng quyết định đã chốt trong architecture.md cho engagement_by_hour/weekday.
ANALYTICS_TIMEZONES: Final = (
    ("Europe/Paris", ZoneInfo("Europe/Paris")),
    ("Asia/Ho_Chi_Minh", ZoneInfo("Asia/Ho_Chi_Minh")),
)
ANALYTICS_TOP_N: Final = 10


class TopPostEntry(BaseModel):
    id: str
    text: str | None
    timestamp: str
    metrics: ContentUnitMetrics


class DistributionStatsOut(BaseModel):
    """Mirror của `DistributionStats` (`src/analysis/stats.py`, generalize từ
    `EngagementBucketStats` cũ) — median/mean cạnh nhau CỐ TÌNH (tầng 3 "Narrative
    Layering Principle", xem docs/claude/data-model.md), kèm n/IQR/insufficient_data
    để dashboard không tuyên bố "tốt nhất" từ 1 tập quá ít bài. Dùng chung cho bucket
    giờ/thứ (`HourBucket`/`WeekdayBucket`) VÀ cho engagement/virality/conversation
    của `WindowAnalyticsOut` (Overview mới) — 1 shape, không lặp lại 2 lần."""

    median: float
    mean: float
    n: int
    iqr_low: float
    iqr_high: float
    insufficient_data: bool


class HourBucket(BaseModel):
    hour: int
    stats: DistributionStatsOut


class WeekdayBucket(BaseModel):
    weekday: int  # 0=Monday .. 6=Sunday, theo datetime.weekday()
    stats: DistributionStatsOut


class TimezoneEngagement(BaseModel):
    timezone: str
    by_hour: list[HourBucket]
    by_weekday: list[WeekdayBucket]


class AnalyticsOverviewOut(BaseModel):
    post_count: int
    average_engagement_rate: float
    top_by_engagement: list[TopPostEntry]
    top_by_virality: list[TopPostEntry]
    top_by_conversation: list[TopPostEntry]
    timezones: list[TimezoneEngagement]


class DailyViewsPointOut(BaseModel):
    date: str
    views: int


class DailyViewsSeriesOut(BaseModel):
    """Toàn bộ `account_daily_views` đã ingest — gọi 1 lần khi trang load để vẽ
    biểu đồ nền của Timeline Brush + xác định biên rail (`min_date`/`max_date`).
    KHÔNG đổi khi kéo cửa sổ — chỉ `WindowAnalyticsOut` (bên dưới) mới re-query
    theo [start, end]."""

    points: list[DailyViewsPointOut]
    min_date: str | None
    max_date: str | None


class WindowAnalyticsOut(BaseModel):
    """Hero band + KPI strip + top content units — tính lại từ data thật CHỈ trong
    [start, end]. `views` = Σ account_daily_views (account-level, gồm views từ
    replies) — KHÁC `top_content_units[].metrics.popularity_index` (post-level, per
    ContentUnit). `engagement`/`virality`/`conversation` là median+mean CỦA TỪNG
    POST trong cửa sổ (đúng methodology Layer 2 đã chốt) — KHÔNG phải pooled ratio
    Σinteractions/Σviews như mockup UI tự vẽ cho đẹp (xem `src/analysis/stats.py`
    docstring)."""

    start: str
    end: str
    views: int
    content_unit_count: int
    interactions: int
    engagement: DistributionStatsOut
    virality: DistributionStatsOut
    conversation: DistributionStatsOut
    top_content_units: list[TopPostEntry]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/content-units", response_model=list[ContentUnitOut])
def get_content_units() -> list[ContentUnitOut]:
    """List toàn bộ ContentUnit kèm 4 base metric (tính on-the-fly từ snapshot mới
    nhất — thuần arithmetic, KHÔNG phải chạy lại pipeline NLP) + topic label
    (`method="cluster"`, có thể null nếu post chưa được gán cluster)."""
    with _db() as conn:
        rows = list_content_units(conn)
        result: list[ContentUnitOut] = []
        for row in rows:
            post_row = get_post(conn, row["id"])
            continuation_ids = json.loads(row["continuation_ids_json"])

            metrics: ContentUnitMetrics | None = None
            snapshot = latest_insight_snapshot(conn, row["id"])
            if snapshot is not None:
                insights = snapshot_row_to_post_insights(snapshot)
                metrics = ContentUnitMetrics(
                    popularity_index=popularity_index(insights),
                    engagement_rate=insights.engagement_rate,
                    virality_index=virality_index(insights),
                    conversation_rate=conversation_rate(insights),
                )

            topic: TopicLabel | None = None
            topic_row = get_post_topic_label(conn, row["id"], method="cluster")
            if topic_row is not None:
                topic = TopicLabel(
                    topic_id=topic_row["topic_id"],
                    method=topic_row["method"],
                    confidence=topic_row["confidence"],
                )

            umap: list[float] | None = None
            if row["umap_x"] is not None:
                umap = [row["umap_x"], row["umap_y"], row["umap_z"]]

            result.append(
                ContentUnitOut(
                    id=row["id"],
                    text=post_row["text"] if post_row is not None else None,
                    full_text=row["full_text"],
                    is_multi_post=len(continuation_ids) > 0,
                    continuation_count=len(continuation_ids),
                    timestamp=post_row["timestamp"] if post_row is not None else None,
                    metrics=metrics,
                    topic=topic,
                    umap=umap,
                )
            )
        return result


@app.get("/topics", response_model=list[TopicOut])
def get_topics() -> list[TopicOut]:
    """List topic đã gán (fixed hoặc cluster) kèm số post thuộc mỗi topic — phục vụ
    legend/filter của Topic Explorer (dashboard)."""
    with _db() as conn:
        topic_rows = conn.execute("SELECT * FROM topics").fetchall()
        result: list[TopicOut] = []
        for topic in topic_rows:
            count_row = conn.execute(
                "SELECT COUNT(*) AS n FROM post_topic_labels WHERE topic_id = ?",
                (topic["id"],),
            ).fetchone()
            result.append(
                TopicOut(
                    id=topic["id"],
                    label_en=topic["label_en"],
                    description_en=topic["description_en"],
                    method=topic["method"],
                    post_count=count_row["n"],
                )
            )
        return result


def _load_root_posts_with_insights(
    conn: sqlite3.Connection,
) -> tuple[list[ThreadsPost], list[PostInsights]]:
    """Chỉ root post (khớp `list_root_posts`) có ít nhất 1 insight snapshot — dùng
    cho `src/analysis/engagement.py` (nhận `list[ThreadsPost]` + `list[PostInsights]`).
    `raw_json` được lưu nguyên vẹn lúc ingest (`upsert_post`), nên reconstruct lại
    `ThreadsPost` mà KHÔNG cần gọi lại API."""
    posts: list[ThreadsPost] = []
    insights: list[PostInsights] = []
    for row in list_root_posts(conn):
        snapshot = latest_insight_snapshot(conn, row["id"])
        if snapshot is None:
            continue
        posts.append(ThreadsPost.model_validate_json(row["raw_json"]))
        insights.append(snapshot_row_to_post_insights(snapshot))
    return posts, insights


def _to_top_post_entry(post: ThreadsPost, insights: PostInsights) -> TopPostEntry:
    return TopPostEntry(
        id=post.id,
        text=post.text,
        timestamp=post.timestamp.isoformat(),
        metrics=ContentUnitMetrics(
            popularity_index=popularity_index(insights),
            engagement_rate=insights.engagement_rate,
            virality_index=virality_index(insights),
            conversation_rate=conversation_rate(insights),
        ),
    )


def _to_stats_out(stats: EngagementBucketStats | DistributionStats) -> DistributionStatsOut:
    """Nhận cả `EngagementBucketStats` (bucket giờ/thứ) lẫn `DistributionStats`
    (window aggregate, `src/analysis/stats.py`) — 2 dataclass field-tương-thích,
    cùng serialize ra 1 shape `DistributionStatsOut` duy nhất."""
    return DistributionStatsOut(
        median=stats.median,
        mean=stats.mean,
        n=stats.n,
        iqr_low=stats.iqr_low,
        iqr_high=stats.iqr_high,
        insufficient_data=stats.insufficient_data,
    )


def _top_by(
    posts: list[ThreadsPost],
    insights: list[PostInsights],
    metric: Callable[[PostInsights], float],
    limit: int,
) -> list[TopPostEntry]:
    """Generic top-N sort theo 1 metric (virality_index/conversation_rate — không có
    hàm `top_posts_by_*` sẵn cho chúng trong `src/analysis/`, chỉ `engagement.py`
    có `top_posts_by_engagement`, dùng trực tiếp hàm đó cho nhánh engagement)."""
    by_id = {item.post_id: item for item in insights}
    paired = [(post, by_id[post.id]) for post in posts if post.id in by_id]
    paired.sort(key=lambda pair: metric(pair[1]), reverse=True)
    return [_to_top_post_entry(post, item) for post, item in paired[:limit]]


@app.get("/analytics/overview", response_model=AnalyticsOverviewOut)
def get_analytics_overview() -> AnalyticsOverviewOut:
    """Overview/Analytics tối giản — bảng top post theo 3 base index (engagement/
    virality/conversation) + engagement theo giờ/thứ, song song Europe/Paris và
    Asia/Ho_Chi_Minh (KHÔNG chọn 1 timezone — Threads không expose viewer timezone
    per-post, xem docs/claude/architecture.md quyết định "Timeline analysis...
    parametrize theo timezone"). Thuần đọc + tính arithmetic từ SQLite, KHÔNG gọi
    lại Threads API, KHÔNG chạy lại pipeline NLP."""
    with _db() as conn:
        posts, insights = _load_root_posts_with_insights(conn)
        top_engagement_pairs = top_posts_by_engagement(posts, insights, limit=ANALYTICS_TOP_N)

        timezones = [
            TimezoneEngagement(
                timezone=tz_name,
                by_hour=[
                    HourBucket(hour=hour, stats=_to_stats_out(stats))
                    for hour, stats in sorted(
                        engagement_by_hour(posts, insights, timezone=tz).items()
                    )
                ],
                by_weekday=[
                    WeekdayBucket(weekday=weekday, stats=_to_stats_out(stats))
                    for weekday, stats in sorted(
                        engagement_by_weekday(posts, insights, timezone=tz).items()
                    )
                ],
            )
            for tz_name, tz in ANALYTICS_TIMEZONES
        ]

        return AnalyticsOverviewOut(
            post_count=len(posts),
            average_engagement_rate=average_engagement_rate(insights),
            top_by_engagement=[
                _to_top_post_entry(post, item) for post, item in top_engagement_pairs
            ],
            top_by_virality=_top_by(posts, insights, virality_index, ANALYTICS_TOP_N),
            top_by_conversation=_top_by(posts, insights, conversation_rate, ANALYTICS_TOP_N),
            timezones=timezones,
        )


ANALYTICS_WINDOW_TOP_N: Final = 5


def _load_posts_with_insights_in_range(
    conn: sqlite3.Connection, start: str, end: str
) -> tuple[list[ThreadsPost], list[PostInsights]]:
    """`_load_root_posts_with_insights()` lọc thêm theo [start, end] — dùng
    `list_root_posts_in_range()` (`src/db/schema.py`) thay vì `list_root_posts()`."""
    posts: list[ThreadsPost] = []
    insights: list[PostInsights] = []
    for row in list_root_posts_in_range(conn, start, end):
        snapshot = latest_insight_snapshot(conn, row["id"])
        if snapshot is None:
            continue
        posts.append(ThreadsPost.model_validate_json(row["raw_json"]))
        insights.append(snapshot_row_to_post_insights(snapshot))
    return posts, insights


@app.get("/analytics/daily-views", response_model=DailyViewsSeriesOut)
def get_analytics_daily_views() -> DailyViewsSeriesOut:
    """Toàn bộ views theo ngày, account-level, đã ingest qua
    `src/pipeline/daily_views.py` (nguồn: `threads_insights?metric=views&period=day`,
    verify live 2026-09-03 — xem `src/api/endpoints.py`). Gọi 1 lần khi trang load
    để vẽ chart nền + biên rail của Timeline Brush, KHÔNG đổi khi kéo cửa sổ."""
    with _db() as conn:
        rows = list_daily_views(conn)
        points = [DailyViewsPointOut(date=row["date"], views=row["views"]) for row in rows]
        return DailyViewsSeriesOut(
            points=points,
            min_date=points[0].date if points else None,
            max_date=points[-1].date if points else None,
        )


@app.get("/analytics/window", response_model=WindowAnalyticsOut)
def get_analytics_window(start: date_cls, end: date_cls) -> WindowAnalyticsOut:
    """Hero band + KPI strip + top content units cho Timeline Brush (Overview mới)
    — tính lại từ data thật CHỈ trong [start, end] mỗi khi cửa sổ đổi (KHÔNG slice
    từ 1 series tĩnh phía client như mockup UI làm). Xem docstring `WindowAnalyticsOut`
    cho định nghĩa từng field — đặc biệt `views` (account-level) khác
    `top_content_units[].metrics.popularity_index` (post-level)."""
    start_s, end_s = start.isoformat(), end.isoformat()
    with _db() as conn:
        posts, insights = _load_posts_with_insights_in_range(conn, start_s, end_s)
        daily_rows = list_daily_views(conn, start_s, end_s)

        interactions = sum(
            item.likes + item.replies + item.reposts + item.quotes for item in insights
        )
        top_content_units = _top_by(posts, insights, popularity_index, ANALYTICS_WINDOW_TOP_N)

        return WindowAnalyticsOut(
            start=start_s,
            end=end_s,
            views=sum(row["views"] for row in daily_rows),
            content_unit_count=len(posts),
            interactions=interactions,
            engagement=_to_stats_out(window_stats(insights, lambda i: i.engagement_rate)),
            virality=_to_stats_out(window_stats(insights, virality_index)),
            conversation=_to_stats_out(window_stats(insights, conversation_rate)),
            top_content_units=top_content_units,
        )
