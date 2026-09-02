from src.analysis.freshness import freshness_weight


def test_freshness_weight_age_zero_is_full_weight() -> None:
    assert freshness_weight(0.0) == 1.0


def test_freshness_weight_at_grace_boundary_is_still_full_weight() -> None:
    # age_hours == grace_hours phải nằm trong nhánh "<=" -> vẫn 1.0, không rơi vào decay.
    assert freshness_weight(12.0, grace_hours=12.0, half_life_hours=48.0) == 1.0


def test_freshness_weight_just_past_grace_boundary_starts_decaying() -> None:
    just_past = freshness_weight(12.0001, grace_hours=12.0, half_life_hours=48.0)
    assert just_past < 1.0


def test_freshness_weight_one_half_life_after_grace_is_half() -> None:
    # age = grace + half_life -> đúng 1 half-life sau grace period -> weight = 0.5
    weight = freshness_weight(12.0 + 48.0, grace_hours=12.0, half_life_hours=48.0)
    assert weight == 0.5


def test_freshness_weight_two_half_lives_after_grace_is_quarter() -> None:
    weight = freshness_weight(12.0 + 96.0, grace_hours=12.0, half_life_hours=48.0)
    assert abs(weight - 0.25) < 1e-9


def test_freshness_weight_very_large_age_approaches_zero() -> None:
    weight = freshness_weight(100_000.0, grace_hours=12.0, half_life_hours=48.0)
    assert 0.0 <= weight < 1e-6


def test_freshness_weight_negative_age_is_clamped_to_zero_and_full_weight() -> None:
    # age_hours âm (VD lỗi đồng bộ giờ) phải clamp về 0.0, không raise, không âm.
    assert freshness_weight(-5.0) == 1.0


def test_freshness_weight_default_grace_and_half_life_hours() -> None:
    assert freshness_weight(6.0) == 1.0  # trong grace period mặc định (12h)
    half = freshness_weight(12.0 + 48.0)  # 1 half-life mặc định (48h) sau grace mặc định (12h)
    assert half == 0.5


def test_freshness_weight_custom_grace_and_half_life_are_respected() -> None:
    assert freshness_weight(5.0, grace_hours=5.0, half_life_hours=10.0) == 1.0
    assert freshness_weight(15.0, grace_hours=5.0, half_life_hours=10.0) == 0.5
