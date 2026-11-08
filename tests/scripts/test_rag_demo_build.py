"""Bước dựng demo RAG: chặn trên chi phí, thứ tự gọi embed, và không gọi API khi thiếu khoá.

Bài giả tự đặt, không chữ bài thật (repo public).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest

from scripts import rag_demo_build
from src.rag_demo.chunking import ChunkingWay
from src.rag_demo.corpus import PostSpan, Unit
from src.rag_demo.cross_encoder import PAIRS_PATH, SCORES_PATH
from src.rag_demo.embedding import EmbeddingCache, token_upper_bound
from src.rag_demo.llm_jobs import Job
from src.rag_demo.questions import QUESTIONS
from tests.rag_demo.test_embedding import FakeClient

REPO = Path(__file__).resolve().parents[2]


def test_build_outputs_are_gitignored() -> None:
    """Vector, kết quả Haiku và file trạng thái chứa chữ bài thật: không bao giờ được commit.
    `data/` không bị bỏ qua cả thư mục, chỉ từng thư mục con có tên trong `.gitignore`."""
    paths = [
        rag_demo_build.DEFAULT_CACHE,
        rag_demo_build.DEFAULT_LLM_DIR / "results.jsonl",
        rag_demo_build.DEFAULT_LLM_DIR / "batch_rerank.json",
        PAIRS_PATH,
        SCORES_PATH,
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *(path.as_posix() for path in paths)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert sorted(result.stdout.split()) == sorted(path.as_posix() for path in paths)


TEXT = "Câu một nói về nhà. Câu hai cũng về nhà. Câu ba nói chuyện khác hẳn."
UNITS = [Unit(id="u1", full_text=TEXT, posts=(PostSpan("p1", 0, len(TEXT)),))]


def test_estimate_bounds_semantic_chunks_by_the_whole_text() -> None:
    texts = rag_demo_build.estimate_texts(UNITS)
    # mọi câu, chunk cố định, câu hỏi đều có; full_text đứng thêm ở cuối làm chặn trên semantic
    assert texts[-1] == TEXT
    assert "Câu ba nói chuyện khác hẳn." in texts
    assert token_upper_bound(texts) >= token_upper_bound([TEXT]) * 2


def test_embed_sends_sentences_first_then_every_chunk_and_question(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient()
    rag_demo_build.run_embed(UNITS, client, EmbeddingCache(tmp_path / "c.jsonl"))
    first, *rest = client.embeddings.calls
    assert first == ["Câu một nói về nhà.", "Câu hai cũng về nhà.", "Câu ba nói chuyện khác hẳn."]
    sent = {text for call in rest for text in call} | set(first)
    for way, chunks in rag_demo_build.fixed_way_chunks(UNITS).items():
        assert {c.text for c in chunks} <= sent, way
    assert "Chunk semantic thật:" in capsys.readouterr().out


def test_fixed_way_chunks_has_every_way_but_semantic() -> None:
    assert set(rag_demo_build.fixed_way_chunks(UNITS)) == set(ChunkingWay) - {ChunkingWay.SEMANTIC}


def test_ce_export_writes_every_question_times_distinct_chunk_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = EmbeddingCache(tmp_path / "c.jsonl")
    rag_demo_build.run_embed(UNITS, FakeClient(), cache)  # semantic cần vector câu trong cache
    path = tmp_path / "pairs.json"
    rag_demo_build.run_ce_export(UNITS, cache, path)
    pairs = json.loads(path.read_text(encoding="utf-8"))["pairs"]
    texts = {
        c.text
        for chunks in rag_demo_build.all_chunks(UNITS, FakeClient(), cache).values()
        for c in chunks
    }
    assert len(pairs) == len(QUESTIONS) * len(texts)
    assert f"{len(pairs)} cặp" in capsys.readouterr().out


def test_rerank_passage_table_matches_every_request(tmp_path: Path) -> None:
    """`collect` kiểm câu trích bằng bảng này: nối sai thì mọi dòng rerank thành lỗi."""
    cache = EmbeddingCache(tmp_path / "c.jsonl")
    rag_demo_build.run_embed(UNITS, FakeClient(), cache)
    requests, passages = rag_demo_build.llm_requests(Job.RERANK, UNITS, cache)
    assert {r.custom_id for r in requests} == set(passages)
    for request in requests:
        content = request.params["messages"][0]["content"]
        assert f"<passage>{passages[request.custom_id]}</passage>" in content


def isolated(tmp_path: Path) -> list[str]:
    """Mọi tham số có mặc định trỏ vào `data/rag_demo/` (file thật, riêng tư) → thư mục tạm."""
    return [
        "--cache",
        str(tmp_path / "c.jsonl"),
        "--llm-dir",
        str(tmp_path / "llm"),
        "--ce-pairs",
        str(tmp_path / "pairs.json"),
        "--ce-scores",
        str(tmp_path / "scores.json"),
    ]


def test_ce_check_needs_no_db_but_other_commands_do(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        rag_demo_build.main(["estimate", *isolated(tmp_path)])
    assert stop.value.code == 2
    # ce-check chỉ so 2 file; file thiếu thì lỗi đọc file, không phải lỗi thiếu --db
    with pytest.raises(FileNotFoundError):
        rag_demo_build.main(["ce-check", *isolated(tmp_path)])


@pytest.fixture
def offline_main(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(rag_demo_build, "load_dotenv", lambda: None)
    monkeypatch.setattr(rag_demo_build, "connect_readonly", lambda _: sqlite3.connect(":memory:"))
    monkeypatch.setattr(rag_demo_build, "load_units", lambda _: UNITS)
    return monkeypatch


def test_llm_submit_without_key_stops_before_any_call(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline_main.delenv("ANTHROPIC_API_KEY", raising=False)

    def fail(*_: object, **__: object) -> None:
        raise AssertionError("không được gửi lô khi thiếu khoá")

    offline_main.setattr(rag_demo_build, "submit", fail)
    argv = ["llm-submit", "--job", "transform", "--db", str(tmp_path / "x.db"), *isolated(tmp_path)]
    assert rag_demo_build.main(argv) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_llm_submit_turns_off_sdk_retries(offline_main: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """SDK mặc định gửi lại POST khi timeout: lô đã tạo mà mất phản hồi → lô thứ hai, trả tiền
    hai lần. Client gửi lô phải có max_retries=0."""
    offline_main.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    seen: dict[str, object] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs: object) -> None:
            seen.update(kwargs)
            self.messages = types.SimpleNamespace(batches=object())

    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = FakeAnthropic  # type: ignore[attr-defined]
    offline_main.setitem(sys.modules, "anthropic", anthropic)
    offline_main.setattr(rag_demo_build, "submit", lambda *_, **__: ("msgbatch_x", 10))
    argv = ["llm-submit", "--job", "transform", "--db", str(tmp_path / "x.db"), *isolated(tmp_path)]
    assert rag_demo_build.main(argv) == 0
    assert seen == {"max_retries": 0}


def test_embed_without_key_stops_before_any_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rag_demo_build, "load_dotenv", lambda: None)
    monkeypatch.setattr(rag_demo_build, "connect_readonly", lambda _: sqlite3.connect(":memory:"))
    monkeypatch.setattr(rag_demo_build, "load_units", lambda _: UNITS)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fail(*_: object, **__: object) -> None:
        raise AssertionError("không được gọi embed khi thiếu khoá")

    monkeypatch.setattr(rag_demo_build, "run_embed", fail)
    code = rag_demo_build.main(["embed", "--db", str(tmp_path / "x.db"), *isolated(tmp_path)])
    assert code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err
