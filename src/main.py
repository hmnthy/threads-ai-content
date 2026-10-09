"""FastAPI app — đọc kết quả ĐÃ TÍNH SẴN từ SQLite (`data/threads.db`, seed bằng
`src/pipeline/ingest.py` + `src/pipeline/snapshot.py`, topic label bằng
`src/nlp/topics.py`). KHÔNG load model transformer / chạy lại embedding+clustering
mỗi request — đây là nguyên tắc kiến trúc đã chốt (batch compute tách khỏi serving
layer), xem docs/decisions/legacy-log.md dòng "Batch pipeline tách riêng khỏi FastAPI serving
layer".

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
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from typing import Final, get_args
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.analysis.conversation import conversation_rate
from src.analysis.engagement import (
    EngagementBucketStats,
    engagement_by_hour,
    engagement_by_weekday,
    top_posts_by_engagement,
)
from src.analysis.popularity import popularity_index
from src.analysis.reach import (
    BASELINE_MIN_PRIOR,
    BASELINE_WINDOW,
    TIERED_STATUSES,
    ReachStatus,
    ReachTiers,
    assign_reach_tiers,
    estimate_maturity,
)
from src.analysis.share_rate import share_rate
from src.analysis.stats import (
    MIN_N_PER_BUCKET,
    DistributionStats,
    split_measurable,
    views_floor,
    window_stats,
)
from src.analysis.topic_comparison import CONCLUSION_ALPHA, METRICS, GroupKind, Metric
from src.api.models import PostInsights, ThreadsPost
from src.db.schema import (
    DEFAULT_DB_PATH,
    cluster_run_topic_events,
    connect,
    count_reply_roles,
    embedding_dim,
    get_content_unit,
    get_post,
    get_post_topic_label,
    insight_views_series,
    latest_cluster_run,
    latest_insight_snapshot,
    latest_snapshot_time,
    latest_topic_comparison_run,
    list_content_units,
    list_daily_views,
    list_root_posts,
    list_root_posts_in_range,
    list_topic_comparisons,
    snapshot_row_to_post_insights,
)
from src.nlp.topic_identity import runs_keeping_label

app = FastAPI(
    title="Unthreaded API",
    description="Internal analytics API for the Threads channel @thydilammuon.",
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
    """6-index architecture — 3 base index tính được từ 1 snapshot insights
    (popularity/share/conversation) + engagement_rate (có quotes). velocity/longevity
    cần chuỗi snapshot theo thời gian nên chưa trả qua endpoint này (deferred)."""

    popularity_index: int
    engagement_rate: float
    share_rate: float
    conversation_rate: float


class TopicLabel(BaseModel):
    topic_id: str
    method: str
    # cosine giữa bài và tâm cụm (cột `post_topic_labels.confidence`, ADR-0004) — KHÔNG
    # phải xác suất thuộc cụm; bge-m3 thường cho 0,5–0,9
    centroid_similarity: float | None


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


# Audience trải cả Pháp và Việt Nam (verify live 2026-08-31 qua
# get_follower_demographics(breakdown="country"): 71.5% VN, 19.3% FR trên 1,423
# follower có dữ liệu country). So sánh song song 2 timezone thay vì chọn 1 — lý do
# tại docs/decisions/legacy-log.md (dòng "Timeline analysis ... parametrize theo timezone").
ANALYTICS_TIMEZONES: Final = (
    ("Europe/Paris", ZoneInfo("Europe/Paris")),
    ("Asia/Ho_Chi_Minh", ZoneInfo("Asia/Ho_Chi_Minh")),
)
ANALYTICS_TOP_N: Final = 10
# Mô tả quy tắc sàn trả kèm số (UI ghi từ đây, không tự đặt) — `views_floor` (ADR-0023 1f)
VIEWS_FLOOR_RULE: Final = (
    "25th percentile of views among posts with recorded views (linear interpolation)"
)


class TopPostEntry(BaseModel):
    id: str
    text: str | None
    timestamp: str
    metrics: ContentUnitMetrics


class DistributionStatsOut(BaseModel):
    """Mirror của `DistributionStats` (`src/analysis/stats.py`, generalize từ
    `EngagementBucketStats` cũ) — median + IQR + n + insufficient_data để dashboard không
    tuyên bố "tốt nhất" từ 1 tập quá ít bài. `mean` vẫn trả cho phân tích/script nhưng UI
    KHÔNG hiện (ADR-0023: tỉ lệ lệch phải, mean bị vài bài đột biến kéo lên). Dùng chung cho bucket
    giờ/thứ (`HourBucket`/`WeekdayBucket`) VÀ cho engagement/share rate/conversation
    của `WindowAnalyticsOut` (Overview mới) — 1 shape, không lặp lại 2 lần."""

    median: float
    mean: float
    n: int
    iqr_low: float
    iqr_high: float
    insufficient_data: bool


class RepresentativePostOut(BaseModel):
    """1 trong các bài gần tâm cụm nhất (`topics.representative_ids_json`, ADR-0004) — để
    người đọc xem, KHÔNG phải đầu vào đặt tên của Claude (UI-0004-representatives)."""

    id: str
    full_text: str  # chỉ chữ của tác giả: root + self_continuation (ADR-0004)
    centroid_similarity: float | None


class TopicOut(BaseModel):
    id: str
    label_en: str
    description_en: str | None
    method: str
    # số bài được gán topic (mọi bài đã embed, kể cả bài views = 0)
    post_count: int
    # c-TF-IDF (src/nlp/topic_profile.py); [] khi lần gom cụm chưa ghi hồ sơ
    keywords: list[str]
    representatives: list[RepresentativePostOut]
    # phân phối engagement rate của các bài đo được trong topic — mô tả, KHÔNG kiểm định
    # (so với phần còn lại + Holm: `GET /topics/comparisons`, ADR-0023); `insufficient_data`
    # là cờ n nhỏ duy nhất của dự án (`MIN_N_PER_BUCKET`, UI-L20260903-small-n-flag)
    engagement: DistributionStatsOut
    excluded_no_views: int
    # ADR-0018 + ADR-0023 1e: tên đặt lúc nào, bằng model/phiên bản prompt nào; null với topic
    # chưa được đặt tên lại từ ADR-0018 (`docs/design/topics-data-audit.md` mục 3)
    labeled_at: str | None
    label_model: str | None
    label_prompt_version: int | None
    # số lần gom cụm LIÊN TIẾP gần nhất giữ nguyên tên (`runs_keeping_label`)
    runs_keeping_label: int


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
    """`engagement` là phân phối engagement rate TỪNG root post trên toàn kênh (median, IQR,
    n; `mean` có trong API, UI không hiện — ADR-0023) — thay `average_engagement_rate` (chỉ
    mean, bị 1 bài đột biến kéo lệch) để trang Analytics hiện median làm số chính, đúng tầng 3
    "Narrative Layering Principle"."""

    post_count: int
    # ADR-0011: bài có views = 0 (insight thiếu) bị loại khỏi MỌI phân phối rate
    # bên dưới — `post_count` chỉ đếm bài đo được, số bị loại báo riêng ở đây.
    excluded_no_views: int
    engagement: DistributionStatsOut
    # ADR-0023 1f: 3 bảng top theo tỉ lệ chỉ xếp bài có views ≥ sàn = P25 views của các bài đo
    # được, tính lại mỗi request (`views_floor`); null khi < 2 bài đo được (không lọc).
    # `below_views_floor` = số bài đo được nằm dưới sàn, không vào 3 bảng top.
    views_floor: float | None
    views_floor_rule: str
    below_views_floor: int
    top_by_engagement: list[TopPostEntry]
    top_by_share_rate: list[TopPostEntry]
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
    ContentUnit). `engagement`/`share_rate`/`conversation` là phân phối CỦA TỪNG
    POST trong cửa sổ (đúng methodology Layer 2 đã chốt) — KHÔNG phải pooled ratio
    Σinteractions/Σviews như mockup UI tự vẽ cho đẹp (xem `src/analysis/stats.py`
    docstring)."""

    start: str
    end: str
    views: int
    content_unit_count: int
    # ADR-0011: số bài trong cửa sổ có views = 0 — bị loại khỏi engagement/share_rate/
    # conversation (vẫn tính trong `content_unit_count`)
    excluded_no_views: int
    interactions: int
    engagement: DistributionStatsOut
    share_rate: DistributionStatsOut
    conversation: DistributionStatsOut
    top_content_units: list[TopPostEntry]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/content-units", response_model=list[ContentUnitOut])
