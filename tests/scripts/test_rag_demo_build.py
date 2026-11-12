"""Bước dựng demo RAG: chặn trên chi phí, thứ tự gọi embed, và không gọi API khi thiếu khoá.

Bài giả tự đặt, không chữ bài thật (repo public).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest

import src.pipeline.publish as publish_module
from scripts import rag_demo_build
from src.api.auth import REQUIRED_ENV_VARS
from src.rag_demo.chunking import ChunkingWay
from src.rag_demo.corpus import PostSpan, Unit, content_hash
from src.rag_demo.cross_encoder import (
    CROSS_ENCODER_MAX_LENGTH,
    CROSS_ENCODER_MODEL,
    CROSS_ENCODER_REVISION,
    PAIRS_PATH,
    SCORES_PATH,
)
from src.rag_demo.demo_file import DEMO_PATH, code_provenance, question_texts_sha256
from src.rag_demo.embedding import EmbeddingCache, token_upper_bound
from src.rag_demo.llm_batch import done_ids
from src.rag_demo.llm_jobs import (
    LLM_MODEL,
    PROMPT_VERSIONS,
    SCHEMAS,
    Job,
    LlmRequest,
    check_output,
)
from src.rag_demo.questions import QUESTIONS, AnswerRule, GoldSpan, Question
from src.rag_demo.unit_metadata import UNCLUSTERED, MetadataError, TopicSnapshot, UnitMeta
from tests.rag_demo.test_embedding import FakeClient

REPO = Path(__file__).resolve().parents[2]


def test_build_outputs_are_gitignored() -> None:
    """Vector, kết quả Haiku và file trạng thái chứa chữ bài thật: không bao giờ được commit.
    `data/` không bị bỏ qua cả thư mục, chỉ từng thư mục con có tên trong `.gitignore`."""
    paths = [
        rag_demo_build.DEFAULT_CACHE,
        rag_demo_build.DEFAULT_LLM_DIR / rag_demo_build.RESULTS_NAME,
        rag_demo_build.DEFAULT_LLM_DIR / "batch_rerank.json",
        PAIRS_PATH,
        SCORES_PATH,
        DEMO_PATH,
        DEMO_PATH.with_suffix(".json.tmp"),
        # chốt `--out` của assemble cho mọi file dưới thư mục này (out_is_private)
        rag_demo_build.PRIVATE_DIR / "bat-ky.json",
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
META = TopicSnapshot(7, "2026-11-10T11:30:00+00:00", {"u1": UnitMeta("2026-10", None, UNCLUSTERED)})


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


QUESTION = Question(
    number=1,
    text="câu hỏi tự đặt",
    english="made-up question",
    rule=AnswerRule.SINGLE,
    gold_unit_ids=("u1",),
    gold_span=GoldSpan(start=0, end=5),
)


@pytest.fixture
def embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EmbeddingCache:
    """Cache có vector câu (để chia semantic) và bộ câu hỏi chỉ một câu, đáp án nằm ở bài giả."""
    cache = EmbeddingCache(tmp_path / "c.jsonl")
    rag_demo_build.run_embed(UNITS, FakeClient(), cache)
    monkeypatch.setattr(rag_demo_build, "QUESTIONS", (QUESTION,))
    # bộ câu hỏi giả coi như là bộ đã gửi lô (hằng thật ghim chữ của 10 câu thật)
    monkeypatch.setattr(
        rag_demo_build, "PAID_QUESTION_TEXTS_SHA256", question_texts_sha256((QUESTION,))
    )
    return cache


EDITED_QUESTION = (
    "chữ câu hỏi khác lúc gửi lô Haiku: tăng PROMPT_VERSIONS của transform + rerank, gửi "
    "lại lô, rồi cập nhật PAID_QUESTION_TEXTS_SHA256"
)


def test_check_passes_only_with_a_current_pairs_file(
    embedded: EmbeddingCache, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    by_way = rag_demo_build.all_chunks(UNITS, FakeClient(), embedded)
    path = tmp_path / "pairs.json"
    assert rag_demo_build.build_problems(UNITS, by_way, path) == [
        f"chưa có file cặp cross-encoder {path}"
    ]
    rag_demo_build.run_ce_export(UNITS, embedded, path)
    assert rag_demo_build.build_problems(UNITS, by_way, path) == []
    # sửa câu hỏi sau khi chấm: điểm cũ thuộc cặp khác, và kết quả Haiku đã trả tiền chấm câu cũ
    monkeypatch.setattr(rag_demo_build, "QUESTIONS", (replace(QUESTION, text="câu đã sửa"),))
    assert rag_demo_build.build_problems(UNITS, by_way, path) == [
        EDITED_QUESTION,
        "file cặp cross-encoder không còn khớp chunk / câu hỏi hiện tại",
    ]
    # chấm lại cross-encoder (miễn phí) không gỡ được lỗi chữ câu hỏi: lô Haiku vẫn là của câu cũ
    rag_demo_build.run_ce_export(UNITS, embedded, path)
    assert rag_demo_build.build_problems(UNITS, by_way, path) == [EDITED_QUESTION]


def test_check_reports_a_way_where_no_chunk_holds_the_answer(
    embedded: EmbeddingCache, tmp_path: Path
) -> None:
    by_way = rag_demo_build.all_chunks(UNITS, FakeClient(), embedded)
    path = tmp_path / "pairs.json"
    rag_demo_build.run_ce_export(UNITS, embedded, path)
    by_way[ChunkingWay.WHOLE] = [c for c in by_way[ChunkingWay.WHOLE] if c.unit_id != "u1"]
    # chữ của chunk bỏ đi vẫn có ở cách chia khác (bài ngắn) nên file cặp vẫn khớp: chỉ một lỗi
    assert rag_demo_build.build_problems(UNITS, by_way, path) == [
        "câu 1, cách whole: không chunk nào trúng u1"
    ]


def test_check_reports_a_gold_unit_missing_from_the_corpus(
    embedded: EmbeddingCache, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag_demo_build, "QUESTIONS", (replace(QUESTION, gold_unit_ids=("u9",)),))
    by_way = rag_demo_build.all_chunks(UNITS, FakeClient(), embedded)
    problems = rag_demo_build.build_problems(UNITS, by_way, tmp_path / "pairs.json")
    # chữ câu hỏi không đổi, chỉ đổi đáp án: không có lỗi chữ câu hỏi
    assert problems[0] == "câu 1: u9 không có trong tập"
    assert sum("không chunk nào trúng u9" in p for p in problems) == len(ChunkingWay)


def test_live_check_exit_code_follows_the_comparison(capsys: pytest.CaptureFixture[str]) -> None:
    # bài giả: mã bài gốc u1 khác mã post p1 (như bài gốc không có chữ) — cả hai phải còn sống
    assert rag_demo_build.run_live_check(UNITS, {"u1": "", "p1": TEXT}) == 0
    assert rag_demo_build.run_live_check(UNITS, {}) == 1
    assert "u1: post không còn trên Threads: u1, p1" in capsys.readouterr().out


def test_live_texts_come_from_posts_and_replies_without_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cache cũ (TTL 6 giờ) sẽ che một bài vừa xoá: phép so phải đọc thẳng API."""
    seen: list[tuple[str, object]] = []

    class FakeThreadsClient:
        def __init__(self, *, access_token: str) -> None:
            assert access_token == "token-not-real"

        async def __aenter__(self) -> FakeThreadsClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    def fake_fetch(name: str, items: list[tuple[str, str | None]]) -> object:
        async def fetch(_client: object, user_id: str, cache: object = None) -> list[object]:
            seen.append((name, cache))
            assert user_id == "user-not-real"
            return [types.SimpleNamespace(id=i, text=t) for i, t in items]

        return fetch

    credentials = types.SimpleNamespace(access_token="token-not-real", user_id="user-not-real")
    monkeypatch.setattr(rag_demo_build, "load_dotenv", lambda *_, **__: None)
    monkeypatch.setattr(rag_demo_build, "load_credentials", lambda: credentials)
    monkeypatch.setattr(rag_demo_build, "ThreadsClient", FakeThreadsClient)
    monkeypatch.setattr(rag_demo_build, "get_posts", fake_fetch("posts", [("p1", "Bài.")]))
    monkeypatch.setattr(rag_demo_build, "get_replies", fake_fetch("replies", [("r1", None)]))
    assert rag_demo_build.fetch_live_texts(tmp_path / ".env") == {"p1": "Bài.", "r1": ""}
    assert seen == [("posts", None), ("replies", None)]


