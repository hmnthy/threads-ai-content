"""Số liệu của ADR-0012 (tầng reach) — sinh lại được từ DB thật, chỉ đọc. Mọi con số ADR-0012
trích "sinh lại bằng script" đều in ở đây.

Chạy: `uv run python -m scripts.reach_report` (mặc định `data/threads.db` của thư mục hiện tại).
In: n, mốc chín + đường tăng views, ngưỡng P50/P80 (reach tương đối + views thô tham chiếu), số
bài mỗi trạng thái, tuổi bài theo tầng, tương quan với tuổi bài trước/sau hiệu chỉnh, engagement
rate giữa các tầng (`compare_groups()`: δ + CI), độ nhạy theo cửa sổ mốc 10/20/30 (giữ cố định
`BASELINE_MIN_PRIOR` để chỉ đổi 1 yếu tố).
"""

from __future__ import annotations

import argparse
import math
import sqlite3
import statistics
import sys
from pathlib import Path

from scipy.stats import spearmanr

from src.analysis.reach import (
    BASELINE_MIN_PRIOR,
    BASELINE_WINDOW,
    CURVE_FIRST_SNAPSHOT_MAX_DAYS,
    CURVE_SETTLED_MIN_DAYS,
    TIERED_STATUSES,
    baseline_spans,
    baseline_start_index,
    time_to_share,
)
from src.analysis.significance import ComparisonResult, compare_groups, holm_adjust
from src.db.schema import DEFAULT_DB_PATH
from src.main import compute_reach

SENSITIVITY_WINDOWS = (10, 20, 30)
CURVE_CHECK_DAYS = (1, 2, 7, 14)
SEED = 0  # bootstrap CI của compare_groups — cố định để số in ra lặp lại được
MIN_POSTS = 3  # dưới mức này không có phân vị / tương quan nào để in
# Mục "Xem lại khi" của ADR-0012: mốc 20 bài trải dài hơn ~3 tháng thì hiệu chỉnh tăng trưởng yếu
# đi. Thy chốt giữ 20 bài (2026-10-07) và ghi hạn chế — script đếm số bài bị ảnh hưởng.
BASELINE_SPAN_REVIEW_DAYS = 90


def _num(value: float | None, spec: str) -> str:
    return "—" if value is None else format(value, spec)


def _fmt_compare(name: str, r: ComparisonResult) -> str:
    if r.effect_size is None or r.p_value is None:
        return f"{name}: một nhóm rỗng (n={r.n_a} vs n={r.n_b}) — không so được"
    return (
        f"{name}: median {r.median_a:.2f}% (n={r.n_a}) vs {r.median_b:.2f}% (n={r.n_b}), "
        f"Cliff's delta={r.effect_size:.2f}, p={r.p_value:.3g}, "
        f"CI95 median(b)-median(a)=[{r.median_diff_ci_low:.2f}, {r.median_diff_ci_high:.2f}]"
    )


