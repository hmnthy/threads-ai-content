"""Request và kiểm output của các vai Haiku (demo RAG). Chữ tự đặt, không chữ bài thật."""

from __future__ import annotations

import re

import pytest

from src.rag_demo.chunking import Chunk
from src.rag_demo.corpus import Unit
from src.rag_demo.llm_jobs import (
    CONTEXT_SYSTEM,
    EFFORT,
    LLM_MODEL,
    PROMPT_VERSIONS,
    RERANK_SYSTEM,
    SCHEMAS,
    TRANSFORM_SYSTEM,
    Job,
    check_output,
    context_requests,
    cost_usd,
    job_of,
    prompt_fingerprint,
    quote_drop_reason,
    rerank_requests,
    transform_requests,
)
from src.rag_demo.questions import QUESTIONS

DOC = "Câu đầu về nhà. Câu sau về sưởi."
UNIT = Unit(id="u1", full_text=DOC, posts=())
WHOLE = Chunk(id=0, unit_id="u1", start=0, end=len(DOC), text=DOC)
FIRST = Chunk(id=1, unit_id="u1", start=0, end=15, text="Câu đầu về nhà.")
# cùng chữ với FIRST nhưng ở cách chia khác (mã chunk khác)
FIRST_AGAIN = Chunk(id=7, unit_id="u1", start=0, end=15, text="Câu đầu về nhà.")
CUSTOM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def test_transform_has_one_request_per_question_with_the_approved_settings() -> None:
    requests = transform_requests(QUESTIONS)
    assert [r.custom_id for r in requests] == [f"tf-q{n:02d}" for n in range(1, 11)]
    params = requests[5].params
    assert params["model"] == LLM_MODEL == "claude-haiku-5-5"
    assert params["output_config"]["effort"] == EFFORT == "low"
    assert params["output_config"]["format"]["schema"] == SCHEMAS[Job.TRANSFORM]
    assert params["system"] == TRANSFORM_SYSTEM
    assert params["messages"] == [{"role": "user", "content": QUESTIONS[5].text}]


def test_context_translates_a_whole_unit_and_situates_a_part() -> None:
    requests = context_requests([UNIT], [WHOLE, FIRST, FIRST_AGAIN])
    jobs = {r.job for r in requests}
    assert jobs == {Job.TRANSLATE, Job.CONTEXT}
    assert len(requests) == 2  # chunk trùng chữ trong cùng bài chỉ gọi một lần
    context = next(r for r in requests if r.job is Job.CONTEXT)
    assert context.custom_id.startswith("cx-")
    system = context.params["system"][0]
    assert system["text"] == CONTEXT_SYSTEM.format(document=DOC)
    assert system["cache_control"] == {"type": "ephemeral"}
    assert "<chunk>Câu đầu về nhà.</chunk>" in context.params["messages"][0]["content"]
    translate = next(r for r in requests if r.job is Job.TRANSLATE)
    assert translate.custom_id.startswith("tr-")
    assert "system" not in translate.params


def test_rerank_scores_each_distinct_text_once_per_question() -> None:
    requests = rerank_requests(QUESTIONS[:2], [WHOLE, FIRST, FIRST_AGAIN])
    assert len(requests) == 2 * 2
    ids = [r.custom_id for r in requests]
    assert len(set(ids)) == len(ids)
    assert all(CUSTOM_ID.fullmatch(i) for i in ids)
    assert QUESTIONS[0].text in requests[0].params["messages"][0]["content"]


@pytest.mark.parametrize(
    ("custom_id", "job"),
    [
        ("cx-ab", Job.CONTEXT),
        ("tr-ab", Job.TRANSLATE),
        ("tf-q01", Job.TRANSFORM),
        ("rr-q01-ab", Job.RERANK),
    ],
)
def test_job_of_reads_the_prefix(custom_id: str, job: Job) -> None:
    assert job_of(custom_id) is job


