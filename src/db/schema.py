"""SQLite schema — `posts`, `content_units`, `insights_snapshots`, `topics`,
`post_topic_labels`, `account_daily_views`, `embeddings`, `cluster_runs` (2 bảng cuối từ
ADR-0004), theo đúng spec tại docs/claude/data-model.md mục "Storage".

Cột `umap_x/y/z` + `language_primary`/`language_mix_score` nằm thẳng trong
`content_units` (không phải bảng riêng) để dashboard Topic Explorer đọc trực tiếp toạ độ
scatter. Embedding đã nằm trong chính file SQLite này (bảng `embeddings`); knowledge
base (`kb_*`, FTS5) cũng sẽ ở đây — xem docs/roadmap.md Phase E (ADR-0010).

Đây là raw archive + derived layer, KHÁC `data/cache/` (TTL 6h) — không tự xoá.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
from collections.abc import Mapping
from pathlib import Path

from src.api.models import PostInsights, ThreadsPost
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot

DEFAULT_DB_PATH = Path("data/threads.db")

_TOPICS_DDL = """
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    label_en TEXT NOT NULL,
    description_en TEXT,
    method TEXT NOT NULL CHECK (method IN ('cluster')),
    centroid_embedding_json TEXT,
    -- c-TF-IDF top từ khoá + id bài gần tâm cụm nhất (src/nlp/topic_profile.py)
    keywords_json TEXT,
    representative_ids_json TEXT
);

CREATE TABLE IF NOT EXISTS post_topic_labels (
    post_id TEXT NOT NULL REFERENCES posts(id),
    topic_id TEXT NOT NULL REFERENCES topics(id),
    method TEXT NOT NULL CHECK (method IN ('cluster')),
    confidence REAL,
    PRIMARY KEY (post_id, method)
);
"""

SCHEMA_SQL = (
    """
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
    raw_json TEXT NOT NULL,
    -- ADR-0004: self_continuation | author_answer | outbound (NULL với root post)
    reply_role TEXT
);

CREATE TABLE IF NOT EXISTS content_units (
    id TEXT PRIMARY KEY REFERENCES posts(id),
    continuation_ids_json TEXT NOT NULL DEFAULT '[]',
    media_ids_json TEXT NOT NULL DEFAULT '[]',
    text_attachment TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    full_text TEXT NOT NULL,
    -- toạ độ UMAP 3D (src/nlp/topics.py) — null tới khi pipeline NLP chạy
    umap_x REAL,
    umap_y REAL,
    umap_z REAL,
    -- LanguageInfo (src/nlp/language.py) — null tới khi pipeline NLP chạy
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

"""
    + _TOPICS_DDL
    + """

-- Vector embedding đã tính (ADR-0004; roadmap D0 bước 5) — chỉ embed lại khi
-- `content_hash` đổi. float32 little-endian, `dim` phần tử. Dùng lại cho bài đại
-- diện của topic và cho knowledge base (Phase E) — cùng file SQLite (ADR-0010).
CREATE TABLE IF NOT EXISTS embeddings (
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (object_type, object_id, model_id)
);

-- 1 dòng mỗi lần gom cụm: tham số + chất lượng (DBCV, tỉ lệ nhiễu) + nhãn từng bài
-- để tính ARI với lần sau. Trước đây các số này chỉ in ra log rồi mất.
CREATE TABLE IF NOT EXISTS cluster_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    model_id TEXT NOT NULL,
    params_json TEXT NOT NULL,
    n_units INTEGER NOT NULL,
    n_clusters INTEGER NOT NULL,
    noise_ratio REAL NOT NULL,
    -- dbcv = validity_index (DBCV đầy đủ); dbcv_relative = relative_validity_ (xấp xỉ,
    -- thước đo lúc calibrate 2026-09-03). 2 thang khác nhau — không so chéo.
    dbcv REAL,
    dbcv_relative REAL,
    -- ARI tính nhiễu là 1 nhóm (lẫn cả việc bài chuyển sang/ra nhiễu) và ARI chỉ trên bài
    -- có cụm ở cả 2 lần; transitions_json đếm cụm→nhiễu / nhiễu→cụm.
    ari_vs_previous REAL,
    ari_clustered_only REAL,
    transitions_json TEXT,
    labels_json TEXT NOT NULL
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
)


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
    _migrate(conn)
    conn.commit()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _in_one_transaction(conn: sqlite3.Connection, statements: list[str]) -> None:
    """Chạy các lệnh (kể cả DDL) trong ĐÚNG 1 transaction tường minh, tắt khoá ngoại
    trong lúc tạo lại bảng. `PRAGMA foreign_keys` không đổi được bên trong transaction
    nên đặt trước BEGIN; không dùng `executescript()` (nó tự COMMIT trước khi chạy).
    Lỗi giữa chừng → ROLLBACK, DB về nguyên trạng.

    Chỉ dùng trong `_migrate()` (gọi sau `executescript`, lúc chưa có transaction nào
    mở). Kiểm khoá ngoại chỉ trên 2 bảng được tạo lại — vi phạm có sẵn ở bảng khác (VD
    bản DB cũ của worktree) không được chặn migration ở mọi lần chạy cron."""
    conn.commit()
    previous_fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        try:
            for statement in statements:
                conn.execute(statement)
            for table in ("topics", "post_topic_labels"):
                if conn.execute(f"PRAGMA foreign_key_check({table})").fetchall():
                    raise sqlite3.IntegrityError(f"foreign_key_check({table}) có vi phạm")
            conn.execute("COMMIT")
        except Exception:
            # SQLite có thể đã tự rollback (SQLITE_FULL/IOERR) — đừng che lỗi gốc
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if previous_fk else 'OFF'}")


