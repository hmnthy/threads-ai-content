"""SQLite schema — `posts`, `content_units`, `insights_snapshots`, `topics`,
`post_topic_labels`, theo đúng spec tại docs/claude/data-model.md mục "Storage".

Quyết định tự chọn (cần xác nhận lại — xem report cuối): thêm cột `umap_x/y/z` +
`language_primary`/`language_mix_score` vào `content_units` (không phải bảng riêng)
để dashboard Topic Explorer (Bước 7 + 11-13) đọc trực tiếp toạ độ scatter mà không
cần dựng vector store riêng (Chroma/FAISS, việc của RAG — Bước 10, hoãn) chỉ để phục
vụ visualize. Vector store thật cho RAG vẫn để dành cho Bước 10, không xây tối nay.

Đây là raw archive + derived layer, KHÁC `data/cache/` (TTL 6h) — không tự xoá.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.api.models import PostInsights, ThreadsPost
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot

DEFAULT_DB_PATH = Path("data/threads.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    text TEXT,
    timestamp TEXT NOT NULL,
    media_type TEXT NOT NULL,
    permalink TEXT,
    is_reply INTEGER NOT NULL DEFAULT 0,
    is_reply_owned_by_me INTEGER NOT NULL DEFAULT 0,
    has_replies INTEGER NOT NULL DEFAULT 0,
    root_post_id TEXT,
    replied_to_id TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_units (
    id TEXT PRIMARY KEY REFERENCES posts(id),
    continuation_ids_json TEXT NOT NULL DEFAULT '[]',
    media_ids_json TEXT NOT NULL DEFAULT '[]',
    text_attachment TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    full_text TEXT NOT NULL,
    -- toạ độ UMAP 3D (Bước 7) — null tới khi pipeline NLP chạy
    umap_x REAL,
    umap_y REAL,
    umap_z REAL,
    -- LanguageInfo (Bước 3) — null tới khi pipeline NLP chạy
    language_primary TEXT,
    language_mix_score REAL
);

CREATE TABLE IF NOT EXISTS insights_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL REFERENCES posts(id),
    fetched_at TEXT NOT NULL,
    views INTEGER NOT NULL,
    likes INTEGER NOT NULL,
    replies INTEGER NOT NULL,
    reposts INTEGER NOT NULL,
    quotes INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insights_snapshots_post_id
    ON insights_snapshots (post_id, fetched_at);

CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    label_en TEXT NOT NULL,
    description_en TEXT,
    method TEXT NOT NULL CHECK (method IN ('fixed', 'cluster')),
    centroid_embedding_json TEXT
);

CREATE TABLE IF NOT EXISTS post_topic_labels (
    post_id TEXT NOT NULL REFERENCES posts(id),
    topic_id TEXT NOT NULL REFERENCES topics(id),
    method TEXT NOT NULL CHECK (method IN ('fixed', 'cluster')),
    confidence REAL,
    PRIMARY KEY (post_id, method)
);

-- Account-level daily views (Threads `threads_insights?metric=views&period=day`,
-- verify live 2026-09-03: trả breakdown thật theo ngày, cap 2 năm lookback, gồm cả
-- views phát sinh từ replies — KHÁC `insights_snapshots` (lifetime cumulative theo
-- 1 post cụ thể). `date` lấy từ `end_time` trừ 7h rồi lấy phần ngày (Meta trả
-- end_time cố định "07:00:00+0000" mỗi điểm — ranh giới ngày kiểu Pacific time,
-- không phải UTC midnight). Dùng UPSERT vì Meta có thể backfill/sửa vài ngày gần
-- nhất sau khi đã fetch lần đầu.
CREATE TABLE IF NOT EXISTS account_daily_views (
    date TEXT PRIMARY KEY,
    views INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
);
"""


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Mở connection SQLite, tạo thư mục cha nếu chưa có. KHÔNG tự tạo schema —
    gọi `create_schema()` riêng (tách bạch "mở kết nối" và "khởi tạo cấu trúc")."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


# --- posts -------------------------------------------------------------------


def upsert_post(conn: sqlite3.Connection, post: ThreadsPost) -> None:
    conn.execute(
        """
        INSERT INTO posts (
            id, text, timestamp, media_type, permalink, is_reply,
            is_reply_owned_by_me, has_replies, root_post_id, replied_to_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            text = excluded.text,
            timestamp = excluded.timestamp,
            media_type = excluded.media_type,
            permalink = excluded.permalink,
            is_reply = excluded.is_reply,
            is_reply_owned_by_me = excluded.is_reply_owned_by_me,
            has_replies = excluded.has_replies,
            root_post_id = excluded.root_post_id,
            replied_to_id = excluded.replied_to_id,
            raw_json = excluded.raw_json
        """,
        (
            post.id,
            post.text,
            post.timestamp.isoformat(),
            post.media_type.value,
            post.permalink,
            int(post.is_reply),
            int(post.is_reply_owned_by_me),
            int(post.has_replies),
            post.root_post_id,
            post.replied_to_id,
            post.model_dump_json(),
        ),
    )


