from src.analysis.engagement import MIN_N_PER_BUCKET
from src.analysis.significance import compare_groups


def test_compare_groups_clear_difference_reports_significant_result() -> None:
    group_a = [float(x) for x in range(1, 11)]  # 1..10, median 5.5
    group_b = [float(x) for x in range(91, 101)]  # 91..100, median 95.5

    result = compare_groups(group_a, group_b, random_seed=0)

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

    result = compare_groups(group_a, group_b, random_seed=0)

    assert result.median_a == result.median_b == 5.5
    # Perfectly symmetric multisets -> Cliff's delta exactly 0 (equal pairs excluded).
    assert result.effect_size == 0.0
    assert result.p_value is not None
    assert result.p_value > 0.5
    assert result.insufficient_data is False


def test_compare_groups_flags_insufficient_data_below_min_n_per_bucket() -> None:
    group_a = [1.0, 2.0]  # n=2, below MIN_N_PER_BUCKET
    group_b = [float(x) for x in range(1, 11)]  # n=10

    result = compare_groups(group_a, group_b, random_seed=0)

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

    result_1 = compare_groups(group_a, group_b, random_seed=42)
    result_2 = compare_groups(group_a, group_b, random_seed=42)

    assert result_1.median_diff_ci_low == result_2.median_diff_ci_low
    assert result_1.median_diff_ci_high == result_2.median_diff_ci_high
