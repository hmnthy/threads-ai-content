"""Chốt chặn 20 bài đóng băng của demo RAG (ADR-0037 D2). DB tự chế, không đọc DB thật."""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from src.db.schema import connect, connect_readonly, create_schema
from src.rag_demo.corpus import (
    FROZEN_UNITS,
    CorpusChangedError,
    FrozenUnit,
    PostSpan,
    content_hash,
    load_units,
)

FIRST_POST = "Bài tự đặt, post đầu."
SECOND_POST = "Post viết tiếp."
FULL_TEXT = f"{FIRST_POST} {SECOND_POST}"


def freeze(unit_id: str, text: str) -> tuple[FrozenUnit, ...]:
    return (FrozenUnit(unit_id, len(text), content_hash(text)),)


def add_post(conn: sqlite3.Connection, post_id: str, text: str | None) -> None:
    conn.execute(
        "INSERT INTO posts (id, text, timestamp, media_type, raw_json) VALUES (?, ?, ?, ?, ?)",
        (post_id, text, "2026-10-01T00:00:00+00:00", "TEXT_POST", "{}"),
    )


def add_unit(
    conn: sqlite3.Connection, unit_id: str, full_text: str, continuation_ids: list[str]
) -> None:
    conn.execute(
        """INSERT INTO content_units
           (id, continuation_ids_json, raw_text, normalized_text, full_text)
           VALUES (?, ?, ?, ?, ?)""",
        (unit_id, json.dumps(continuation_ids), full_text, full_text, full_text),
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "demo.db")
    create_schema(connection)
    add_post(connection, "root", FIRST_POST)
    add_post(connection, "next", SECOND_POST)
    add_unit(connection, "root", FULL_TEXT, ["next"])
    connection.commit()
    return connection


def test_frozen_list_has_20_distinct_units_with_length_and_full_sha256() -> None:
    assert len(FROZEN_UNITS) == 20
    assert len({unit.id for unit in FROZEN_UNITS}) == 20
    assert len({unit.sha256 for unit in FROZEN_UNITS}) == 20
    for unit in FROZEN_UNITS:
        assert unit.id.isdigit()
        assert unit.length > 0
        assert re.fullmatch(r"[0-9a-f]{64}", unit.sha256)


def test_content_hash_is_sha256_of_utf8() -> None:
    assert content_hash("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    # "é" dạng UTF-8 là 2 byte c3 a9; giá trị lấy từ `sha256sum`, không qua code đang kiểm
    assert content_hash("é") == ("4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c")


def test_load_units_reads_text_and_post_positions(conn: sqlite3.Connection) -> None:
    units = load_units(conn, freeze("root", FULL_TEXT))
    assert len(units) == 1
    assert units[0].id == "root"
    assert units[0].full_text == FULL_TEXT
    assert units[0].posts == (PostSpan("root", 0, 21), PostSpan("next", 22, 37))
    first, second = units[0].posts
    assert FULL_TEXT[first.start : first.end] == FIRST_POST
    assert FULL_TEXT[second.start : second.end] == SECOND_POST


def test_load_units_keeps_the_order_of_the_frozen_list(conn: sqlite3.Connection) -> None:
    add_post(conn, "other", "Bài khác.")
    add_unit(conn, "other", "Bài khác.", [])
    order = freeze("other", "Bài khác.") + freeze("root", FULL_TEXT)
    assert [unit.id for unit in load_units(conn, order)] == ["other", "root"]


def test_load_units_works_on_a_read_only_connection(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    conn.close()
    readonly = connect_readonly(tmp_path / "demo.db")
    assert len(load_units(readonly, freeze("root", FULL_TEXT))) == 1
    readonly.close()


def test_load_units_skips_empty_posts_without_shifting_offsets(
    conn: sqlite3.Connection,
) -> None:
    add_post(conn, "blank", "")
    conn.execute(
        "UPDATE content_units SET continuation_ids_json = ? WHERE id = 'root'",
        (json.dumps(["blank", "next"]),),
    )
    units = load_units(conn, freeze("root", FULL_TEXT))
    assert units[0].posts == (PostSpan("root", 0, 21), PostSpan("next", 22, 37))


def test_stops_when_a_unit_is_gone(conn: sqlite3.Connection) -> None:
    with pytest.raises(CorpusChangedError, match="missing: không còn"):
        load_units(conn, freeze("missing", "x"))


def test_stops_when_text_changed_at_the_same_length_and_error_shows_no_post_text(
    conn: sqlite3.Connection,
) -> None:
    """Cùng độ dài nên chỉ hash bắt được."""
    old_text = FULL_TEXT[::-1]
    assert len(old_text) == len(FULL_TEXT)
    with pytest.raises(CorpusChangedError) as caught:
        load_units(conn, freeze("root", old_text))
    message = str(caught.value)
    assert "root: full_text đã đổi" in message
    assert FIRST_POST not in message


def test_stops_when_the_stored_length_is_wrong(conn: sqlite3.Connection) -> None:
    """Hash đúng mà độ dài sai: số CI dùng để kiểm vị trí đáp án không được lệch bài thật."""
    wrong = (FrozenUnit("root", len(FULL_TEXT) + 1, content_hash(FULL_TEXT)),)
    with pytest.raises(CorpusChangedError, match="root: độ dài"):
        load_units(conn, wrong)


def test_stops_when_posts_no_longer_rebuild_full_text(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE posts SET text = 'Post đã sửa.' WHERE id = 'next'")
    with pytest.raises(CorpusChangedError, match="không ghép lại đúng"):
        load_units(conn, freeze("root", FULL_TEXT))


def test_stops_when_a_new_continuation_appears(conn: sqlite3.Connection) -> None:
    """Thêm post viết tiếp làm `full_text` dài ra: không lọt qua."""
    longer = f"{FULL_TEXT} Post mới."
    conn.execute("UPDATE content_units SET full_text = ? WHERE id = 'root'", (longer,))
    with pytest.raises(CorpusChangedError, match="root: độ dài"):
        load_units(conn, freeze("root", FULL_TEXT))
