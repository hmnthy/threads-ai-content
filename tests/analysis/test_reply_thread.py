from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.analysis.reply_thread import early_reply_velocity, reply_depth, unique_repliers
from src.api.models import MediaType, ThreadsPost
from src.db.schema import connect, create_schema, upsert_post

ROOT_TS = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def _reply(
    reply_id: str,
    *,
    root_id: str,
    replied_to_id: str,
    hours_after_root: float,
    owned_by_me: bool = False,
    username: str | None = "someuser",
) -> ThreadsPost:
    return ThreadsPost(
        id=reply_id,
        timestamp=ROOT_TS + timedelta(hours=hours_after_root),
        media_type=MediaType.TEXT_POST,
        is_reply=True,
        is_reply_owned_by_me=owned_by_me,
        root_post={"id": root_id},
        replied_to={"id": replied_to_id},
        username=username,
    )


def _root() -> ThreadsPost:
    return ThreadsPost(id="root-1", timestamp=ROOT_TS, media_type=MediaType.TEXT_POST)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    conn = connect(path)
    create_schema(conn)
    conn.close()
    return path


def _seed(db_path: Path, posts: list[ThreadsPost]) -> None:
    conn = connect(db_path)
    for post in posts:
        upsert_post(conn, post)
    conn.commit()
    conn.close()


# --- unique_repliers -----------------------------------------------------------


def test_unique_repliers_counts_distinct_usernames(db_path: Path) -> None:
    posts = [
        _root(),
        _reply(
            "r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1, username="alice"
        ),
        _reply(
            "r2", root_id="root-1", replied_to_id="root-1", hours_after_root=2, username="alice"
        ),
        _reply("r3", root_id="root-1", replied_to_id="root-1", hours_after_root=3, username="bob"),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert unique_repliers("root-1", conn) == 2  # alice, bob
    conn.close()


def test_unique_repliers_excludes_author_self_continuations(db_path: Path) -> None:
    posts = [
        _root(),
        _reply(
            "self-1",
            root_id="root-1",
            replied_to_id="root-1",
            hours_after_root=0.1,
            owned_by_me=True,
            username=None,
        ),
        _reply(
            "r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1, username="alice"
        ),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert unique_repliers("root-1", conn) == 1  # only alice — self-continuation excluded
    conn.close()


def test_unique_repliers_falls_back_to_post_id_when_username_missing(db_path: Path) -> None:
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1, username=None),
        _reply("r2", root_id="root-1", replied_to_id="root-1", hours_after_root=2, username=None),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    # Known limitation: 2 replies missing username are counted as 2 distinct people
    # (id-proxy over-count), even though they could be the same person in reality.
    assert unique_repliers("root-1", conn) == 2
    conn.close()


def test_unique_repliers_returns_zero_when_no_replies(db_path: Path) -> None:
    _seed(db_path, [_root()])
    conn = connect(db_path)
    assert unique_repliers("root-1", conn) == 0
    conn.close()


# --- reply_depth -----------------------------------------------------------------


def test_reply_depth_zero_when_no_replies(db_path: Path) -> None:
    _seed(db_path, [_root()])
    conn = connect(db_path)
    assert reply_depth("root-1", conn) == 0
    conn.close()


def test_reply_depth_one_for_direct_replies_only(db_path: Path) -> None:
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1),
        _reply("r2", root_id="root-1", replied_to_id="root-1", hours_after_root=2),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert reply_depth("root-1", conn) == 1
    conn.close()


def test_reply_depth_counts_reply_to_reply_chains(db_path: Path) -> None:
    # root -> r1 -> r2 -> r3  => depth 3
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1),
        _reply("r2", root_id="root-1", replied_to_id="r1", hours_after_root=2),
        _reply("r3", root_id="root-1", replied_to_id="r2", hours_after_root=3),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert reply_depth("root-1", conn) == 3
    conn.close()


def test_reply_depth_takes_the_deepest_branch_among_multiple(db_path: Path) -> None:
    # root -> r1 -> r2 (depth 2)
    # root -> r3 (depth 1)
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1),
        _reply("r2", root_id="root-1", replied_to_id="r1", hours_after_root=2),
        _reply("r3", root_id="root-1", replied_to_id="root-1", hours_after_root=1.5),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert reply_depth("root-1", conn) == 2
    conn.close()


# --- early_reply_velocity ---------------------------------------------------------


def test_early_reply_velocity_counts_only_replies_within_window(db_path: Path) -> None:
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1),
        _reply("r2", root_id="root-1", replied_to_id="root-1", hours_after_root=5),
        _reply("r3", root_id="root-1", replied_to_id="root-1", hours_after_root=30),  # outside 24h
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    # 2 replies within 24h -> 2/24 replies per hour
    assert early_reply_velocity("root-1", conn, window_hours=24.0) == pytest.approx(2 / 24)
    conn.close()


def test_early_reply_velocity_excludes_author_self_continuations(db_path: Path) -> None:
    posts = [
        _root(),
        _reply("r1", root_id="root-1", replied_to_id="root-1", hours_after_root=1),
        _reply(
            "self-1",
            root_id="root-1",
            replied_to_id="root-1",
            hours_after_root=1,
            owned_by_me=True,
        ),
    ]
    _seed(db_path, posts)
    conn = connect(db_path)
    assert early_reply_velocity("root-1", conn, window_hours=24.0) == pytest.approx(1 / 24)
    conn.close()


def test_early_reply_velocity_returns_zero_when_root_not_found(db_path: Path) -> None:
    conn = connect(db_path)
    assert early_reply_velocity("missing-root", conn) == 0.0
    conn.close()


def test_early_reply_velocity_raises_on_non_positive_window(db_path: Path) -> None:
    _seed(db_path, [_root()])
    conn = connect(db_path)
    with pytest.raises(ValueError):
        early_reply_velocity("root-1", conn, window_hours=0)
    conn.close()
