"""Số liệu của ADR-0023 (vai trò 3 trang + phương pháp so sánh topic) — sinh lại được từ DB thật,
chỉ đọc. Mọi con số ADR-0023 trích "sinh lại bằng script" đều in ở đây.

Chạy: `uv run python -m scripts.topic_method_report` (mặc định `data/threads.db` của thư mục hiện
tại; `--db` để trỏ DB khác). Mọi mô phỏng/hoán vị dùng seed cố định → in lại ra đúng số cũ.
Mục 5 (hiệu chuẩn bản hoán vị) tốn ~15–20 phút; cả script ~25 phút.

Ba phương pháp được đặt CẠNH NHAU ở mọi mục (cùng câu hỏi: bài của topic có xu hướng cao hơn bài
phần còn lại không — Cliff's delta = P(topic > rest) − P(topic < rest)):
- MW: Mann-Whitney U (phương sai theo công thức, giả định 2 nhóm cùng phân phối);
- BM-t: Brunner-Munzel, xấp xỉ t (phương sai ước lượng từ dữ liệu) — `brunner_munzel_asymptotic()`;
- BM-perm: Brunner-Munzel hoán vị có chuẩn hoá — engine `compare_groups()` (ADR-0023 chọn).

In theo thứ tự đọc của ADR:
1. Mẫu số — lần gom cụm mới nhất (unit có embedding) và bài gốc đo được (mục 7–8).
2. 27 phép so trên dữ liệu thật: delta, p của 3 phương pháp, CI của delta (BM-t, BM-perm); kết luận
   theo phương pháp × họ Holm (27 = cả trang Topics, 9 = chỉ engagement như panel landing).
3. Độ nhạy theo nhóm so sánh: phần còn lại bỏ nhiễu; so với 1 con số median kênh (Wilcoxon).
4. Độ phân tán: IQR topic ÷ IQR phần còn lại — điều kiện làm MW sai.
5. Tỉ lệ báo động giả khi KHÔNG có khác biệt thật, ở 2 ngưỡng: 0.05 và bước chặt nhất của Holm
   (0.05/27): (a) 2 nhóm rút từ cùng phân phối thật; (b) cùng xu hướng nhưng khác độ phân tán
   (bài toán Behrens-Fisher); (c) CI bootstrap percentile của delta (phương án đã loại).
6. Sức mạnh thống kê: delta nhỏ nhất phát hiện được với power 80% theo cỡ topic.
7. Độ nhiễu của tỉ lệ theo views + sàn P25 + số bài dưới sàn trong top-10 mỗi chỉ số.
8. Mean vs median: độ lệch phân phối, số bài dưới mean.
9. Tên topic: lý do trong lịch sử tên, số lần chạy liên tiếp giữ tên.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy import stats as scipy_stats

from src.analysis.conversation import conversation_rate
from src.analysis.engagement import MIN_N_PER_BUCKET
from src.analysis.share_rate import share_rate
from src.analysis.significance import (
    DEFAULT_N_PERMUTATIONS,
    BrunnerMunzelResult,
    ComparisonResult,
    brunner_munzel_asymptotic,
    brunner_munzel_permutation,
    compare_groups,
    holm_adjust,
)
from src.analysis.stats import split_measurable
from src.api.models import PostInsights
from src.db.schema import DEFAULT_DB_PATH, latest_cluster_run
from src.main import _load_posts_with_insights, _load_root_posts_with_insights
from src.nlp.topic_identity import runs_keeping_label

SEED = 0  # mọi mô phỏng, hoán vị và bootstrap — cố định để số in ra lặp lại được
ALPHA = 0.05
TARGET_POWER = 0.8  # quy ước Cohen (1988) cho "đủ sức phát hiện"
TOPIC_FAMILY = 27  # 9 topic × 3 chỉ số — bước chặt nhất của Holm là ALPHA / 27
LANDING_FAMILY_METRIC = "engagement"  # panel topic trên landing chỉ hiện engagement (họ 9)
# Mô phỏng tiệm cận (MW, BM-t) rẻ: 40.000 lần cho sai số Monte Carlo ở ngưỡng 0.05/27 ≈ 0.0002
N_SIMULATIONS = 40_000
# Bản hoán vị đắt (mỗi lần mô phỏng = N_SIM_PERMUTATIONS lần hoán vị) → ít lần hơn; 2.000 hoán vị
# cho p phân giải 0.001 (< 0.00185) — đủ để phân biệt "đúng mức" với "gấp 3 lần"
N_SIM_PERM_RUNS = 4_000
N_SIM_PERMUTATIONS = 2_000
N_SIMULATIONS_BOOTSTRAP = 1_000
# Hoán vị cho 27 phép so thật (mục 2–3) — mặc định của engine, đặt tên riêng để test thu nhỏ
N_REPORT_PERMUTATIONS = DEFAULT_N_PERMUTATIONS
N_BOOTSTRAP = 1_000
# Lưới dịch chuyển (điểm %) khi tìm hiệu ứng nhỏ nhất phát hiện được — đủ rộng để power tới ~1 ở
# n = MIN_N_PER_BUCKET trên phân phối engagement thật (IQR ~1 điểm %).
SHIFT_GRID = tuple(round(0.05 * k, 2) for k in range(0, 61))
# Tỉ lệ độ lệch chuẩn topic ÷ phần còn lại cho mô phỏng Behrens-Fisher: một nửa, bằng, gấp đôi —
# bao khoảng IQR topic ÷ phần còn lại đo được trên data thật (mục 4).
SPREAD_RATIOS = (0.5, 1.0, 2.0)
SIMULATED_TOPIC_SIZES = (5, 8, 12)
PERM_CHECK_SIZES = (5, 12)  # bản hoán vị: chỉ 2 cỡ (đắt) — nhỏ nhất và lớn nhất thường gặp
TOP_N = 10  # bảng top của `/analytics/overview` (`ANALYTICS_TOP_N`)

Metric = Callable[[PostInsights], float]
METRICS: dict[str, Metric] = {
    "engagement": lambda item: item.engagement_rate,
    "share_rate": share_rate,
    "conversation": conversation_rate,
}
METHODS = ("MW", "BM-t", "BM-perm")


@dataclass(frozen=True)
class TopicTest:
    topic_id: str
    metric: str
    result: ComparisonResult  # engine: BM-perm (+ p MW để đối chiếu)
    asymptotic: BrunnerMunzelResult | None  # BM-t, chỉ để so sánh

    def p_of(self, method: str) -> float | None:
        if method == "MW":
            return self.result.p_value_mann_whitney
        if method == "BM-t":
            return None if self.asymptotic is None else self.asymptotic.p_value
        return self.result.p_value


def population_delta(values: Sequence[float], shift: float) -> float:
    """Cliff's delta của phân phối `values` dịch lên `shift` so với chính nó —
    mean(sign(x + shift − y)) trên mọi cặp. Là delta "thật" ứng với 1 hiệu ứng dịch vị trí, dùng để
    đổi lưới shift sang thang delta trong bảng sức mạnh thống kê."""
    arr = np.asarray(values, dtype=float)
    return float(np.sign(np.subtract.outer(arr + shift, arr)).mean())


def rejection_rate(p_values: NDArray[np.float64], alpha: float = ALPHA) -> float:
    """Tỉ lệ p < alpha; p = NaN (mọi giá trị trùng nhau) tính là không bác bỏ."""
    return float(np.mean(np.nan_to_num(p_values, nan=1.0) < alpha))


def asymptotic_p_values(
    topic: NDArray[np.float64], rest: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """p theo lô (mỗi hàng 1 lần mô phỏng) của BM-t và MW. BM-t không xác định khi 2 nhóm tách hẳn
    (sai số chuẩn 0, scipy trả NaN) → lấy p MW cho hàng đó, để hàng không bị đếm nhầm là "không bác
    bỏ" (cách xử lý cũ của engine trước bản hoán vị). Trả (p BM-t, p MW)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        brunner_munzel = scipy_stats.brunnermunzel(topic, rest, axis=1).pvalue
    mann_whitney = scipy_stats.mannwhitneyu(topic, rest, axis=1).pvalue
    return np.where(np.isnan(brunner_munzel), mann_whitney, brunner_munzel), mann_whitney


