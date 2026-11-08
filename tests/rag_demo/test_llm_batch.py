"""Gửi / thu lô Haiku với API giả: không gửi trùng, ghi cả lỗi, kiểm theo đúng việc của request."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.rag_demo import llm_jobs
from src.rag_demo.llm_batch import collect, done_ids, read_rows, submit
from src.rag_demo.llm_jobs import PROMPT_VERSIONS, Job, LlmRequest, job_of, prompt_fingerprint

V_TRANSFORM = PROMPT_VERSIONS[Job.TRANSFORM]


def done_row(custom_id: str, ok: bool = True, version: str = V_TRANSFORM) -> str:
    return json.dumps(
        {
            "custom_id": custom_id,
            "job": job_of(custom_id).value,
            "ok": ok,
            "prompt_version": version,
        }
    )


@dataclass
class Block:
    type: str
    text: str = ""


@dataclass
class Usage:
    input_tokens: int = 100
    output_tokens: int = 20
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass
class Message:
    content: list[Block]
    stop_reason: str = "end_turn"
    model: str = "claude-haiku-5-5"
    usage: Usage = field(default_factory=Usage)


@dataclass
class Outcome:
    type: str
    message: Message | None = None


@dataclass
class Result:
    custom_id: str
    result: Outcome


@dataclass
class Batch:
    id: str
    processing_status: str = "ended"


@dataclass
class FakeBatches:
    status: str = "ended"
    results_list: list[Result] = field(default_factory=list)
    created: list[list[dict[str, Any]]] = field(default_factory=list)

    def create(self, *, requests: list[Any]) -> Batch:
        self.created.append(requests)
        return Batch("msgbatch_1")

    def retrieve(self, message_batch_id: str) -> Batch:
        assert message_batch_id == "msgbatch_1"
        return Batch(message_batch_id, self.status)

    def results(self, message_batch_id: str) -> list[Result]:
        return self.results_list


def ok(custom_id: str, payload: dict[str, Any], stop: str = "end_turn") -> Result:
    message = Message([Block("thinking"), Block("text", json.dumps(payload))], stop_reason=stop)
    return Result(custom_id, Outcome("succeeded", message))


TRANSFORM_OUTPUT: dict[str, Any] = {
    key: (["x"] if key.startswith(("multi_query", "decompose")) else "x")
    for key in (
        "rewrite",
        "rewrite_en",
        "expand",
        "expand_en",
        "hyde",
        "hyde_en",
        "multi_query",
        "multi_query_en",
        "decompose",
        "decompose_en",
        "step_back",
        "step_back_en",
    )
}


def test_collect_reports_cache_tokens_separately(tmp_path: Path) -> None:
    usage = Usage(input_tokens=10, output_tokens=5, cache_read_input_tokens=70)
    message = Message([Block("text", json.dumps(TRANSFORM_OUTPUT))], usage=usage)
    api = FakeBatches(results_list=[Result("tf-q01", Outcome("succeeded", message))])
    results = tmp_path / "r.jsonl"
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, results)
    report = collect(Job.TRANSFORM, api, tmp_path, results)
    assert (report.input_tokens, report.cache_read_tokens, report.cache_write_tokens) == (10, 70, 0)


def req(custom_id: str) -> LlmRequest:
    return LlmRequest(custom_id, job_of(custom_id), {"model": "m"})


def test_submit_skips_done_requests_and_records_the_batch(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text(
        done_row("tf-q01")
        + "\n"
        + done_row("tf-q02", ok=False)
        + "\n"
        + done_row("tf-q03", version="old")
        + "\n",
        encoding="utf-8",
    )
    api = FakeBatches()
    batch_id, count = submit(
        Job.TRANSFORM, [req("tf-q01"), req("tf-q02"), req("tf-q03")], api, tmp_path, results
    )
    assert (batch_id, count) == ("msgbatch_1", 2)
    assert [r["custom_id"] for r in api.created[0]] == ["tf-q02", "tf-q03"]
    state = json.loads((tmp_path / "batch_transform.json").read_text(encoding="utf-8"))
    assert state["batch_id"] == "msgbatch_1"
    assert state["prompt_versions"] == {"transform": V_TRANSFORM}


def test_submit_refuses_duplicate_ids_before_sending(tmp_path: Path) -> None:
    api = FakeBatches()
    with pytest.raises(ValueError, match="trùng"):
        submit(Job.TRANSFORM, [req("tf-q01"), req("tf-q01")], api, tmp_path, tmp_path / "r.jsonl")
    assert api.created == []
    assert not (tmp_path / "batch_transform.json").exists()


def test_collect_labels_rows_with_the_version_sent_not_the_current_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prompt đổi (phiên bản tăng) khi lô đang chạy: kết quả vẫn là của prompt cũ, nên mang nhãn cũ
    và lần gửi sau không coi nó là đã xong với prompt mới."""
    api = FakeBatches(results_list=[ok("tf-q01", TRANSFORM_OUTPUT)])
    results = tmp_path / "r.jsonl"
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, results)
    monkeypatch.setitem(llm_jobs.PROMPT_VERSIONS, Job.TRANSFORM, "new")  # llm_batch dùng chung dict
    collect(Job.TRANSFORM, api, tmp_path, results)
    row = json.loads(results.read_text(encoding="utf-8"))
    assert row["ok"] and row["prompt_version"] == V_TRANSFORM
    assert done_ids(results) == set()


