import math
import random
import statistics

import numpy as np
import pytest
from scipy import stats as scipy_stats

from src.analysis.engagement import MIN_N_PER_BUCKET
from src.analysis.significance import (
    _brunner_munzel_rows,
    _studentize,
    brunner_munzel_asymptotic,
    brunner_munzel_permutation,
    compare_groups,
    holm_adjust,
)


def test_holm_adjust_matches_hand_computation_and_keeps_input_order() -> None:
    # p xếp tăng: 0.01×3 = 0.03, 0.03×2 = 0.06, 0.04×1 = 0.04 → giữ đơn điệu = 0.06
    assert holm_adjust([0.04, 0.01, 0.03]) == pytest.approx([0.06, 0.03, 0.06])


def test_holm_adjust_caps_at_one_and_handles_empty() -> None:
    assert holm_adjust([0.6, 0.7]) == [1.0, 1.0]
    assert holm_adjust([]) == []


def test_holm_adjust_ties_get_the_same_adjusted_value() -> None:
    # Khớp statsmodels multipletests(method="holm")
    assert holm_adjust([0.02, 0.01, 0.02, 0.5]) == pytest.approx([0.06, 0.04, 0.06, 0.5])


def test_holm_adjust_rejects_nan() -> None:
    with pytest.raises(ValueError):
        holm_adjust([0.04, float("nan"), 0.01])


def test_compare_groups_clear_difference_reports_significant_result() -> None:
    group_a = [float(x) for x in range(1, 11)]  # 1..10, median 5.5
    group_b = [float(x) for x in range(91, 101)]  # 91..100, median 95.5

    result = compare_groups(group_a, group_b, n_permutations=2_000, random_seed=0)

    assert result.median_a == 5.5
    assert result.median_b == 95.5
    assert result.n_a == 10
    assert result.n_b == 10
    assert result.insufficient_data is False
    assert result.p_value is not None
    assert result.p_value < 0.001
    # group_a always < group_b -> Cliff's delta must be exactly -1 (no pair overlaps).
    assert result.effect_size == -1.0
    # median_diff = median(b) - median(a) = 90 -> CI should not straddle 0.
    assert result.median_diff_ci_low is not None
    assert result.median_diff_ci_high is not None
    assert result.median_diff_ci_low > 0
    assert result.median_diff_ci_low < result.median_diff_ci_high


def test_compare_groups_identical_distributions_report_no_difference() -> None:
    group_a = [float(x) for x in range(1, 11)]
    group_b = [float(x) for x in range(1, 11)]

    result = compare_groups(group_a, group_b, n_permutations=2_000, random_seed=0)

    assert result.median_a == result.median_b == 5.5
    # Perfectly symmetric multisets -> Cliff's delta exactly 0 (equal pairs excluded).
    assert result.effect_size == 0.0
    assert result.p_value is not None
    assert result.p_value > 0.5
    assert result.insufficient_data is False


def test_compare_groups_flags_insufficient_data_below_min_n_per_bucket() -> None:
    group_a = [1.0, 2.0]  # n=2, below MIN_N_PER_BUCKET
    group_b = [float(x) for x in range(1, 11)]  # n=10

    result = compare_groups(group_a, group_b, n_permutations=2_000, random_seed=0)

    assert min(len(group_a), len(group_b)) < MIN_N_PER_BUCKET
    assert result.insufficient_data is True
    # Still computed (small n != undefined) — only the confidence flag differs.
    assert result.p_value is not None
    assert result.effect_size is not None


def test_compare_groups_empty_group_returns_none_stats_and_flags_insufficient_data() -> None:
    result = compare_groups([], [1.0, 2.0, 3.0], random_seed=0)

    assert result.n_a == 0
    assert result.median_a == 0.0
    assert result.p_value is None
    assert result.effect_size is None
    assert result.median_diff_ci_low is None
    assert result.median_diff_ci_high is None
    assert result.insufficient_data is True


def test_compare_groups_bootstrap_ci_is_reproducible_with_same_seed() -> None:
    group_a = [1.0, 3.0, 5.0, 7.0, 9.0, 2.0]
    group_b = [4.0, 6.0, 8.0, 10.0, 12.0, 5.0]

    result_1 = compare_groups(group_a, group_b, n_permutations=500, random_seed=42)
    result_2 = compare_groups(group_a, group_b, n_permutations=500, random_seed=42)

    assert result_1.median_diff_ci_low == result_2.median_diff_ci_low
    assert result_1.median_diff_ci_high == result_2.median_diff_ci_high