def test_live_check_uses_the_token_of_env_file_over_one_already_loaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`src/api/auth.py` đã nạp `.env` gần nhất lúc import (bản sao trong worktree, token có thể
    cũ): `--env-file` phải thắng, không thì tuỳ chọn không có tác dụng."""
    for name in REQUIRED_ENV_VARS:
        monkeypatch.setenv(name, "cu-not-real")  # như biến đã nạp từ .env cũ; teardown trả lại
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{name}=moi-not-real" for name in REQUIRED_ENV_VARS), encoding="utf-8"
    )
    seen: list[str] = []

    class FakeThreadsClient:
        def __init__(self, *, access_token: str) -> None:
            seen.append(access_token)

        async def __aenter__(self) -> FakeThreadsClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    async def no_posts(*_: object, **__: object) -> list[object]:
        return []

    monkeypatch.setattr(rag_demo_build, "ThreadsClient", FakeThreadsClient)
    monkeypatch.setattr(rag_demo_build, "get_posts", no_posts)
    monkeypatch.setattr(rag_demo_build, "get_replies", no_posts)
    assert rag_demo_build.fetch_live_texts(env_file) == {}
    assert seen == ["moi-not-real"]


@pytest.fixture
def offline_main(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(rag_demo_build, "load_dotenv", lambda *_, **__: None)
    monkeypatch.setattr(rag_demo_build, "connect_readonly", lambda _: sqlite3.connect(":memory:"))
    monkeypatch.setattr(rag_demo_build, "load_units", lambda _: UNITS)
    monkeypatch.setattr(rag_demo_build, "read_unit_metadata", lambda *_: META)
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


def test_check_command_exits_1_and_lists_problems(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rag_demo_build.run_embed(UNITS, FakeClient(), EmbeddingCache(tmp_path / "c.jsonl"))
    argv = ["check", "--db", str(tmp_path / "x.db"), *isolated(tmp_path)]
    assert rag_demo_build.main(argv) == 1
    out = capsys.readouterr().out
    assert "chưa có file cặp cross-encoder" in out
    # bộ câu hỏi thật: bài đáp án không có trong bài giả
    assert f"câu 1: {QUESTIONS[0].gold_unit_ids[0]} không có trong tập" in out


def test_live_check_without_threads_token_stops_before_any_call(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in REQUIRED_ENV_VARS:
        offline_main.delenv(name, raising=False)

    def fail(*_: object, **__: object) -> None:
        raise AssertionError("không được gọi Threads khi thiếu token")

    offline_main.setattr(rag_demo_build, "ThreadsClient", fail)
    env_file = tmp_path / ".env"
    env_file.write_text("# không có token\n", encoding="utf-8")
    argv = ["live-check", "--db", str(tmp_path / "x.db"), "--env-file", str(env_file)]
    assert rag_demo_build.main([*argv, *isolated(tmp_path)]) == 2
    assert "THREADS_ACCESS_TOKEN" in capsys.readouterr().err


def test_live_check_with_a_missing_env_file_stops_before_any_call(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gõ sai `--env-file` không được âm thầm chạy bằng token đã nạp lúc import."""
    for name in REQUIRED_ENV_VARS:
        offline_main.setenv(name, "da-nap-not-real")

    def fail(*_: object, **__: object) -> None:
        raise AssertionError("không được gọi Threads khi file .env không có")

    offline_main.setattr(rag_demo_build, "ThreadsClient", fail)
    missing = tmp_path / "khong-co" / ".env"
    argv = ["live-check", "--db", str(tmp_path / "x.db"), "--env-file", str(missing)]
    assert rag_demo_build.main([*argv, *isolated(tmp_path)]) == 2
    assert "Không thấy file" in capsys.readouterr().err


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


