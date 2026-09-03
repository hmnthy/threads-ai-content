"""Layer 4 — engine thống kê suy diễn DÙNG CHUNG cho mọi so sánh 2 nhóm trong dự
án: viral vs non-viral (`virality.py`), có/không author reply event
(`topic_affinity.py`), topic vs topic, theo giờ/thứ (`engagement.py`) — tránh
viết lặp lại Mann-Whitney U + effect size + bootstrap CI ở từng chỗ. Đây là tầng
5 "Narrative Layering Principle" (suy diễn thống kê), xem docs/claude/data-model.md
— PHẢI đi sau tầng 3/4 (central tendency + percentile), không đứng một mình.

Bộ 3 kiểm định (Mann-Whitney U + Cliff's delta + bootstrap CI 95%) port từ
`vunderkind/threads-analytics` (xem docs/research/market-scan-2026-09.html) —
Mann-Whitney U được chọn thay t-test vì KHÔNG giả định phân phối chuẩn (engagement
rate trên Threads lệch phải mạnh, có outlier viral — đúng lý do median thắng mean
ở Layer 2), Cliff's delta là effect size non-parametric tương ứng.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from scipy import stats as scipy_stats

from src.analysis.engagement import MIN_N_PER_BUCKET

# Số lần resample cho bootstrap CI — mượn từ vunderkind/threads-analytics.
DEFAULT_N_RESAMPLES = 1000
_BOOTSTRAP_ALPHA = 0.05  # 95% CI


@dataclass(frozen=True)
class ComparisonResult:
    """Kết quả so sánh 2 nhóm số liệu độc lập (VD virality_index của post viral
    vs non-viral, engagement_rate của giờ A vs giờ B).

    `p_value`/`effect_size`/`median_diff_ci_*` là `None` CHỈ khi 1 trong 2 nhóm
    rỗng (Mann-Whitney U không định nghĩa được trên tập rỗng — khác hẳn trường hợp
    `insufficient_data`, vẫn tính đủ số liệu, chỉ đánh dấu độ tin cậy thấp).

    `effect_size` là Cliff's delta, khoảng [-1, 1]: dương nghĩa `group_a` có xu
    hướng lớn hơn `group_b`, âm nghĩa ngược lại, 0 nghĩa không có xu hướng rõ
    (Romano et al. 2006: |δ|<0.147 negligible, <0.33 small, <0.474 medium, else
    large — ngưỡng tham khảo, KHÔNG hardcode thành nhãn ở đây, để tầng diễn giải
    tự quyết định theo ngữ cảnh).

    `median_diff_ci_low/high` là bootstrap CI 95% (`DEFAULT_N_RESAMPLES` resample)
    trên `median(group_b) - median(group_a)` — chênh lệch B trừ A, CÙNG CHIỀU với
    cách đọc "group_b cao hơn group_a bao nhiêu". Khoảng này KHÔNG chứa 0 là dấu
    hiệu chênh lệch median đáng tin (tương đương ý nghĩa của p_value < 0.05, nhìn
    từ góc độ khoảng tin cậy thay vì kiểm định giả thuyết).

    `insufficient_data=True` khi `min(n_a, n_b) < MIN_N_PER_BUCKET` (dùng LẠI
    đúng ngưỡng của `engagement.py` — 1 nguồn sự thật cho "mẫu quá nhỏ để diễn
    giải" xuyên suốt dự án, không định nghĩa lại ở mỗi module) — số liệu vẫn được
    tính đầy đủ, chỉ là tầng diễn giải (tầng 6) phải tôn trọng cờ này, không tuyên
    bố kết luận chắc chắn từ mẫu quá nhỏ.
    """

    median_a: float
    median_b: float
    n_a: int
    n_b: int
    p_value: float | None
    effect_size: float | None
    median_diff_ci_low: float | None
    median_diff_ci_high: float | None
    insufficient_data: bool


def compare_groups(
    group_a: list[float],
    group_b: list[float],
    *,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    random_seed: int | None = None,
) -> ComparisonResult:
    """So sánh 2 nhóm số liệu độc lập — xem `ComparisonResult` cho ý nghĩa từng
    field. `random_seed` chỉ dùng để test tái lập bootstrap CI xác định; để
    `None` (mặc định) cho dùng thật — bootstrap resample ngẫu nhiên mỗi lần gọi
    là đúng bản chất phương pháp, không cần cố định.
    """
    n_a, n_b = len(group_a), len(group_b)
    median_a = statistics.median(group_a) if group_a else 0.0
    median_b = statistics.median(group_b) if group_b else 0.0
    insufficient_data = min(n_a, n_b) < MIN_N_PER_BUCKET

    if n_a == 0 or n_b == 0:
        # Mann-Whitney U/Cliff's delta/bootstrap không định nghĩa được trên tập
        # rỗng — khác `insufficient_data` (mẫu nhỏ nhưng khác 0 vẫn tính được).
        return ComparisonResult(
            median_a=median_a,
            median_b=median_b,
            n_a=n_a,
            n_b=n_b,
            p_value=None,
            effect_size=None,
            median_diff_ci_low=None,
            median_diff_ci_high=None,
            insufficient_data=True,
        )

    p_value = float(scipy_stats.mannwhitneyu(group_a, group_b, alternative="two-sided").pvalue)
    effect_size = _cliffs_delta(group_a, group_b)
    ci_low, ci_high = _bootstrap_median_diff_ci(
        group_a, group_b, n_resamples=n_resamples, random_seed=random_seed
    )

    return ComparisonResult(
        median_a=median_a,
        median_b=median_b,
        n_a=n_a,
        n_b=n_b,
        p_value=p_value,
        effect_size=effect_size,
        median_diff_ci_low=ci_low,
        median_diff_ci_high=ci_high,
        insufficient_data=insufficient_data,
    )


def _cliffs_delta(group_a: list[float], group_b: list[float]) -> float:
    """(#{x in group_a > y in group_b} - #{x < y}) / (n_a * n_b) — cặp bằng nhau
    không tính vào cả 2 phía (đúng định nghĩa gốc Cliff's delta), nên 2 nhóm
    giống hệt nhau (cùng multiset giá trị) cho delta = 0 chính xác."""
    n_a, n_b = len(group_a), len(group_b)
    more = sum(1 for x in group_a for y in group_b if x > y)
    less = sum(1 for x in group_a for y in group_b if x < y)
    return (more - less) / (n_a * n_b)


def _bootstrap_median_diff_ci(
    group_a: list[float],
    group_b: list[float],
    *,
    n_resamples: int,
    random_seed: int | None,
) -> tuple[float, float]:
    """Bootstrap phân phối `median(resample_b) - median(resample_a)` bằng resample
    có hoàn lại (mỗi resample giữ nguyên n_a/n_b gốc), rồi lấy percentile 2.5/97.5
    làm CI 95% — chuẩn "percentile bootstrap", đơn giản và đủ dùng cho quy mô dữ
    liệu dự án (không cần bias-corrected/BCa)."""
    rng = random.Random(random_seed)
    diffs = [
        statistics.median(rng.choices(group_b, k=len(group_b)))
        - statistics.median(rng.choices(group_a, k=len(group_a)))
        for _ in range(n_resamples)
    ]
    diffs.sort()
    low_index = int((_BOOTSTRAP_ALPHA / 2) * n_resamples)
    high_index = min(int((1 - _BOOTSTRAP_ALPHA / 2) * n_resamples), n_resamples - 1)
    return diffs[low_index], diffs[high_index]
