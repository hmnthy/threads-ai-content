"""Gửi và thu lô Message Batches cho các vai Haiku của demo RAG (Thy chốt C3 A 2026-11-07).

Batch API rẻ hơn 50%, chạy nền (thường dưới 1 giờ, tối đa 24 giờ). Để không trả tiền hai lần:
- request đã có kết quả thành công trong file kết quả thì không gửi lại;
- file trạng thái được ghi TRƯỚC khi tạo lô (chưa có mã lô), rồi điền mã lô sau: chết giữa hai
  bước thì file "chưa có mã" chặn mọi lần gửi sau cho tới khi người chạy xem Console;
- gọi `submit` lần nữa khi lô chưa thu thì từ chối;
- thu lại một lô đã ghi (chết trước khi xoá file trạng thái) không ghi trùng dòng.
Mỗi dòng kết quả mang mã lô, phiên bản prompt và dấu vân tay request của LÚC GỬI.

Client được đưa từ ngoài vào (`anthropic.Anthropic().messages.batches` khi chạy thật, client giả
trong test). Module không đọc khoá, không in chữ bài.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.rag_demo.llm_jobs import (
    PROMPT_VERSIONS,
    Job,
    LlmRequest,
    check_output,
    job_of,
    parse_text,
    prompt_fingerprint,
)


class BatchApi(Protocol):
    """Phần của `client.messages.batches` mà module dùng."""

    def create(self, *, requests: list[Any]) -> Any: ...

    def retrieve(self, message_batch_id: str) -> Any: ...

    def results(self, message_batch_id: str) -> Iterable[Any]: ...


@dataclass(frozen=True)
class CollectReport:
    status: str
    succeeded: int
    failed: int
    input_tokens: int  # phần vào không qua cache
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0


def _state_path(state_dir: Path, job: Job) -> Path:
    return state_dir / f"batch_{job.value}.json"


def read_rows(results_path: Path) -> list[dict[str, Any]]:
    """Các dòng của file kết quả. Dòng cuối ghi dở (chết giữa lúc ghi) bị bỏ qua; dòng hỏng ở giữa
    là lỗi thật → `ValueError`."""
    if not results_path.exists():
        return []
    # Đọc theo byte: dòng ghi với ensure_ascii=False, chết giữa một ký tự nhiều byte thì decode cả
    # file sẽ lỗi trước khi tới bước bỏ dòng dở. json.loads(bytes) ném UnicodeDecodeError hoặc
    # JSONDecodeError, cả hai là ValueError.
    lines = results_path.read_bytes().split(b"\n")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            if number != len(lines):
                raise ValueError(f"{results_path}: dòng {number} hỏng") from None
    return rows


def _prepare_append(results_path: Path) -> None:
    """Ngay trước khi ghi thêm: cắt dòng cuối ghi dở, hoặc thêm `\\n` còn thiếu, để dòng mới không
    dính vào dòng cũ."""
    if not results_path.exists():
        return
    data = results_path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    last = data.rsplit(b"\n", 1)[-1]
    try:
        json.loads(last)
    except ValueError:  # JSON dở hoặc cắt giữa một ký tự UTF-8
        # truncate tại chỗ, không ghi lại cả file: chết giữa chừng thì phần trước vẫn còn
        with results_path.open("r+b") as file:
            file.truncate(len(data) - len(last))
        return
    with results_path.open("ab") as file:
        file.write(b"\n")


def done_ids(results_path: Path) -> set[str]:
    """custom_id đã có kết quả thành công với đúng phiên bản prompt hiện tại của việc đó."""
    return {
        row["custom_id"]
        for row in read_rows(results_path)
        if row["ok"] and row["prompt_version"] == PROMPT_VERSIONS[Job(row["job"])]
    }


_PENDING = (
    "lô {job} có thể đã được tạo nhưng chưa ghi được mã lô ({state}). Xem Console "
    "(console.anthropic.com → Batches): có lô thì điền `batch_id` vào file này rồi chạy collect; "
    "không có thì xoá file rồi gửi lại."
)


def submit(
    job: Job, requests: Sequence[LlmRequest], api: BatchApi, state_dir: Path, results_path: Path
) -> tuple[str | None, int]:
    """Gửi một lô gồm các request chưa có kết quả.

    Trả (mã lô, số request); hết việc thì (None, 0)."""
    state = _state_path(state_dir, job)
    if state.exists():
        if json.loads(state.read_text(encoding="utf-8")).get("batch_id") is None:
            raise RuntimeError(_PENDING.format(job=job.value, state=state))
        raise RuntimeError(f"lô {job.value} đã gửi và chưa thu ({state}); chạy collect trước")
    done = done_ids(results_path)
    todo = [r for r in requests if r.custom_id not in done]
    if not todo:
        return None, 0
    if len({r.custom_id for r in todo}) != len(todo):
        raise ValueError("custom_id trùng trong một lô")
    jobs = {r.job for r in todo}
    sent: dict[str, Any] = {
        "batch_id": None,  # điền sau khi `create` trả về
        "job": job.value,
        # phiên bản + dấu vân tay của LÚC GỬI, theo từng việc có trong lô (lô context chứa cả
        # request dịch): `collect` gắn nhãn kết quả bằng các giá trị này, không bằng hằng số lúc thu
        "prompt_versions": {j.value: PROMPT_VERSIONS[j] for j in jobs},
        "prompt_fingerprints": {j.value: prompt_fingerprint(j) for j in jobs},
        "n": len(todo),
    }
    state_dir.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(sent), encoding="utf-8")
    batch = api.create(requests=[{"custom_id": r.custom_id, "params": r.params} for r in todo])
    state.write_text(json.dumps(sent | {"batch_id": str(batch.id)}), encoding="utf-8")
    return str(batch.id), len(todo)


def _row(
    custom_id: str,
    result: Any,
    passage_of: Callable[[str], str | None],
    sent: dict[str, Any],
) -> dict[str, Any]:
    job = job_of(custom_id)
    version = sent["prompt_versions"].get(job.value)
    row: dict[str, Any] = {
        "custom_id": custom_id,
        "job": job.value,
        "batch_id": sent["batch_id"],
        "prompt_version": version,
        "prompt_fingerprint": sent["prompt_fingerprints"].get(job.value),
    }
    if version is None:
        return row | {"ok": False, "error": f"việc {job.value} không có trong lô đã gửi"}
    outcome = result.result
    if outcome.type != "succeeded":
        return row | {"ok": False, "error": f"batch result {outcome.type}"}
    message = outcome.message
    usage = message.usage
    row |= {
        "model": message.model,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
        },
    }
    if message.stop_reason != "end_turn":
        return row | {"ok": False, "error": f"stop_reason {message.stop_reason}"}
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        return row | {"ok": False, "error": "không có khối text"}
    try:
        raw = parse_text(text)
    except ValueError as error:
        return row | {"ok": False, "error": str(error)}
    # Lưu output thô trước mọi bước chuẩn hoá: kết quả đã trả tiền, chạy lại không ra y hệt, nên
    # đổi luật hậu kiểm sau này (mức giữ, cách so nguyên văn) phải áp lại được trên chính bản thô.
    row["raw"] = raw
    try:
        output = check_output(job, dict(raw), passage_of(custom_id))
    except ValueError as error:
        return row | {"ok": False, "error": str(error)}
    return row | {"ok": True, "output": output}


def collect(
    job: Job,
    api: BatchApi,
    state_dir: Path,
    results_path: Path,
    passage_of: Callable[[str], str | None] = lambda _: None,
) -> CollectReport:
    """Lô chưa xong thì chỉ báo trạng thái. Xong thì ghi từng kết quả (kể cả lỗi) rồi xoá file
    trạng thái; request lỗi sẽ được `submit` lần sau gửi lại."""
    state = _state_path(state_dir, job)
    if not state.exists():
        raise RuntimeError(f"không có lô {job.value} nào đang chờ")
    sent = json.loads(state.read_text(encoding="utf-8"))
    batch_id = sent["batch_id"]
    if batch_id is None:
        raise RuntimeError(_PENDING.format(job=job.value, state=state))
    batch = api.retrieve(batch_id)
    if batch.processing_status != "ended":
        return CollectReport(str(batch.processing_status), 0, 0, 0, 0)

    results = list(api.results(batch_id))
    # chunk của lúc gửi không dựng lại được (cache vector đổi → chunk semantic đổi): ghi thành dòng
    # lỗi sẽ khiến `submit` sau gửi lại và trả tiền lại kết quả đã có → dừng, giữ file trạng thái
    lost = [
        r.custom_id
        for r in results
        if job_of(r.custom_id) is Job.RERANK and passage_of(r.custom_id) is None
    ]
    if lost:
        raise RuntimeError(
            f"{len(lost)} kết quả rerank không tìm được chữ chunk lúc gửi (chunk đã đổi?): "
            "chưa ghi gì, file trạng thái giữ nguyên; dựng lại đúng chunk rồi thu lại"
        )
    rows = [_row(result.custom_id, result, passage_of, sent) for result in results]
    # lần thu trước đã ghi (một phần) lô này rồi chết trước khi xoá file trạng thái: không ghi lại
    written = {r["custom_id"] for r in read_rows(results_path) if r.get("batch_id") == batch_id}
    results_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_append(results_path)
    with results_path.open("a", encoding="utf-8") as file:
        for row in rows:
            if row["custom_id"] not in written:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
    state.unlink()
    usages = [row["usage"] for row in rows if "usage" in row]
    return CollectReport(
        status="ended",
        succeeded=sum(1 for row in rows if row["ok"]),
        failed=sum(1 for row in rows if not row["ok"]),
        input_tokens=sum(u["input_tokens"] for u in usages),
        output_tokens=sum(u["output_tokens"] for u in usages),
        cache_write_tokens=sum(u["cache_creation_input_tokens"] for u in usages),
        cache_read_tokens=sum(u["cache_read_input_tokens"] for u in usages),
    )
