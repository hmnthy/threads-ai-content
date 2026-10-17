"""Test bước lấy snapshot insights (`src/pipeline/snapshot.py`).

Lỗi thật 10/10 + 11/10/2026: job snapshot insert ngay sau mỗi lần gọi API nên giữ khoá ghi
suốt ~160 lần gọi; job NLP chạy chồng lúc máy thức dậy gặp `database is locked`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.api.client import ThreadsAPIError, ThreadsClient
from src.api.models import PostInsights, ThreadsPost
from src.db.schema import connect, create_schema, upsert_post
from src.pipeline import snapshot as snapshot_module
from src.pipeline.snapshot import fetch_and_store_insights_snapshot

POST_IDS = ["p1", "p2", "p3"]


def _db_with_posts(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    create_schema(conn)
    for post_id in POST_IDS:
        upsert_post(
            conn,
            ThreadsPost.model_validate(
                {"id": post_id, "timestamp": "2026-10-01T10:00:00+0000", "media_type": "TEXT_POST"}
            ),
        )
    conn.commit()
    return conn


def _other_writer_can_lock_now(db_path: Path) -> bool:
    """Tiến trình khác (VD job NLP) lấy được khoá ghi ngay, không phải chờ?"""
    other = sqlite3.connect(db_path, timeout=0)
    try:
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        other.close()


async def test_no_write_lock_is_held_while_calling_the_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "t.db"
    conn = _db_with_posts(db_path)
    lock_free_during_calls: list[bool] = []

    async def fake_insights(client: ThreadsClient, post_id: str) -> PostInsights:
        lock_free_during_calls.append(_other_writer_can_lock_now(db_path))
        return PostInsights(post_id=post_id, views=10, likes=1)

    monkeypatch.setattr(snapshot_module, "get_post_insights", fake_insights)
    client = ThreadsClient(access_token="tok")

    count = await fetch_and_store_insights_snapshot(client, conn, POST_IDS)

    assert count == 3
    # Mọi lần gọi API (kể cả sau bài đầu) không có khoá ghi nào đang bị giữ
    assert lock_free_during_calls == [True, True, True]
    rows = conn.execute(
        "SELECT post_id, views, likes FROM insights_snapshots ORDER BY post_id"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("p1", 10, 1), ("p2", 10, 1), ("p3", 10, 1)]
    await client.aclose()
    conn.close()


async def test_fetched_at_is_the_time_of_each_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Gom ghi về cuối không được đổi nghĩa `fetched_at` (tuổi bài tính tại snapshot đó)
    conn = _db_with_posts(tmp_path / "t.db")
    times = iter(["2026-10-17T17:08:20+00:00", "2026-10-17T17:08:21+00:00"])

    async def fake_insights(client: ThreadsClient, post_id: str) -> PostInsights:
        return PostInsights(post_id=post_id, views=1)

    class FakeDatetime:
        @staticmethod
        def now(tz: object) -> object:
            from datetime import datetime

            return datetime.fromisoformat(next(times))

    monkeypatch.setattr(snapshot_module, "get_post_insights", fake_insights)
    monkeypatch.setattr(snapshot_module, "datetime", FakeDatetime)
    client = ThreadsClient(access_token="tok")

    await fetch_and_store_insights_snapshot(client, conn, ["p1", "p2"])

    stamps = conn.execute(
        "SELECT post_id, fetched_at FROM insights_snapshots ORDER BY post_id"
    ).fetchall()
    assert [tuple(row) for row in stamps] == [
        ("p1", "2026-10-17T17:08:20+00:00"),
        ("p2", "2026-10-17T17:08:21+00:00"),
    ]
    await client.aclose()
    conn.close()


async def test_api_error_midway_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _db_with_posts(tmp_path / "t.db")

    async def failing_insights(client: ThreadsClient, post_id: str) -> PostInsights:
        if post_id == "p2":
            raise ThreadsAPIError("boom", status_code=500, error_code=1)
        return PostInsights(post_id=post_id, views=1)

    monkeypatch.setattr(snapshot_module, "get_post_insights", failing_insights)
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ThreadsAPIError):
        await fetch_and_store_insights_snapshot(client, conn, POST_IDS)

    conn.rollback()  # như job: lỗi → tiến trình thoát, transaction (nếu có) bỏ đi
    assert conn.execute("SELECT COUNT(*) FROM insights_snapshots").fetchone()[0] == 0
    await client.aclose()
    conn.close()