def get_post(conn: sqlite3.Connection, post_id: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return row  # type: ignore[no-any-return]


def list_root_posts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Chỉ root post (`is_reply = 0`) — mỗi row map 1:1 với 1 `content_units.id`.
    Dùng cho analytics đọc theo ContentUnit (engagement_by_hour/weekday, top posts),
    KHÔNG lẫn 1,285 audience/self-reply cũng nằm trong bảng `posts`."""
    return conn.execute("SELECT * FROM posts WHERE is_reply = 0").fetchall()


def list_root_posts_in_range(conn: sqlite3.Connection, start: str, end: str) -> list[sqlite3.Row]:
    """`list_root_posts()` lọc thêm theo `timestamp` (so sánh chuỗi ISO, an toàn vì
    format cố định) trong [start, end] (start/end dạng "YYYY-MM-DD", inclusive cả
    2 đầu — so `timestamp[:10]` chứ không so nguyên chuỗi ISO có giờ). Lọc Python-side
    sau khi lấy toàn bộ root post — quy mô hiện tại (~141 content unit) chưa cần
    SQL WHERE riêng, nhưng đặt tên hàm rõ để nơi gọi (`main.py`) không tự parse ngày
    inline."""
    return [row for row in list_root_posts(conn) if start <= row["timestamp"][:10] <= end]


# --- content_units -------------------------------------------------------------


def upsert_content_unit(conn: sqlite3.Connection, unit: ContentUnit) -> None:
    conn.execute(
        """
        INSERT INTO content_units (
            id, continuation_ids_json, media_ids_json, text_attachment,
            raw_text, normalized_text, full_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            continuation_ids_json = excluded.continuation_ids_json,
            media_ids_json = excluded.media_ids_json,
            text_attachment = excluded.text_attachment,
            raw_text = excluded.raw_text,
            normalized_text = excluded.normalized_text,
            full_text = excluded.full_text
        """,
        (
            unit.id,
            json.dumps([post.id for post in unit.continuations]),
            json.dumps([post.id for post in unit.media]),
            unit.text_attachment,
            unit.full_text,
            unit.full_text,
            unit.full_text,
        ),
    )


def update_content_unit_text(
    conn: sqlite3.Connection, unit_id: str, *, raw_text: str, normalized_text: str
) -> None:
    """`raw_text` bất biến, `normalized_text` chỉ whitespace+URL — xem
    `src/processing/text.py`. Tách khỏi upsert_content_unit vì text.py chạy sau
    thread_reconstruction.py trong pipeline."""
    conn.execute(
        "UPDATE content_units SET raw_text = ?, normalized_text = ? WHERE id = ?",
        (raw_text, normalized_text, unit_id),
    )


def update_content_unit_embedding_coords(
    conn: sqlite3.Connection, unit_id: str, *, x: float, y: float, z: float
) -> None:
    conn.execute(
        "UPDATE content_units SET umap_x = ?, umap_y = ?, umap_z = ? WHERE id = ?",
        (x, y, z, unit_id),
    )


def update_content_unit_language(
    conn: sqlite3.Connection, unit_id: str, *, primary_language: str | None, mix_score: float
) -> None:
    conn.execute(
        "UPDATE content_units SET language_primary = ?, language_mix_score = ? WHERE id = ?",
        (primary_language, mix_score, unit_id),
    )


def get_content_unit(conn: sqlite3.Connection, unit_id: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM content_units WHERE id = ?", (unit_id,)).fetchone()
    return row  # type: ignore[no-any-return]


def list_content_units(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM content_units").fetchall()


# --- insights_snapshots ---------------------------------------------------------


def insert_insight_snapshot(conn: sqlite3.Connection, snapshot: InsightSnapshot) -> None:
    conn.execute(
        """
        INSERT INTO insights_snapshots
            (post_id, fetched_at, views, likes, replies, reposts, quotes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.post_id,
            snapshot.fetched_at.isoformat(),
            snapshot.views,
            snapshot.likes,
            snapshot.replies,
            snapshot.reposts,
            snapshot.quotes,
        ),
    )


def latest_insight_snapshot(conn: sqlite3.Connection, post_id: str) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT * FROM insights_snapshots
        WHERE post_id = ?
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (post_id,),
    ).fetchone()
    return row  # type: ignore[no-any-return]


