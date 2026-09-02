from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_insight_snapshot,
    upsert_content_unit,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot


def _seed_full_db(db_path: Path) -> None:
    conn = connect(db_path)
    create_schema(conn)

    root = ThreadsPost(
        id="post-1",
        text="hello world",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, root)
    upsert_content_unit(conn, ContentUnit(root=root, full_text="hello world"))
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-1",
            fetched_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
            views=1000,
            likes=80,
            replies=10,
            reposts=5,
            quotes=2,
        ),
    )
    upsert_topic(
        conn,
        topic_id="cluster-0",
        label_en="Alternance search stories",
        description_en="Posts about finding an alternance placement in France.",
        method="cluster",
    )
    upsert_post_topic_label(
        conn, post_id="post-1", topic_id="cluster-0", method="cluster", confidence=0.9
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)
    _seed_full_db(db_path)
    yield TestClient(main_module.app)


def test_health() -> None:
    with TestClient(main_module.app) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_content_units_endpoint_returns_metrics_and_topic(client: TestClient) -> None:
    response = client.get("/content-units")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    unit = data[0]
    assert unit["id"] == "post-1"
    assert unit["full_text"] == "hello world"
    assert unit["is_multi_post"] is False
    # (likes + replies + reposts + quotes) / views * 100 = (80+10+5+2)/1000*100
    assert unit["metrics"]["popularity_index"] == 1000
    assert unit["metrics"]["engagement_rate"] == pytest.approx(9.7)
    assert unit["metrics"]["virality_index"] == pytest.approx((5 + 2) / 1000 * 100)
    assert unit["metrics"]["conversation_rate"] == pytest.approx(10 / 1000 * 100)
    assert unit["topic"]["topic_id"] == "cluster-0"
    assert unit["topic"]["confidence"] == pytest.approx(0.9)
    assert unit["umap"] is None  # NLP pipeline chưa gán toạ độ cho unit này


def test_content_units_endpoint_handles_missing_metrics_and_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)

    conn = connect(db_path)
    create_schema(conn)
    root = ThreadsPost(
        id="post-2",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, root)
    upsert_content_unit(conn, ContentUnit(root=root, full_text="no metrics yet"))
    conn.commit()
    conn.close()

    with TestClient(main_module.app) as test_client:
        response = test_client.get("/content-units")
    data = response.json()

    assert len(data) == 1
    assert data[0]["metrics"] is None  # post chưa có insight snapshot nào
    assert data[0]["topic"] is None  # post chưa được gán cluster


def test_topics_endpoint_returns_post_count(client: TestClient) -> None:
    response = client.get("/topics")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "cluster-0"
    assert data[0]["post_count"] == 1


def test_analytics_overview_ranks_top_posts_per_metric_and_breaks_down_by_timezone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "analytics.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)

    conn = connect(db_path)
    create_schema(conn)

    post_a = ThreadsPost(
        id="post-a",
        text="post a",
        timestamp=datetime(2026, 8, 20, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    post_b = ThreadsPost(
        id="post-b",
        text="post b",
        timestamp=datetime(2026, 8, 21, 20, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, post_a)
    upsert_post(conn, post_b)
    upsert_content_unit(conn, ContentUnit(root=post_a, full_text="post a"))
    upsert_content_unit(conn, ContentUnit(root=post_b, full_text="post b"))

    # post_a: high likes/replies (engagement + conversation), no reposts/quotes (virality=0).
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-a",
            fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
            views=1000,
            likes=200,
            replies=10,
            reposts=0,
            quotes=0,
        ),
    )
    # post_b: no likes/replies, heavy reposts/quotes -> high virality, low engagement/conversation.
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-b",
            fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
            views=1000,
            likes=0,
            replies=0,
            reposts=50,
            quotes=50,
        ),
    )
    conn.commit()
    conn.close()

    with TestClient(main_module.app) as test_client:
        response = test_client.get("/analytics/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["post_count"] == 2
    assert data["top_by_engagement"][0]["id"] == "post-a"
    assert data["top_by_conversation"][0]["id"] == "post-a"
    assert data["top_by_virality"][0]["id"] == "post-b"

    timezone_names = [tz["timezone"] for tz in data["timezones"]]
    assert timezone_names == ["Europe/Paris", "Asia/Ho_Chi_Minh"]
    for tz in data["timezones"]:
        assert len(tz["by_hour"]) == 2  # 1 bucket per post's local hour
        assert len(tz["by_weekday"]) == 2


def test_analytics_overview_excludes_posts_without_insight_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "analytics-empty.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)

    conn = connect(db_path)
    create_schema(conn)
    root = ThreadsPost(
        id="post-x",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, root)
    upsert_content_unit(conn, ContentUnit(root=root, full_text="x"))
    conn.commit()
    conn.close()

    with TestClient(main_module.app) as test_client:
        response = test_client.get("/analytics/overview")

    data = response.json()
    assert data["post_count"] == 0
    assert data["top_by_engagement"] == []
    assert data["average_engagement_rate"] == 0.0


def test_analytics_overview_excludes_reply_posts_from_the_posts_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `posts` also holds the 1,285 audience/self-replies ingested alongside root
    # posts — analytics must only ever count root posts (== content units).
    db_path = tmp_path / "analytics-reply.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)

    conn = connect(db_path)
    create_schema(conn)
    root = ThreadsPost(
        id="post-root",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    reply = ThreadsPost(
        id="post-reply",
        timestamp=datetime(2026, 8, 24, 10, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
        is_reply=True,
    )
    upsert_post(conn, root)
    upsert_post(conn, reply)
    upsert_content_unit(conn, ContentUnit(root=root, full_text="root"))
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-root",
            fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
            views=100,
            likes=1,
            replies=0,
            reposts=0,
            quotes=0,
        ),
    )
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-reply",
            fetched_at=datetime(2026, 8, 30, tzinfo=UTC),
            views=999,
            likes=999,
            replies=999,
            reposts=999,
            quotes=999,
        ),
    )
    conn.commit()
    conn.close()

    with TestClient(main_module.app) as test_client:
        response = test_client.get("/analytics/overview")

    data = response.json()
    assert data["post_count"] == 1
    assert data["top_by_engagement"][0]["id"] == "post-root"