def _rebuild_topic_tables(conn: sqlite3.Connection) -> None:
    """Tạo lại `topics`/`post_topic_labels` với CHECK mới, chỉ giữ dòng `cluster`."""
    old_cols = _columns(conn, "topics")
    copy_topics = (
        "INSERT INTO topics SELECT * FROM topics_old WHERE method = 'cluster'"
        if "keywords_json" in old_cols
        else "INSERT INTO topics (id, label_en, description_en, method, "
        "centroid_embedding_json) SELECT id, label_en, description_en, method, "
        "centroid_embedding_json FROM topics_old WHERE method = 'cluster'"
    )
    create = [stmt.strip() for stmt in _TOPICS_DDL.split(";") if stmt.strip()]
    _in_one_transaction(
        conn,
        [
            "ALTER TABLE post_topic_labels RENAME TO post_topic_labels_old",
            "ALTER TABLE topics RENAME TO topics_old",
            *create,
            copy_topics,
            "INSERT INTO post_topic_labels SELECT * FROM post_topic_labels_old "
            "WHERE method = 'cluster'",
            "DROP TABLE post_topic_labels_old",
            "DROP TABLE topics_old",
        ],
    )


def _restore_interrupted_rebuild(conn: sqlite3.Connection) -> None:
    """Phục hồi DB bị dừng giữa lần tạo lại bảng của phiên bản migration cũ (không
    nguyên tử): bảng `*_old` mới là dữ liệu thật; bảng cùng tên hiện có (nếu có) do
    `SCHEMA_SQL` vừa tạo rỗng → bỏ đi và đổi tên `*_old` về chỗ cũ. Sau đó migration
    chạy lại bình thường."""
    statements: list[str] = []
    for name in ("post_topic_labels", "topics"):
        if _table_exists(conn, f"{name}_old"):
            if _table_exists(conn, name):
                statements.append(f"DROP TABLE {name}")
            statements.append(f"ALTER TABLE {name}_old RENAME TO {name}")
    _in_one_transaction(conn, statements)


def _migrate(conn: sqlite3.Connection) -> None:
    """Đưa DB cũ lên schema hiện tại — idempotent, chạy ở MỌI `create_schema()` (job
    cron gọi hàm này mỗi lần chạy). `CREATE TABLE IF NOT EXISTS` không sửa bảng đã có,
    nên cột mới/ràng buộc mới phải thêm ở đây.

    ADR-0004: thêm `posts.reply_role`; bỏ `'fixed'` khỏi CHECK `method` của
    `topics`/`post_topic_labels` (bộ phân loại 6 nhãn không còn là thành phần sản
    phẩm — ADR-0001). SQLite không sửa CHECK tại chỗ → tạo lại 2 bảng, chỉ giữ dòng
    `method='cluster'` (topic sinh lại được từ lần gom cụm sau)."""
    if "reply_role" not in _columns(conn, "posts"):
        conn.execute("ALTER TABLE posts ADD COLUMN reply_role TEXT")

    if _table_exists(conn, "topics_old") or _table_exists(conn, "post_topic_labels_old"):
        _restore_interrupted_rebuild(conn)

    topics_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'topics'"
    ).fetchone()[0]
    if "'fixed'" in topics_sql:
        _rebuild_topic_tables(conn)

    run_cols = _columns(conn, "cluster_runs")
    for column, kind in (
        ("dbcv_relative", "REAL"),
        ("ari_clustered_only", "REAL"),
        ("transitions_json", "TEXT"),
    ):
        if column not in run_cols:
            conn.execute(f"ALTER TABLE cluster_runs ADD COLUMN {column} {kind}")

    topic_cols = _columns(conn, "topics")
    for column in ("keywords_json", "representative_ids_json"):
        if column not in topic_cols:
            conn.execute(f"ALTER TABLE topics ADD COLUMN {column} TEXT")


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
    KHÔNG lẫn các reply của tác giả (1.368 tại 2026-09-30) cũng nằm trong bảng `posts`."""
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
    keywords: list[str] | None = None,
    representative_ids: list[str] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO topics (
            id, label_en, description_en, method, centroid_embedding_json,
            keywords_json, representative_ids_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            label_en = excluded.label_en,
            description_en = excluded.description_en,
            method = excluded.method,
            centroid_embedding_json = excluded.centroid_embedding_json,
            keywords_json = excluded.keywords_json,
            representative_ids_json = excluded.representative_ids_json
        """,
        (
            topic_id,
            label_en,
            description_en,
            method,
            json.dumps(centroid_embedding) if centroid_embedding is not None else None,
            json.dumps(keywords, ensure_ascii=False) if keywords is not None else None,
            json.dumps(representative_ids) if representative_ids is not None else None,
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
    cũ sai). Từ ADR-0004 CHECK chỉ còn `method='cluster'`; điều kiện WHERE giữ lại
    để rõ ý đồ nếu sau này có method khác.
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