def asymptotic_rates(
    topic: NDArray[np.float64], rest: NDArray[np.float64], alphas: Sequence[float]
) -> dict[str, list[float]]:
    """Tỉ lệ bác bỏ của MW và BM-t ở từng ngưỡng trong `alphas`."""
    bm_t, mw = asymptotic_p_values(topic, rest)
    return {
        "MW": [rejection_rate(mw, a) for a in alphas],
        "BM-t": [rejection_rate(bm_t, a) for a in alphas],
    }


def permutation_rates(
    topic: NDArray[np.float64], rest: NDArray[np.float64], alphas: Sequence[float], *, seed: int
) -> list[float]:
    """Tỉ lệ bác bỏ của BM-perm ở từng ngưỡng, mỗi hàng 1 lần mô phỏng với `N_SIM_PERMUTATIONS`."""
    p_values = []
    for row, (t, r) in enumerate(zip(topic, rest, strict=True)):
        result = brunner_munzel_permutation(
            t.tolist(), r.tolist(), n_permutations=N_SIM_PERMUTATIONS, random_seed=seed + row
        )
        p_values.append(math.nan if result is None else result.p_value)
    arr = np.asarray(p_values)
    return [rejection_rate(arr, a) for a in alphas]


def attainable_level(alpha: float, n_permutations: int) -> float:
    """Tỉ lệ báo động giả thật sự đạt được của 1 kiểm định hoán vị có p = 2·k/(B+1) (k = số hoán vị
    ở đuôi nhỏ hơn + 1) khi 2 nhóm cùng phân phối: p < alpha ⇔ k ≤ k_max = ⌈alpha(B+1)/2⌉ − 1, và
    P(k ≤ k_max) = 2·k_max/(B+1). VD B = 2.000, alpha = 0.05/27 → chỉ k = 1 đạt → 0.10%, không phải
    0.185% (review ADR-0023)."""
    k_max = math.ceil(alpha * (n_permutations + 1) / 2) - 1
    return 2 * k_max / (n_permutations + 1)