PASSAGE = "Chủ nhà phải bật sưởi từ tháng 10."


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            {"score": 3, "quote": "bật sưởi từ tháng 10", "quote_en": "turn on"},
            {
                "score": 3,
                "keep": True,
                "quote": "bật sưởi từ tháng 10",
                "quote_en": "turn on",
                "quote_dropped": False,
            },
        ),
        (  # không phải chuỗi con nguyên văn → bỏ câu trích, giữ điểm
            {"score": 2, "quote": "bật sưởi tháng 10", "quote_en": "x"},
            {"score": 2, "keep": True, "quote": "", "quote_en": "", "quote_dropped": True},
        ),
        (  # điểm 0–1 không mang câu trích
            {"score": 1, "quote": "bật sưởi", "quote_en": "x"},
            {"score": 1, "keep": False, "quote": "", "quote_en": "", "quote_dropped": True},
        ),
        (
            {"score": 0, "quote": "", "quote_en": ""},
            {"score": 0, "keep": False, "quote": "", "quote_en": "", "quote_dropped": False},
        ),
    ],
)
def test_rerank_output_keeps_only_verbatim_quotes(
    output: dict[str, object], expected: dict[str, object]
) -> None:
    assert check_output(Job.RERANK, dict(output), PASSAGE) == expected


@pytest.mark.parametrize("score", [4, -1, True, "3"])
def test_rerank_score_outside_the_scale_is_an_error(score: object) -> None:
    with pytest.raises(ValueError):
        check_output(Job.RERANK, {"score": score, "quote": "", "quote_en": ""}, PASSAGE)


def test_wrong_keys_are_an_error() -> None:
    with pytest.raises(ValueError):
        check_output(Job.TRANSLATE, {"chunk_en": "x", "extra": "y"})


def test_batch_cost_is_half_the_listed_price() -> None:
    # 1 triệu token vào ($0,10) + 1 triệu token ra ($0,50), giảm 50% → $0,30
    assert cost_usd(1_000_000, 1_000_000) == pytest.approx(0.30)
    assert cost_usd(1_000_000, 1_000_000, batch=False) == pytest.approx(0.60)


def test_cache_tokens_are_priced_with_their_own_multipliers() -> None:
    # ghi cache ×1,25 → $0,125 / triệu; đọc cache ×0,1 → $0,01 / triệu; chưa giảm giá lô
    assert cost_usd(0, 0, cache_write_tokens=1_000_000, batch=False) == pytest.approx(0.125)
    assert cost_usd(0, 0, cache_read_tokens=1_000_000, batch=False) == pytest.approx(0.01)
    assert cost_usd(0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.005)  # giảm 50% cộng dồn


# Mỗi (việc, phiên bản) ghim đúng một dấu vân tay. Sửa chữ prompt / schema / model / effort / trần
# token của một việc → test đỏ → TĂNG PROMPT_VERSIONS[việc] rồi thêm một dòng mới ở đây; không sửa
# dòng cũ (kết quả đã lưu mang phiên bản cũ, dòng cũ là bằng chứng chúng sinh ra từ chữ nào).
# Ghim 2026-11-08 từ code hiện tại. 3 lô ngày 2026-11-07 được gửi trước khi kết quả mang dấu vân
# tay, nên việc chúng sinh từ đúng chữ này chỉ dựa vào người viết (không sửa hằng prompt từ lúc
# gửi). Dựng lại được đúng cả 5.182 custom_id chỉ chứng minh cùng ĐẦU VÀO (tập chunk, câu hỏi) —
# custom_id không phụ thuộc chữ prompt. Lô từ nay ghi dấu vân tay vào file trạng thái và từng dòng
# kết quả, nên kiểm được bằng dữ liệu.
PROMPT_FINGERPRINTS: dict[tuple[Job, str], str] = {
    (Job.CONTEXT, "2026-11-07.1"): (
        "eeb5f0b57a2935e7fe8e403d5bd65ecd6a5060206f2037de9240bda9ca443fbc"
    ),
    (Job.TRANSLATE, "2026-11-07.1"): (
        "4b6272feda0c63bea57be229e5de34cc23ea6f1652bbe5a163672ee128e33e21"
    ),
    (Job.TRANSFORM, "2026-11-07.1"): (
        "53cff0775247534c3bc97e51429178321c8f01718bdb48179f61fea7be8359bd"
    ),
    (Job.RERANK, "2026-11-07.1"): (
        "e10d066cfec77e8eb0f686768ae62c19699b7718111f8bb7bff6b201f32b277b"
    ),
}


