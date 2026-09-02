from datetime import UTC, datetime, timedelta

import pytest

from src.analysis.velocity import amplification_velocity, view_velocity
from src.models.insight_snapshot import InsightSnapshot

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _snap(hours_after_t0: float, **overrides: int) -> InsightSnapshot:
    defaults: dict[str, int] = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0}
    defaults.update(overrides)
    return InsightSnapshot(
        post_id="p1",
        fetched_at=T0 + timedelta(hours=hours_after_t0),
        **defaults,
    )


def test_view_velocity_basic_rate() -> None:
    t1 = _snap(0, views=100)
    t2 = _snap(4, views=500)
    assert view_velocity(t1, t2) == 100.0  # (500-100)/4h


def test_view_velocity_can_be_negative_if_views_somehow_drop() -> None:
    t1 = _snap(0, views=500)
    t2 = _snap(2, views=480)
    assert view_velocity(t1, t2) == -10.0


def test_view_velocity_raises_on_non_positive_delta_t() -> None:
    t1 = _snap(4, views=100)
    t2 = _snap(0, views=500)  # t2 trước t1
    with pytest.raises(ValueError):
        view_velocity(t1, t2)


def test_view_velocity_raises_on_equal_timestamps() -> None:
    t1 = _snap(0, views=100)
    t2 = _snap(0, views=200)
    with pytest.raises(ValueError):
        view_velocity(t1, t2)


def test_amplification_velocity_basic_rate() -> None:
    t1 = _snap(0, reposts=2, quotes=1)
    t2 = _snap(3, reposts=5, quotes=4)
    # delta amplification = (5+4)-(2+1) = 6, over 3h -> 2.0/h
    assert amplification_velocity(t1, t2) == 2.0


def test_amplification_velocity_independent_of_views() -> None:
    # views tăng vọt nhưng reposts/quotes đứng yên -> amplification_velocity = 0
    t1 = _snap(0, views=100, reposts=3, quotes=1)
    t2 = _snap(5, views=10_000, reposts=3, quotes=1)
    assert amplification_velocity(t1, t2) == 0.0


def test_amplification_velocity_raises_on_non_positive_delta_t() -> None:
    t1 = _snap(2, reposts=1)
    t2 = _snap(1, reposts=5)
    with pytest.raises(ValueError):
        amplification_velocity(t1, t2)
