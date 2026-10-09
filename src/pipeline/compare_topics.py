"""Bước 4/4 của job NLP hằng ngày (`nlp_cluster_job`) — so sánh từng topic với phần còn lại của
kênh trên lần gom cụm mới nhất và lưu kết quả (ADR-0023). Chạy trên Windows (numpy + scipy, không
cần WSL2).

Vì sao tính trong job, không tính khi có request: 27 phép so × 100.000 hoán vị mất ~70 giây
(đo 2026-10-09). Vì sao chỉ sau lần gom cụm (12:30), không sau mỗi snapshot 4h: thành viên topic
chỉ đổi lúc gom cụm; tính lại mỗi 4h chỉ cập nhật views, đổi lại thêm ~70 giây × 6 lần/ngày khi máy
chạy pin (Thy chốt D1, 2026-10-09). Kết quả ghi kèm `snapshot_as_of` để trang nói rõ số "tính tới"
lúc nào.

Tập unit = khoá `cluster_runs.labels_json` của lần gom cụm mới nhất (unit có chữ lúc export —
`docs/design/topics-data-audit.md` mục 1); topic của unit đọc từ `post_topic_labels`, ghi cùng
transaction với dòng `cluster_runs` đó ở bước import. Bước này lỗi thì kết quả gom cụm vẫn giữ;
API thấy kết quả so sánh thuộc lần gom cụm cũ → `stale` (ADR-0023, Thy chốt D3).

Chạy tay: `uv run python -m src.pipeline.compare_topics`
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.analysis.significance import DEFAULT_N_PERMUTATIONS
from src.analysis.topic_comparison import (
    CONCLUSION_ALPHA,
    GroupComparison,
    TopicComparisonSet,
    UnitObservation,
    compare_topics,
)
from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    create_schema,
    latest_cluster_run,
    latest_insight_snapshot,
    replace_topic_comparisons,
    snapshot_row_to_post_insights,
)

# Quy tắc vận hành, không phải tham số thống kê: job snapshot giữ khoá ghi ~2 phút mỗi lần chạy
# (`scripts/job_health.py`: "job snapshot chạy ~2 phút")
WRITE_LOCK_WAIT_MS = 120_000


def load_observations(
    conn: sqlite3.Connection, labels: dict[str, int]
) -> tuple[list[UnitObservation], str | None]:
    """Mỗi unit của lần gom cụm + topic của nó + snapshot mới nhất; kèm `fetched_at` mới nhất
    trong các snapshot đã dùng."""
    topic_of = {
        row["post_id"]: row["topic_id"]
        for row in conn.execute(
            "SELECT post_id, topic_id FROM post_topic_labels WHERE method = 'cluster'"
        )
    }
    observations: list[UnitObservation] = []
    as_of: str | None = None
    for unit_id in sorted(labels):
        snapshot = latest_insight_snapshot(conn, unit_id)
        if snapshot is not None and (as_of is None or snapshot["fetched_at"] > as_of):
            as_of = snapshot["fetched_at"]
        observations.append(
            UnitObservation(
                unit_id=unit_id,
                topic_id=topic_of.get(unit_id),
                insights=None if snapshot is None else snapshot_row_to_post_insights(snapshot),
            )
        )
    return observations, as_of


def _row(row: GroupComparison) -> dict[str, object]:
    return {
        "group_id": row.group_id,
        "kind": row.kind,
        "metric": row.metric,
        "n": row.group.n,
        "excluded_no_views": row.group_excluded_no_views,
        "median": row.group.median,
        "iqr_low": row.group.iqr_low,
        "iqr_high": row.group.iqr_high,
        "rest_n": None if row.rest is None else row.rest.n,
        "rest_excluded_no_views": row.rest_excluded_no_views,
        "rest_median": None if row.rest is None else row.rest.median,
        "rest_iqr_low": None if row.rest is None else row.rest.iqr_low,
        "rest_iqr_high": None if row.rest is None else row.rest.iqr_high,
        "tested": int(row.tested),
        "effect_size": row.effect_size,
        "effect_size_ci_low": row.effect_size_ci_low,
        "effect_size_ci_high": row.effect_size_ci_high,
        "p_value": row.p_value,
        "p_value_holm": row.p_value_holm,
        "p_value_mann_whitney": row.p_value_mann_whitney,
        "test_method": row.test_method,
        "insufficient_data": int(row.insufficient_data),
    }


def store(
    conn: sqlite3.Connection,
    *,
    cluster_run_id: int,
    result: TopicComparisonSet,
    snapshot_as_of: str | None,
    computed_at: str,
) -> None:
    replace_topic_comparisons(
        conn,
        cluster_run_id=cluster_run_id,
        computed_at=computed_at,
        snapshot_as_of=snapshot_as_of,
        n_permutations=result.n_permutations,
        random_seed=result.random_seed,
        holm_family_size=result.holm_family_size,
        rows=[_row(row) for row in result.rows],
    )


def run_compare(
    db_path: Path = DEFAULT_DB_PATH, *, n_permutations: int = DEFAULT_N_PERMUTATIONS
) -> dict[str, Any]:
    conn = connect(db_path)
    # Job snapshot 4h có thể đang giữ khoá ghi (DB chưa WAL tới Phase C): chờ tới 2 phút thay vì
    # 5 giây mặc định, để ~70 giây tính toán không mất vì `database is locked` lúc ghi
    # (code-reviewer 2026-10-09). Hết 2 phút vẫn khoá → bước lỗi, API trả `stale`, `job_health`
    # cảnh báo.
    conn.execute(f"PRAGMA busy_timeout = {WRITE_LOCK_WAIT_MS}")
    try:
        create_schema(conn)
        run = latest_cluster_run(conn)
        if run is None:
            return {"skipped": "chưa có lần gom cụm nào"}
        labels: dict[str, int] = json.loads(run["labels_json"])
        observations, snapshot_as_of = load_observations(conn, labels)
        result = compare_topics(observations, n_permutations=n_permutations)
        store(
            conn,
            cluster_run_id=run["id"],
            result=result,
            snapshot_as_of=snapshot_as_of,
            computed_at=datetime.now(UTC).isoformat(),
        )
        passing = sorted(
            f"{row.group_id}:{row.metric}"
            for row in result.rows
            if row.p_value_holm is not None and row.p_value_holm < CONCLUSION_ALPHA
        )
        return {
            "cluster_run_id": run["id"],
            "snapshot_as_of": snapshot_as_of,
            "holm_family_size": result.holm_family_size,
            "p_holm_below_alpha": passing,
        }
    finally:
        conn.close()


def main() -> None:
    # Log job là UTF-8; console Windows cp1252 khi chạy tay
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(run_compare())


if __name__ == "__main__":
    main()