def main() -> None:
    # Console Windows mặc định cp1252 — in UTF-8 để chữ Việt / ký tự đặc biệt không làm script lỗi;
    # đặt trước argparse vì `--help` in `__doc__` tiếng Việt
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    conn = sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    result = compute_reach(conn)
    tiers, posts, insights = result.tiers, result.posts, result.insights
    ages = [curve[-1][0] for curve in result.curves]  # tuổi tại snapshot mới nhất
    print(f"measurable root posts n={len(posts)} (excluded_no_views={result.excluded_no_views})")
    if len(posts) < MIN_POSTS:
        print(f"Cần ít nhất {MIN_POSTS} bài đo được — dừng.")
        return

    # Độ chín: đường tăng views của các bài đủ điều kiện
    eligible = [
        c
        for c in result.curves
        if c[0][0] < CURVE_FIRST_SNAPSHOT_MAX_DAYS and c[-1][0] >= CURVE_SETTLED_MIN_DAYS
    ]
    times = [t for c in eligible if (t := time_to_share(c)) is not None]
    m = tiers.maturity
    days = "—" if m.days is None else f"{m.days:.1f}"
    print(f"maturity: P90 time-to-90% = {days} days (n_curves={m.n_curves})")
    if times:
        print(f"  time-to-90%: median={statistics.median(times):.1f}d max={max(times):.1f}d")
    for day in CURVE_CHECK_DAYS:
        shares = [
            [v for a, v in c if a <= day][-1] / c[-1][1]
            for c in eligible
            if any(a <= day for a, _ in c)
        ]
        if shares:
            print(f"  at {day}d: median share of latest views={statistics.median(shares):.2f}")

    print(f"tiered n={tiers.n_tiered} insufficient_data={tiers.insufficient_data}")
    print(
        f"P50 relative reach = {_num(tiers.p50_ratio, '.2f')}x  "
        f"P80 = {_num(tiers.p80_ratio, '.2f')}x"
    )
    print(
        f"raw views at P50 = {_num(tiers.p50_views, ',.0f')}  P80 = {_num(tiers.p80_views, ',.0f')}"
    )
    by_status: dict[str, list[int]] = {}
    for i, status in enumerate(tiers.statuses):
        by_status.setdefault(status, []).append(i)
    for name, idx in sorted(by_status.items()):
        med_age = statistics.median(ages[i] for i in idx)
        print(f"  {name}: {len(idx)} (median age {med_age:.0f}d)")

    views = [item.views for item in insights]
    # Đối chứng: nếu xếp theo views thô toàn lịch sử, tuổi bài lệch hẳn giữa các tầng
    raw50, raw80 = (statistics.quantiles(views, n=100, method="inclusive")[q - 1] for q in (50, 80))
    raw_top_age = statistics.median(a for v, a in zip(views, ages, strict=True) if v >= raw80)
    raw_low_age = statistics.median(a for v, a in zip(views, ages, strict=True) if v < raw50)
    print(
        f"raw-views tiers (all n={len(views)}): P50={raw50:,.0f} P80={raw80:,.0f}, median age "
        f">=P80 {raw_top_age:.0f}d vs <P50 {raw_low_age:.0f}d"
    )
    raw = spearmanr(views, ages)
    print(f"Spearman(raw views, age) rho={raw.statistic:.2f} p={raw.pvalue:.2g} n={len(views)}")
    tiered = [i for i, s in enumerate(tiers.statuses) if s in TIERED_STATUSES]
    if len(tiered) >= MIN_POSTS:
        adj = spearmanr([tiers.ratios[i] for i in tiered], [ages[i] for i in tiered])
        print(
            f"Spearman(relative reach, age) rho={adj.statistic:.2f} p={adj.pvalue:.2g} "
            f"n={len(tiered)}"
        )

    # Reach và engagement rate là hai chiều khác nhau: so engagement rate giữa các tầng
    er = {s: [insights[i].engagement_rate for i in by_status.get(s, [])] for s in by_status}
    below = er.get("below_median", [])
    pairs = [("top_20 vs below_median", "top_20"), ("above_median vs below_median", "above_median")]
    tested: list[tuple[str, float]] = []
    for label, tier in pairs:
        r = compare_groups(er.get(tier, []), below, random_seed=SEED)
        print(_fmt_compare(f"engagement {label}", r))
        if r.p_value is not None and not math.isnan(r.p_value):  # NaN: mọi giá trị bằng nhau
            tested.append((label, r.p_value))
    # Holm cho họ các phép so ở trên
    for (label, _), p_holm in zip(tested, holm_adjust([p for _, p in tested]), strict=True):
        print(f"  p Holm ({len(tested)} comparisons) {label} = {p_holm:.3g}")

    top = {posts[i].id for i in by_status.get("top_20", [])}
    raw_cut = tiers.p80_views
    raw_top = {posts[i].id for i in tiered if raw_cut is not None and views[i] >= raw_cut}
    print(
        f"top_20 relative={len(top)} vs raw-views top 20% (same pool)={len(raw_top)}, "
        f"overlap={len(top & raw_top)}"
    )
    for window in SENSITIVITY_WINDOWS:
        if window == BASELINE_WINDOW:
            continue
        alt = compute_reach(conn, window=window, min_prior=BASELINE_MIN_PRIOR).tiers
        alt_top = {posts[i].id for i, s in enumerate(alt.statuses) if s == "top_20"}
        print(
            f"window={window} (min_prior={BASELINE_MIN_PRIOR}): top_20 n={len(alt_top)}, "
            f"overlap with window={BASELINE_WINDOW}: {len(alt_top & top)}/{len(top)}"
        )

    # Hạn chế đã biết (Thy giữ 20 bài, 2026-10-07): mốc trải nhiều tháng khi kênh đăng thưa,
    # và các bài đầu kênh chỉ có 10–19 bài trước (mốc neo vào bài đầu tiên)
    spans = baseline_spans([post.timestamp for post in posts])
    tiered_spans = [span for i in tiered if (span := spans[i]) is not None]
    long_span = [
        i for i in tiered if (span := spans[i]) is not None and span > BASELINE_SPAN_REVIEW_DAYS
    ]
    if tiered_spans:
        print(
            f"baseline span (up to {BASELINE_WINDOW} prior posts): "
            f"median {statistics.median(tiered_spans):.0f}d, max {max(tiered_spans):.0f}d; "
            f"tiered posts with span > {BASELINE_SPAN_REVIEW_DAYS}d: "
            f"{len(long_span)}/{len(tiered)} "
            f"(top_20 among them: {sum(1 for i in long_span if tiers.statuses[i] == 'top_20')}, "
            f"with fewer than {BASELINE_WINDOW} prior posts: "
            f"{sum(1 for i in long_span if i < BASELINE_WINDOW)})"
        )
    if long_span:
        starts = [posts[baseline_start_index(i)].timestamp.date() for i in long_span]
        print(
            f"  those posts were published {posts[long_span[0]].timestamp.date()} to "
            f"{posts[long_span[-1]].timestamp.date()}; their baselines start "
            f"{min(starts)} to {max(starts)}"
        )


if __name__ == "__main__":
    main()