def _skewed_groups(seed: int, n_a: int, n_b: int) -> tuple[list[float], list[float]]:
    """2 nhóm lệch phải có giá trị trùng (làm tròn 1 chữ số) — giống rate thật của kênh."""
    rng = np.random.default_rng(seed)
    a = [float(x) for x in np.round(rng.gamma(2.0, 1.0, n_a), 1)]
    b = [float(x) for x in np.round(rng.gamma(2.0, 1.3, n_b), 1)]
    return a, b


@pytest.mark.parametrize("seed", range(8))
def test_brunner_munzel_asymptotic_matches_scipy(seed: int) -> None:
    group_a, group_b = _skewed_groups(seed, 8, 40)

    result = brunner_munzel_asymptotic(group_a, group_b)
    expected = scipy_stats.brunnermunzel(group_a, group_b)

    assert result is not None
    assert result.p_value == pytest.approx(float(expected.pvalue), rel=1e-9)
    assert result.delta == pytest.approx(
        compare_groups(group_a, group_b, n_permutations=100).effect_size
    )


@pytest.mark.parametrize("seed", range(4))
def test_compare_groups_uses_the_permutation_test_and_keeps_mann_whitney_for_sensitivity(
    seed: int,
) -> None:
    group_a, group_b = _skewed_groups(seed, 8, 40)

    result = compare_groups(group_a, group_b, n_permutations=5_000, random_seed=3)
    permutation = brunner_munzel_permutation(group_a, group_b, n_permutations=5_000, random_seed=3)

    assert permutation is not None
    assert result.test_method == "brunner_munzel_permutation"
    assert result.p_value == permutation.p_value
    assert result.effect_size_ci_low == permutation.delta_ci_low
    assert result.effect_size_ci_high == permutation.delta_ci_high
    assert result.p_value_mann_whitney == pytest.approx(
        float(scipy_stats.mannwhitneyu(group_a, group_b).pvalue)
    )


@pytest.mark.parametrize("seed", range(40))
def test_compare_groups_effect_size_ci_excludes_zero_when_p_below_alpha(seed: int) -> None:
    """CI của delta và p cùng 1 phân phối hoán vị (phân vị 2.5/97.5 ↔ 2 × đuôi nhỏ hơn) — CI loại
    trừ 0 ⇔ p < 0.05, trừ sát ngưỡng (phân vị nội suy và hiệu chỉnh +1 lệch nhau 1 bậc rời rạc)."""
    group_a, group_b = _skewed_groups(seed, 6 + seed % 7, 60)

    result = compare_groups(group_a, group_b, n_permutations=5_000, random_seed=0)

    assert result.p_value is not None
    assert result.effect_size_ci_low is not None
    assert result.effect_size_ci_high is not None
    if abs(result.p_value - 0.05) > 0.01:
        excludes_zero = result.effect_size_ci_low > 0 or result.effect_size_ci_high < 0
        assert excludes_zero == (result.p_value < 0.05)


@pytest.mark.parametrize("seed", range(40))
def test_brunner_munzel_asymptotic_ci_excludes_zero_exactly_when_p_below_alpha(seed: int) -> None:
    """Bản xấp xỉ t: CI và p cùng SE, cùng bậc tự do → tương đương chính xác."""
    group_a, group_b = _skewed_groups(seed, 6 + seed % 7, 60)

    result = brunner_munzel_asymptotic(group_a, group_b)

    assert result is not None
    assert result.delta_ci_low is not None
    assert result.delta_ci_high is not None
    excludes_zero = result.delta_ci_low > 0 or result.delta_ci_high < 0
    assert excludes_zero == (result.p_value < 0.05)


@pytest.mark.parametrize("seed", range(5))
def test_compare_groups_effect_size_ci_brackets_cliffs_delta(seed: int) -> None:
    group_a, group_b = _skewed_groups(seed, 10, 30)

    result = compare_groups(group_a, group_b, n_permutations=5_000, random_seed=0)

    assert result.effect_size is not None
    assert result.effect_size_ci_low is not None
    assert result.effect_size_ci_high is not None
    assert -1.0 <= result.effect_size_ci_low <= result.effect_size
    assert result.effect_size <= result.effect_size_ci_high <= 1.0