def test_collect_rejects_a_result_of_a_job_that_was_not_sent(tmp_path: Path) -> None:
    api = FakeBatches(results_list=[ok("tr-aa", {"chunk_en": "x"})])
    results = tmp_path / "r.jsonl"
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, results)
    report = collect(Job.TRANSFORM, api, tmp_path, results)
    assert report.failed == 1
    assert "không có trong lô" in json.loads(results.read_text(encoding="utf-8"))["error"]


def test_collect_stops_when_a_rerank_chunk_cannot_be_rebuilt(tmp_path: Path) -> None:
    """Chunk đổi từ lúc gửi: ghi thành dòng lỗi thì lần gửi sau trả tiền lại → dừng, không ghi."""
    api = FakeBatches(results_list=[ok("rr-q01-aa", {"score": 3, "quote": "x", "quote_en": "x"})])
    results = tmp_path / "r.jsonl"
    submit(Job.RERANK, [req("rr-q01-aa")], api, tmp_path, results)
    no_passages: dict[str, str] = {}
    with pytest.raises(RuntimeError, match="không tìm được chữ chunk"):
        collect(Job.RERANK, api, tmp_path, results, no_passages.get)
    assert not results.exists()
    assert (tmp_path / "batch_rerank.json").exists()  # thu lại được sau khi dựng đúng chunk
    collect(Job.RERANK, api, tmp_path, results, {"rr-q01-aa": "x y"}.get)
    assert done_ids(results) == {"rr-q01-aa"}


def test_submit_refuses_while_a_batch_is_waiting(tmp_path: Path) -> None:
    api = FakeBatches()
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, tmp_path / "r.jsonl")
    with pytest.raises(RuntimeError):
        submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, tmp_path / "r.jsonl")
    assert len(api.created) == 1


def test_submit_with_nothing_left_sends_nothing(tmp_path: Path) -> None:
    results = tmp_path / "r.jsonl"
    results.write_text(done_row("tf-q01") + "\n", encoding="utf-8")
    api = FakeBatches()
    assert submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, results) == (None, 0)
    assert api.created == []


def test_collect_waits_while_the_batch_runs(tmp_path: Path) -> None:
    api = FakeBatches(status="in_progress")
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, tmp_path / "r.jsonl")
    report = collect(Job.TRANSFORM, api, tmp_path, tmp_path / "r.jsonl")
    assert report.status == "in_progress"
    assert (tmp_path / "batch_transform.json").exists()
    assert not (tmp_path / "r.jsonl").exists()