def snapshot_row_to_post_insights(row: sqlite3.Row) -> PostInsights:
    return PostInsights(
        post_id=row["post_id"],
        views=row["views"],
        likes=row["likes"],
        replies=row["replies"],
        reposts=row["reposts"],
        quotes=row["quotes"],
    )


# --- topics + post_topic_labels --------------------------------------------------


def upsert_topic(
    conn: sqlite3.Connection,
    *,
    topic_id: str,
    label_en: str,
    description_en: str | None,
    method: str,
    centroid_embedding: list[float] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO topics (id, label_en, description_en, method, centroid_embedding_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            label_en = excluded.label_en,
            description_en = excluded.description_en,
            method = excluded.method,
            centroid_embedding_json = excluded.centroid_embedding_json
        """,
        (
            topic_id,
            label_en,
            description_en,
            method,
            json.dumps(centroid_embedding) if centroid_embedding is not None else None,
        ),
    )


def upsert_post_topic_label(
    conn: sqlite3.Connection,
    *,
    post_id: str,
    topic_id: str,
    method: str,
    confidence: float | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO post_topic_labels (post_id, topic_id, method, confidence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(post_id, method) DO UPDATE SET
            topic_id = excluded.topic_id,
            confidence = excluded.confidence
        """,
        (post_id, topic_id, method, confidence),
    )


def get_post_topic_label(
    conn: sqlite3.Connection, post_id: str, method: str = "cluster"
) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM post_topic_labels WHERE post_id = ? AND method = ?",
        (post_id, method),
    ).fetchone()
    return row  # type: ignore[no-any-return]


def delete_cluster_topics(conn: sqlite3.Connection) -> None:
    """Xoá sạch mọi `topics`/`post_topic_labels` có `method='cluster'` — dùng
    TRƯỚC khi `src/pipeline/clustering_import.py` ghi lại kết quả cluster mới.

    Lý do (Layer 10, xem docs/claude/data-model.md): `topic_id = f"cluster_{n}"`
    lấy theo VỊ TRÍ nhãn HDBSCAN trả về, thứ tự này không ổn định giữa các lần
    chạy — cùng 1 `topic_id` số có thể đại diện 2 chủ đề khác nhau ở 2 lần chạy.
    Vì `clustering_import.py` vốn đã là full-recompute mỗi lần (không có logic
    incremental), xoá-rồi-ghi-lại là đúng và an toàn hơn hẳn upsert-theo-vị-trí:
    tránh (a) cluster cũ không còn ở lần chạy mới vẫn tồn tại vĩnh viễn (rác),
    (b) `post_topic_labels` của bài chuyển sang noise không được dọn (trỏ topic
    cũ sai). Chỉ xoá `method='cluster'` — giữ nguyên `method='fixed'` (hiện chưa
    có code nào ghi 'fixed', nhưng tách theo method để không đụng nhầm nếu sau
    này có fixed-category classifier ghi vào cùng 2 bảng này).
    """
    conn.execute("DELETE FROM post_topic_labels WHERE method = 'cluster'")
    conn.execute("DELETE FROM topics WHERE method = 'cluster'")


# --- account_daily_views ---------------------------------------------------------


def upsert_daily_views(conn: sqlite3.Connection, *, date: str, views: int, fetched_at: str) -> None:
    """UPSERT 1 điểm — Meta có thể trả số đã sửa cho vài ngày gần nhất ở lần fetch
    sau (backfill trễ), ghi đè bằng giá trị mới nhất là đúng hành vi mong muốn."""
    conn.execute(
        """
        INSERT INTO account_daily_views (date, views, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            views = excluded.views,
            fetched_at = excluded.fetched_at
        """,
        (date, views, fetched_at),
    )


def list_daily_views(
    conn: sqlite3.Connection, start: str | None = None, end: str | None = None
) -> list[sqlite3.Row]:
    """Toàn bộ `account_daily_views` sắp theo ngày tăng dần, lọc theo [start, end]
    nếu truyền (inclusive cả 2 đầu, "YYYY-MM-DD"). Không truyền gì -> toàn bộ lịch
    sử đã ingest."""
    if start is not None and end is not None:
        return conn.execute(
            "SELECT * FROM account_daily_views WHERE date BETWEEN ? AND ? ORDER BY date",
            (start, end),
        ).fetchall()
    return conn.execute("SELECT * FROM account_daily_views ORDER BY date").fetchall()
