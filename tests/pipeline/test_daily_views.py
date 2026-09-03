from datetime import UTC, datetime
from pathlib import Path

import respx
from httpx import Response

from src.api.client import ThreadsClient
from src.db.schema import connect, create_schema, list_daily_views, upsert_daily_views
from src.pipeline.daily_views import fetch_and_store_daily_views

BASE = "https://graph.threads.net/v1.0"


def _mock_daily_views_response(values: list[dict[str, object]]) -> None:
    respx.get(f"{BASE}/999/threads_insights").mock(
        return_value=Response(
            200, json={"data": [{"name": "views", "period": "day", "values": values}]}
        )
    )


@respx.mock
async def test_backfills_full_history_when_table_is_empty(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    _mock_daily_views_response([{"value": 5, "end_time": "2026-08-30T07:00:00+0000"}])
    client = ThreadsClient(access_token="tok")

    count = await fetch_and_store_daily_views(client, conn, "999")

    assert count == 1
    request = respx.calls.last.request
    since_param = request.url.params["since"]
    # Bảng rỗng -> since phải cách "hôm nay" ~729 ngày (full backfill), không phải 7.
    since_date = datetime.fromisoformat(since_param).date()
    assert (datetime.now(UTC).date() - since_date).days >= 700
    await client.aclose()
    conn.close()


@respx.mock
async def test_only_refetches_recent_window_when_data_already_exists(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    upsert_daily_views(conn, date="2026-01-01", views=10, fetched_at="2026-01-02T00:00:00+00:00")
    conn.commit()
    _mock_daily_views_response([{"value": 9, "end_time": "2026-08-30T07:00:00+0000"}])
    client = ThreadsClient(access_token="tok")

    await fetch_and_store_daily_views(client, conn, "999")

    since_param = respx.calls.last.request.url.params["since"]
    since_date = datetime.fromisoformat(since_param).date()
    assert (datetime.now(UTC).date() - since_date).days <= 7
    await client.aclose()
    conn.close()


@respx.mock
async def test_upserts_points_without_duplicating_existing_dates(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    _mock_daily_views_response(
        [
            {"value": 1, "end_time": "2026-08-29T07:00:00+0000"},
            {"value": 2, "end_time": "2026-08-30T07:00:00+0000"},
        ]
    )
    client = ThreadsClient(access_token="tok")

    await fetch_and_store_daily_views(client, conn, "999")
    await fetch_and_store_daily_views(client, conn, "999")  # chạy lại, không tăng gấp đôi

    rows = list_daily_views(conn)
    assert len(rows) == 2
    await client.aclose()
    conn.close()
