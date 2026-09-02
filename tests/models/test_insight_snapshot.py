from datetime import UTC, datetime

from src.models.insight_snapshot import InsightSnapshot


def test_insight_snapshot_holds_a_single_point_in_time_measurement() -> None:
    snap = InsightSnapshot(
        post_id="1",
        fetched_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        views=1000,
        likes=80,
        replies=10,
        reposts=5,
        quotes=2,
    )
    assert snap.post_id == "1"
    assert snap.views == 1000
    assert snap.quotes == 2
