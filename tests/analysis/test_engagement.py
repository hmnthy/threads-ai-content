from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.analysis.engagement import (
    average_engagement_rate,
    engagement_by_hour,
    engagement_by_weekday,
    top_posts_by_engagement,
)
from src.api.models import MediaType, PostInsights, ThreadsPost


def _post(post_id: str, timestamp: datetime) -> ThreadsPost:
    return ThreadsPost(id=post_id, timestamp=timestamp, media_type=MediaType.TEXT_POST)


def _insights(post_id: str, *, views: int, likes: int) -> PostInsights:
    return PostInsights(post_id=post_id, views=views, likes=likes, replies=0, reposts=0, quotes=0)


def test_average_engagement_rate_returns_mean_across_posts() -> None:
    insights = [
        _insights("1", views=1000, likes=100),  # 10%
        _insights("2", views=1000, likes=50),  # 5%
    ]
    assert average_engagement_rate(insights) == 7.5


def test_average_engagement_rate_empty_list_returns_zero() -> None:
    assert average_engagement_rate([]) == 0.0


def test_top_posts_by_engagement_sorts_descending_and_skips_unmatched_posts() -> None:
    ts = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    posts = [
        _post("1", ts),
        _post("2", ts),
        _post("3", ts),  # no matching insights below — must be excluded, not error
    ]
    insights = [
        _insights("1", views=1000, likes=10),  # 1%
        _insights("2", views=1000, likes=100),  # 10%
    ]

    top = top_posts_by_engagement(posts, insights)

    assert [post.id for post, _ in top] == ["2", "1"]


def test_top_posts_by_engagement_respects_limit() -> None:
    ts = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    posts = [_post(str(i), ts) for i in range(5)]
    insights = [_insights(str(i), views=1000, likes=i) for i in range(5)]

    top = top_posts_by_engagement(posts, insights, limit=2)

    assert [post.id for post, _ in top] == ["4", "3"]


def test_engagement_by_hour_averages_rates_within_the_same_hour() -> None:
    posts = [
        _post("1", datetime(2026, 8, 24, 9, 0, tzinfo=UTC)),
        _post("2", datetime(2026, 8, 25, 9, 0, tzinfo=UTC)),
        _post("3", datetime(2026, 8, 24, 20, 0, tzinfo=UTC)),
    ]
    insights = [
        _insights("1", views=1000, likes=100),  # 10%
        _insights("2", views=1000, likes=0),  # 0%
        _insights("3", views=1000, likes=50),  # 5%
    ]

    result = engagement_by_hour(posts, insights)

    assert result[9] == 5.0
    assert result[20] == 5.0
    assert 21 not in result


def test_engagement_by_hour_converts_to_the_given_timezone() -> None:
    ts_utc = datetime(2026, 8, 24, 23, 30, tzinfo=UTC)
    ts_paris = ts_utc.astimezone(ZoneInfo("Europe/Paris"))
    ts_vn = ts_utc.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    posts = [_post("1", ts_utc)]
    insights = [_insights("1", views=1000, likes=100)]  # 10%

    assert engagement_by_hour(posts, insights) == {ts_utc.hour: 10.0}
    assert engagement_by_hour(posts, insights, timezone=ZoneInfo("Europe/Paris")) == {
        ts_paris.hour: 10.0
    }
    assert engagement_by_hour(posts, insights, timezone=ZoneInfo("Asia/Ho_Chi_Minh")) == {
        ts_vn.hour: 10.0
    }
    # The whole point of parametrizing: converting actually changes the bucket.
    assert ts_paris.hour != ts_utc.hour
    assert ts_vn.hour != ts_utc.hour


def test_engagement_by_weekday_can_shift_across_timezones_near_midnight() -> None:
    ts_utc = datetime(2026, 8, 24, 23, 30, tzinfo=UTC)
    ts_paris = ts_utc.astimezone(ZoneInfo("Europe/Paris"))
    ts_vn = ts_utc.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    posts = [_post("1", ts_utc)]
    insights = [_insights("1", views=1000, likes=100)]  # 10%

    assert engagement_by_weekday(posts, insights) == {ts_utc.weekday(): 10.0}
    assert engagement_by_weekday(posts, insights, timezone=ZoneInfo("Europe/Paris")) == {
        ts_paris.weekday(): 10.0
    }
    assert engagement_by_weekday(posts, insights, timezone=ZoneInfo("Asia/Ho_Chi_Minh")) == {
        ts_vn.weekday(): 10.0
    }
    # A post near UTC midnight lands on the next local day in both audience timezones.
    assert ts_paris.weekday() != ts_utc.weekday()
    assert ts_vn.weekday() != ts_utc.weekday()


def test_engagement_by_weekday_buckets_by_weekday_number() -> None:
    ts_a = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
    ts_b = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    posts = [_post("1", ts_a), _post("2", ts_b)]
    insights = [
        _insights("1", views=1000, likes=100),  # 10%
        _insights("2", views=1000, likes=20),  # 2%
    ]

    result = engagement_by_weekday(posts, insights)

    assert result[ts_a.weekday()] == 10.0
    assert result[ts_b.weekday()] == 2.0
