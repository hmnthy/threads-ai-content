"""Các vai Claude Haiku 5.5 của demo RAG (ADR-0037 D7, D8): dựng request, kiểm kết quả.

Ba việc, prompt Thy duyệt 2026-11-07 (đổi chữ prompt thì tăng phiên bản của việc đó trong
`PROMPT_VERSIONS`):
- `context`: câu ngữ cảnh cho mỗi chunk + bản tiếng Anh của câu đó và của chunk (contextual
  chunking, phỏng theo prompt Anthropic công bố:
  https://www.anthropic.com/news/contextual-retrieval). Cách "không chia" chỉ lấy bản dịch
  (`translate`), vì chunk đã là cả bài (ADR-0039 D2).
- `transform`: 6 cách biến đổi câu hỏi, viết bằng tiếng Việt (ngôn ngữ của bài), kèm tiếng Anh.
- `rerank`: chấm từng cặp câu hỏi gốc × chunk (Thy chốt C4 A), thang 0–3 có định nghĩa (C1 A),
  câu trích phải là chuỗi con nguyên văn của chunk, sai thì bỏ (ADR-0037 D8).

Module chỉ dựng tham số request và kiểm output, không gọi mạng; việc gửi lô nằm ở `llm_batch.py`.
Haiku 5.5 không nhận `temperature` khác mặc định, nên chạy lại có thể ra kết quả khác: kết quả được
lưu kèm model + phiên bản prompt và không tự chạy lại.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.rag_demo.chunking import Chunk
from src.rag_demo.corpus import Unit
from src.rag_demo.questions import Question

LLM_MODEL = "claude-haiku-5-5"  # ADR-0037 D7
EFFORT = "low"  # Thy chốt C2 A 2026-11-07: bật suy nghĩ ở mức thấp
# Trần token ra mỗi lần gọi, gồm cả phần suy nghĩ. Lựa chọn thiết kế: đủ rộng để JSON không bị cắt;
# tiền tính theo token thật, không theo trần.
MAX_TOKENS = 4096
# Giá Haiku 5.5 theo bảng của skill claude-api (cache 2026-10-06), USD / 1 triệu token, prompt
# ≤ 100K token; Batch API giảm 50% trên mọi token, kể cả token cache (skill claude-api,
# shared/cost-optimization.md). Token ghi cache (TTL 5 phút, mặc định của
# `cache_control: ephemeral`) tính ×1,25 giá vào, token đọc cache ×0,1 (shared/evals/build-eval.md).
PRICE_IN_PER_MILLION = 0.10
PRICE_OUT_PER_MILLION = 0.50
BATCH_DISCOUNT = 0.5
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.1
# Mức "giữ" của rerank: điểm ≥ 2 (thang 0–3). Lựa chọn thiết kế, Thy chốt C1 A 2026-11-07.
RERANK_KEEP_MIN_SCORE = 2


class Job(StrEnum):
    CONTEXT = "context"
    TRANSLATE = "translate"
    TRANSFORM = "transform"
    RERANK = "rerank"


@dataclass(frozen=True)
class LlmRequest:
    custom_id: str
    job: Job
    params: dict[str, Any]


def _digest(*parts: str) -> str:
    """16 ký tự hex: custom_id của Batch API chỉ nhận [a-zA-Z0-9_-], tối đa 64 ký tự."""
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
_STRINGS = {"type": "array", "items": _STRING}

SCHEMAS: dict[Job, dict[str, Any]] = {
    Job.CONTEXT: _object_schema({"context": _STRING, "context_en": _STRING, "chunk_en": _STRING}),
    Job.TRANSLATE: _object_schema({"chunk_en": _STRING}),
    Job.TRANSFORM: _object_schema(
        {
            "rewrite": _STRING,
            "rewrite_en": _STRING,
            "expand": _STRING,
            "expand_en": _STRING,
            "hyde": _STRING,
            "hyde_en": _STRING,
            "multi_query": _STRINGS,
            "multi_query_en": _STRINGS,
            "decompose": _STRINGS,
            "decompose_en": _STRINGS,
            "step_back": _STRING,
            "step_back_en": _STRING,
        }
    ),
    Job.RERANK: _object_schema(
        {"score": {"type": "integer", "enum": [0, 1, 2, 3]}, "quote": _STRING, "quote_en": _STRING}
    ),
}

CONTEXT_SYSTEM = (
    "You add search context to one chunk of a Threads post by a Vietnamese creator living in "
    "France.\n<document>{document}</document>"
)
CONTEXT_USER = (
    "Here is the chunk we want to situate within the whole document:\n<chunk>{chunk}</chunk>\n"
    "Give a short, succinct context (1–2 sentences) to situate this chunk within the overall "
    "document for the purposes of improving search retrieval of the chunk. Write it in the "
    "language of the document. Do not add facts that are not in the document.\n"
    'Return JSON: {{"context": ..., "context_en": English translation of the context, '
    '"chunk_en": faithful English translation of the chunk}}'
)
TRANSLATE_USER = (
    "Translate this Threads post by a Vietnamese creator living in France into English, "
    "faithfully.\n<document>{document}</document>\n"
    'Return JSON: {{"chunk_en": the English translation}}'
)
TRANSFORM_SYSTEM = (
    "You help a search engine find passages in a small collection of Vietnamese Threads posts "
    "(life, studies and work as a Vietnamese person in France). Given a user question, write "
    "search text in Vietnamese, whatever the language of the question. Return JSON with:\n"
    "- rewrite: one clear, self-contained search query\n"
    "- expand: the question plus synonyms and related terms (Vietnamese, French or English) the "
    "posts might use\n"
    "- hyde: a short hypothetical passage (2–4 sentences) written like a Threads post that would "
    "answer the question; it is only used for searching and may be wrong\n"
    "- multi_query: 3 different phrasings\n"
    "- decompose: 1–3 self-contained sub-questions (1 if it is already a single question)\n"
    "- step_back: one broader question about the general topic\n"
    "For every text also give an English translation (fields ending in _en)."
)
RERANK_SYSTEM = (
    "You judge whether a passage from a Vietnamese Threads post answers a user's question."
)
RERANK_USER = (
    "<question>{question}</question>\n<passage>{passage}</passage>\n"
    "Score: 0 = not about the question's topic · 1 = same topic but does not help answer · "
    "2 = partly answers · 3 = answers the question directly.\n"
    "Copy the shortest span of the passage that supports your score exactly as written, "
    "character for character; leave it empty if the score is 0 or 1. Give an English "
    "translation of that span.\n"
    'Return JSON: {{"score": 0-3, "quote": "...", "quote_en": "..."}}'
)


# Phiên bản prompt riêng cho từng việc: đổi prompt của một việc chỉ làm việc đó chạy lại (Haiku
# không khoá được temperature, nên chạy lại là ra output khác và trả tiền lại). Đổi bất cứ gì đi vào
# request của một việc (chữ prompt, schema, model, effort, trần token, cách dựng) → tăng phiên bản
# của việc đó; test ghim `prompt_fingerprint` theo từng phiên bản nên quên tăng thì test đỏ.
PROMPT_VERSIONS: dict[Job, str] = {
    Job.CONTEXT: "2026-11-07.1",
    Job.TRANSLATE: "2026-11-07.1",
    Job.TRANSFORM: "2026-11-07.1",
    Job.RERANK: "2026-11-07.1",
}


def prompt_fingerprint(job: Job) -> str:
    """sha256 của tham số request thật mà việc đó gửi đi, dựng từ một đầu vào giả cố định.

    Băm cả request (model, trần token, effort, schema, system, cách ghép chữ vào prompt,
    `cache_control`) chứ không chỉ các hằng chữ: sửa cách dựng request cũng đổi output."""
    from src.rag_demo.questions import AnswerRule

    unit = Unit(id="fp", full_text="Một. Hai.", posts=())
    part, whole = Chunk(0, "fp", 0, 4, "Một."), Chunk(1, "fp", 0, 9, "Một. Hai.")
    question = Question(1, "câu hỏi", "question", AnswerRule.NONE, ())
    built = {
        Job.CONTEXT: context_requests([unit], [part]),
        Job.TRANSLATE: context_requests([unit], [whole]),
        Job.TRANSFORM: transform_requests([question]),
        Job.RERANK: rerank_requests([question], [part]),
    }[job]
    (request,) = built
    if request.job is not job:
        raise AssertionError(f"đầu vào giả của {job} dựng ra việc {request.job}")
    payload = json.dumps(request.params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _params(
    job: Job, user: str, system: list[dict[str, Any]] | str | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "output_config": {
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": SCHEMAS[job]},
        },
        "messages": [{"role": "user", "content": user}],
    }
    if system is not None:
        params["system"] = system
    return params


def context_requests(units: Sequence[Unit], chunks: Sequence[Chunk]) -> list[LlmRequest]:
    """Một request cho mỗi chunk khác nhau trong cùng bài; chunk là cả bài thì chỉ dịch.

    Bài đặt trong system có `cache_control`: các chunk cùng bài dùng chung tiền tố. Bài dưới mức tối
    thiểu để cache (512 token với Haiku 5.5) thì không cache, không lỗi."""
    by_id = {unit.id: unit for unit in units}
    requests: dict[str, LlmRequest] = {}
    for chunk in chunks:
        document = by_id[chunk.unit_id].full_text
        if chunk.text == document.strip():
            custom_id = f"tr-{_digest(chunk.unit_id, chunk.text)}"
            request = LlmRequest(
                custom_id,
                Job.TRANSLATE,
                _params(Job.TRANSLATE, TRANSLATE_USER.format(document=document)),
            )
        else:
            custom_id = f"cx-{_digest(chunk.unit_id, chunk.text)}"
            system = [
                {
                    "type": "text",
                    "text": CONTEXT_SYSTEM.format(document=document),
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            request = LlmRequest(
                custom_id,
                Job.CONTEXT,
                _params(Job.CONTEXT, CONTEXT_USER.format(chunk=chunk.text), system),
            )
        requests.setdefault(custom_id, request)
    return list(requests.values())


def transform_requests(questions: Sequence[Question]) -> list[LlmRequest]:
    return [
        LlmRequest(
            f"tf-q{q.number:02d}", Job.TRANSFORM, _params(Job.TRANSFORM, q.text, TRANSFORM_SYSTEM)
        )
        for q in questions
    ]


def rerank_id(question: Question, chunk_text: str) -> str:
    return f"rr-q{question.number:02d}-{_digest(chunk_text)}"


def rerank_requests(questions: Sequence[Question], chunks: Sequence[Chunk]) -> list[LlmRequest]:
    """Mọi cặp câu hỏi gốc × chữ chunk khác nhau.

    Chunk trùng chữ giữa các cách chia chỉ chấm một lần."""
    texts = list(dict.fromkeys(chunk.text for chunk in chunks))
    return [
        LlmRequest(
            rerank_id(q, text),
            Job.RERANK,
            _params(Job.RERANK, RERANK_USER.format(question=q.text, passage=text), RERANK_SYSTEM),
        )
        for q in questions
        for text in texts
    ]


def check_output(job: Job, output: dict[str, Any], passage: str | None = None) -> dict[str, Any]:
    """Kiểm output đã parse; trả bản đã chuẩn hoá. Lỗi cấu trúc → `ValueError`.

    Rerank: điểm ngoài 0–3 là lỗi; câu trích không phải chuỗi con nguyên văn của chunk thì bỏ câu
    trích (giữ điểm) và ghi `quote_dropped` (ADR-0037 D8); điểm 0–1 không mang câu trích (cũng ghi
    `quote_dropped` nếu model vẫn trả câu trích — lý do tách bằng `quote_drop_reason`)."""
    properties = SCHEMAS[job]["properties"]
    if set(output) != set(properties):
        raise ValueError(f"{job}: khoá {sorted(output)} khác {sorted(properties)}")
    for key, schema in properties.items():
        value = output[key]
        if schema["type"] == "string" and not isinstance(value, str):
            raise ValueError(f"{job}: {key} không phải chuỗi")
        if schema["type"] == "array" and not (
            isinstance(value, list) and all(isinstance(item, str) for item in value)
        ):
            raise ValueError(f"{job}: {key} không phải danh sách chuỗi")
    if job is not Job.RERANK:
        return output
    if passage is None:
        raise ValueError("rerank cần chữ chunk để kiểm câu trích")
    score = output["score"]
    if not isinstance(score, int) or isinstance(score, bool) or score not in (0, 1, 2, 3):
        raise ValueError(f"điểm rerank ngoài thang 0–3: {score!r}")
    quote, quote_en = output["quote"], output["quote_en"]
    dropped = bool(quote) and (score < RERANK_KEEP_MIN_SCORE or quote not in passage)
    if dropped or not quote:
        quote, quote_en = "", ""
    return {
        "score": score,
        "keep": score >= RERANK_KEEP_MIN_SCORE,
        "quote": quote,
        "quote_en": quote_en,
        "quote_dropped": dropped,
    }


def quote_drop_reason(output: dict[str, Any]) -> str:
    """Vì sao câu trích của một output rerank đã chuẩn hoá bị bỏ: "" (không bỏ), "low_score" (điểm
    0–1 mà model vẫn trả câu trích — đúng luật, không phải lỗi), "not_verbatim" (điểm ≥ 2 nhưng câu
    trích không phải chuỗi con nguyên văn — lỗi bịa chữ ADR-0037 D8 muốn bắt). Suy được từ điểm vì
    điểm 0–1 luôn bỏ câu trích trước khi kiểm nguyên văn."""
    if not output["quote_dropped"]:
        return ""
    return "low_score" if output["score"] < RERANK_KEEP_MIN_SCORE else "not_verbatim"


_PREFIX_JOB = {"cx": Job.CONTEXT, "tr": Job.TRANSLATE, "tf": Job.TRANSFORM, "rr": Job.RERANK}


def job_of(custom_id: str) -> Job:
    """Việc của một request theo tiền tố custom_id: lô context chứa cả request dịch."""
    return _PREFIX_JOB[custom_id.split("-", 1)[0]]


def parse_text(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("output không phải object JSON")
    return value


def cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    batch: bool = True,
) -> float:
    """Giá theo bảng. `input_tokens` là phần vào KHÔNG qua cache (trường `input_tokens` của usage);
    hai phần cache tính riêng theo hệ số của chúng."""
    price_in = (
        input_tokens
        + cache_write_tokens * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * CACHE_READ_MULTIPLIER
    ) * PRICE_IN_PER_MILLION
    price = price_in + output_tokens * PRICE_OUT_PER_MILLION
    return price / 1_000_000 * (BATCH_DISCOUNT if batch else 1.0)