def test_collect_checks_each_request_by_its_own_job_and_records_failures(tmp_path: Path) -> None:
    passage = "Chủ nhà phải bật sưởi."
    api = FakeBatches(
        results_list=[
            ok("tr-aa", {"chunk_en": "The post."}),  # lô context có cả request dịch
            ok("cx-bb", {"context": "ngữ cảnh", "context_en": "context", "chunk_en": "chunk"}),
            ok("rr-q01-cc", {"score": 3, "quote": "bật sưởi", "quote_en": "heating"}),
            ok("cx-dd", {"context": "x"}, stop="max_tokens"),
            Result("cx-ee", Outcome("errored")),
            ok("cx-ff", {"wrong": 1}),
        ]
    )
    results = tmp_path / "r.jsonl"
    sent = ["tr-aa", "cx-bb", "rr-q01-cc", "cx-dd", "cx-ee", "cx-ff"]
    submit(Job.CONTEXT, [req(custom_id) for custom_id in sent], api, tmp_path, results)
    report = collect(Job.CONTEXT, api, tmp_path, results, {"rr-q01-cc": passage}.get)
    assert (report.succeeded, report.failed) == (3, 3)
    assert (report.input_tokens, report.output_tokens) == (500, 100)  # 5 kết quả có usage
    rows = {
        row["custom_id"]: row
        for row in map(json.loads, results.read_text(encoding="utf-8").splitlines())
    }
    assert rows["tr-aa"]["job"] == "translate"
    assert rows["rr-q01-cc"]["output"]["keep"] is True
    assert rows["cx-dd"]["error"] == "stop_reason max_tokens"
    assert rows["cx-ee"]["error"] == "batch result errored"
    assert not rows["cx-ff"]["ok"]
    assert not (tmp_path / "batch_context.json").exists()
    # request lỗi chưa tính là xong: lần gửi sau sẽ gửi lại
    assert done_ids(results) == {"tr-aa", "cx-bb", "rr-q01-cc"}


class CrashingBatches(FakeBatches):
    """`create` lỗi sau khi lô có thể đã được tạo phía server (mất phản hồi)."""

    def create(self, *, requests: list[Any]) -> Batch:
        self.created.append(requests)
        raise TimeoutError("no response")


def test_a_crash_while_creating_blocks_every_later_submit_and_collect(tmp_path: Path) -> None:
    api = CrashingBatches()
    with pytest.raises(TimeoutError):
        submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, tmp_path / "r.jsonl")
    state = json.loads((tmp_path / "batch_transform.json").read_text(encoding="utf-8"))
    assert state["batch_id"] is None  # file trạng thái đã ghi TRƯỚC khi gọi create
    with pytest.raises(RuntimeError, match="Console"):
        submit(Job.TRANSFORM, [req("tf-q01")], FakeBatches(), tmp_path, tmp_path / "r.jsonl")
    with pytest.raises(RuntimeError, match="Console"):
        collect(Job.TRANSFORM, FakeBatches(), tmp_path, tmp_path / "r.jsonl")
    assert len(api.created) == 1


def test_rows_carry_the_batch_id_and_the_fingerprint_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = FakeBatches(results_list=[ok("tf-q01", TRANSFORM_OUTPUT)])
    results = tmp_path / "r.jsonl"
    sent_fingerprint = prompt_fingerprint(Job.TRANSFORM)
    submit(Job.TRANSFORM, [req("tf-q01")], api, tmp_path, results)
    monkeypatch.setattr(llm_jobs, "MAX_TOKENS", 1)  # request đổi giữa lúc gửi và lúc thu
    assert prompt_fingerprint(Job.TRANSFORM) != sent_fingerprint
    collect(Job.TRANSFORM, api, tmp_path, results)
    row = json.loads(results.read_text(encoding="utf-8"))
    assert row["batch_id"] == "msgbatch_1"
    assert row["prompt_fingerprint"] == sent_fingerprint


def test_rows_keep_the_raw_output_before_normalising(tmp_path: Path) -> None:
    """Câu trích bị bỏ ở `output` nhưng còn nguyên ở `raw`: đổi luật hậu kiểm vẫn áp lại được."""
    raw = {"score": 1, "quote": "bật sưởi", "quote_en": "heating"}
    api = FakeBatches(results_list=[ok("rr-q01-aa", raw)])
    results = tmp_path / "r.jsonl"
    submit(Job.RERANK, [req("rr-q01-aa")], api, tmp_path, results)
    collect(Job.RERANK, api, tmp_path, results, {"rr-q01-aa": "Phải bật sưởi."}.get)
    row = json.loads(results.read_text(encoding="utf-8"))
    assert row["output"]["quote"] == ""
    assert row["raw"] == raw


