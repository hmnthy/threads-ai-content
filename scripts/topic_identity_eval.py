"""Thí nghiệm chọn quy tắc danh tính cụm (ADR-0018) — tái lập được, gọi đúng code production.

Hai bước:
1. `seeds` (chạy TRONG WSL, venv ML): gom cụm lại CÙNG dữ liệu (embedding đã lưu) với nhiều seed
   UMAP, tham số y hệt production → `data/experiments/topic_identity_seeds.json`.
     wsl -d Ubuntu -- bash -c "cd <repo WSL> && source ~/threads-clustering-env/bin/activate \\
       && python3 -m scripts.topic_identity_eval seeds"
2. `evaluate` (Windows): áp từng biến thể quy tắc (`match_topics` với các cờ) lên mọi cặp seed có
   thứ tự (lần trước → lần sau) + các lần chuyển thật trong `cluster_runs`; in bảng + ghi
   `data/experiments/topic_identity_eval.json`.
     uv run python -m scripts.topic_identity_eval evaluate

Hai loại lỗi được đo (1 quy tắc "giữ tất cả" sẽ đạt 0% ở loại 1 — phải có loại 2):
1. **Đổi tên thừa**: data y nguyên giữa các seed → mọi lần đổi tên = tên trên dashboard đổi khi
   nội dung không đổi. Kiểm ngữ nghĩa: cosine tâm (bge-m3) giữa cụm bị đổi tên và topic cũ gần
   nhất, so với `semantic_reference` CỦA CHÍNH CẶP ĐÓ (cosine lớn nhất giữa 2 topic khác nhau
   của lần trước) — vượt mốc = gần như chắc là cùng chủ đề.
2. **Giữ id sai**: với mỗi cụm được giữ, xoá hẳn cụm đó + mọi bài của topic cũ khỏi lần sau rồi
   ghép lại — topic đã biến mất mà id vẫn được trao cho cụm khác là lỗi.

CI95: **bootstrap hai chiều theo seed** — mỗi cặp phụ thuộc CẢ seed lần trước lẫn lần sau (thiết
kế chéo), nên lấy mẫu lại tập seed (có hoàn lại) rồi lấy trung bình mọi cặp có thứ tự giữa 2 seed
khác nhau trong mẫu; chênh lệch giữa biến thể là bootstrap ghép cặp trên cùng mẫu seed.
Biên (lần chuyển thật): với mỗi cụm giữ bằng thành viên, số bài phải đổi chỗ để 1 trong 2 tỉ lệ
đa số rơi xuống ≤ 1/2.

Kết quả thô chứa id bài thật → ở `data/experiments/` (gitignored); số tổng hợp ghi ở ADR-0018.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import struct
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from itertools import permutations
from pathlib import Path
from typing import Any

import numpy as np

from src.nlp.topic_identity import centroid, match_topics, semantic_reference

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "threads.db"
OUT_DIR = REPO_ROOT / "data" / "experiments"
SEEDS_PATH = OUT_DIR / "topic_identity_seeds.json"
EVAL_PATH = OUT_DIR / "topic_identity_eval.json"
SEEDS = (42, 0, 1, 2, 3, 4, 5, 6, 7, 8)  # 42 = seed production
BOOTSTRAP_REPS = 5000

_NO_SEMANTIC = {"semantic": False}
_OLD_MERGE = {"merge_counts_noise": False}  # phép thử nhập cũng bỏ nhiễu (bản đã review)
# Hàng đầu = quy tắc trước ADR-0018 (mốc so sánh); hàng cuối = quy tắc Thy chốt 2026-10-04
VARIANTS: tuple[tuple[str, dict[str, bool]], ...] = (
    (
        "count_noise+all_new",
        {"exclude_noise": False, "core_keeps": False, **_NO_SEMANTIC},
    ),
    ("count_noise+core_keeps", {"exclude_noise": False, **_NO_SEMANTIC}),
    ("exclude_noise+all_new", {"core_keeps": False, **_NO_SEMANTIC, **_OLD_MERGE}),
    ("exclude_noise+core_keeps", {**_NO_SEMANTIC, **_OLD_MERGE}),
    (
        "exclude_noise+core_keeps+semantic_incl_merged (exploratory)",
        {
            **_OLD_MERGE,
            "semantic_for_merged": True,
        },
    ),
    ("exclude_noise+core_keeps+semantic (reviewed draft)", dict(_OLD_MERGE)),
    ("exclude_noise_keep_only+core_keeps+semantic (chosen)", {}),
)


def _db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)


def load_vectors(conn: sqlite3.Connection) -> dict[str, np.ndarray]:
    vectors: dict[str, np.ndarray] = {}
    for oid, dim, blob in conn.execute(
        "SELECT e.object_id, e.dim, e.vector FROM embeddings e "
        "JOIN content_units c ON c.id = e.object_id "
        "WHERE e.object_type = 'content_unit' AND e.model_id = 'BAAI/bge-m3' "
        "AND trim(coalesce(c.full_text, '')) != '' ORDER BY e.object_id"
    ):
        vectors[oid] = np.array(struct.unpack(f"<{dim}f", blob))
    return vectors


def run_seeds() -> None:
    from src.nlp import topics  # chỉ có trong WSL (umap, hdbscan)

    conn = _db()
    vectors = load_vectors(conn)
    conn.close()
    ids = sorted(vectors)
    matrix = np.array([vectors[u] for u in ids])
    runs: dict[str, dict[str, int]] = {}
    for seed in SEEDS:
        topics.UMAP_RANDOM_STATE = seed
        labels = [int(x) for x in topics.cluster_embeddings(matrix).labels]
        runs[str(seed)] = dict(zip(ids, labels, strict=True))
        n = len({x for x in labels if x != -1})
        print(f"seed {seed}: {n} clusters, noise {labels.count(-1) / len(labels):.0%}", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SEEDS_PATH.write_text(json.dumps({"ids": ids, "runs": runs}), encoding="utf-8")
    print(f"wrote {SEEDS_PATH}")


def as_topics(labels: Mapping[str, int]) -> dict[str, str]:
    """Nhãn HDBSCAN của 1 lần → {unit_id: topic_id} như topic đang lưu (bỏ nhiễu)."""
    return {u: f"t{label}" for u, label in labels.items() if label != -1}


def evaluate_pair(
    prev: Mapping[str, int],
    cur: Mapping[str, int],
    vectors: Mapping[str, np.ndarray],
    flags: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """1 dòng / cụm của lần sau: sự kiện + cosine tới topic cũ gần nhất + mốc của cặp này."""
    previous = as_topics(prev)
    reference = semantic_reference(previous, vectors)
    matches = match_topics(previous, cur, vectors, reference, **flags)
    old_members: dict[str, set[str]] = defaultdict(set)
    for u, t in previous.items():
        old_members[t].add(u)
    old_c = [c for m in old_members.values() if (c := centroid(m, vectors)) is not None]
    rows = []
    for cluster, m in matches.items():
        cc = centroid({u for u, label in cur.items() if label == cluster}, vectors)
        best = max(float(cc @ oc) for oc in old_c) if cc is not None and old_c else None
        rows.append(
            {
                "event": m.event,
                "via": m.via,
                "topic_id": m.topic_id,
                "cluster": cluster,
                "best_cosine": best,
                "reference": reference,
            }
        )
    return rows


def false_keeps(
    prev: Mapping[str, int],
    cur: Mapping[str, int],
    vectors: Mapping[str, np.ndarray],
    flags: Mapping[str, bool],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[int, int]:
    """(số lần id sống sót sai, số phép thử): với mỗi cụm được giữ, xoá hẳn cụm đó và mọi bài
    của topic cũ khỏi lần sau rồi ghép lại. Quy tắc chỉ thành viên luôn ra 0 theo cấu tạo (topic
    bị xoá không còn bài để làm cha) — phép thử chỉ đo được lỗi của bước ngữ nghĩa."""
    previous = as_topics(prev)
    reference = semantic_reference(previous, vectors)
    wrong = trials = 0
    for row in rows:
        if row["event"] != "kept":
            continue
        gone = {u for u, t in previous.items() if t == row["topic_id"]}
        gone |= {u for u, label in cur.items() if label == row["cluster"]}
        reduced = {u: label for u, label in cur.items() if u not in gone}
        again = match_topics(previous, reduced, vectors, reference, **flags)
        trials += 1
        wrong += any(m.topic_id == row["topic_id"] for m in again.values())
    return wrong, trials


def pair_bootstrap(
    pair_values: Mapping[tuple[str, str], float],
    seeds: Sequence[str],
    reps: int = BOOTSTRAP_REPS,
) -> tuple[float, float]:
    """CI95 của trung bình theo cặp, bootstrap HAI CHIỀU: lấy mẫu lại seed (có hoàn lại), lấy mọi
    cặp có thứ tự giữa 2 vị trí mang seed KHÁC nhau (cặp seed trùng không có trong thiết kế)."""
    rng = random.Random(0)
    means: list[float] = []
    for _ in range(reps):
        sample = rng.choices(seeds, k=len(seeds))
        vals = [
            pair_values[(a, b)]
            for i, a in enumerate(sample)
            for j, b in enumerate(sample)
            if i != j and a != b
        ]
        if vals:
            means.append(statistics.mean(vals))
    means.sort()
    return means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1]


def flip_margin(part: int, whole: int) -> int:
    """Số bài phải đổi chỗ để `part/whole > 1/2` thành ≤ 1/2 (0 nếu đã không là đa số)."""
    return max(0, part - whole // 2)


def membership_margins(prev: Mapping[str, int], cur: Mapping[str, int]) -> list[dict[str, Any]]:
    """Biên của các cụm giữ bằng thành viên (quy tắc chốt) ở 1 lần chuyển thật."""
    previous = as_topics(prev)
    matches = match_topics(previous, cur, semantic=False)
    rows = []
    for cluster, m in matches.items():
        if m.via != "membership" or m.topic_id is None:
            continue
        new = {u for u, label in cur.items() if label == cluster}
        old = {u for u, t in previous.items() if t == m.topic_id and u in cur}
        old_now = {u for u in old if cur[u] != -1}
        shared = len(new & old)
        rows.append(
            {
                "cluster": cluster,
                "share_new": shared / len(new),
                "share_old": len(new & old_now) / len(old_now),
                "posts_to_flip": min(
                    flip_margin(shared, len(new)), flip_margin(len(new & old_now), len(old_now))
                ),
            }
        )
    return rows


def run_evaluate() -> dict[str, Any]:
    data = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    runs: dict[str, dict[str, int]] = data["runs"]
    conn = _db()
    vectors = load_vectors(conn)
    real = [
        (rid, json.loads(lab))
        for rid, lab in conn.execute("SELECT id, labels_json FROM cluster_runs ORDER BY id")
    ]
    conn.close()
    seeds = list(runs)
    pairs = list(permutations(seeds, 2))

    diff_topic: list[float] = []
    for s in seeds:
        groups: dict[int, set[str]] = defaultdict(set)
        for u, label in runs[s].items():
            if label != -1:
                groups[label].add(u)
        cs = [c for g in groups.values() if (c := centroid(g, vectors)) is not None]
        diff_topic += [float(a @ b) for i, a in enumerate(cs) for b in cs[i + 1 :]]

    results: dict[str, Any] = {
        "n_units": len(data["ids"]),
        "seeds": seeds,
        "n_pairs": len(pairs),
        "clusters_per_seed": {s: len({x for x in runs[s].values() if x != -1}) for s in seeds},
        "noise_per_seed": {
            s: sum(1 for x in runs[s].values() if x == -1) / len(runs[s]) for s in seeds
        },
        "different_topic_cosine_within_run": {
            "n": len(diff_topic),
            "median": statistics.median(diff_topic),
            "max": max(diff_topic),
        },
        "variants": {},
        "real_transitions": {},
    }
    rate_by_pair: dict[str, dict[tuple[str, str], float]] = {}
    for name, flags in VARIANTS:
        rates: dict[tuple[str, str], float] = {}
        events: Counter[str] = Counter()
        renamed = renamed_closer = wrong = trials = 0
        for a, b in pairs:
            rows = evaluate_pair(runs[a], runs[b], vectors, flags)
            out = [r for r in rows if r["event"] != "kept"]
            rates[(a, b)] = len(out) / len(rows)
            events.update(
                f"kept_{r['via']}" if r["event"] == "kept" else str(r["event"]) for r in rows
            )
            renamed += len(out)
            renamed_closer += sum(
                1
                for r in out
                if r["best_cosine"] is not None
                and r["reference"] is not None
                and r["best_cosine"] > r["reference"]
            )
            w, t = false_keeps(runs[a], runs[b], vectors, flags, rows)
            wrong, trials = wrong + w, trials + t
        rate_by_pair[name] = rates
        results["variants"][name] = {
            "flags": dict(flags),
            "n_clusters": sum(events.values()),
            "rename_rate": statistics.mean(rates.values()),
            "ci95_two_way": list(pair_bootstrap(rates, seeds)),
            "events": dict(events),
            "renamed": renamed,
            "renamed_closer_than_reference": renamed_closer,
            "false_keeps": wrong,
            "false_keep_trials": trials,
        }
    base = rate_by_pair[VARIANTS[0][0]]
    for name, rates in rate_by_pair.items():
        diffs = {k: base[k] - rates[k] for k in pairs}
        results["variants"][name]["reduction_vs_baseline"] = {
            "mean": statistics.mean(diffs.values()),
            "ci95_two_way": list(pair_bootstrap(diffs, seeds)),
        }
    for (ra, la), (rb, lb) in zip(real, real[1:], strict=False):
        key = f"{ra}->{rb}"
        results["real_transitions"][key] = {
            "events": {
                name: dict(Counter(r["event"] for r in evaluate_pair(la, lb, vectors, flags)))
                for name, flags in VARIANTS
            },
            "margins_chosen_rule": membership_margins(la, lb),
        }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    serialisable = json.loads(json.dumps(results, default=str))
    EVAL_PATH.write_text(json.dumps(serialisable, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def _print(results: dict[str, Any]) -> None:
    d = results["different_topic_cosine_within_run"]
    print(
        f"units {results['n_units']}, pairs {results['n_pairs']}; clusters/seed "
        f"{results['clusters_per_seed']}"
    )
    print(
        f"cosine 2 topic KHÁC nhau cùng lần: n={d['n']}, median {d['median']:.3f}, "
        f"max {d['max']:.3f}"
    )
    for name, v in results["variants"].items():
        lo, hi = v["ci95_two_way"]
        r = v["reduction_vs_baseline"]
        print(
            f"{name}\n  đổi tên {v['rename_rate']:.1%} [{lo:.1%}, {hi:.1%}], giảm "
            f"{r['mean']:.1%} [{r['ci95_two_way'][0]:.1%}, {r['ci95_two_way'][1]:.1%}]; "
            f"{v['events']}; đổi tên mà gần topic cũ hơn mốc {v['renamed_closer_than_reference']}"
            f"/{v['renamed']}; giữ id sai {v['false_keeps']}/{v['false_keep_trials']}"
        )
    for key, t in results["real_transitions"].items():
        events = {name: ev for name, ev in t["events"].items()}
        print(f"thật {key}: {events}")
        print(
            f"  biên (bài để lật): {sorted(m['posts_to_flip'] for m in t['margins_chosen_rule'])}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ADR-0018 topic identity experiment")
    parser.add_argument("step", choices=["seeds", "evaluate"])
    args = parser.parse_args(argv)
    if args.step == "seeds":
        run_seeds()
    else:
        _print(run_evaluate())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main())