# --- reply_role (ADR-0004) -------------------------------------------------------


def update_reply_roles(conn: sqlite3.Connection, roles: Mapping[str, str]) -> None:
    """Ghi vai của từng reply (`assign_reply_roles`). Root post giữ `reply_role` NULL."""
    conn.executemany(
        "UPDATE posts SET reply_role = ? WHERE id = ?",
        [(role, post_id) for post_id, role in roles.items()],
    )


def count_reply_roles(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT reply_role, COUNT(*) AS n FROM posts WHERE is_reply = 1 GROUP BY reply_role"
    ).fetchall()
    return {row["reply_role"] or "unassigned": row["n"] for row in rows}


# --- embeddings (ADR-0004) -------------------------------------------------------


def content_hash(text: str) -> str:
    """Hash của đúng chuỗi được embed — đổi text thì đổi hash → embed lại."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_embedding(
    conn: sqlite3.Connection,
    *,
    object_type: str,
    object_id: str,
    model_id: str,
    text_hash: str,
    vector: list[float],
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO embeddings (
            object_type, object_id, model_id, content_hash, dim, vector, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(object_type, object_id, model_id) DO UPDATE SET
            content_hash = excluded.content_hash,
            dim = excluded.dim,
            vector = excluded.vector,
            created_at = excluded.created_at
        """,
        (
            object_type,
            object_id,
            model_id,
            text_hash,
            len(vector),
            struct.pack(f"<{len(vector)}f", *vector),
            created_at,
        ),
    )


def load_embeddings(
    conn: sqlite3.Connection, *, object_type: str, model_id: str
) -> dict[str, tuple[str, list[float]]]:
    """`{object_id: (content_hash, vector)}` cho 1 loại đối tượng + 1 model."""
    rows = conn.execute(
        "SELECT object_id, content_hash, dim, vector FROM embeddings "
        "WHERE object_type = ? AND model_id = ?",
        (object_type, model_id),
    ).fetchall()
    return {
        row["object_id"]: (
            row["content_hash"],
            list(struct.unpack(f"<{row['dim']}f", row["vector"])),
        )
        for row in rows
    }


# --- cluster_runs ------------------------------------------------------------------


def insert_cluster_run(
    conn: sqlite3.Connection,
    *,
    run_at: str,
    model_id: str,
    params: dict[str, object],
    n_units: int,
    n_clusters: int,
    noise_ratio: float,
    dbcv: float | None,
    ari_vs_previous: float | None,
    labels: dict[str, int],
    dbcv_relative: float | None = None,
    ari_clustered_only: float | None = None,
    transitions: dict[str, int] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO cluster_runs (
            run_at, model_id, params_json, n_units, n_clusters, noise_ratio, dbcv,
            dbcv_relative, ari_vs_previous, ari_clustered_only, transitions_json,
            labels_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_at,
            model_id,
            json.dumps(params, sort_keys=True),
            n_units,
            n_clusters,
            noise_ratio,
            dbcv,
            dbcv_relative,
            ari_vs_previous,
            ari_clustered_only,
            json.dumps(transitions, sort_keys=True) if transitions is not None else None,
            json.dumps(labels, sort_keys=True),
        ),
    )


def latest_cluster_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM cluster_runs ORDER BY id DESC LIMIT 1").fetchone()
    return row  # type: ignore[no-any-return]
