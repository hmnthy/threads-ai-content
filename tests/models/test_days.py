from datetime import date

import pytest

from src.models.days import (
    author_day,
    is_meta_summer_time,
    meta_day_of_end_time,
    warn_if_not_pacific_midnight,
)


@pytest.mark.parametrize(
    ("end_time", "expected"),
    [
        ("2026-10-31T07:00:00+0000", date(2026, 10, 31)),  # giờ mùa hè Pacific (UTC-7)
        ("2026-01-15T08:00:00+0000", date(2026, 1, 15)),  # giờ mùa đông Pacific (UTC-8)
        ("2025-11-02T07:00:00+0000", date(2025, 11, 2)),  # ngày về giờ mùa đông
        ("2025-11-03T08:00:00+0000", date(2025, 11, 3)),
        ("2026-03-08T08:00:00+0000", date(2026, 3, 8)),  # ngày sang giờ mùa hè
        ("2026-03-09T07:00:00+0000", date(2026, 3, 9)),
    ],
)
def test_meta_day_is_the_pacific_day_starting_at_end_time(end_time: str, expected: date) -> None:
    assert meta_day_of_end_time(end_time) == expected


def test_off_midnight_end_times_give_one_summary_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 07:00Z giữa mùa đông = 23:00 Pacific hôm trước: Meta đổi quy ước → vẫn gắn nhãn theo ngày
    # Pacific, ghi ĐÚNG 1 cảnh báo cho cả lần gọi (lần tải lại 729 ngày không làm ngập log)
    odd = ["2026-01-15T07:00:00+0000", "2026-01-16T07:00:00+0000"]
    assert meta_day_of_end_time(odd[0]) == date(2026, 1, 14)
    with caplog.at_level("WARNING", logger="src.models.days"):
        warn_if_not_pacific_midnight([*odd, "2026-07-01T07:00:00+0000"])
    assert len(caplog.records) == 1
    assert "2 of 3" in caplog.text


def test_pacific_midnight_end_times_are_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="src.models.days"):
        warn_if_not_pacific_midnight(["2026-07-01T07:00:00+0000", "2026-01-15T08:00:00+0000"])
    assert caplog.text == ""


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-08-09T22:00:00+00:00", "2026-08-10"),  # 00:00 Paris giờ mùa hè (UTC+2)
        ("2026-08-09T21:59:00+00:00", "2026-08-09"),
        ("2026-01-09T23:00:00+00:00", "2026-01-10"),  # 00:00 Paris giờ mùa đông (UTC+1)
        ("2026-01-09T22:59:00+00:00", "2026-01-09"),
        ("2025-04-14T20:49:33+0000", "2025-04-14"),  # dạng "+0000" thô của Threads
    ],
)
def test_author_day_is_the_paris_calendar_day(timestamp: str, expected: str) -> None:
    assert author_day(timestamp) == expected


def test_is_meta_summer_time_follows_pacific_dst() -> None:
    assert is_meta_summer_time(date(2026, 7, 1))
    assert not is_meta_summer_time(date(2026, 1, 15))
    # Nửa đêm đầu ngày đổi giờ vẫn ở giờ cũ (đồng hồ đổi lúc 2h sáng)
    assert is_meta_summer_time(date(2025, 11, 2))
    assert not is_meta_summer_time(date(2026, 3, 8))
    assert is_meta_summer_time(date(2026, 3, 9))
