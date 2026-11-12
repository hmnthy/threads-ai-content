"""Embedding của demo RAG với client giả: không gọi mạng, không cần khoá."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from src.rag_demo.embedding import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbedReport,
    cache_key,
    cost_upper_bound_usd,
    embed_texts,
    token_upper_bound,
)


@dataclass
class FakeItem:
    index: int
    embedding: list[float]


@dataclass
class FakeUsage:
    total_tokens: int


@dataclass
class FakeResponse:
    data: list[FakeItem]
    usage: FakeUsage


def vector_of(text: str) -> list[float]:
    """Vector tính tay từ chữ: [độ dài, số chữ 'a', 1]."""
    return [float(len(text)), float(text.count("a")), 1.0]


@dataclass
class FakeEmbeddings:
    calls: list[list[str]] = field(default_factory=list)
    reverse: bool = False  # trả về ngược thứ tự để kiểm việc xếp theo `index`
    drop_last: bool = False
    bad_value: bool = False

    def create(self, *, model: str, input: list[str]) -> FakeResponse:
        assert model == EMBEDDING_MODEL
        self.calls.append(list(input))
        items = [FakeItem(i, vector_of(text)) for i, text in enumerate(input)]
        if self.bad_value:
            items[0] = FakeItem(0, [float("nan"), 0.0, 1.0])
        if self.drop_last:
            items = items[:-1]
        if self.reverse:
            items = items[::-1]
        return FakeResponse(items, FakeUsage(total_tokens=10 * len(input)))


@dataclass
class FakeClient:
    embeddings: FakeEmbeddings = field(default_factory=FakeEmbeddings)


def test_rows_follow_input_order_and_duplicates_call_once(tmp_path: Path) -> None:
    client = FakeClient(FakeEmbeddings(reverse=True))
    matrix, report = embed_texts(
        ["ba", "a", "ba"], client=client, cache=EmbeddingCache(tmp_path / "c.jsonl")
    )
    assert matrix.tolist() == [[2.0, 1.0, 1.0], [1.0, 1.0, 1.0], [2.0, 1.0, 1.0]]
    assert client.embeddings.calls == [["ba", "a"]]
    assert report == EmbedReport(texts=2, from_cache=0, requested=2, tokens=20)


def test_cache_survives_a_new_instance_and_skips_the_call(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    embed_texts(["xin chào"], client=FakeClient(), cache=EmbeddingCache(path))
    client = FakeClient()
    matrix, report = embed_texts(["xin chào", "mới"], client=client, cache=EmbeddingCache(path))
    assert client.embeddings.calls == [["mới"]]
    assert report == EmbedReport(texts=2, from_cache=1, requested=1, tokens=10)
    assert matrix[0].tolist() == vector_of("xin chào")
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["key"] == cache_key("xin chào", EMBEDDING_MODEL)
    assert row["model"] == EMBEDDING_MODEL


def test_cache_key_depends_on_the_model() -> None:
    assert cache_key("x", "model-a") != cache_key("x", "model-b")


def test_requests_are_split_into_batches(tmp_path: Path) -> None:
    client = FakeClient()
    texts = [f"chữ {i}" for i in range(5)]
    _, report = embed_texts(
        texts, client=client, cache=EmbeddingCache(tmp_path / "c.jsonl"), batch_size=2
    )
    assert [len(call) for call in client.embeddings.calls] == [2, 2, 1]
    assert report.tokens == 50


@pytest.mark.parametrize(
    "fake",
    [FakeEmbeddings(drop_last=True), FakeEmbeddings(bad_value=True)],
    ids=["missing vector", "nan value"],
)
def test_a_bad_response_raises_and_caches_nothing(fake: FakeEmbeddings, tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    with pytest.raises(ValueError):
        embed_texts(["một", "hai"], client=FakeClient(fake), cache=EmbeddingCache(path))
    assert not path.exists()


def test_empty_text_is_refused_before_any_call(tmp_path: Path) -> None:
    client = FakeClient()
    with pytest.raises(ValueError):
        embed_texts(["một", " "], client=client, cache=EmbeddingCache(tmp_path / "c.jsonl"))
    assert client.embeddings.calls == []


def test_token_upper_bound_counts_utf8_bytes() -> None:
    # "ệ" là 3 byte UTF-8 (U+1EC7), "a" là 1 byte
    assert token_upper_bound(["ệ", "a"]) == 4
    assert token_upper_bound([]) == 0


def test_cost_upper_bound_uses_the_listed_price() -> None:
    # 1 triệu byte ASCII → chặn trên 1 triệu token → $0,02
    assert cost_upper_bound_usd(["a" * 1_000_000]) == pytest.approx(0.02)


def test_report_cost_is_tokens_times_price() -> None:
    assert EmbedReport(texts=1, from_cache=0, requested=1, tokens=500_000).cost_usd == (
        pytest.approx(0.01)
    )


def test_matrix_is_float64(tmp_path: Path) -> None:
    matrix, _ = embed_texts(["a"], client=FakeClient(), cache=EmbeddingCache(tmp_path / "c.jsonl"))
    assert matrix.dtype == np.float64


def test_cached_vectors_of_different_lengths_are_an_error(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "c.jsonl")
    cache.add(
        [
            (cache_key("a", EMBEDDING_MODEL), EMBEDDING_MODEL, [1.0, 0.0]),
            (cache_key("b", EMBEDDING_MODEL), EMBEDDING_MODEL, [1.0]),
        ]
    )
    with pytest.raises(ValueError, match="số chiều"):
        embed_texts(["a", "b"], client=FakeClient(), cache=cache)


def _line(key: str) -> str:
    return json.dumps({"key": key, "model": "m", "vector": [1.0]})


def test_a_half_written_last_line_is_cut_and_the_next_write_starts_clean(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    path.write_text(_line("a") + "\n" + _line("b")[:10], encoding="utf-8")  # chết giữa lúc ghi
    before = path.read_bytes()
    cache = EmbeddingCache(path)
    assert cache.dropped_partial_line
    assert (cache.get("a"), cache.get("b")) == ([1.0], None)
    assert path.read_bytes() == before  # mở để đọc không sửa file
    cache.add([("c", "m", [2.0])])
    reopened = EmbeddingCache(path)
    assert not reopened.dropped_partial_line
    assert (reopened.get("a"), reopened.get("c")) == ([1.0], [2.0])


def test_a_nul_tail_after_a_crash_is_treated_as_a_partial_line(tmp_path: Path) -> None:
    """Máy sập có thể để lại đuôi toàn byte NUL: json.loads ném UnicodeDecodeError (không phải
    JSONDecodeError), vẫn phải coi là dòng dở và cắt trước lần ghi sau."""
    path = tmp_path / "c.jsonl"
    path.write_bytes((_line("a") + "\n").encode() + b"\x00" * 5)
    cache = EmbeddingCache(path)
    assert cache.dropped_partial_line
    cache.add([("b", "m", [2.0])])
    reopened = EmbeddingCache(path)
    assert (reopened.get("a"), reopened.get("b")) == ([1.0], [2.0])
    assert b"\x00" not in path.read_bytes()


def test_a_complete_last_line_without_newline_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    path.write_text(_line("a"), encoding="utf-8")
    cache = EmbeddingCache(path)
    assert not cache.dropped_partial_line
    cache.add([("b", "m", [2.0])])
    reopened = EmbeddingCache(path)
    assert (reopened.get("a"), reopened.get("b")) == ([1.0], [2.0])


def test_repair_stops_if_another_process_wrote_since_opening(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    path.write_text(_line("a") + "\n" + _line("b")[:10], encoding="utf-8")
    cache = EmbeddingCache(path)
    with path.open("a", encoding="utf-8") as file:  # lệnh embed khác ghi nốt dòng của nó
        file.write(_line("b")[10:] + "\n")
    with pytest.raises(RuntimeError, match="đã đổi"):
        cache.add([("c", "m", [2.0])])
    reopened = EmbeddingCache(path)  # dòng của tiến trình kia còn nguyên
    assert (reopened.get("b"), reopened.get("c")) == ([1.0], None)


def test_a_broken_line_in_the_middle_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    path.write_text(_line("a")[:10] + "\n" + _line("b") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dòng 1"):
        EmbeddingCache(path)
    assert path.read_text(encoding="utf-8").endswith(_line("b") + "\n")  # không sửa file
