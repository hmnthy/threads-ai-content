"""Số liệu của ADR-0024 (độ bền kết luận so sánh topic qua các cách chia cụm) — sinh lại được từ DB
thật, chỉ đọc. Mọi con số ADR-0024 trích đều in ở đây.

Chạy: `uv run python -m scripts.topic_stability_report` (mặc định `data/threads.db` của thư mục
hiện tại; `--db` để trỏ DB khác; `--topic` hoặc `--reference-run/--reference-cluster` chọn nhóm bài
tham chiếu; `--permutations` số lần xáo nhãn — mặc định 20.000, ~15 giây mỗi cách chia).

In theo thứ tự đọc của ADR:
1. Các lần gom cụm và **cách chia khác nhau**: 1 lần gom cụm thuộc cùng cách chia với lần trước khi
   nhãn của MỌI unit giống hệt (cùng tập unit, cùng nhãn). Không dùng `ari_vs_previous` = 1: ARI chỉ
   tính trên unit chung của 2 lần, nên lần có thêm bài mới vẫn có thể ra ARI 1.
2. Kết luận đã lưu (`topic_comparisons`) của từng lần so sánh: phép so đạt p Holm < ngưỡng, kèm n đo
   được (topic / phần còn lại), δ [CI chưa hiệu chỉnh], p Holm.
3. Giữ CỐ ĐỊNH số liệu (snapshot mới nhất của mọi bài), chạy lại phép so trên lần gom cụm cuối của
   mỗi cách chia (mỗi cách chia trên tập unit của chính nó).
4. Như 3 nhưng chỉ trên unit có mặt ở MỌI cách chia → cùng tập bài, cùng số liệu, chỉ khác cách
   chia (tách ảnh hưởng của cách chia khỏi ảnh hưởng của bài mới).
5. Theo dõi nhóm bài tham chiếu (mặc định: topic có p Holm engagement nhỏ nhất ở lần so sánh mới
   nhất; hoặc `--reference-run R --reference-cluster C` = cụm C của lần R) qua mọi cách chia: bài
   nằm ở đâu, cụm khớp nhất (Jaccard), engagement của cụm đó.
6. Lịch sử "đạt ở k trong m cách chia" của mọi topic × chỉ số — cùng hàm với API/landing
   (`--history-only` chỉ in mục này, vài giây).

Số ADR-0024 (2026-10-18): `--reference-run 16 --reference-cluster 8` (topic_11 ở lần 16, 18 bài).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Định nghĩa "cách chia" dùng chung với API (lịch sử "k trong m cách chia", ADR-0024)
from src.analysis.partition_history import (
    StoredComparison,
    distinct_partitions,
    partition_history,
    partition_run_ids,
    representatives,
)
from src.analysis.topic_comparison import (
    CONCLUSION_ALPHA,
    GroupComparison,
    TopicComparisonSet,
    UnitObservation,
    compare_topics,
)
from src.api.models import PostInsights
from src.db.schema import (
    DEFAULT_DB_PATH,
    latest_insight_snapshot,
    list_cluster_run_labels,
    list_tested_topic_comparisons,
    snapshot_row_to_post_insights,
)

# Độ phân giải đủ để phân biệt quanh ngưỡng Holm 0.05/30 ≈ 0.0017 (sàn p thô ≈ 1/20.001); job thật
# dùng 100.000 — đây là báo cáo thăm dò, không phải số hiển thị
DEFAULT_PERMUTATIONS = 20_000


@dataclass(frozen=True)
class ClusterRun:
    id: int
    run_at: str
    n_clusters: int
    noise_ratio: float
    ari_vs_previous: float | None
    labels: dict[str, int]


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def members(labels: dict[str, int], label: int) -> set[str]:
    return {unit for unit, lab in labels.items() if lab == label}


def observations(
    labels: dict[str, int], insights: dict[str, PostInsights | None]
) -> list[UnitObservation]:
    """Mỗi unit của cách chia: nhóm "c<nhãn>" (nhiễu → None) + snapshot cố định."""
    return [
        UnitObservation(
            unit_id=unit,
            topic_id=None if label == -1 else f"c{label}",
            insights=insights.get(unit),
        )
        for unit, label in sorted(labels.items())
    ]


def passing(result: TopicComparisonSet) -> list[GroupComparison]:
    return [
        row
        for row in result.rows
        if row.kind == "topic"
        and row.p_value_holm is not None
        and row.p_value_holm < CONCLUSION_ALPHA
    ]


def load_runs(conn: sqlite3.Connection) -> list[ClusterRun]:
    return [
        ClusterRun(
            id=row["id"],
            run_at=row["run_at"],
            n_clusters=row["n_clusters"],
            noise_ratio=row["noise_ratio"],
            ari_vs_previous=row["ari_vs_previous"],
            labels={unit: int(label) for unit, label in json.loads(row["labels_json"]).items()},
        )
        for row in conn.execute(
            "SELECT id, run_at, n_clusters, noise_ratio, ari_vs_previous, labels_json "
            "FROM cluster_runs ORDER BY id"
        )
    ]


def reference_topic(conn: sqlite3.Connection, requested: str | None) -> str | None:
    if requested:
        return requested
    row = conn.execute(
        "SELECT group_id FROM topic_comparisons WHERE kind = 'topic' AND metric = 'engagement' "
        "AND p_value_holm IS NOT NULL AND cluster_run_id = "
        "(SELECT MAX(cluster_run_id) FROM topic_comparison_runs) ORDER BY p_value_holm LIMIT 1"
    ).fetchone()
    return None if row is None else str(row["group_id"])


def fmt(value: float | None, spec: str = "+.2f") -> str:
    return "n/a" if value is None else format(value, spec)


def describe(row: GroupComparison) -> str:
    """n đo được (bài views > 0, ADR-0011) của topic và phần còn lại + δ [CI] + p Holm."""
    rest_n = "n/a" if row.rest is None else str(row.rest.n)
    excluded = (
        f", loại {row.group_excluded_no_views} bài views = 0" if row.group_excluded_no_views else ""
    )
    return (
        f"{row.group_id} {row.metric}: n = {row.group.n} vs {rest_n}{excluded}, "
        f"δ {fmt(row.effect_size)} [{fmt(row.effect_size_ci_low)}; "
        f"{fmt(row.effect_size_ci_high)}], p Holm {fmt(row.p_value_holm, '.4f')}"
    )


def rerun(
    groups: list[list[ClusterRun]],
    insights: dict[str, PostInsights | None],
    n_permutations: int,
    keep: set[str] | None = None,
) -> dict[int, TopicComparisonSet]:
    """Chạy lại phép so trên lần cuối của mỗi cách chia; `keep` = chỉ giữ các unit này."""
    results: dict[int, TopicComparisonSet] = {}
    for group in groups:
        run = group[-1]
        labels = run.labels
        if keep is not None:
            labels = {unit: label for unit, label in labels.items() if unit in keep}
        results[run.id] = compare_topics(
            observations(labels, insights), n_permutations=n_permutations
        )
        sizes = Counter(label for label in labels.values() if label != -1)
        rows = passing(results[run.id])
        noise = sum(1 for label in labels.values() if label == -1)
        size_range = f"{min(sizes.values())}–{max(sizes.values())}" if sizes else "—"
        print(
            f"   lần {run.id}: {len(labels)} unit, {len(sizes)} cụm ({size_range} bài/cụm), "
            f"{noise} bài nhiễu, họ {results[run.id].holm_family_size}, đạt {len(rows)}"
        )
        for row in rows:
            print(f"      {describe(row)}")
    return results


def main(argv: Sequence[str] | None = None) -> None:
    # Console Windows mặc định cp1252 — in UTF-8 để chữ Việt / ký tự đặc biệt không làm script lỗi
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--topic", default=None, help="topic_N làm nhóm bài tham chiếu (mục 5)")
    parser.add_argument(
        "--reference-run",
        type=int,
        default=None,
        help="cùng --reference-cluster: nhóm bài tham chiếu = 1 cụm của 1 lần gom cụm cũ",
    )
    parser.add_argument("--reference-cluster", type=int, default=None)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument(
        "--history-only",
        action="store_true",
        help="chỉ in mục 6 (lịch sử k trong m cách chia) — vài giây, không chạy lại phép so",
    )
    args = parser.parse_args(argv)
    if (args.reference_run is None) != (args.reference_cluster is None):
        parser.error("--reference-run và --reference-cluster phải đi cùng nhau")

    conn = sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not args.history_only:
            report(conn, args, parser)
        history(conn)
    finally:
        conn.close()


def history(conn: sqlite3.Connection) -> None:
    """Mục 6: lịch sử "đạt ở k trong m cách chia" — đúng hàm `GET /topics/comparisons` dùng
    (`src/analysis/partition_history.py`), nên số in ra là số landing hiển thị."""
    print("\n6. Lịch sử k trong m cách chia (như `GET /topics/comparisons`)")
    # DB chưa migrate (chưa có `cluster_runs` / `topic_comparisons`) đọc là "chưa có kết quả"
    try:
        stored = [
            StoredComparison(
                cluster_run_id=row["cluster_run_id"],
                run_at=row["run_at"],
                group_id=row["group_id"],
                metric=row["metric"],
                effect_size=row["effect_size"],
                p_value_holm=row["p_value_holm"],
                insufficient_data=bool(row["insufficient_data"]),
            )
            for row in list_tested_topic_comparisons(conn)
        ]
        partitions = partition_run_ids(list_cluster_run_labels(conn))
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        stored, partitions = [], []
    compared = representatives(partitions, {row.cluster_run_id for row in stored})
    if not compared:
        print("   Chưa có lần so sánh nào.")
        return
    print(
        f"   {len(compared)} cách chia có kết quả so sánh (đại diện = lần {compared}), "
        f"từ {next(r.run_at for r in stored if r.cluster_run_id == compared[0])[:10]}"
    )
    current = {(row.group_id, row.metric) for row in stored if row.cluster_run_id == compared[-1]}
    tallies = partition_history(partitions, stored, alpha=CONCLUSION_ALPHA)
    for (topic, metric), tally in sorted(tallies.items()):
        print(
            f"   {topic} {metric}: cao hơn {tally.higher}, thấp hơn {tally.lower} / m = "
            f"{tally.clusterings} (+{tally.too_few_posts} thiếu bài), từ {tally.since[:10]}"
            f"{'' if (topic, metric) in current else ' — không còn ở cách chia mới nhất'}"
        )


def report(
    conn: sqlite3.Connection, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    runs = load_runs(conn)
    if not runs:
        print("Chưa có lần gom cụm nào — không có gì để báo cáo.")
        return
    by_id = {run.id: run for run in runs}
    if args.reference_run is not None and args.reference_run not in by_id:
        parser.error(f"không có lần gom cụm {args.reference_run}")
    groups = distinct_partitions(runs)

    print(f"1. {len(runs)} lần gom cụm = {len(groups)} cách chia khác nhau")
    previous_units: set[str] | None = None
    for group in groups:
        first, last = group[0], group[-1]
        units = set(last.labels)
        added = "?" if previous_units is None else f"+{len(units - previous_units)}"
        print(
            f"   lần {first.id}–{last.id} ({first.run_at[:10]} → {last.run_at[:10]}): "
            f"{last.n_clusters} cụm, nhiễu {last.noise_ratio:.0%}, {len(units)} unit "
            f"({added} so với cách chia trước), ARI so với lần trước "
            f"{fmt(first.ari_vs_previous, '.2f')}"
        )
        previous_units = units

    print("\n2. Kết luận đã lưu theo lần so sánh (p Holm < ngưỡng)")
    stored = conn.execute(
        "SELECT r.cluster_run_id AS run, r.snapshot_as_of AS as_of, r.holm_family_size AS family "
        "FROM topic_comparison_runs r ORDER BY r.cluster_run_id"
    ).fetchall()
    for run_row in stored:
        hits = conn.execute(
            "SELECT group_id, metric, n, rest_n, effect_size, effect_size_ci_low, "
            "effect_size_ci_high, p_value_holm FROM topic_comparisons "
            "WHERE cluster_run_id = ? AND kind = 'topic' AND p_value_holm < ? "
            "ORDER BY p_value_holm",
            (run_row["run"], CONCLUSION_ALPHA),
        ).fetchall()
        print(
            f"   lần {run_row['run']} (số liệu tới {str(run_row['as_of'])[:10]}, "
            f"họ {run_row['family']}): đạt {len(hits)}"
        )
        for hit in hits:
            print(
                f"      {hit['group_id']} {hit['metric']}: n = {hit['n']} vs {hit['rest_n']}, "
                f"δ {fmt(hit['effect_size'])} [{fmt(hit['effect_size_ci_low'])}; "
                f"{fmt(hit['effect_size_ci_high'])}], p Holm {fmt(hit['p_value_holm'], '.4f')}"
            )

    all_units = sorted({unit for run in runs for unit in run.labels})
    insights: dict[str, PostInsights | None] = {}
    for unit in all_units:
        snapshot = latest_insight_snapshot(conn, unit)
        insights[unit] = None if snapshot is None else snapshot_row_to_post_insights(snapshot)

    print(
        "\n3. Cố định số liệu (snapshot mới nhất), chạy lại phép so trên lần cuối mỗi cách chia "
        f"({args.permutations} hoán vị)"
    )
    results = rerun(groups, insights, args.permutations)

    common = set.intersection(*(set(group[-1].labels) for group in groups))
    print(f"\n4. Như 3, chỉ trên {len(common)} unit có mặt ở mọi cách chia")
    rerun(groups, insights, args.permutations, keep=common)

    if args.reference_run is not None:
        # Nhóm bài của 1 cụm ở 1 lần gom cụm cũ — `post_topic_labels` chỉ giữ cách chia mới nhất
        reference = members(by_id[args.reference_run].labels, args.reference_cluster)
        title = f"cụm c{args.reference_cluster} của lần {args.reference_run}"
    else:
        topic = reference_topic(conn, args.topic)
        reference = {
            r["post_id"]
            for r in conn.execute(
                "SELECT post_id FROM post_topic_labels WHERE method = 'cluster' AND topic_id = ?",
                (topic,),
            )
        }
        title = f"{topic} hiện tại"
    print(f"\n5. Nhóm bài tham chiếu: {title} (n = {len(reference)})")
    if not reference:
        print("   (không có bài — chọn `--topic` hoặc `--reference-run/--reference-cluster` khác)")
        return
    for group in groups:
        run = group[-1]
        where = Counter(
            "chưa có" if unit not in run.labels else str(run.labels[unit]) for unit in reference
        )
        candidates = {run.labels[u] for u in reference if run.labels.get(u, -1) != -1}
        line = f"   lần {run.id}: bài nằm ở {dict(sorted(where.items()))}"
        if candidates:
            best = max(candidates, key=lambda lab: jaccard(members(run.labels, lab), reference))
            group_members = members(run.labels, best)
            row = next(
                r
                for r in results[run.id].rows
                if r.group_id == f"c{best}" and r.metric == "engagement"
            )
            line += (
                f" → cụm khớp nhất c{best} ({len(group_members)} bài, Jaccard "
                f"{jaccard(group_members, reference):.2f}): {describe(row)}"
            )
        print(line)


if __name__ == "__main__":
    main()
