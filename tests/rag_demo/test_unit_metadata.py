"""Tháng đăng + topic của mỗi bài cho bộ lọc metadata (ADR-0041): DB tự chế với schema thật, mở chỉ
đọc như lệnh `assemble`. Giá trị mong đợi tính tay (giờ Paris: CET = UTC+1 sau 2026-10-25,
CEST = UTC+2 trước đó)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.db.schema import connect_readonly, create_schema, insert_cluster_run
from src.rag_demo.corpus import PostSpan, Unit
from src.rag_demo.unit_metadata import (
    UNCLUSTERED,
    MetadataError,
    TopicSnapshot,
    UnitMeta,
    read_unit_metadata,
    summary,
)


def unit(unit_id: str) -> Unit:
    return Unit(unit_id, "chữ", (PostSpan(unit_id, 0, 3),))


def add_post(conn: sqlite3.Connection, post_id: str, timestamp: str) -> None:
    conn.execute(
        "INSERT INTO posts (id, timestamp, media_type, raw_json) VALUES (?, ?, 'TEXT_POST', '{}')",
        (post_id, timestamp),
    )


def add_run(conn: sqlite3.Connection, run_at: str) -> None:
    insert_cluster_run(
        conn,
        run_at=run_at,
        model_id="m",
        params={},
        n_units=3,
        n_clusters=1,
        noise_ratio=0.5,
        dbcv=None,
        ari_vs_previous=None,
        labels={},
    )


def add_label(conn: sqlite3.Connection, post_id: str, topic_id: str, label_en: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO topics (id, label_en, method) VALUES (?, ?, 'cluster')",
        (topic_id, label_en),
    )
    conn.execute(
        "INSERT INTO post_topic_labels (post_id, topic_id, method) VALUES (?, ?, 'cluster')",
        (post_id, topic_id),
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "threads.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    # a: giữa tháng 10; b: 23:30 UTC ngày 31/10 = 00:30 ngày 1/11 giờ Paris (CET);
    # c: 22:30 UTC ngày 30/6 = 00:30 ngày 1/7 giờ Paris (CEST);
    # d: 22:30 UTC ngày 31/10 = 23:30 cùng ngày giờ Paris (CET) — cộng cố định +2 giờ sẽ ra tháng 11
    add_post(conn, "a", "2026-10-12T09:13:00+00:00")
    add_post(conn, "b", "2026-10-31T23:30:00+00:00")
    add_post(conn, "c", "2026-06-30T22:30:00+00:00")
    add_post(conn, "d", "2026-10-31T22:30:00+00:00")
    add_run(conn, "2026-11-09T11:30:00+00:00")
    add_run(conn, "2026-11-10T11:30:00+00:00")
    add_label(conn, "a", "topic-3", "Housing in France")
    conn.commit()
    conn.close()
    return path


def test_months_are_paris_months_of_the_opening_post(db: Path) -> None:
    units = [unit("a"), unit("b"), unit("c"), unit("d")]
    snapshot = read_unit_metadata(connect_readonly(db), units)
    assert [snapshot.units[u].month for u in "abcd"] == ["2026-10", "2026-11", "2026-07", "2026-10"]


def test_unlabelled_units_are_unclustered_and_the_latest_run_is_recorded(db: Path) -> None:
    snapshot = read_unit_metadata(connect_readonly(db), [unit("a"), unit("b")])
    assert snapshot == TopicSnapshot(
        cluster_run_id=2,
        cluster_run_at="2026-11-10T11:30:00+00:00",
        units={
            "a": UnitMeta("2026-10", "topic-3", "Housing in France"),
            "b": UnitMeta("2026-11", None, UNCLUSTERED),
        },
    )
    assert UNCLUSTERED == "Unclustered"


def test_the_read_is_one_transaction_and_leaves_none_open(db: Path) -> None:
    """Bỏ `BEGIN` thì nhãn và mã lần gom cụm có thể lấy từ 2 lần chạy khác nhau: test phải đỏ."""
    conn = connect_readonly(db)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    read_unit_metadata(conn, [unit("a"), unit("b")])
    assert statements[0] == "BEGIN"
    assert statements[-1] == "ROLLBACK"
    assert len(statements) == 1 + 1 + 2 * 2 + 1  # BEGIN, lần gom cụm, 2 SELECT mỗi bài, ROLLBACK
    assert not conn.in_transaction


def test_a_label_pointing_to_a_missing_topic_stops(tmp_path: Path) -> None:
    path = tmp_path / "dangling.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    add_post(conn, "a", "2026-10-12T09:13:00+00:00")
    add_run(conn, "2026-11-10T11:30:00+00:00")
    conn.execute(
        "INSERT INTO post_topic_labels (post_id, topic_id, method) VALUES ('a', 'gone', 'cluster')"
    )
    conn.commit()
    conn.close()
    with pytest.raises(MetadataError, match="a: nhãn trỏ tới topic gone không có trong topics"):
        read_unit_metadata(connect_readonly(path), [unit("a")])


def test_a_missing_opening_post_stops(db: Path) -> None:
    conn = connect_readonly(db)
    with pytest.raises(MetadataError, match="zz: post mở đầu không có trong posts"):
        read_unit_metadata(conn, [unit("a"), unit("zz")])
    assert not conn.in_transaction


def test_no_cluster_run_means_every_unit_is_unclustered(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    add_post(conn, "a", "2026-10-12T09:13:00+00:00")
    conn.commit()
    conn.close()
    snapshot = read_unit_metadata(connect_readonly(path), [unit("a")])
    assert snapshot == TopicSnapshot(None, None, {"a": UnitMeta("2026-10", None, UNCLUSTERED)})
    assert summary(snapshot) == (
        "Topic: chưa có lần gom cụm nào · 0 / 1 bài có topic, 1 Unclustered"
        " · tháng đăng (giờ Paris): 2026-10 1"
    )


def test_an_unreadable_timestamp_stops_with_a_message(tmp_path: Path) -> None:
    path = tmp_path / "bad.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    add_post(conn, "a", "not a date")
    conn.commit()
    conn.close()
    with pytest.raises(MetadataError, match="a: timestamp không đọc được"):
        read_unit_metadata(connect_readonly(path), [unit("a")])


def test_a_timestamp_without_time_zone_stops_instead_of_using_the_machine_zone(
    tmp_path: Path,
) -> None:
    # 23:30 không múi giờ: giờ máy UTC → tháng 10, giờ Paris → tháng 11; không được đoán
    path = tmp_path / "naive.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    add_post(conn, "a", "2026-10-31T23:30:00")
    conn.commit()
    conn.close()
    with pytest.raises(MetadataError, match=r"a: timestamp không đọc được \(không có múi giờ\)"):
        read_unit_metadata(connect_readonly(path), [unit("a")])


def test_a_label_without_any_cluster_run_stops(tmp_path: Path) -> None:
    path = tmp_path / "broken.db"
    conn = sqlite3.connect(path)
    create_schema(conn)
    add_post(conn, "a", "2026-10-12T09:13:00+00:00")
    add_label(conn, "a", "topic-1", "Jobs")
    conn.commit()
    conn.close()
    with pytest.raises(MetadataError, match="a: có nhãn topic mà DB không có lần gom cụm nào"):
        read_unit_metadata(connect_readonly(path), [unit("a")])


def test_summary_counts_topics_and_months(db: Path) -> None:
    snapshot = read_unit_metadata(connect_readonly(db), [unit("a"), unit("b"), unit("c")])
    assert summary(snapshot) == (
        "Topic: lần gom cụm 2 (2026-11-10T11:30:00+00:00) · 1 / 3 bài có topic, 2 Unclustered"
        " · tháng đăng (giờ Paris): 2026-07 1, 2026-10 1, 2026-11 1"
    )