def null_from_values(
    values: Sequence[float], n_topic: int, n_simulations: int, seed: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Topic và phần còn lại cùng rút có hoàn lại từ phân phối thật — không có khác biệt thật."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    return rng.choice(arr, (n_simulations, n_topic)), rng.choice(
        arr, (n_simulations, len(arr) - n_topic)
    )


def null_behrens_fisher(
    spread_ratio: float, n_topic: int, n_total: int, n_simulations: int, seed: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """2 nhóm cùng phân phối chuẩn tâm 0 — P(topic > rest) = P(topic < rest), delta thật = 0 —
    nhưng độ lệch chuẩn của topic gấp `spread_ratio` lần phần còn lại."""
    rng = np.random.default_rng(seed)
    return (
        rng.normal(0.0, spread_ratio, (n_simulations, n_topic)),
        rng.normal(0.0, 1.0, (n_simulations, n_total - n_topic)),
    )


def null_percentile_ci_rate(
    values: Sequence[float], n_topic: int, *, n_simulations: int, n_bootstrap: int, seed: int
) -> float:
    """Tỉ lệ CI bootstrap percentile 95% của Cliff's delta loại trừ 0 khi không có khác biệt thật
    (phương án 1g ban đầu, đã loại)."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    n_rest = len(arr) - n_topic
    excluded = 0
    for _ in range(n_simulations):
        topic = rng.choice(arr, n_topic)
        rest = rng.choice(arr, n_rest)
        boot_topic = topic[rng.integers(0, n_topic, (n_bootstrap, n_topic))]
        boot_rest = rest[rng.integers(0, n_rest, (n_bootstrap, n_rest))]
        deltas = np.sign(boot_topic[:, :, None] - boot_rest[:, None, :]).mean(axis=(1, 2))
        low, high = np.percentile(deltas, [2.5, 97.5])
        excluded += bool(low > 0 or high < 0)
    return excluded / n_simulations


def detectable_deltas(
    values: Sequence[float], n_topic: int, alpha: float, *, n_simulations: int, seed: int
) -> dict[str, float | None]:
    """Delta nhỏ nhất (theo `population_delta`) mà MW và BM-t phát hiện với xác suất ≥
    `TARGET_POWER` khi nhóm topic n_topic bài (rút từ phân phối thật, dịch lên `shift`) so với phần
    còn lại. Mô hình dịch vị trí giữ nguyên độ phân tán → MW đúng mức ở đây; BM-t dễ dãi ở ngưỡng
    chặt nên power của nó LẠC QUAN. None khi cả lưới chưa đạt."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    n_rest = len(arr) - n_topic
    found: dict[str, float | None] = {"MW": None, "BM-t": None}
    for shift in SHIFT_GRID:
        topic = rng.choice(arr, (n_simulations, n_topic)) + shift
        rest = rng.choice(arr, (n_simulations, n_rest))
        bm_t, mw = asymptotic_p_values(topic, rest)
        for method, p_values in (("MW", mw), ("BM-t", bm_t)):
            if found[method] is None and rejection_rate(p_values, alpha) >= TARGET_POWER:
                found[method] = population_delta(values, shift)
        if all(v is not None for v in found.values()):
            break
    return found


def binomial_se_points(rate_pct: float, views: int) -> float:
    """Sai số chuẩn xấp xỉ (điểm %) của 1 tỉ lệ đo trên `views` lượt xem, coi mỗi lượt xem là 1 phép
    thử Bernoulli. Chỉ là xấp xỉ bậc độ lớn: 1 người có thể vừa like vừa reply, nên tương tác không
    phải phép thử độc lập."""
    p = rate_pct / 100
    return math.sqrt(p * (1 - p) / views) * 100


def holm_by_key(tests: Sequence[TopicTest], method: str) -> dict[tuple[str, str], float]:
    """p Holm (theo p của `method`) của mọi phép so có p xác định — không None/NaN, KỂ CẢ topic
    n < MIN_N_PER_BUCKET — trong 1 họ duy nhất."""
    keyed = [
        ((t.topic_id, t.metric), p)
        for t in tests
        if (p := t.p_of(method)) is not None and not math.isnan(p)
    ]
    adjusted = holm_adjust([p for _, p in keyed])
    return {key: value for (key, _), value in zip(keyed, adjusted, strict=True)}


def _fmt(value: float | None, spec: str = ".2f") -> str:
    return "—" if value is None else format(value, spec)


def _values(conn: sqlite3.Connection, ids: list[str], metric: Metric) -> tuple[list[float], int]:
    _, insights, excluded = split_measurable(*_load_posts_with_insights(conn, ids))
    return [metric(item) for item in insights], excluded


def _iqr(values: Sequence[float]) -> float:
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q3 - q1


def _rates_line(label: str, rates: dict[str, list[float]], alphas: Sequence[float]) -> str:
    cells = [
        f"{method} " + " / ".join(f"{rate:.2%}" for rate in values)
        for method, values in rates.items()
    ]
    thresholds = " / ".join(f"{a:.4g}" for a in alphas)
    return f"{label} [ngưỡng {thresholds}]: " + " · ".join(cells)


def main() -> None:
    # Console Windows mặc định cp1252 — in UTF-8 để chữ Việt / ký tự đặc biệt không làm script lỗi
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    run = latest_cluster_run(conn)
    if run is None:
        print("Chưa có lần gom cụm nào — không có gì để báo cáo.")
        return
    labels: dict[str, int] = json.loads(run["labels_json"])
    unit_ids = list(labels)
    noise_ids = [uid for uid, label in labels.items() if label == -1]
    topic_ids = [row["id"] for row in conn.execute("SELECT id FROM topics ORDER BY id")]
    members = {
        tid: [
            row["post_id"]
            for row in conn.execute(
                "SELECT post_id FROM post_topic_labels WHERE topic_id = ? AND method = 'cluster'",
                (tid,),
            )
        ]
        for tid in topic_ids
    }
    _, all_excluded = _values(conn, unit_ids, METRICS["engagement"])
    _, root_insights, root_excluded = split_measurable(*_load_root_posts_with_insights(conn))
    alphas = (ALPHA, ALPHA / TOPIC_FAMILY)

    print("=== 1. Mẫu số")
    print(
        f"Lần gom cụm mới nhất run_at={run['run_at']}: unit có embedding={len(unit_ids)} · "
        f"nhiễu={len(noise_ids)} ({len(noise_ids) / len(unit_ids):.1%}) · trong topic="
        f"{sum(map(len, members.values()))} · topic={len(topic_ids)} · loại vì views = 0: "
        f"{all_excluded}"
    )
    print(
        f"Bài gốc đo được (mục 5a, 7, 8): {len(root_insights)} · loại vì views = 0: "
        f"{root_excluded} "
        "(tập khác với unit có embedding — trùng số đếm là ngẫu nhiên)"
    )

    print("\n=== 2. 27 phép so trên dữ liệu thật: topic vs phần còn lại của kênh (gồm nhiễu)")
    print(
        "delta > 0 = bài của topic có xu hướng cao hơn. CI 95% của delta CHƯA hiệu chỉnh nhiều "
        "phép "
        f"so. BM-perm: {N_REPORT_PERMUTATIONS} hoán vị, seed {SEED}. Cờ n < {MIN_N_PER_BUCKET} = "
        "mẫu nhỏ."
    )
    tests: list[TopicTest] = []
    for metric_name, metric in METRICS.items():
        for tid in topic_ids:
            member_set = set(members[tid])
            topic_values, _ = _values(conn, members[tid], metric)
            rest_values, _ = _values(conn, [u for u in unit_ids if u not in member_set], metric)
            result = compare_groups(
                topic_values, rest_values, n_permutations=N_REPORT_PERMUTATIONS, random_seed=SEED
            )
            asymptotic = brunner_munzel_asymptotic(topic_values, rest_values)
            tests.append(TopicTest(tid, metric_name, result, asymptotic))
    for t in tests:
        r, asym = t.result, t.asymptotic
        print(
            f"{t.metric:<12} {t.topic_id:<9} n={r.n_a:>3} median={r.median_a:.3f}% vs "
            f"{r.median_b:.3f}% | delta={_fmt(r.effect_size, '+.2f')} | p MW="
            f"{_fmt(r.p_value_mann_whitney, '.2g')} BM-t="
            f"{_fmt(None if asym is None else asym.p_value, '.2g')} BM-perm="
            f"{_fmt(r.p_value, '.2g')} | CI BM-t "
            f"[{_fmt(None if asym is None else asym.delta_ci_low, '+.2f')}; "
            f"{_fmt(None if asym is None else asym.delta_ci_high, '+.2f')}] BM-perm "
            f"[{_fmt(r.effect_size_ci_low, '+.2f')}; {_fmt(r.effect_size_ci_high, '+.2f')}]"
            f"{' | mẫu nhỏ' if r.insufficient_data else ''}"
        )
    print(f"\nKết luận đạt p Holm < {ALPHA} — phương pháp × họ Holm:")
    for method in METHODS:
        family_27 = holm_by_key(tests, method)
        landing = [t for t in tests if t.metric == LANDING_FAMILY_METRIC]
        family_9 = holm_by_key(landing, method)
        passing_27 = sorted(k for k, p in family_27.items() if p < ALPHA)
        passing_9 = sorted(k for k, p in family_9.items() if p < ALPHA)
        landing_27 = [k for k in passing_27 if k[1] == LANDING_FAMILY_METRIC]
        print(f"{method:<8} họ {len(family_27)} (trang Topics): {passing_27}")
        print(
            f"{'':<8} họ {len(family_9)} (chỉ {LANDING_FAMILY_METRIC}, panel landing): {passing_9}"
        )
        disagree = sorted(set(passing_9) ^ set(landing_27))
        print(
            f"{'':<8} {LANDING_FAMILY_METRIC} kết luận khác nhau giữa 2 họ: {disagree or 'không'}"
        )
    # p Holm của MỌI phương pháp cho mọi phép so đạt ở ÍT NHẤT 1 phương pháp / 1 họ — để ADR trích
    # được cả số của phương pháp không đạt (VD MW 0.090) từ chính output này
    landing = [t for t in tests if t.metric == LANDING_FAMILY_METRIC]
    families = {
        method: (holm_by_key(tests, method), holm_by_key(landing, method)) for method in METHODS
    }
    keys = sorted(
        {k for f27, f9 in families.values() for k, p in (*f27.items(), *f9.items()) if p < ALPHA}
    )
    print("\np Holm của từng phương pháp (họ 27 / họ 9) cho mọi phép so đạt ở ít nhất 1 cách:")
    for key in keys:
        cells = " · ".join(
            f"{method} {_fmt(f27.get(key), '.4f')} / {_fmt(f9.get(key), '.4f')}"
            for method, (f27, f9) in families.items()
        )
        print(f"{key}: {cells}")

    print("\n=== 3. Độ nhạy theo nhóm so sánh (engagement, BM-perm)")
    engagement = METRICS["engagement"]
    channel_values, _ = _values(conn, unit_ids, engagement)
    channel_median = statistics.median(channel_values)
    for tid in topic_ids:
        member_set = set(members[tid])
        topic_values, _ = _values(conn, members[tid], engagement)
        clustered_rest = [u for u in unit_ids if u not in member_set and labels[u] != -1]
        no_noise = brunner_munzel_permutation(
            topic_values,
            _values(conn, clustered_rest, engagement)[0],
            n_permutations=N_REPORT_PERMUTATIONS,
            random_seed=SEED,
        )
        diffs = [v - channel_median for v in topic_values if v != channel_median]
        wilcoxon_p = float(scipy_stats.wilcoxon(diffs).pvalue) if diffs else None
        above = sum(v > channel_median for v in topic_values)
        print(
            f"{tid:<9} (ii) phần còn lại bỏ nhiễu: delta="
            f"{_fmt(None if no_noise is None else no_noise.delta, '+.2f')} p="
            f"{_fmt(None if no_noise is None else no_noise.p_value, '.2g')} | (iii) vs median kênh "
            f"{channel_median:.3f}%: {above}/{len(topic_values)} bài trên, Wilcoxon p="
            f"{_fmt(wilcoxon_p, '.3g')}"
        )

    print("\n=== 4. Độ phân tán: IQR topic ÷ IQR phần còn lại")
    for metric_name, metric in METRICS.items():
        ratios = []
        for tid in topic_ids:
            member_set = set(members[tid])
            topic_values, _ = _values(conn, members[tid], metric)
            rest_values, _ = _values(conn, [u for u in unit_ids if u not in member_set], metric)
            ratios.append(f"{tid}:{_iqr(topic_values) / _iqr(rest_values):.2f}")
        print(f"{metric_name:<12} {' '.join(ratios)}")

    print(
        f"\n=== 5. Tỉ lệ báo động giả khi không có khác biệt thật — đúng phải bằng chính ngưỡng "
        f"({ALPHA} và {ALPHA}/{TOPIC_FAMILY} = {ALPHA / TOPIC_FAMILY:.5f}); seed {SEED}"
    )
    print(
        f"MW, BM-t: {N_SIMULATIONS} mô phỏng/ô (sai số Monte Carlo ở 0.00185 ≈ ±0.02 điểm %). "
        f"BM-perm: {N_SIM_PERM_RUNS} mô phỏng × {N_SIM_PERMUTATIONS} hoán vị/ô — đắt nên chỉ "
        "vài ô. p hoán vị rời rạc theo bậc 2/(B+1) → mức chuẩn ĐẠT ĐƯỢC của cột BM-perm = "
        f"{attainable_level(ALPHA, N_SIM_PERMUTATIONS):.3%} / "
        f"{attainable_level(ALPHA / TOPIC_FAMILY, N_SIM_PERMUTATIONS):.3%} "
        "(so cột này với 2 số đó, không với 2 ngưỡng danh nghĩa)."
    )
    sizes = sorted({len(v) for v in members.values()} | {MIN_N_PER_BUCKET})
    for metric_name in ("engagement", "share_rate"):
        values = [METRICS[metric_name](item) for item in root_insights]
        for size in sizes:
            topic, rest = null_from_values(values, size, N_SIMULATIONS, SEED)
            rates = asymptotic_rates(topic, rest, alphas)
            if metric_name == "engagement" and size in PERM_CHECK_SIZES:
                topic, rest = null_from_values(values, size, N_SIM_PERM_RUNS, SEED)
                rates["BM-perm"] = permutation_rates(topic, rest, alphas, seed=SEED)
            print(
                _rates_line(
                    f"(a) cùng phân phối thật {metric_name:<10} n topic={size:>2}", rates, alphas
                )
            )
    for ratio in SPREAD_RATIOS:
        for size in SIMULATED_TOPIC_SIZES:
            topic, rest = null_behrens_fisher(ratio, size, len(unit_ids), N_SIMULATIONS, SEED)
            rates = asymptotic_rates(topic, rest, alphas)
            if ratio != 1.0 and size in PERM_CHECK_SIZES:
                topic, rest = null_behrens_fisher(ratio, size, len(unit_ids), N_SIM_PERM_RUNS, SEED)
                rates["BM-perm"] = permutation_rates(topic, rest, alphas, seed=SEED)
            print(
                _rates_line(
                    f"(b) độ lệch chuẩn topic ÷ phần còn lại = {ratio}, n topic={size:>2}",
                    rates,
                    alphas,
                )
            )
    for metric_name in ("engagement", "share_rate"):
        values = [METRICS[metric_name](item) for item in root_insights]
        for size in sizes:
            percentile = null_percentile_ci_rate(
                values,
                size,
                n_simulations=N_SIMULATIONS_BOOTSTRAP,
                n_bootstrap=N_BOOTSTRAP,
                seed=SEED,
            )
            print(
                f"(c) CI bootstrap percentile của delta loại trừ 0, {metric_name:<10} "
                f"n topic={size:>2}: "
                f"{percentile:.1%} ({N_SIMULATIONS_BOOTSTRAP} mô phỏng, ngưỡng 0.05)"
            )

    print(
        f"\n=== 6. Sức mạnh thống kê (engagement thật, {N_SIMULATIONS // 10} mô phỏng/ô, mô hình "
        "dịch vị trí)"
    )
    print(
        "MW đúng mức trong mô hình này (cùng độ phân tán); BM-t dễ dãi ở ngưỡng chặt nên power của "
        "nó lạc quan. BM-perm đúng mức → power gần MW."
    )
    for size in sizes:
        loose = detectable_deltas(
            channel_values, size, ALPHA, n_simulations=N_SIMULATIONS // 10, seed=SEED
        )
        strict = detectable_deltas(
            channel_values, size, ALPHA / TOPIC_FAMILY, n_simulations=N_SIMULATIONS // 10, seed=SEED
        )
        print(
            f"n topic={size:>2}: delta cần cho power {TARGET_POWER:.0%} — alpha {ALPHA}: MW "
            f"{_fmt(loose['MW'])} BM-t {_fmt(loose['BM-t'])} | alpha {ALPHA}/{TOPIC_FAMILY}: MW "
            f"{_fmt(strict['MW'])} BM-t {_fmt(strict['BM-t'])}"
        )

    print("\n=== 7. Độ nhiễu của tỉ lệ theo views (bài gốc đo được) + sàn views")
    views = np.array([item.views for item in root_insights])
    q1, q2, q3 = statistics.quantiles(views.tolist(), n=4, method="inclusive")
    floor = q1  # sàn views ADR-0023 (1f) = P25, cùng cách tính phân vị với IQR
    print(
        f"n={len(root_insights)} (loại views = 0: {root_excluded}) · views P25/P50/P75 = "
        f"{q1:.0f}/{q2:.0f}/{q3:.0f} (statistics.quantiles method='inclusive' = nội suy "
        "tuyến tính, cùng cách tính IQR của `distribution_stats`)"
    )
    bins = np.digitize(views, [q1, q2, q3])
    for k in range(4):
        group = [item for item, b in zip(root_insights, bins, strict=True) if b == k]
        eng = [item.engagement_rate for item in group]
        shares = [share_rate(item) for item in group]
        se = [binomial_se_points(item.engagement_rate, item.views) for item in group]
        print(
            f"Q{k + 1} views {min(i.views for i in group)}–{max(i.views for i in group)}: "
            f"n={len(group)} engagement median={statistics.median(eng):.2f}% "
            f"IQR={_iqr(eng):.2f} điểm % · SE nhị thức median={statistics.median(se):.2f} điểm % · "
            f"share_rate = 0: {sum(s == 0 for s in shares)}/{len(group)}"
        )
    rho = scipy_stats.spearmanr(views, [item.engagement_rate for item in root_insights])
    print(
        f"Spearman rho(views, engagement) = {rho.statistic:.2f} (p={rho.pvalue:.3g}) — chung "
        "mẫu số views, chỉ mô tả, không diễn giải cơ chế"
    )
    print(f"Sàn P25 = {floor:.0f} views")
    for metric_name, metric in METRICS.items():
        top = sorted(root_insights, key=metric, reverse=True)[:TOP_N]
        below = sum(item.views < floor for item in top)
        print(f"top-{TOP_N} {metric_name}: {below}/{TOP_N} bài dưới sàn")

    print("\n=== 8. Mean vs median (bài gốc đo được)")
    for metric_name, metric in METRICS.items():
        values = [metric(item) for item in root_insights]
        mean = statistics.mean(values)
        print(
            f"{metric_name:<12} median={statistics.median(values):.3f}% mean={mean:.3f}% "
            f"skewness={scipy_stats.skew(values):.2f} · bài dưới mean: "
            f"{sum(v < mean for v in values)}/{len(values)}"
        )

    print("\n=== 9. Tên topic (ADR-0018)")
    for row in conn.execute(
        "SELECT reason, COUNT(*) AS n, MIN(labeled_at) AS first, MAX(labeled_at) AS last "
        "FROM topic_label_history GROUP BY reason ORDER BY reason"
    ):
        print(
            f"lịch sử tên: lý do {row['reason']}: {row['n']} dòng ({row['first']} → {row['last']})"
        )
    events_by_run = [
        json.loads(row["topic_events_json"]) if row["topic_events_json"] else None
        for row in conn.execute("SELECT topic_events_json FROM cluster_runs ORDER BY id")
    ]
    for row in conn.execute("SELECT id, labeled_at FROM topics ORDER BY id"):
        print(
            f"{row['id']:<9} đặt tên {row['labeled_at']} · giữ tên qua "
            f"{runs_keeping_label(events_by_run, row['id'])} lần chạy liên tiếp gần nhất"
        )


if __name__ == "__main__":
    main()
