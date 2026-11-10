"""Tháng đăng + topic của mỗi bài cho bộ lọc metadata của demo RAG (ADR-0041, "Dữ liệu thêm vào file
demo").

Topic là ảnh chụp của **lần gom cụm mới nhất** lúc `assemble` — cùng lần trang `/topics` đang hiện
lúc đó. Job gom cụm ghi `cluster_runs` và `post_topic_labels` trong cùng một commit
(`src/pipeline/clustering_import.py`), nên đọc cả hai trong một giao dịch đọc là đủ để không lấy
nhãn của lần này với mã của lần khác khi job đang chạy song song.

Bài không có nhãn (bài nhiễu, hoặc không có trong lần gom cụm đó) ghi topic `{id: None,
label_en: "Unclustered"}` — "Unclustered" là một giá trị lọc được (ADR-0041, quy ước của tìm kiếm
theo mặt; cách ghi Thy chọn 2026-11-10). Thông báo lỗi chỉ ghi mã bài, không ghi chữ bài.
"""

import sqlite3
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.models.days import author_day
from src.rag_demo.corpus import Unit

UNCLUSTERED = "Unclustered"


class MetadataError(ValueError):
    """DB không đủ để ghi tháng đăng / topic của mọi bài."""


@dataclass(frozen=True)
class UnitMeta:
    month: str  # "YYYY-MM" theo giờ Paris của post mở đầu (ADR-0034: ngày đăng = giờ tác giả)
    topic_id: str | None  # None = Unclustered
    topic_label_en: str


@dataclass(frozen=True)
class TopicSnapshot:
    cluster_run_id: int | None  # None = DB chưa có lần gom cụm nào: mọi bài Unclustered
    cluster_run_at: str | None  # UTC, như `cluster_runs.run_at`
    units: dict[str, UnitMeta]


def author_month(timestamp: str) -> str:
    """Tháng đăng "YYYY-MM" theo giờ Paris, cùng quy ước với ngày đăng (`author_day`)."""
    # Không có múi giờ thì `astimezone` lặng lẽ hiểu là giờ của máy chạy lệnh: bài đăng gần nửa
    # đêm đầu tháng có thể sang tháng khác tuỳ máy. Dừng thay vì đoán.
    if datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError("không có múi giờ")
    return author_day(timestamp)[:7]


def read_unit_metadata(conn: sqlite3.Connection, units: Sequence[Unit]) -> TopicSnapshot:
    """Tháng đăng + topic của từng bài, đọc trong một giao dịch đọc (ảnh chụp nhất quán)."""
    conn.execute("BEGIN")
    try:
        run = conn.execute(
            "SELECT id, run_at FROM cluster_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        metadata: dict[str, UnitMeta] = {}
        for unit in units:
            # mã bài = mã post mở đầu (content unit, ADR-0004)
            post = conn.execute("SELECT timestamp FROM posts WHERE id = ?", (unit.id,)).fetchone()
            if post is None:
                raise MetadataError(f"{unit.id}: post mở đầu không có trong posts")
            # LEFT JOIN: nhãn trỏ tới topic đã mất (SQLite không bật khoá ngoại) phải dừng, không
            # lặng lẽ thành Unclustered
            label = conn.execute(
                "SELECT l.topic_id, t.label_en FROM post_topic_labels AS l "
                "LEFT JOIN topics AS t ON t.id = l.topic_id "
                "WHERE l.post_id = ? AND l.method = 'cluster'",
                (unit.id,),
            ).fetchone()
            if label is not None and label[1] is None:
                raise MetadataError(
                    f"{unit.id}: nhãn trỏ tới topic {label[0]} không có trong topics"
                )
            if label is not None and run is None:
                raise MetadataError(f"{unit.id}: có nhãn topic mà DB không có lần gom cụm nào")
            try:
                month = author_month(post[0])
            except (TypeError, ValueError) as error:
                raise MetadataError(f"{unit.id}: timestamp không đọc được ({error})") from error
            metadata[unit.id] = UnitMeta(
                month=month,
                topic_id=None if label is None else label[0],
                topic_label_en=UNCLUSTERED if label is None else label[1],
            )
    finally:
        conn.rollback()  # chỉ đọc: kết thúc giao dịch, không ghi gì
    return TopicSnapshot(
        cluster_run_id=None if run is None else int(run[0]),
        cluster_run_at=None if run is None else run[1],
        units=metadata,
    )


def summary(snapshot: TopicSnapshot) -> str:
    """Một dòng cho lệnh `assemble`: lần gom cụm, số bài có topic, số bài theo tháng."""
    metas = list(snapshot.units.values())
    clustered = sum(1 for meta in metas if meta.topic_id is not None)
    months = ", ".join(f"{m} {n}" for m, n in sorted(Counter(x.month for x in metas).items()))
    run = (
        "chưa có lần gom cụm nào"
        if snapshot.cluster_run_id is None
        else f"lần gom cụm {snapshot.cluster_run_id} ({snapshot.cluster_run_at})"
    )
    return (
        f"Topic: {run} · {clustered} / {len(metas)} bài có topic, "
        f"{len(metas) - clustered} {UNCLUSTERED} · tháng đăng (giờ Paris): {months}"
    )
