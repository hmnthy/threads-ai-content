import pytest

from src.analysis.reach import (
    MaturityEstimate,
    assign_reach_tiers,
    estimate_maturity,
    relative_reach,
    time_to_share,
)

MATURE = MaturityEstimate(days=4.0, n_curves=7)


def test_time_to_share_returns_first_age_reaching_ninety_percent_of_latest() -> None:
    curve = [(0.2, 100), (1.0, 850), (2.0, 920), (20.0, 1000)]
    assert time_to_share(curve) == 2.0


def test_time_to_share_none_for_empty_or_zero_views() -> None:
    assert time_to_share([]) is None
    assert time_to_share([(0.5, 0), (15.0, 0)]) is None


def test_estimate_maturity_uses_only_curves_seen_early_and_settled() -> None:
    early_settled = [(0.5, 10), (3.0, 95), (15.0, 100)]  # đạt 90% ở ngày 3
    first_seen_late = [(2.0, 50), (30.0, 100)]  # snapshot đầu sau 24 h — loại
    not_settled = [(0.5, 10), (5.0, 100)]  # snapshot cuối < 14 ngày — loại
    estimate = estimate_maturity([early_settled, first_seen_late, not_settled])
    assert estimate == MaturityEstimate(days=3.0, n_curves=1)


def test_estimate_maturity_none_without_eligible_curves() -> None:
    assert estimate_maturity([[(2.0, 50), (30.0, 100)]]) == MaturityEstimate(None, 0)


def test_relative_reach_needs_min_prior_posts_and_uses_previous_window_median() -> None:
    baselines, ratios = relative_reach([10, 20, 30, 40, 100], window=3, min_prior=2)
    assert baselines == [None, None, 15.0, 20.0, 30.0]
    assert ratios == [None, None, 2.0, 2.0, pytest.approx(100 / 30)]


def test_relative_reach_corrects_channel_growth() -> None:
    # Kênh tăng gấp 10 lần: bài mới views thô cao hơn nhưng không vượt mức bình thường lúc đăng.
    views = [100] * 5 + [1000] * 5
    _, ratios = relative_reach(views, window=5, min_prior=5)
    assert ratios[5] == 10.0  # bài đầu tiên của giai đoạn mới — vượt hẳn mốc cũ
    assert ratios[-1] == 1.0  # khi mốc đã bắt kịp tăng trưởng, bài bình thường = 1.0


def test_assign_reach_tiers_statuses_follow_priority_and_percentiles() -> None:
    views = [100, 100, 100, 100, 50, 100, 150, 300, 400, 1000]
    ages = [100.0] * 9 + [1.0]  # bài cuối chưa chín
    tiers = assign_reach_tiers(views, ages, MATURE, window=4, min_prior=4)
    assert tiers.statuses[:4] == ["no_baseline"] * 4
    assert tiers.statuses[-1] == "still_growing"
    assert tiers.n_tiered == 5  # bài 5..9, trừ bài chưa chín
    assert tiers.statuses.count("top_20") == 1
    assert tiers.statuses[8] == "top_20"  # ratio cao nhất trong nhóm đã chín
    assert tiers.statuses[4] == "below_median"
    assert tiers.insufficient_data is False  # n_tiered = MIN_N_PER_BUCKET = 5


def test_assign_reach_tiers_boundary_is_inclusive() -> None:
    # Nhóm đã chín có ratio [1, 1, 1, 1, 1] → P50 = P80 = 1 → mọi bài đạt ≥ P80.
    views = [100] * 9
    tiers = assign_reach_tiers(views, [100.0] * 9, MATURE, window=4, min_prior=4)
    assert tiers.statuses[4:] == ["top_20"] * 5


def test_assign_reach_tiers_maturity_unknown_tiers_nothing() -> None:
    tiers = assign_reach_tiers(
        [100] * 6, [100.0] * 6, MaturityEstimate(None, 0), window=2, min_prior=2
    )
    assert tiers.statuses == ["no_baseline"] * 2 + ["maturity_unknown"] * 4
    assert tiers.n_tiered == 0
    assert tiers.p80_ratio is None and tiers.p80_views is None
    assert tiers.insufficient_data is True


def test_assign_reach_tiers_reports_raw_views_reference_on_same_pool() -> None:
    views = [100, 100, 200, 400, 800]
    tiers = assign_reach_tiers(views, [100.0] * 5, MATURE, window=2, min_prior=2)
    # Nhóm được xếp tầng = 3 bài cuối (200, 400, 800) → P50 views thô = 400.
    assert tiers.p50_views == 400.0


def test_assign_reach_tiers_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        assign_reach_tiers([1, 2], [1.0], MATURE)


def test_relative_reach_rejects_unmeasurable_posts() -> None:
    # views = 0 là insight thiếu (ADR-0011) và có thể làm median mốc bằng 0
    with pytest.raises(ValueError):
        relative_reach([0, 0, 0, 10], window=3, min_prior=2)


def test_estimate_maturity_is_interpolated_p90_over_eligible_curves() -> None:
    # 5 đường cong đạt 90% ở ngày 1, 2, 3, 4, 5 → P90 nội suy tuyến tính = 4.6
    curves = [[(0.1, 10), (float(d), 95), (20.0, 100)] for d in range(1, 6)]
    estimate = estimate_maturity(curves)
    assert estimate.days == pytest.approx(4.6)
    assert estimate.n_curves == 5