def test_compare_groups_complete_separation_gets_a_permutation_p_without_ci() -> None:
    # Mọi cặp cùng chiều → SE = 0: p hoán vị vẫn xác định (chính xác 2 / C(10, 5)), CI thì không.
    result = compare_groups(
        [1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 11.0, 12.0, 13.0, 14.0], random_seed=0
    )

    assert result.effect_size == -1.0
    assert result.test_method == "brunner_munzel_permutation"
    assert result.p_value == pytest.approx(2 / 252, abs=0.002)
    assert result.effect_size_ci_low is None
    assert result.effect_size_ci_high is None


def test_compare_groups_falls_back_to_mann_whitney_with_a_single_post() -> None:
    result = compare_groups([1.0], [2.0, 3.0, 4.0])

    assert result.test_method == "mann_whitney"
    assert result.insufficient_data is True
    assert result.effect_size_ci_low is None


def test_compare_groups_all_values_tied_give_p_one() -> None:
    # Mọi hoán vị cho cùng T = 0 → không có gì để phân biệt
    result = compare_groups([2.0] * 6, [2.0] * 6, n_permutations=1_000, random_seed=0)

    assert result.effect_size == 0.0
    assert result.test_method == "brunner_munzel_permutation"
    assert result.p_value == 1.0


def test_compare_groups_empty_group_has_no_test_method() -> None:
    result = compare_groups([1.0, 2.0], [])

    assert result.test_method is None
    assert result.p_value_mann_whitney is None
    assert result.effect_size_ci_low is None
    assert result.effect_size_ci_high is None


def test_compare_groups_median_ci_keeps_the_original_bootstrap() -> None:
    """CI chênh median vẫn là bootstrap percentile gốc (rút b trước a) — cùng seed phải ra đúng
    số cũ để số liệu ADR-0012 về CI median sinh lại không đổi."""
    group_a = [0.4, 1.9, 2.2, 2.8, 3.1, 1.2, 0.7]
    group_b = [1.5, 2.0, 2.6, 3.3, 4.0, 2.4, 1.1, 2.9]
    rng = random.Random(3)
    diffs = sorted(
        statistics.median(rng.choices(group_b, k=len(group_b)))
        - statistics.median(rng.choices(group_a, k=len(group_a)))
        for _ in range(1000)
    )

    result = compare_groups(group_a, group_b, n_permutations=500, random_seed=3)

    assert result.median_diff_ci_low == diffs[25]
    assert result.median_diff_ci_high == diffs[975]


def test_brunner_munzel_permutation_matches_scipy_permutation_test() -> None:
    group_a, group_b = _skewed_groups(3, 8, 60)

    result = brunner_munzel_permutation(group_a, group_b, n_permutations=20_000, random_seed=0)
    reference = scipy_stats.permutation_test(
        (group_a, group_b),
        lambda x, y, axis: scipy_stats.brunnermunzel(x, y, axis=axis).statistic,
        vectorized=True,
        n_resamples=20_000,
        random_state=0,
    )

    assert result is not None
    # 2 lần hoán vị ngẫu nhiên độc lập — sai số Monte Carlo ~0.004 ở p ~0.1
    assert result.p_value == pytest.approx(float(reference.pvalue), abs=0.02)
    assert result.delta == pytest.approx(
        compare_groups(group_a, group_b, n_permutations=100).effect_size
    )


def test_brunner_munzel_permutation_is_reproducible_with_a_seed() -> None:
    group_a, group_b = _skewed_groups(4, 6, 30)

    first = brunner_munzel_permutation(group_a, group_b, n_permutations=2_000, random_seed=7)
    second = brunner_munzel_permutation(group_a, group_b, n_permutations=2_000, random_seed=7)

    assert first == second


def test_brunner_munzel_permutation_handles_complete_separation_without_fallback() -> None:
    # p chính xác của hoán vị khi 5 vs 5 tách hẳn = 2 / C(10, 5) = 2/252
    result = brunner_munzel_permutation(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [10.0, 11.0, 12.0, 13.0, 14.0],
        n_permutations=20_000,
        random_seed=0,
    )

    assert result is not None
    assert result.delta == -1.0
    assert result.p_value == pytest.approx(2 / 252, abs=0.003)
    assert result.delta_ci_low is None
    assert result.delta_ci_high is None


