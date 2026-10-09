"""Layer 4 — engine thống kê suy diễn DÙNG CHUNG cho mọi so sánh 2 nhóm trong dự
án: topic vs phần còn lại của kênh (ADR-0023), tầng reach vs phần còn lại (ADR-0012),
có/không author reply event (`topic_affinity.py`), theo giờ/thứ — tránh viết lặp lại
kiểm định + effect size + CI ở từng chỗ. Đây là tầng 5 "Narrative Layering Principle"
(suy diễn thống kê), xem docs/claude/data-model.md — PHẢI đi sau tầng 3/4 (central
tendency + percentile), không đứng một mình.

Phương pháp (ADR-0023, thay bộ Mann-Whitney + bootstrap port từ `vunderkind/threads-analytics`).
Câu hỏi luôn là "bài nhóm A có xu hướng cao hơn bài nhóm B không" — Cliff's delta =
P(A > B) − P(A < B); H0: delta = 0. So trên dữ liệu kênh bằng mô phỏng
(`scripts/topic_method_report.py` mục 5), ở ngưỡng 0.05 VÀ ở ngưỡng chặt nhất của Holm:
- **Mann-Whitney** suy phương sai từ công thức, giả định 2 nhóm cùng phân phối: topic phân tán gấp
  đôi kênh → báo động giả ~13% thay vì 5%; topic đồng đều hơn → gần như không phát hiện được gì.
- **Brunner-Munzel xấp xỉ t** (Brunner & Munzel 2000) ước lượng phương sai từ dữ liệu (không cần
  cùng độ phân tán) nhưng phân phối t sai ở vùng đuôi khi mẫu nhỏ: ở ngưỡng 0.05/27 báo động giả
  gấp 2–10 lần với topic 4–13 bài — cam kết của Holm không giữ được.
- **Brunner-Munzel hoán vị có chuẩn hoá** (Neubert & Brunner 2007) — ĐƯỢC CHỌN: cùng thống kê,
  nhưng phân phối tham chiếu dựng bằng cách xáo nhãn nhóm → ở ngưỡng Holm không vượt mức đạt được
  ngoài sai số Monte Carlo, trừ khi topic rất nhỏ (n = 5) VÀ phân tán hơn kênh; ở 0.05 có 2 ô mô
  phỏng vượt, 1 ô chưa rõ nguyên nhân; bảo thủ (mất power) khi topic đồng đều hơn kênh
  (ADR-0023). CI của delta lấy từ cùng phân phối hoán vị (Pauly, Asendorf & Konietschke 2016).
Mann-Whitney vẫn tính (`p_value_mann_whitney`) làm phân tích độ nhạy; bản xấp xỉ t giữ ở
`brunner_munzel_asymptotic` để báo cáo đặt 3 cách cạnh nhau.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import stats as scipy_stats

from src.analysis.engagement import MIN_N_PER_BUCKET

# Số lần resample cho bootstrap CI chênh median — mượn từ vunderkind/threads-analytics.
DEFAULT_N_RESAMPLES = 1000
_ALPHA = 0.05  # CI 95%, kiểm định 2 phía
# Số lần hoán vị mặc định: p nhỏ nhất phân giải được = 2/(B+1) ≈ 2e-5, dưới xa ngưỡng chặt nhất của
# Holm 27 (0.05/27 ≈ 0.00185). p = 2 × đuôi nhỏ hơn q = p/2 → sai số Monte Carlo của p =
# 2·sqrt(q(1−q)/B): ở p = 0.002 là ≈ 0.0002.
DEFAULT_N_PERMUTATIONS = 100_000
_PERMUTATION_CHUNK = 5_000  # số hoán vị mỗi lô — giới hạn bộ nhớ (lô × n phần tử float64)

TestMethod = Literal["brunner_munzel_permutation", "mann_whitney"]


@dataclass(frozen=True)
class ComparisonResult:
    """Kết quả so sánh 2 nhóm số liệu độc lập (VD: engagement_rate của 1 topic vs phần còn
    lại của kênh, share_rate của bài "Top 20% reach" vs phần còn lại).

    `p_value` 2 phía của kiểm định ghi ở `test_method`:
    - `brunner_munzel_permutation` (mặc định, `n_permutations` lần hoán vị);
    - `mann_whitney` CHỈ khi bản hoán vị không chạy được: 1 nhóm có < 2 phần tử (phương sai cần
      n − 1) hoặc đầu vào có NaN (khi đó p Mann-Whitney cũng NaN, `effect_size` vẫn tính trên
      phần còn lại — người gọi loại khỏi họ Holm). Mọi giá trị bằng nhau → p hoán vị = 1.
    `p_value`, `test_method`, `effect_size` là None CHỈ khi 1 nhóm rỗng.

    `effect_size` là Cliff's delta trong [-1, 1]: dương nghĩa bài `group_a` có xu hướng lớn hơn
    bài `group_b` (Romano et al. 2006: |δ| < 0.147 negligible, < 0.33 small, < 0.474 medium,
    còn lại large — ngưỡng tham khảo, KHÔNG gắn nhãn ở đây, tầng diễn giải tự quyết).

    `effect_size_ci_low/high`: CI 95% của delta từ cùng phân phối hoán vị — None khi không có bản
    hoán vị hoặc khi sai số chuẩn quan sát = 0 (2 nhóm tách hẳn). CHƯA hiệu chỉnh nhiều phép so
    (Holm chỉ hiệu chỉnh p) — UI ghi "unadjusted".

    `median_diff_ci_low/high`: bootstrap percentile CI 95% (`DEFAULT_N_RESAMPLES` resample) của
    `median(group_b) − median(group_a)` — chiều B trừ A. Chỉ để MÔ TẢ, không dùng để kết luận:
    chênh median là đại lượng khác delta (CI loại trừ 0 không đồng nghĩa kiểm định có ý nghĩa), và
    bootstrap percentile chưa được kiểm độ phủ cho chênh median ở mẫu nhỏ — cùng cách đó áp cho
    CHÍNH delta báo động giả 8.4% ở n = 8 thay vì 5% (ADR-0023, `scripts/topic_method_report.py`
    mục 5c).

    `insufficient_data=True` khi `min(n_a, n_b) < MIN_N_PER_BUCKET` (1 nguồn sự thật cho "mẫu
    quá nhỏ để diễn giải" xuyên suốt dự án) — số liệu vẫn tính đủ, tầng diễn giải không kết luận.
    """

    median_a: float
    median_b: float
    n_a: int
    n_b: int
    p_value: float | None
    test_method: TestMethod | None
    p_value_mann_whitney: float | None
    effect_size: float | None
    effect_size_ci_low: float | None
    effect_size_ci_high: float | None
    median_diff_ci_low: float | None
    median_diff_ci_high: float | None
    insufficient_data: bool


@dataclass(frozen=True)
class BrunnerMunzelResult:
    """p 2 phía, Cliff's delta và CI 95% của delta từ 1 cách tính Brunner-Munzel."""

    p_value: float
    delta: float
    delta_ci_low: float | None
    delta_ci_high: float | None


def compare_groups(
    group_a: list[float],
    group_b: list[float],
    *,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    random_seed: int | None = None,
) -> ComparisonResult:
    """So sánh 2 nhóm số liệu độc lập — xem `ComparisonResult` cho ý nghĩa từng field.
    `random_seed` cố định CẢ hoán vị lẫn bootstrap CI chênh median — bắt buộc khi số liệu cần tái
    lập (script, API); `None` → mỗi lần gọi p dao động trong sai số Monte Carlo."""
    n_a, n_b = len(group_a), len(group_b)
    median_a = statistics.median(group_a) if group_a else 0.0
    median_b = statistics.median(group_b) if group_b else 0.0
    insufficient_data = min(n_a, n_b) < MIN_N_PER_BUCKET

    if n_a == 0 or n_b == 0:
        # Không kiểm định / effect size nào định nghĩa được trên tập rỗng — khác
        # `insufficient_data` (mẫu nhỏ nhưng khác 0 vẫn tính được).
        return ComparisonResult(
            median_a=median_a,
            median_b=median_b,
            n_a=n_a,
            n_b=n_b,
            p_value=None,
            test_method=None,
            p_value_mann_whitney=None,
            effect_size=None,
            effect_size_ci_low=None,
            effect_size_ci_high=None,
            median_diff_ci_low=None,
            median_diff_ci_high=None,
            insufficient_data=True,
        )

    p_mann_whitney = float(
        scipy_stats.mannwhitneyu(group_a, group_b, alternative="two-sided").pvalue
    )
    permutation = brunner_munzel_permutation(
        group_a, group_b, n_permutations=n_permutations, random_seed=random_seed
    )
    ci_low, ci_high = _bootstrap_median_diff_ci(
        group_a, group_b, n_resamples=n_resamples, random_seed=random_seed
    )
    return ComparisonResult(
        median_a=median_a,
        median_b=median_b,
        n_a=n_a,
        n_b=n_b,
        p_value=permutation.p_value if permutation else p_mann_whitney,
        test_method="brunner_munzel_permutation" if permutation else "mann_whitney",
        p_value_mann_whitney=p_mann_whitney,
        effect_size=_cliffs_delta(group_a, group_b),
        effect_size_ci_low=permutation.delta_ci_low if permutation else None,
        effect_size_ci_high=permutation.delta_ci_high if permutation else None,
        median_diff_ci_low=ci_low,
        median_diff_ci_high=ci_high,
        insufficient_data=insufficient_data,
    )


def holm_adjust(p_values: list[float]) -> list[float]:
    """Hiệu chỉnh Holm (step-down) cho 1 họ phép so — trả p đã hiệu chỉnh, CÙNG thứ tự đầu vào.

    p thứ k (xếp tăng dần, k từ 0) nhân (m − k), giữ đơn điệu không giảm, chặn ở 1.0. Kiểm soát
    FWER (xác suất có ≥ 1 kết luận sai trong cả họ) mà không giả định các phép so độc lập.
    p = NaN (nhánh dự phòng Mann-Whitney khi mọi giá trị bằng nhau hoặc đầu vào có NaN) làm thứ
    tự sắp không xác định → người gọi loại khỏi họ trước; hàm báo lỗi thay vì trả số sai.
    """
    if any(math.isnan(p) for p in p_values):
        raise ValueError("holm_adjust không nhận p = NaN — loại phép so đó khỏi họ trước")
    m = len(p_values)
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(sorted(range(m), key=lambda i: p_values[i])):
        running = max(running, min(1.0, p_values[index] * (m - rank)))
        adjusted[index] = running
    return adjusted


def brunner_munzel_asymptotic(
    group_a: list[float], group_b: list[float]
) -> BrunnerMunzelResult | None:
    """Brunner & Munzel (2000), xấp xỉ t bậc tự do Satterthwaite — trả p 2 phía, delta và CI
    95% của delta; None khi không xác định (1 nhóm < 2 phần tử, sai số chuẩn = 0, hoặc NaN).
    KHÔNG dùng để kết luận (ADR-0023: sai ở vùng đuôi khi mẫu nhỏ) — giữ để báo cáo so sánh.

    p̂ = P(B > A) + ½P(B = A) = (mean hạng của B trong mẫu gộp − (n_b + 1)/2) / n_a. Phương sai
    ước lượng từ "placement" (hạng trong mẫu gộp trừ hạng trong chính nhóm). Hạng trung bình cho
    giá trị bằng nhau (midrank) nên chịu được nhiều số 0 của share_rate. Delta(a, b) = 1 − 2p̂.
    Thống kê và p khớp `scipy.stats.brunnermunzel` (test giữ điều này); tự tính để lấy được SE
    và bậc tự do cho CI."""
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return None
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    ranks = scipy_stats.rankdata(np.concatenate([a, b]))
    ranks_a, ranks_b = ranks[:n_a], ranks[n_a:]
    placement_a = ranks_a - scipy_stats.rankdata(a)
    placement_b = ranks_b - scipy_stats.rankdata(b)
    p_hat = (float(ranks_b.mean()) - (n_b + 1) / 2) / n_a
    var_a = float(((placement_a - placement_a.mean()) ** 2).sum()) / (n_a - 1) / n_b**2
    var_b = float(((placement_b - placement_b.mean()) ** 2).sum()) / (n_b - 1) / n_a**2
    variance = var_a / n_a + var_b / n_b
    # NaN trong đầu vào làm variance NaN — `max/min` với NaN sẽ trả CI [−1, 1] giả, nên từ chối
    if not math.isfinite(variance) or variance <= 0:
        return None
    se = math.sqrt(variance)
    df = variance**2 / ((var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1))
    statistic = (p_hat - 0.5) / se
    p_value = float(2 * scipy_stats.t.sf(abs(statistic), df))
    half_width = float(scipy_stats.t.ppf(1 - _ALPHA / 2, df)) * se
    return BrunnerMunzelResult(
        p_value=p_value,
        delta=1 - 2 * p_hat,
        delta_ci_low=max(-1.0, 1 - 2 * (p_hat + half_width)),
        delta_ci_high=min(1.0, 1 - 2 * (p_hat - half_width)),
    )


def brunner_munzel_permutation(
    group_a: list[float],
    group_b: list[float],
    *,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    random_seed: int | None = None,
) -> BrunnerMunzelResult | None:
    """Brunner-Munzel hoán vị có chuẩn hoá (Neubert & Brunner 2007): phân phối tham chiếu của
    T = (p̂ − ½) / SE dựng bằng cách xáo nhãn nhóm `n_permutations` lần, mỗi lần tính lại CẢ p̂
    lẫn SE (chuẩn hoá lại — điều làm nó vẫn đúng khi 2 nhóm khác độ phân tán, khác hoán vị thô).
    Thay cho xấp xỉ t ở mẫu nhỏ: xấp xỉ t báo động giả gấp 2–10 lần ở ngưỡng 0.05/27 với topic
    4–13 bài (ADR-0023).

    - p 2 phía = 2 × min(tỉ lệ T* ≥ T, tỉ lệ T* ≤ T), có hiệu chỉnh +1 (không bao giờ trả 0).
    - CI 95% của delta theo Pauly, Asendorf & Konietschke (2016): đảo T bằng phân vị 2.5/97.5 của
      T* thay cho phân vị t — CI và p cùng 1 phân phối tham chiếu. None khi SE quan sát = 0 (2
      nhóm tách hẳn hoặc mọi giá trị bằng nhau); p hoán vị vẫn xác định trong trường hợp đó.
    - None khi 1 nhóm < 2 phần tử hoặc đầu vào có NaN.
    - Cùng tập giá trị + cùng seed → cùng p và CI, bất kể thứ tự phần tử trong mỗi nhóm.
    - So T* với T quan sát có dung sai dấu phẩy động (quy ước của `scipy.stats.permutation_test`):
      cùng 1 tập giá trị khác thứ tự cho T lệch ~1e-15, không có dung sai thì hoán vị "bằng" T
      bị đếm sót và p nhỏ hơn thật — rõ nhất khi nhiều số 0 (share_rate, conversation).
    """
    if n_permutations < 1:
        raise ValueError("n_permutations phải ≥ 1")
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return None
    # Sắp xếp mỗi nhóm: hoán vị thứ k của `rng` xáo VỊ TRÍ trong mảng gộp, nên cùng seed nhưng
    # khác thứ tự đầu vào (VD SQL không có ORDER BY) cho tập T* khác → p/CI lệch trong sai số
    # Monte Carlo (đo 2026-10-09: tới 0.008 giữa job và script báo cáo). Sắp xếp → kết quả chỉ
    # phụ thuộc tập giá trị + seed; p̂ và SE vốn không phụ thuộc thứ tự.
    a = np.sort(np.asarray(group_a, dtype=float))
    b = np.sort(np.asarray(group_b, dtype=float))
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return None
    p_hat, se = _brunner_munzel_rows(a[None, :], b[None, :])
    observed = float(_studentize(p_hat, se)[0])
    rng = np.random.default_rng(random_seed)
    pooled = np.concatenate([a, b])
    stats: list[np.ndarray] = []
    remaining = n_permutations
    while remaining > 0:
        size = min(_PERMUTATION_CHUNK, remaining)
        shuffled = rng.permuted(np.broadcast_to(pooled, (size, n_a + n_b)), axis=1)
        perm_p, perm_se = _brunner_munzel_rows(shuffled[:, :n_a], shuffled[:, n_a:])
        stats.append(_studentize(perm_p, perm_se))
        remaining -= size
    t_star = np.concatenate(stats)
    tolerance = abs(np.finfo(float).eps * 100 * observed) if math.isfinite(observed) else 0.0
    upper = (np.count_nonzero(t_star >= observed - tolerance) + 1) / (n_permutations + 1)
    lower = (np.count_nonzero(t_star <= observed + tolerance) + 1) / (n_permutations + 1)
    p_value = float(min(1.0, 2 * min(upper, lower)))
    delta = 1 - 2 * float(p_hat[0])
    if float(se[0]) <= 0:
        return BrunnerMunzelResult(p_value, delta, None, None)
    with np.errstate(
        invalid="ignore"
    ):  # inf − inf khi nội suy giữa 2 phân vị vô hạn → NaN, xử lý dưới
        q_low, q_high = (float(q) for q in np.quantile(t_star, [_ALPHA / 2, 1 - _ALPHA / 2]))
    # θ ∈ [p̂ − q_high·SE, p̂ − q_low·SE] (θ = P(B > A) + ½ ties) → delta = 1 − 2θ. Nhóm rất nhỏ
    # có thể có ≥ 2.5% hoán vị tách hẳn (T* = ±inf) → phân vị ±inf/NaN → cận đó là ±1 (hết thang)
    se_obs = float(se[0])
    low = delta + 2 * q_low * se_obs if math.isfinite(q_low) else -1.0
    high = delta + 2 * q_high * se_obs if math.isfinite(q_high) else 1.0
    return BrunnerMunzelResult(
        p_value=p_value,
        delta=delta,
        delta_ci_low=max(-1.0, low),
        delta_ci_high=min(1.0, high),
    )


def _brunner_munzel_rows(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """p̂ và SE Brunner-Munzel cho từng hàng (mỗi hàng 1 cặp nhóm) — cùng công thức
    `brunner_munzel_asymptotic`, vector hoá để tính hàng chục nghìn hoán vị."""
    n_a, n_b = a.shape[1], b.shape[1]
    ranks = scipy_stats.rankdata(np.concatenate([a, b], axis=1), axis=1)
    ranks_a, ranks_b = ranks[:, :n_a], ranks[:, n_a:]
    placement_a = ranks_a - scipy_stats.rankdata(a, axis=1)
    placement_b = ranks_b - scipy_stats.rankdata(b, axis=1)
    p_hat = (ranks_b.mean(axis=1) - (n_b + 1) / 2) / n_a
    var_a = placement_a.var(axis=1, ddof=1) / n_b**2
    var_b = placement_b.var(axis=1, ddof=1) / n_a**2
    return p_hat, np.sqrt(var_a / n_a + var_b / n_b)


def _studentize(p_hat: np.ndarray, se: np.ndarray) -> np.ndarray:
    """T = (p̂ − ½)/SE; SE = 0 (tách hẳn / mọi giá trị trùng) → ±inf theo dấu p̂ − ½, hoặc 0."""
    diff = p_hat - 0.5
    with np.errstate(divide="ignore", invalid="ignore"):
        t = diff / se
    degenerate = np.where(diff > 0, np.inf, np.where(diff < 0, -np.inf, 0.0))
    return np.where(se > 0, t, degenerate)


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
    làm CI 95% — "percentile bootstrap". Chỉ dùng để mô tả (xem `ComparisonResult`)."""
    rng = random.Random(random_seed)
    diffs = [
        statistics.median(rng.choices(group_b, k=len(group_b)))
        - statistics.median(rng.choices(group_a, k=len(group_a)))
        for _ in range(n_resamples)
    ]
    diffs.sort()
    low_index = int((_ALPHA / 2) * n_resamples)
    high_index = min(int((1 - _ALPHA / 2) * n_resamples), n_resamples - 1)
    return diffs[low_index], diffs[high_index]