def test_collecting_again_after_a_crash_does_not_duplicate_rows(tmp_path: Path) -> None:
    api = FakeBatches(results_list=[ok("tf-q01", TRANSFORM_OUTPUT), ok("tf-q02", TRANSFORM_OUTPUT)])
    results = tmp_path / "r.jsonl"
    submit(Job.TRANSFORM, [req("tf-q01"), req("tf-q02")], api, tmp_path, results)
    state = (tmp_path / "batch_transform.json").read_text(encoding="utf-8")
    collect(Job.TRANSFORM, api, tmp_path, results)
    (tmp_path / "batch_transform.json").write_text(state, encoding="utf-8")  # chết trước unlink
    collect(Job.TRANSFORM, api, tmp_path, results)
    ids = [row["custom_id"] for row in read_rows(results)]
    assert sorted(ids) == ["tf-q01", "tf-q02"]


def test_a_half_written_last_result_line_is_skipped_then_cut_before_appending(
    tmp_path: Path,
) -> None:
    results = tmp_path / "r.jsonl"
    results.write_text(done_row("tf-q01") + "\n" + done_row("tf-q02")[:15], encoding="utf-8")
    assert done_ids(results) == {"tf-q01"}
    api = FakeBatches(results_list=[ok("tf-q02", TRANSFORM_OUTPUT)])
    submit(Job.TRANSFORM, [req("tf-q01"), req("tf-q02")], api, tmp_path, results)
    collect(Job.TRANSFORM, api, tmp_path, results)
    assert [row["custom_id"] for row in read_rows(results)] == ["tf-q01", "tf-q02"]
    assert done_ids(results) == {"tf-q01", "tf-q02"}


def test_a_last_line_cut_inside_a_multibyte_character_is_recovered(tmp_path: Path) -> None:
    """Dòng ghi với ensure_ascii=False: chết giữa ký tự "ậ" (3 byte UTF-8) thì phần dở không
    decode được — vẫn phải bỏ qua khi đọc và cắt trước khi ghi thêm."""
    results = tmp_path / "r.jsonl"
    vietnamese = json.dumps({"custom_id": "tf-q02", "note": "ngữ cảnh bậc"}, ensure_ascii=False)
    raw = vietnamese.encode("utf-8")
    cut = raw[: raw.index("ậ".encode()) + 1]  # dừng sau byte đầu của "ậ"
    results.write_bytes((done_row("tf-q01") + "\n").encode() + cut)
    assert done_ids(results) == {"tf-q01"}
    api = FakeBatches(results_list=[ok("tf-q02", TRANSFORM_OUTPUT)])
    submit(Job.TRANSFORM, [req("tf-q01"), req("tf-q02")], api, tmp_path, results)
    collect(Job.TRANSFORM, api, tmp_path, results)
    assert [row["custom_id"] for row in read_rows(results)] == ["tf-q01", "tf-q02"]


def test_a_complete_last_result_line_without_newline_gets_one_before_appending(
    tmp_path: Path,
) -> None:
    results = tmp_path / "r.jsonl"
    results.write_text(done_row("tf-q01"), encoding="utf-8")  # đủ JSON, mất "\n" cuối
    api = FakeBatches(results_list=[ok("tf-q02", TRANSFORM_OUTPUT)])
    submit(Job.TRANSFORM, [req("tf-q01"), req("tf-q02")], api, tmp_path, results)
    collect(Job.TRANSFORM, api, tmp_path, results)
    assert [row["custom_id"] for row in read_rows(results)] == ["tf-q01", "tf-q02"]


def test_a_broken_result_line_in_the_middle_is_an_error(tmp_path: Path) -> None:
    results = tmp_path / "r.jsonl"
    results.write_text(done_row("tf-q01")[:15] + "\n" + done_row("tf-q02") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dòng 1"):
        done_ids(results)


def test_collect_without_a_waiting_batch_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        collect(Job.RERANK, FakeBatches(), tmp_path, tmp_path / "r.jsonl")