@pytest.mark.parametrize("seed", range(6))
def test_brunner_munzel_permutation_ci_brackets_delta(seed: int) -> None:
    group_a, group_b = _skewed_groups(seed, 9, 50)

    result = brunner_munzel_permutation(group_a, group_b, n_permutations=5_000, random_seed=0)

    assert result is not None
    assert result.delta_ci_low is not None
    assert result.delta_ci_high is not None
    assert -1.0 <= result.delta_ci_low <= result.delta <= result.delta_ci_high <= 1.0


def test_brunner_munzel_permutation_rejects_tiny_groups_and_nan() -> None:
    assert brunner_munzel_permutation([1.0], [2.0, 3.0, 4.0]) is None
    assert brunner_munzel_permutation([1.0, math.nan, 3.0], [2.0, 3.0, 4.0]) is None


def test_compare_groups_nan_input_gives_no_fake_ci() -> None:
    """NaN làm phương sai NaN; trước đây `max(-1, nan)` trả CI [−1, 1] giả (review ADR-0023)."""
    result = compare_groups([1.0, math.nan, 3.0, 4.0, 5.0], [2.0, 3.0, 6.0, 7.0, 8.0])

    assert result.test_method == "mann_whitney"
    assert result.effect_size_ci_low is None
    assert result.effect_size_ci_high is None


def test_brunner_munzel_permutation_counts_floating_point_ties_as_ties() -> None:
    """Review ADR-0023: hoán vị cho cùng tập giá trị với T quan sát (topic toàn số 0) có T* lệch
    ~1e-15 vì thứ tự cộng khác; không có dung sai thì chúng bị đếm sót và p nhỏ hơn thật. Dữ liệu
    nhiều số 0 như share_rate. Đối chiếu với cách đếm "bằng nhau trong 1e-9" trên đúng các hoán vị
    engine dùng (cùng seed, 1 lô vì 4.000 < `_PERMUTATION_CHUNK`)."""
    rng = np.random.default_rng(11)
    topic = [0.0] * 6
    rest = [0.0] * 50 + [float(x) for x in np.round(rng.gamma(2.0, 0.05, 90), 3)]
    a, b = np.asarray(topic), np.asarray(rest)
    p_hat, se = _brunner_munzel_rows(a[None, :], b[None, :])
    observed = float(_studentize(p_hat, se)[0])
    pooled = np.concatenate([a, b])
    shuffled = np.random.default_rng(5).permuted(
        np.broadcast_to(pooled, (4_000, len(pooled))), axis=1
    )
    t_star = _studentize(*_brunner_munzel_rows(shuffled[:, :6], shuffled[:, 6:]))
    # dữ liệu phải thật sự có T* "bằng" T nhưng khác ở chữ số cuối — nếu không, test không kiểm gì
    assert np.count_nonzero(np.abs(t_star - observed) < 1e-9) > np.count_nonzero(t_star == observed)
    upper = (np.count_nonzero(t_star >= observed - 1e-9) + 1) / 4_001
    lower = (np.count_nonzero(t_star <= observed + 1e-9) + 1) / 4_001

    result = brunner_munzel_permutation(topic, rest, n_permutations=4_000, random_seed=5)

    assert result is not None
    assert result.p_value == pytest.approx(min(1.0, 2 * min(upper, lower)))


def test_brunner_munzel_permutation_tiny_groups_give_finite_ci_bounds() -> None:
    """2 vs 3: nhiều hoán vị tách hẳn (T* = ±inf) → phân vị vô hạn/NaN → cận CI là ±1, không NaN."""
    result = brunner_munzel_permutation(
        [1.0, 4.0], [2.0, 3.0, 5.0], n_permutations=2_000, random_seed=0
    )

    assert result is not None
    assert result.delta_ci_low is not None
    assert result.delta_ci_high is not None
    assert math.isfinite(result.delta_ci_low)
    assert math.isfinite(result.delta_ci_high)
    assert -1.0 <= result.delta_ci_low <= result.delta <= result.delta_ci_high <= 1.0


def test_brunner_munzel_permutation_rejects_zero_permutations() -> None:
    with pytest.raises(ValueError):
        brunner_munzel_permutation([1.0, 2.0], [3.0, 4.0], n_permutations=0)