def get_content_units() -> list[ContentUnitOut]:
    """List toàn bộ ContentUnit kèm 4 base metric (tính on-the-fly từ snapshot mới
    nhất — thuần arithmetic, KHÔNG phải chạy lại pipeline NLP) + topic label
    (`method="cluster"`, có thể null nếu post chưa được gán cluster). `metrics` null khi
    chưa có snapshot hoặc snapshot mới nhất views = 0 (ADR-0011)."""
    with _db() as conn:
        rows = list_content_units(conn)
        result: list[ContentUnitOut] = []
        for row in rows:
            post_row = get_post(conn, row["id"])
            continuation_ids = json.loads(row["continuation_ids_json"])

            # ADR-0011: snapshot mới nhất views = 0 là insight thiếu → metrics null (cùng điều
            # kiện `split_measurable`), không trả rate 0.0 giả cho client vẽ vào phân phối
            metrics: ContentUnitMetrics | None = None
            snapshot = latest_insight_snapshot(conn, row["id"])
            if snapshot is not None and snapshot["views"] > 0:
                insights = snapshot_row_to_post_insights(snapshot)
                metrics = ContentUnitMetrics(
                    popularity_index=popularity_index(insights),
                    engagement_rate=insights.engagement_rate,
                    share_rate=share_rate(insights),
                    conversation_rate=conversation_rate(insights),
                )

            topic: TopicLabel | None = None
            topic_row = get_post_topic_label(conn, row["id"], method="cluster")
            if topic_row is not None:
                topic = TopicLabel(
                    topic_id=topic_row["topic_id"],
                    method=topic_row["method"],
                    centroid_similarity=topic_row["confidence"],
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
    """List topic cluster đã gán kèm số post, hồ sơ cụm (từ khoá, bài gần tâm) và phân
    phối engagement mô tả của từng topic — phục vụ Topic Explorer và landing."""
    with _db() as conn:
        topic_rows = conn.execute("SELECT * FROM topics").fetchall()
        events_by_run = cluster_run_topic_events(conn)
        result: list[TopicOut] = []
        for topic in topic_rows:
            label_rows = conn.execute(
                "SELECT post_id, confidence FROM post_topic_labels WHERE topic_id = ?",
                (topic["id"],),
            ).fetchall()
            similarity = {row["post_id"]: row["confidence"] for row in label_rows}
            _, insights, excluded = split_measurable(
                *_load_posts_with_insights(conn, list(similarity))
            )
            result.append(
                TopicOut(
                    id=topic["id"],
                    label_en=topic["label_en"],
                    description_en=topic["description_en"],
                    method=topic["method"],
                    post_count=len(label_rows),
                    keywords=json.loads(topic["keywords_json"] or "[]"),
                    representatives=_representatives(
                        conn, json.loads(topic["representative_ids_json"] or "[]"), similarity
                    ),
                    engagement=_to_stats_out(window_stats(insights, lambda i: i.engagement_rate)),
                    excluded_no_views=excluded,
                    labeled_at=topic["labeled_at"],
                    label_model=topic["label_model"],
                    label_prompt_version=topic["label_prompt_version"],
                    runs_keeping_label=runs_keeping_label(events_by_run, topic["id"]),
                )
            )
        return result


class GroupStatsOut(BaseModel):
    """Mô tả 1 nhóm trong phép so topic: median + IQR + n của bài đo được (không có mean —
    ADR-0023 1d), số bài bị loại vì views = 0 (ADR-0011)."""

    n: int
    excluded_no_views: int
    median: float
    iqr_low: float
    iqr_high: float
    insufficient_data: bool


class TopicComparisonRowOut(BaseModel):
    """1 nhóm × 1 chỉ số. `kind = topic`: so với `rest` (phần còn lại của kênh, gồm nhiễu);
    `noise`/`channel`: chỉ mô tả, `tested = false`. `effect_size` = Cliff's delta, > 0 nghĩa bài
    của topic có xu hướng cao hơn; CI 95% CHƯA hiệu chỉnh; chỉ được khẳng định khi
    `p_value_holm < conclusion_alpha` VÀ `insufficient_data = false`. Các trường kiểm định null
    khi `stale` (kết quả thuộc lần gom cụm cũ — Thy chốt D3) hoặc khi không kiểm định được."""

    group_id: str
    kind: GroupKind
    metric: Metric
    group: GroupStatsOut
    rest: GroupStatsOut | None
    tested: bool
    # min(n topic, n phần còn lại) < `MIN_N_PER_BUCKET`: vẫn có p trong họ Holm, không có kết luận
    insufficient_data: bool
    effect_size: float | None
    effect_size_ci_low: float | None
    effect_size_ci_high: float | None
    p_value: float | None
    p_value_holm: float | None
    test_method: str | None


class ComparisonMethodOut(BaseModel):
    """Phương pháp đi kèm số liệu (ADR-0023) — UI ghi từ đây, không tự đặt."""

    test: str
    effect_size: str
    ci: str
    comparison_group: str
    n_permutations: int
    random_seed: int
    holm_family_size: int
    conclusion_alpha: float
    min_posts_to_compare: int


class TopicComparisonsOut(BaseModel):
    # null khi bước so sánh chưa chạy lần nào
    cluster_run_id: int | None
    computed_at: str | None
    # `fetched_at` mới nhất trong các snapshot đã dùng — số liệu "tính tới" lúc này
    snapshot_as_of: str | None
    # true khi kết quả thuộc 1 lần gom cụm cũ hơn lần mới nhất (bước so sánh của job lỗi): các
    # trường kiểm định bị ẩn (null), phần mô tả vẫn trả, ghi rõ của lần gom cụm nào
    stale: bool
    method: ComparisonMethodOut | None
    rows: list[TopicComparisonRowOut]


def _group_stats_out(
    n: int, excluded: int, median: float, iqr_low: float, iqr_high: float
) -> GroupStatsOut:
    return GroupStatsOut(
        n=n,
        excluded_no_views=excluded,
        median=median,
        iqr_low=iqr_low,
        iqr_high=iqr_high,
        insufficient_data=n < MIN_N_PER_BUCKET,
    )


@app.get("/topics/comparisons", response_model=TopicComparisonsOut)
def get_topic_comparisons() -> TopicComparisonsOut:
    """Mỗi topic × engagement / share_rate / conversation so với phần còn lại của kênh, cộng
    dòng nhiễu và dòng kênh — ĐỌC kết quả bước `compare` của job NLP (`compare_topics`), không
    tính theo request (~70 giây cho 27 phép so). Họ Holm = mọi phép so có p xác định; kích thước
    họ ở `method.holm_family_size` (ADR-0023)."""
    with _db() as conn:
        run = latest_topic_comparison_run(conn)
        if run is None:
            return TopicComparisonsOut(
                cluster_run_id=None,
                computed_at=None,
                snapshot_as_of=None,
                stale=False,
                method=None,
                rows=[],
            )
        latest = latest_cluster_run(conn)
        stale = latest is not None and latest["id"] != run["cluster_run_id"]
        order = {metric: index for index, metric in enumerate(METRICS)}
        kind_order = {"topic": 0, "noise": 1, "channel": 2}
        rows = sorted(
            list_topic_comparisons(conn, run["cluster_run_id"]),
            key=lambda row: (order[row["metric"]], kind_order[row["kind"]], row["group_id"]),
        )
        out: list[TopicComparisonRowOut] = []
        for row in rows:
            show_test = bool(row["tested"]) and not stale
            out.append(
                TopicComparisonRowOut(
                    group_id=row["group_id"],
                    kind=row["kind"],
                    metric=row["metric"],
                    group=_group_stats_out(
                        row["n"],
                        row["excluded_no_views"],
                        row["median"],
                        row["iqr_low"],
                        row["iqr_high"],
                    ),
                    rest=(
                        _group_stats_out(
                            row["rest_n"],
                            row["rest_excluded_no_views"],
                            row["rest_median"],
                            row["rest_iqr_low"],
                            row["rest_iqr_high"],
                        )
                        if row["rest_n"] is not None
                        else None
                    ),
                    tested=bool(row["tested"]),
                    insufficient_data=bool(row["insufficient_data"]),
                    effect_size=row["effect_size"] if show_test else None,
                    effect_size_ci_low=row["effect_size_ci_low"] if show_test else None,
                    effect_size_ci_high=row["effect_size_ci_high"] if show_test else None,
                    p_value=row["p_value"] if show_test else None,
                    p_value_holm=row["p_value_holm"] if show_test else None,
                    test_method=row["test_method"] if show_test else None,
                )
            )
        return TopicComparisonsOut(
            cluster_run_id=run["cluster_run_id"],
            computed_at=run["computed_at"],
            snapshot_as_of=run["snapshot_as_of"],
            stale=stale,
            method=ComparisonMethodOut(
                test="brunner_munzel_permutation",
                effect_size="cliffs_delta",
                ci="95% from the permutation distribution, not adjusted for multiple comparisons",
                comparison_group="rest of the channel, including posts in no topic",
                n_permutations=run["n_permutations"],
                random_seed=run["random_seed"],
                holm_family_size=run["holm_family_size"],
                conclusion_alpha=CONCLUSION_ALPHA,
                min_posts_to_compare=MIN_N_PER_BUCKET,
            ),
            rows=out,
        )


def _representatives(
    conn: sqlite3.Connection, unit_ids: list[str], similarity: dict[str, float | None]
) -> list[RepresentativePostOut]:
    """Giữ thứ tự đã lưu (gần tâm nhất trước); bỏ id không còn content unit."""
    result: list[RepresentativePostOut] = []
    for unit_id in unit_ids:
        unit = get_content_unit(conn, unit_id)
        if unit is None:
            continue
        result.append(
            RepresentativePostOut(
                id=unit_id,
                full_text=unit["full_text"],
                centroid_similarity=similarity.get(unit_id),
            )
        )
    return result


def _load_posts_with_insights(
    conn: sqlite3.Connection, post_ids: list[str]
) -> tuple[list[ThreadsPost], list[PostInsights]]:
    """Như `_load_root_posts_with_insights()` nhưng cho 1 tập id cho trước (thành viên 1
    topic, bài nhiễu) — bài chưa có snapshot nào bị bỏ, đúng cách hàm kia làm."""
    posts: list[ThreadsPost] = []
    insights: list[PostInsights] = []
    for post_id in post_ids:
        row = get_post(conn, post_id)
        snapshot = latest_insight_snapshot(conn, post_id)
        if row is None or snapshot is None:
            continue
        posts.append(ThreadsPost.model_validate_json(row["raw_json"]))
        insights.append(snapshot_row_to_post_insights(snapshot))
    return posts, insights


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
            share_rate=share_rate(insights),
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
    """Generic top-N sort theo 1 metric (share_rate/conversation_rate — không có
    hàm `top_posts_by_*` sẵn cho chúng trong `src/analysis/`, chỉ `engagement.py`
    có `top_posts_by_engagement`, dùng trực tiếp hàm đó cho nhánh engagement)."""
    by_id = {item.post_id: item for item in insights}
    paired = [(post, by_id[post.id]) for post in posts if post.id in by_id]
    paired.sort(key=lambda pair: metric(pair[1]), reverse=True)
    return [_to_top_post_entry(post, item) for post, item in paired[:limit]]


@app.get("/analytics/overview", response_model=AnalyticsOverviewOut)
def get_analytics_overview() -> AnalyticsOverviewOut:
    """Overview/Analytics tối giản — bảng top post theo 3 base index (engagement/
    share rate/conversation) + engagement theo giờ/thứ, song song Europe/Paris và
    Asia/Ho_Chi_Minh (KHÔNG chọn 1 timezone — Threads không expose viewer timezone
    per-post, xem docs/decisions/legacy-log.md dòng "Timeline analysis ... parametrize theo
    timezone"). Thuần đọc + tính arithmetic từ SQLite, KHÔNG gọi
    lại Threads API, KHÔNG chạy lại pipeline NLP."""
    with _db() as conn:
        posts, insights, excluded = split_measurable(*_load_root_posts_with_insights(conn))
        # Sàn chỉ áp cho 3 bảng top theo tỉ lệ — phân phối và bucket giờ/thứ vẫn dùng mọi bài đo
        # được (ADR-0023 1f: tỉ lệ của bài ít views dao động mạnh, chiếm bảng top)
        floor = views_floor(insights)
        ranked = insights if floor is None else [item for item in insights if item.views >= floor]
        top_engagement_pairs = top_posts_by_engagement(posts, ranked, limit=ANALYTICS_TOP_N)

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
            excluded_no_views=excluded,
            engagement=_to_stats_out(window_stats(insights, lambda i: i.engagement_rate)),
            views_floor=floor,
            views_floor_rule=VIEWS_FLOOR_RULE,
            below_views_floor=len(insights) - len(ranked),
            top_by_engagement=[
                _to_top_post_entry(post, item) for post, item in top_engagement_pairs
            ],
            top_by_share_rate=_top_by(posts, ranked, share_rate, ANALYTICS_TOP_N),
            top_by_conversation=_top_by(posts, ranked, conversation_rate, ANALYTICS_TOP_N),
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
        _, measurable, excluded = split_measurable(posts, insights)

        return WindowAnalyticsOut(
            start=start_s,
            end=end_s,
            views=sum(row["views"] for row in daily_rows),
            content_unit_count=len(posts),
            excluded_no_views=excluded,
            interactions=interactions,
            engagement=_to_stats_out(window_stats(measurable, lambda i: i.engagement_rate)),
            share_rate=_to_stats_out(window_stats(measurable, share_rate)),
            conversation=_to_stats_out(window_stats(measurable, conversation_rate)),
            top_content_units=top_content_units,
        )


class ReachPostOut(BaseModel):
    """1 bài gốc đo được trong bảng tầng reach (ADR-0012). `views` thô luôn trả kèm làm
    tham chiếu; `baseline_views` = median views của các bài đăng ngay trước; `relative_reach` =
    views ÷ baseline_views — đại lượng dùng để xếp tầng. Cả hai None với bài chưa xếp tầng (bài
    chưa chín có reach tương đối bị hạ thấp — không trả để client không tự chia)."""

    id: str
    timestamp: str
    views: int
    baseline_views: float | None
    relative_reach: float | None
    status: ReachStatus


class ReachMaturityOut(BaseModel):
    # P90 thời gian đạt 90% views mới nhất; None khi chưa có đường cong nào đủ điều kiện
    days: float | None
    n_curves: int


class ReachTiersOut(BaseModel):
    """Tầng reach toàn lịch sử kênh (ADR-0012) — "Top 20% reach" (`top_20`, ≥ P80) và
    "Above median reach" (`above_median`, ≥ P50) của reach tương đối, chỉ trên bài đã chín
    và có mốc so sánh (`n_tiered`). `p50_views`/`p80_views` = views thô ở cùng phân vị của
    cùng nhóm bài — tham chiếu, không dùng để xếp tầng."""

    baseline_window: int
    baseline_min_prior: int
    maturity: ReachMaturityOut
    p50_ratio: float | None
    p80_ratio: float | None
    p50_views: float | None
    p80_views: float | None
    n_tiered: int
    insufficient_data: bool
    # ADR-0011: bài views = 0 không nằm trong `posts`, báo số bị loại riêng
    excluded_no_views: int
    counts: dict[str, int]
    posts: list[ReachPostOut]


@dataclass(frozen=True)
class ReachComputation:
    """Đầu vào + kết quả tầng reach, cùng thứ tự (thời gian đăng tăng dần)."""

    posts: list[ThreadsPost]
    insights: list[PostInsights]  # snapshot mới nhất của từng bài
    curves: list[list[tuple[float, int]]]  # (tuổi bài lúc chụp, views) theo thời gian
    tiers: ReachTiers
    excluded_no_views: int


def compute_reach(
    conn: sqlite3.Connection,
    window: int = BASELINE_WINDOW,
    min_prior: int = BASELINE_MIN_PRIOR,
) -> ReachComputation:
    """Tầng reach trên toàn bộ bài gốc đo được, xếp theo thời gian đăng — dùng chung cho
    endpoint và `scripts/reach_report.py` (số liệu ADR-0012 sinh lại được từ đây)."""
    posts, insights, excluded = split_measurable(*_load_root_posts_with_insights(conn))
    by_id = {item.post_id: item for item in insights}
    posts = sorted(posts, key=lambda post: post.timestamp)
    ordered = [by_id[post.id] for post in posts]
    series = insight_views_series(conn)
    curves = [
        [
            ((datetime.fromisoformat(fetched_at) - post.timestamp).total_seconds() / 86400, views)
            for fetched_at, views in series.get(post.id, [])
        ]
        for post in posts
    ]
    # Tuổi tại snapshot mới nhất (nơi lấy `views`), không phải tới `now` — cron ngắt vài ngày
    # (ADR-0017) thì views vẫn là số đo lúc bài còn non
    ages = [curve[-1][0] if curve else 0.0 for curve in curves]
    tiers = assign_reach_tiers(
        [item.views for item in ordered],
        ages,
        estimate_maturity(curves),
        window=window,
        min_prior=min_prior,
    )
    return ReachComputation(posts, ordered, curves, tiers, excluded)


@app.get("/analytics/reach", response_model=ReachTiersOut)
def get_analytics_reach() -> ReachTiersOut:
    """Tầng reach (ADR-0012): bài nào chạm tới nhiều người hơn mức bình thường của kênh lúc
    đăng. Toàn lịch sử, không theo cửa sổ thời gian — ngưỡng là phân vị của chính kênh."""
    with _db() as conn:
        result = compute_reach(conn)
    tiers = result.tiers
    counts = {status: tiers.statuses.count(status) for status in get_args(ReachStatus)}
    return ReachTiersOut(
        baseline_window=BASELINE_WINDOW,
        baseline_min_prior=BASELINE_MIN_PRIOR,
        maturity=ReachMaturityOut(days=tiers.maturity.days, n_curves=tiers.maturity.n_curves),
        p50_ratio=tiers.p50_ratio,
        p80_ratio=tiers.p80_ratio,
        p50_views=tiers.p50_views,
        p80_views=tiers.p80_views,
        n_tiered=tiers.n_tiered,
        insufficient_data=tiers.insufficient_data,
        excluded_no_views=result.excluded_no_views,
        counts=counts,
        posts=[
            ReachPostOut(
                id=post.id,
                timestamp=post.timestamp.isoformat(),
                views=item.views,
                baseline_views=tiers.baselines[i] if tiers.statuses[i] in TIERED_STATUSES else None,
                relative_reach=tiers.ratios[i] if tiers.statuses[i] in TIERED_STATUSES else None,
                status=tiers.statuses[i],
            )
            for i, (post, item) in enumerate(zip(result.posts, result.insights, strict=True))
        ],
    )


class ReplyRolesOut(BaseModel):
    """Vai của các reply do tác giả viết (ADR-0004, `posts.reply_role`)."""

    self_continuation: int
    author_answer: int
    outbound: int
    # reply chưa được phân vai (ingest chưa chạy `assign_reply_roles`) — báo ra, không giấu
    unassigned: int


class ClusterRunOut(BaseModel):
    """Lần gom cụm mới nhất (`cluster_runs`) — `run_at` lưu UTC, UI đổi sang Europe/Paris."""

    run_at: str
    model_id: str
    params: dict[str, str | int | float | bool | None]
    embedding_dim: int | None
    # số unit có `full_text` không rỗng đã đem gom cụm — mẫu số của tỉ lệ nhiễu
    n_units: int
    n_clusters: int
    n_noise: int
    noise_ratio: float
    # = hdbscan validity_index (DBCV đầy đủ); null khi < 2 cụm (UI-0004-dbcv-named)
    dbcv: float | None
    ari_vs_previous: float | None
    ari_clustered_only: float | None


class PipelineSummaryOut(BaseModel):
    """Số liệu sống của pipeline cho landing và sơ đồ "How it works" — thuần đếm/đọc từ
    SQLite, không thêm methodology mới."""

    content_units: int
    # unit không có chữ để embed (bài chỉ ảnh/video) — loại khỏi gom cụm (UI-0011-two-exclusions)
    units_without_text: int
    reply_roles: ReplyRolesOut
    latest_snapshot_at: str | None
    latest_cluster_run: ClusterRunOut | None
    # phân phối engagement của bài nhiễu (nhãn HDBSCAN -1) ở lần gom cụm mới nhất — mô tả,
    # không kiểm định; null khi chưa gom cụm lần nào
    noise_engagement: DistributionStatsOut | None
    noise_excluded_no_views: int
    # ngưỡng mẫu nhỏ duy nhất của dự án (`MIN_N_PER_BUCKET`) — UI ghi số này thay vì tự đặt ngưỡng
    # thứ hai (UI-L20260903-small-n-flag); dưới ngưỡng thì `insufficient_data` = true
    min_posts_to_compare: int


@app.get("/pipeline/summary", response_model=PipelineSummaryOut)
def get_pipeline_summary() -> PipelineSummaryOut:
    with _db() as conn:
        units = list_content_units(conn)
        roles = count_reply_roles(conn)
        run = latest_cluster_run(conn)

        run_out: ClusterRunOut | None = None
        noise_engagement: DistributionStatsOut | None = None
        noise_excluded = 0
        if run is not None:
            labels: dict[str, int] = json.loads(run["labels_json"])
            noise_ids = [unit_id for unit_id, label in labels.items() if label == -1]
            run_out = ClusterRunOut(
                run_at=run["run_at"],
                model_id=run["model_id"],
                params=json.loads(run["params_json"]),
                embedding_dim=embedding_dim(conn, run["model_id"]),
                n_units=run["n_units"],
                n_clusters=run["n_clusters"],
                n_noise=len(noise_ids),
                noise_ratio=run["noise_ratio"],
                dbcv=run["dbcv"],
                ari_vs_previous=run["ari_vs_previous"],
                ari_clustered_only=run["ari_clustered_only"],
            )
            _, insights, noise_excluded = split_measurable(
                *_load_posts_with_insights(conn, noise_ids)
            )
            noise_engagement = _to_stats_out(window_stats(insights, lambda i: i.engagement_rate))

        return PipelineSummaryOut(
            content_units=len(units),
            units_without_text=sum(1 for unit in units if not (unit["full_text"] or "").strip()),
            reply_roles=ReplyRolesOut(
                self_continuation=roles.get("self_continuation", 0),
                author_answer=roles.get("author_answer", 0),
                outbound=roles.get("outbound", 0),
                unassigned=roles.get("unassigned", 0),
            ),
            latest_snapshot_at=latest_snapshot_time(conn),
            latest_cluster_run=run_out,
            noise_engagement=noise_engagement,
            noise_excluded_no_views=noise_excluded,
            min_posts_to_compare=MIN_N_PER_BUCKET,
        )