# --- assemble: ghép file demo từ kết quả đã lưu ---


def fake_output(request: LlmRequest, passage: str | None) -> dict[str, object]:
    """Output hợp lệ theo đúng schema của việc đó, đi qua cùng phép kiểm của bước thu lô."""
    schema = SCHEMAS[request.job]["properties"]
    if request.job is Job.RERANK:
        raw: dict[str, object] = {"score": 0, "quote": "", "quote_en": ""}
    else:
        raw = {key: ["x"] if spec["type"] == "array" else "x" for key, spec in schema.items()}
    return check_output(request.job, raw, passage)


def stored_inputs(tmp_path: Path, cache: EmbeddingCache) -> Path:
    """Đủ đầu vào cho bài giả: vector câu hỏi, file cặp + điểm cross-encoder, kết quả Haiku."""
    rag_demo_build.run_embed(UNITS, FakeClient(), cache)  # thêm vector của câu hỏi đã thay
    pairs = tmp_path / "pairs.json"
    rag_demo_build.run_ce_export(UNITS, cache, pairs)
    pair_ids = [pair["id"] for pair in json.loads(pairs.read_bytes())["pairs"]]
    scores = {
        "pairs_digest": hashlib.sha256(pairs.read_bytes()).hexdigest(),
        "model": CROSS_ENCODER_MODEL,
        "revision": CROSS_ENCODER_REVISION,
        "max_length": CROSS_ENCODER_MAX_LENGTH,
        "longest_pair_tokens": 10,
        "scores": {pair_id: 0.5 for pair_id in pair_ids},
    }
    (tmp_path / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    rows = []
    for job in (Job.TRANSFORM, Job.CONTEXT, Job.RERANK):
        requests, passages = rag_demo_build.llm_requests(job, UNITS, cache)
        rows += [
            {
                "custom_id": r.custom_id,
                "job": r.job.value,
                "ok": True,
                "model": LLM_MODEL,
                "prompt_version": PROMPT_VERSIONS[r.job],
                "output": fake_output(r, passages.get(r.custom_id)),
            }
            for r in requests
        ]
    results = tmp_path / "llm" / "results.jsonl"
    results.parent.mkdir()
    results.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return results


def assemble_argv(tmp_path: Path) -> list[str]:
    out = ["--out", str(tmp_path / "demo.json")]
    return ["assemble", "--db", str(tmp_path / "x.db"), *isolated(tmp_path), *out]


def test_assemble_writes_the_demo_file_from_stored_results(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = stored_inputs(tmp_path, embedded)
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    rerank = next(row for row in rows if row["job"] == "rerank")
    extra = [
        {"custom_id": "rr-q01-bai-da-xoa", "job": "rerank", "ok": True},  # ADR-0040
        rerank | {"ok": False, "error": "batch result errored"},  # thất bại, rồi gửi lại được
        rerank | {"prompt_version": "2000-01-01.1"},  # dòng của phiên bản prompt cũ
        rerank | {"prompt_version": "2000-01-02.1"},
    ]
    with results.open("a", encoding="utf-8") as file:
        file.write("".join(json.dumps(row) + "\n" for row in extra))
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 0
    demo = json.loads((tmp_path / "demo.json").read_text(encoding="utf-8"))
    assert demo["format"] == 2
    assert demo["units"][0]["month"] == "2026-10"
    assert demo["units"][0]["topic"] == {"id": None, "label_en": "Unclustered"}
    assert demo["provenance"]["topics"] == {
        "cluster_run_id": 7,
        "cluster_run_at": "2026-11-10T11:30:00+00:00",
    }
    assert [q["number"] for q in demo["questions"]] == [1]
    inputs = demo["provenance"]["inputs"]
    pairs_digest = hashlib.sha256((tmp_path / "pairs.json").read_bytes()).hexdigest()
    assert inputs["cross_encoder_pairs_sha256"] == pairs_digest
    assert inputs["llm_results_sha256"] == hashlib.sha256(results.read_bytes()).hexdigest()
    scores_digest = hashlib.sha256((tmp_path / "scores.json").read_bytes()).hexdigest()
    assert inputs["cross_encoder_scores_sha256"] == scores_digest
    skipped = {"not_in_current_set": 1, "failed": 1, "other_prompt_version": 2}
    assert inputs["llm_rows_skipped"] == skipped
    assert inputs["llm_rows_with_fingerprint"] == 0
    by_way = rag_demo_build.all_chunks(UNITS, FakeClient(), embedded)
    texts = {c.text for chunks in by_way.values() for c in chunks}
    assert [p["text"] for p in demo["passages"]] == list(
        dict.fromkeys(c.text for chunks in by_way.values() for c in chunks)
    )
    assert len(demo["questions"][0]["llm"]) == len(texts)
    out = capsys.readouterr().out
    assert "bỏ qua: 1 không thuộc tập hiện tại, 1 thất bại, 2 khác phiên bản prompt hiện tại" in out
    assert "Topic: lần gom cụm 7 (2026-11-10T11:30:00+00:00) · 0 / 1 bài có topic" in out
    assert "Đoạn Haiku giữ mà không trúng đáp án: 0" in out


def test_assemble_keeps_the_old_file_when_a_result_is_missing(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = stored_inputs(tmp_path, embedded)
    lines = results.read_text(encoding="utf-8").splitlines(keepends=True)
    results.write_text("".join(lines[:-1]), encoding="utf-8")
    old = tmp_path / "demo.json"
    old.write_text("bản cũ", encoding="utf-8")
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert "chưa có kết quả thành công" in capsys.readouterr().out
    assert old.read_text(encoding="utf-8") == "bản cũ"


def test_assemble_runs_every_check_before_writing(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored_inputs(tmp_path, embedded)
    # sửa câu hỏi sau khi chấm: file cặp cross-encoder không còn khớp code
    offline_main.setattr(rag_demo_build, "QUESTIONS", (replace(QUESTION, text="câu đã sửa"),))
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    out = capsys.readouterr().out
    assert "Chưa ghép được: 2 lỗi của lệnh check" in out
    assert EDITED_QUESTION in out
    assert not (tmp_path / "demo.json").exists()


def test_assemble_stops_on_scores_of_another_pairs_file(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored_inputs(tmp_path, embedded)
    scores = tmp_path / "scores.json"
    data = json.loads(scores.read_text(encoding="utf-8"))
    scores.write_text(json.dumps(data | {"pairs_digest": "0" * 64}), encoding="utf-8")
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert "file điểm thuộc một file cặp khác" in capsys.readouterr().out
    assert not (tmp_path / "demo.json").exists()


def test_demo_file_inside_a_git_tree_must_stay_under_data_rag_demo(tmp_path: Path) -> None:
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)  # checkout chính: .git là thư mục
    worktree = main / ".claude" / "worktrees" / "wt"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: ../../../.git/worktrees/wt", encoding="utf-8")
    private = rag_demo_build.out_is_private
    assert private(worktree / "data" / "rag_demo" / "demo.json")
    # chính thư mục thì không: file tạm sẽ là data/rag_demo.tmp
    assert not private(worktree / "data" / "rag_demo")
    # data/ không bị gitignore cả thư mục
    assert not private(worktree / "data" / "demo.json")
    assert not private(worktree / "src" / "dashboard" / "demo.json")
    # worktree nằm trong checkout chính: cây làm việc của checkout chính cũng bị chặn
    assert not private(main / "src" / "demo.json")
    assert private(main / "data" / "rag_demo" / "demo.json")
    assert private(tmp_path / "elsewhere" / "demo.json")


def test_assemble_refuses_a_public_path_before_writing_anything(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = REPO / "src" / "dashboard" / "public" / "rag-demo-test.json"
    argv = ["assemble", "--db", str(tmp_path / "x.db"), *isolated(tmp_path), "--out", str(target)]
    assert rag_demo_build.main(argv) == 1
    assert "ngoài data/" in capsys.readouterr().out
    assert not target.exists()


def test_assemble_without_sentence_vectors_stops_with_a_message(
    offline_main: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert "Chưa ghép được: 3 chữ chưa có vector trong cache" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("pairs", "trùng một file đầu vào"),
        ("scores", "trùng một file đầu vào"),
        ("llm-dir", "nằm trong thư mục kết quả Haiku"),
        ("results", "không phải .json"),
        ("not-json", "không phải .json"),
    ],
)
def test_assemble_never_overwrites_a_paid_input(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    target: str,
    reason: str,
) -> None:
    results = stored_inputs(tmp_path, embedded)
    paid = [results, tmp_path / "pairs.json", tmp_path / "scores.json"]
    out = {
        "pairs": paid[1],
        "scores": paid[2],
        "llm-dir": results.parent / "demo.json",
        "results": results,
        "not-json": tmp_path / "demo.jsonl",
    }[target]
    before = {p: p.read_bytes() for p in paid}
    argv = ["assemble", "--db", str(tmp_path / "x.db"), *isolated(tmp_path), "--out", str(out)]
    assert rag_demo_build.main(argv) == 1
    assert f"{out} {reason}" in capsys.readouterr().out
    assert {p: p.read_bytes() for p in paid} == before
    assert out in paid or not out.exists()


def test_assemble_stops_on_a_hand_edited_score_and_keeps_the_old_file(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = stored_inputs(tmp_path, embedded)
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    target = next(row for row in rows if row["job"] == "rerank")
    target["output"]["score"] = "3"  # sửa tay: chuỗi thay vì số
    results.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    old = tmp_path / "demo.json"
    old.write_text("bản cũ", encoding="utf-8")
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert "output sai dạng (điểm '3')" in capsys.readouterr().out
    assert old.read_text(encoding="utf-8") == "bản cũ"


def test_assemble_checks_the_pairs_bytes_it_actually_uses(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """File cặp đổi sau lần kiểm của `build_problems` (giả lập bằng cách bỏ qua lần kiểm đó)."""
    stored_inputs(tmp_path, embedded)
    offline_main.setattr(rag_demo_build, "build_problems", lambda *_: [])
    pairs = tmp_path / "pairs.json"
    pairs.write_bytes(pairs.read_bytes().replace(b"}]}", b'}], "x": 1}'))
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert "file cặp cross-encoder đổi giữa lúc kiểm và lúc ghép" in capsys.readouterr().out
    assert not (tmp_path / "demo.json").exists()


def test_assemble_never_overwrites_the_default_input_paths(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Đầu vào được trỏ chỗ khác (`isolated`), nhưng file mặc định vẫn là file đã trả tiền thật."""
    stored_inputs(tmp_path, embedded)
    offline_main.chdir(tmp_path)
    default = tmp_path / PAIRS_PATH
    default.parent.mkdir(parents=True)
    default.write_bytes(b"cap that")
    argv = ["assemble", "--db", "x.db", *isolated(tmp_path), "--out", PAIRS_PATH.as_posix()]
    assert rag_demo_build.main(argv) == 1
    assert "trùng một file đầu vào" in capsys.readouterr().out
    assert default.read_bytes() == b"cap that"


def test_a_results_row_missing_a_key_stops_instead_of_resubmitting(tmp_path: Path) -> None:
    """Dòng hỏng không được coi là "chưa xong": coi vậy thì llm-submit gửi lại và trả tiền."""
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"custom_id": "tf-q01", "job": "transform", "ok": True}) + "\n")
    with pytest.raises(KeyError):
        done_ids(results)


# --- publish (ADR-0037 D3 + ADR-0040 D3) ---


class Uploads:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    def __call__(self, pathname: str, body: bytes) -> None:
        self.calls.append((pathname, body))


def current_demo(**changes: object) -> bytes:
    """File demo tối thiểu khớp `UNITS` + bộ câu hỏi đang dùng (chỉ các trường publish kiểm)."""
    demo: dict[str, object] = {
        "format": 2,
        "units": [
            {
                "id": u.id,
                "sha256": content_hash(u.full_text),
                "month": "2026-10",
                "topic": {"id": None, "label_en": "Unclustered"},
            }
            for u in UNITS
        ],
        "provenance": {
            "question_texts_sha256": question_texts_sha256(QUESTIONS),
            "topics": {"cluster_run_id": 7, "cluster_run_at": "2026-11-10T11:30:00+00:00"},
            **code_provenance(),
        },
    }
    demo.update(changes)
    return json.dumps(demo).encode()


def test_publish_uploads_the_file_to_the_fixed_pathname(
    capsys: pytest.CaptureFixture[str],
) -> None:
    uploads, data = Uploads(), current_demo()
    assert rag_demo_build.run_publish(UNITS, data, [], uploads) == 0
    assert uploads.calls == [("rag-demo/common.json", data)]
    assert "Đã publish rag-demo/common.json" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("data", "live", "reason"),
    [
        (current_demo(), ["bài u1 đã bị xoá"], "live-check: bài u1 đã bị xoá"),
        (current_demo(format=3), [], "định dạng 3"),
        (current_demo(units=[{"id": "u1", "sha256": "cu"}]), [], "khác các bài đóng băng"),
        (current_demo(units=[]), [], "khác các bài đóng băng"),
        (current_demo(provenance={"question_texts_sha256": "cu"}), [], "chữ câu hỏi"),
        (current_demo(provenance=None), [], "chữ câu hỏi"),
        (
            current_demo(
                provenance={
                    "question_texts_sha256": question_texts_sha256(QUESTIONS),
                    **(code_provenance() | {"pending": []}),
                }
            ),
            [],
            "provenance khác code hiện tại (pending)",
        ),
        (
            current_demo(provenance={"question_texts_sha256": question_texts_sha256(QUESTIONS)}),
            [],
            "provenance khác code hiện tại (cosine_layout, cross_encoder",
        ),
        (b"<html>", [], "không phải JSON"),
        (b"[]", [], "không phải object"),
    ],
)
def test_publish_uploads_nothing_on_any_problem(
    data: bytes, live: list[str], reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    uploads = Uploads()
    assert rag_demo_build.run_publish(UNITS, data, live, uploads) == 1
    assert uploads.calls == []
    out = capsys.readouterr().out
    assert "bản công khai giữ nguyên" in out
    assert reason in out


def test_publish_refuses_a_file_at_the_size_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    data = current_demo()
    uploads = Uploads()
    monkeypatch.setattr(rag_demo_build, "DEMO_FILE_MAX_BYTES", len(data))
    assert rag_demo_build.run_publish(UNITS, data, [], uploads) == 1
    monkeypatch.setattr(rag_demo_build, "DEMO_FILE_MAX_BYTES", len(data) + 1)
    assert rag_demo_build.run_publish(UNITS, data, [], uploads) == 0
    assert len(uploads.calls) == 1


def test_a_freshly_assembled_file_passes_the_publish_checks(
    offline_main: pytest.MonkeyPatch, embedded: EmbeddingCache, tmp_path: Path
) -> None:
    stored_inputs(tmp_path, embedded)
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 0
    data = (tmp_path / "demo.json").read_bytes()
    assert rag_demo_build.publish_problems(UNITS, data) == []
    # đối chứng: cùng file, bài đổi chữ sau lần dựng → bị chặn
    edited = [replace(UNITS[0], full_text=UNITS[0].full_text + " sửa")]
    assert rag_demo_build.publish_problems(edited, data) != []


@pytest.fixture
def main_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Thư mục chính giả (`.git` là thư mục) có `.env` + file demo; `conftest` đã chặn tải thật."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    env = root / ".env"
    env.write_text("BLOB_READ_WRITE_TOKEN=vercel_blob_rw_test\n", encoding="utf-8")
    monkeypatch.setattr(publish_module, "REPO_ROOT", root)
    monkeypatch.setattr(publish_module, "ENV_FILE", env)
    demo = root / "demo.json"
    demo.write_bytes(current_demo())
    monkeypatch.setattr(rag_demo_build, "DEMO_PATH", demo)
    return root


def test_publish_wires_live_check_then_upload_with_the_env_token(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []

    def live(env_file: Path) -> dict[str, str]:
        seen.append(env_file)
        return {"u1": TEXT, "p1": TEXT}

    def upload(pathname: str, body: bytes, token: str, content_type: str) -> None:
        seen.append((pathname, token, content_type, body == current_demo()))

    monkeypatch.setattr(rag_demo_build, "fetch_live_texts", live)
    monkeypatch.setattr(publish_module, "vercel_upload", upload)
    assert rag_demo_build.main_publish(UNITS) == 0
    assert seen == [
        main_checkout / ".env",
        ("rag-demo/common.json", "vercel_blob_rw_test", "application/json", True),
    ]


def test_publish_stops_when_a_post_changed_on_threads(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        rag_demo_build, "fetch_live_texts", lambda env_file: {"u1": TEXT, "p1": "chữ khác"}
    )
    # `conftest` thay `vercel_upload` bằng hàm raise → lỡ tải là test lỗi
    assert rag_demo_build.main_publish(UNITS) == 1
    assert "live-check:" in capsys.readouterr().out


def _no_network(env_file: Path) -> dict[str, str]:
    pytest.fail("không được gọi Threads")


def test_publish_never_runs_from_a_worktree(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (main_checkout / ".git").rmdir()
    (main_checkout / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    monkeypatch.setattr(rag_demo_build, "fetch_live_texts", _no_network)
    assert rag_demo_build.main_publish(UNITS) == 2
    assert "worktree" in capsys.readouterr().err


def test_publish_needs_the_blob_token_before_any_network_call(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (main_checkout / ".env").write_text("OTHER=1\n", encoding="utf-8")
    monkeypatch.setattr(rag_demo_build, "fetch_live_texts", _no_network)
    assert rag_demo_build.main_publish(UNITS) == 2


def test_publish_without_an_assembled_file_stops(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (main_checkout / "demo.json").unlink()
    monkeypatch.setattr(rag_demo_build, "fetch_live_texts", _no_network)
    assert rag_demo_build.main_publish(UNITS) == 2


def test_publish_reads_the_file_from_the_repo_root_not_the_cwd(
    main_checkout: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "demo.json").write_bytes(b"file khac")
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(rag_demo_build, "DEMO_PATH", Path("demo.json"))
    monkeypatch.setattr(
        rag_demo_build, "fetch_live_texts", lambda env_file: {"u1": TEXT, "p1": TEXT}
    )
    seen: list[bytes] = []

    def upload(pathname: str, body: bytes, token: str, content_type: str) -> None:
        seen.append(body)

    monkeypatch.setattr(publish_module, "vercel_upload", upload)
    assert rag_demo_build.main_publish(UNITS) == 0
    assert seen == [current_demo()]


def test_assemble_stops_when_the_metadata_cannot_be_read(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored_inputs(tmp_path, embedded)

    def broken(*_: object) -> TopicSnapshot:
        raise MetadataError("u1: post mở đầu không có trong posts")

    offline_main.setattr(rag_demo_build, "read_unit_metadata", broken)
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert not (tmp_path / "demo.json").exists()
    out = capsys.readouterr().out
    assert "Chưa ghép được: MetadataError: u1: post mở đầu không có trong posts" in out


@pytest.mark.parametrize(
    "unit_change",
    [
        {"month": None},
        {"month": "2026-1"},
        {"month": "2026-13"},
        {"month": "２０２６-10"},  # chữ số toàn khổ: `\d` của Python khớp, `[0-9]` thì không
        {"topic": {"id": None, "label_en": "Jobs"}},  # id None chỉ đi với "Unclustered"
        {"topic": None},
        {"topic": {"id": None}},
        {"topic": {"id": None, "label_en": ""}},
        {"topic": {"id": 3, "label_en": "Jobs"}},
        # mỗi điều kiện một ca chỉ vi phạm đúng nó (ca vi phạm 2 điều kiện che mất một)
        {"topic": {"id": "topic_1", "label_en": ""}},
        {"topic": {"id": "topic_1", "label_en": 5}},
        {"topic": {"id": "topic_1", "label_en": "Jobs", "x": 1}},
    ],
)
def test_publish_refuses_a_unit_without_a_valid_month_or_topic(
    unit_change: dict[str, object],
) -> None:
    """Định dạng 2 (ADR-0041): bộ lọc metadata của trang cần tháng đăng + topic của mọi bài."""
    good = json.loads(current_demo())
    assert rag_demo_build.publish_problems(UNITS, json.dumps(good).encode()) == []
    units = [unit | unit_change for unit in good["units"]]
    data = current_demo(units=units)
    assert rag_demo_build.publish_problems(UNITS, data) == [
        "bài thiếu tháng đăng / topic: chạy lại assemble"
    ]


def test_publish_accepts_a_unit_with_a_real_topic() -> None:
    good = json.loads(current_demo())
    units = [u | {"topic": {"id": "topic_18", "label_en": "Renting"}} for u in good["units"]]
    assert rag_demo_build.publish_problems(UNITS, current_demo(units=units)) == []


@pytest.mark.parametrize(
    "topics",
    [
        {"cluster_run_id": 7, "cluster_run_at": "2026-11-10T11:30:00+00:00"},
        # DB chưa có lần gom cụm nào: assemble ghi cả hai None
        {"cluster_run_id": None, "cluster_run_at": None},
    ],
)
def test_publish_accepts_a_valid_topic_run(topics: dict[str, object]) -> None:
    good = json.loads(current_demo())
    provenance = good["provenance"] | {"topics": topics}
    assert rag_demo_build.publish_problems(UNITS, current_demo(provenance=provenance)) == []


@pytest.mark.parametrize(
    "topics",
    [
        "missing",
        None,
        # mỗi ca chỉ vi phạm đúng một điều kiện
        {"cluster_run_id": 7},
        {"cluster_run_id": "7", "cluster_run_at": "2026-11-10T11:30:00+00:00"},
        {"cluster_run_id": True, "cluster_run_at": "2026-11-10T11:30:00+00:00"},
        {"cluster_run_id": 7, "cluster_run_at": None},
        {"cluster_run_id": None, "cluster_run_at": "2026-11-10T11:30:00+00:00"},
        {"cluster_run_id": 7, "cluster_run_at": "2026-11-10", "x": 1},
    ],
)
def test_publish_refuses_a_file_without_a_valid_topic_run(topics: object) -> None:
    good = json.loads(current_demo())
    provenance = {k: v for k, v in good["provenance"].items() if k != "topics"}
    if topics != "missing":
        provenance["topics"] = topics
    assert rag_demo_build.publish_problems(UNITS, current_demo(provenance=provenance)) == [
        "provenance thiếu lần gom cụm của topic: chạy lại assemble"
    ]


def test_assemble_reports_a_locked_db_instead_of_a_traceback(
    offline_main: pytest.MonkeyPatch,
    embedded: EmbeddingCache,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored_inputs(tmp_path, embedded)

    def locked(*_: object) -> TopicSnapshot:
        raise sqlite3.OperationalError("database is locked")

    offline_main.setattr(rag_demo_build, "read_unit_metadata", locked)
    assert rag_demo_build.main(assemble_argv(tmp_path)) == 1
    assert not (tmp_path / "demo.json").exists()
    out = capsys.readouterr().out
    assert "Chưa ghép được: OperationalError: database is locked" in out


def test_publish_refuses_a_format_1_file() -> None:
    assert "định dạng 1 ≠ 2: chạy lại assemble" in rag_demo_build.publish_problems(
        UNITS, current_demo(format=1)
    )