@pytest.mark.parametrize("job", list(Job))
def test_prompt_change_needs_a_new_version(job: Job) -> None:
    pinned = PROMPT_FINGERPRINTS.get((job, PROMPT_VERSIONS[job]))
    assert pinned is not None, f"{job}: phiên bản {PROMPT_VERSIONS[job]} chưa ghim dấu vân tay"
    assert prompt_fingerprint(job) == pinned, (
        f"{job}: prompt đã đổi mà phiên bản vẫn là {PROMPT_VERSIONS[job]} — tăng phiên bản"
    )


def test_fingerprint_changes_when_a_prompt_word_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.rag_demo import llm_jobs

    before = prompt_fingerprint(Job.RERANK)
    monkeypatch.setattr(llm_jobs, "RERANK_SYSTEM", RERANK_SYSTEM + " ")
    assert prompt_fingerprint(Job.RERANK) != before
    assert prompt_fingerprint(Job.CONTEXT) == PROMPT_FINGERPRINTS[(Job.CONTEXT, "2026-11-07.1")]


def test_fingerprint_changes_when_the_request_is_built_differently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cùng chữ prompt nhưng request khác (trần token, bỏ cache_control) cũng là output khác."""
    from src.rag_demo import llm_jobs

    before = {job: prompt_fingerprint(job) for job in Job}
    monkeypatch.setattr(llm_jobs, "MAX_TOKENS", 2048)
    assert all(prompt_fingerprint(job) != before[job] for job in Job)
    monkeypatch.undo()
    real_context_requests = llm_jobs.context_requests

    def without_cache(units: list[Unit], chunks: list[Chunk]) -> list[llm_jobs.LlmRequest]:
        requests = real_context_requests(units, chunks)
        for request in requests:
            if "system" in request.params:
                request.params["system"][0].pop("cache_control")
        return requests

    monkeypatch.setattr(llm_jobs, "context_requests", without_cache)
    assert prompt_fingerprint(Job.CONTEXT) != before[Job.CONTEXT]


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ({"score": 3, "quote": "bật sưởi", "quote_en": "x"}, ""),
        ({"score": 2, "quote": "bật sưởi tháng 10", "quote_en": "x"}, "not_verbatim"),
        ({"score": 1, "quote": "bật sưởi", "quote_en": "x"}, "low_score"),
        # điểm thấp + câu trích bịa: tính là low_score (điểm 0–1 bỏ câu trích trước khi xét
        # nguyên văn)
        ({"score": 0, "quote": "không có trong đoạn", "quote_en": "x"}, "low_score"),
        ({"score": 0, "quote": "", "quote_en": ""}, ""),
    ],
)
def test_quote_drop_reason_separates_fabricated_quotes(
    output: dict[str, object], reason: str
) -> None:
    assert quote_drop_reason(check_output(Job.RERANK, dict(output), PASSAGE)) == reason


@pytest.mark.parametrize(
    ("job", "output"),
    [
        (Job.RERANK, {"score": 2, "quote": None, "quote_en": ""}),
        (Job.RERANK, {"score": 2, "quote": "bật sưởi", "quote_en": 3}),
        (Job.TRANSLATE, {"chunk_en": ["not", "a", "string"]}),
        (Job.CONTEXT, {"context": "x", "context_en": "x", "chunk_en": None}),
    ],
)
def test_wrong_field_types_are_an_error_not_a_crash(job: Job, output: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        check_output(job, output, PASSAGE)


def test_transform_lists_must_hold_strings() -> None:
    output: dict[str, object] = {key: "x" for key in SCHEMAS[Job.TRANSFORM]["properties"]}
    output |= {"multi_query": ["a"], "multi_query_en": ["a"], "decompose": ["a"]}
    output["decompose_en"] = ["a", 1]
    with pytest.raises(ValueError, match="decompose_en"):
        check_output(Job.TRANSFORM, output)
    output["decompose_en"] = ["a"]
    assert check_output(Job.TRANSFORM, output) == output
