"""Ghép file demo: chọn đúng kết quả đã trả tiền, vị trí theo UTF-16, làm tròn, chốt chặn cỡ file.

Bài, vector và điểm tự đặt (repo public, không chữ bài thật). Giá trị mong đợi tính tay và ghi cứng,
không đọc lại từ code đang test.
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
from pathlib import Path
from typing import Any, cast

import pytest

from src.rag_demo.chunking import Chunk, ChunkingWay
from src.rag_demo.corpus import PostSpan, Unit
from src.rag_demo.demo_file import (
    DEMO_FILE_MAX_BYTES,
    PENDING_PARTS,
    DemoFileError,
    build_demo,
    encode_demo,
    non_gold_kept,
    rounding_ties,
    score_counts,
    select_outputs,
    utf16_offset,
    write_demo,
)
from src.rag_demo.llm_jobs import (
    LLM_MODEL,
    PROMPT_VERSIONS,
    Job,
    check_output,
    context_id,
    context_requests,
    prompt_fingerprint,
    rerank_id,
    rerank_requests,
    transform_requests,
)
from src.rag_demo.questions import AnswerRule, GoldSpan, Question
from src.rag_demo.unit_metadata import UNCLUSTERED, TopicSnapshot, UnitMeta

# Post 1 có emoji ngoài BMP: 13 điểm mã nhưng 14 đơn vị UTF-16
POST_1 = "Nhà ấm 😀 quá."
POST_2 = "Sưởi hỏng rồi."
FULL_1 = f"{POST_1} {POST_2}"
FULL_2 = "Bút viết êm."
U1 = Unit("u1", FULL_1, (PostSpan("p1", 0, 13), PostSpan("p2", 14, 14 + len(POST_2))))
U2 = Unit("u2", FULL_2, (PostSpan("u2", 0, len(FULL_2)),))
UNITS = [U1, U2]
BY_WAY = {
    ChunkingWay.WHOLE: [Chunk(0, "u1", 0, len(FULL_1), FULL_1), Chunk(1, "u2", 0, 12, FULL_2)],
    ChunkingWay.POST: [
        Chunk(0, "u1", 0, 13, POST_1),
        Chunk(1, "u1", 14, 14 + len(POST_2), POST_2),
        Chunk(2, "u2", 0, 12, FULL_2),  # trùng chữ với chunk 1 của WHOLE → cùng một đoạn
    ],
    # 4 chunk: đọc tam giác trên theo hàng khác theo cột (n ≤ 3 thì như nhau). Mã chunk đáp án
    # (0, 1) khác chỉ số đoạn đáp án (0, 3): bỏ bước đổi mã chunk → đoạn thì phép đếm ra số khác.
    ChunkingWay.FIXED_300: [
        Chunk(0, "u1", 0, len(FULL_1), FULL_1),
        Chunk(1, "u1", 14, 14 + len(POST_2), POST_2),
        Chunk(2, "u2", 0, 12, FULL_2),
        Chunk(3, "u1", 0, 13, POST_1),
    ],
}
QUESTION = Question(
    number=1,
    text="câu hỏi tự đặt",
    english="made-up question",
    rule=AnswerRule.SINGLE,
    gold_unit_ids=("u1",),
    gold_span=GoldSpan(start=14, end=16),  # 2 ký tự đầu của post 2
)
# Thứ tự đoạn: FULL_1, FULL_2, POST_1, POST_2 (lần đầu gặp, theo cách chia rồi theo mã chunk)
VECTORS: dict[str, list[float]] = {
    FULL_1: [1.0, 0.0, 0.0],
    FULL_2: [0.0, 1.0, 0.0],
    POST_1: [1.0, 1.0, 0.0],
    POST_2: [0.0, 0.0, 2.0],  # chưa chuẩn hoá: cosine phải chia độ dài
    QUESTION.text: [1.0, 0.0, 1.0],
}
LOGITS = [1.23456789, -2.0000004, 0.5, 3.0]
LLM = [(3, "Nhà ấm"), (1, ""), (2, "Nhà ấm"), (2, "Sưởi")]
TRANSFORM = {
    "rewrite": "a",
    "rewrite_en": "a",
    "expand": "b",
    "expand_en": "b",
    "hyde": "c",
    "hyde_en": "c",
    "multi_query": ["d"],
    "multi_query_en": ["d"],
    "decompose": ["e"],
    "decompose_en": ["e"],
    "step_back": "f",
    "step_back_en": "f",
}
PASSAGES = [FULL_1, FULL_2, POST_1, POST_2]
DOCUMENT = {FULL_1: FULL_1, FULL_2: FULL_2, POST_1: FULL_1, POST_2: FULL_1}
UNIT_OF = {FULL_1: "u1", FULL_2: "u2", POST_1: "u1", POST_2: "u1"}
# u1 có topic, u2 Unclustered (ADR-0041 "Dữ liệu thêm vào file demo")
META = TopicSnapshot(
    cluster_run_id=37,
    cluster_run_at="2026-11-10T11:30:42+00:00",
    units={
        "u1": UnitMeta("2026-10", "topic-3", "Housing in France"),
        "u2": UnitMeta("2026-11", None, UNCLUSTERED),
    },
)
build = functools.partial(build_demo, metadata=META)


def context_key(text: str) -> str:
    return context_id(DOCUMENT[text], Chunk(0, UNIT_OF[text], 0, len(text), text))


def outputs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {"tf-q01": dict(TRANSFORM)}
    for text in PASSAGES:
        key = context_key(text)
        result[key] = (
            {"chunk_en": f"en {len(text)}"}
            if key.startswith("tr-")
            else {"context": "ngữ cảnh", "context_en": "context", "chunk_en": f"en {len(text)}"}
        )
    for text, (score, quote) in zip(PASSAGES, LLM, strict=True):
        raw = {"score": score, "quote": quote, "quote_en": quote and "en"}
        result[rerank_id(QUESTION, text)] = check_output(Job.RERANK, raw, text)
    return result


def logits() -> dict[str, float]:
    return {rerank_id(QUESTION, t): v for t, v in zip(PASSAGES, LOGITS, strict=True)}


def demo() -> dict[str, Any]:
    return build(UNITS, BY_WAY, [QUESTION], outputs(), logits(), VECTORS)


def test_utf16_offset_counts_an_astral_emoji_as_two_units() -> None:
    text = "a😀b é"
    assert [utf16_offset(text, i) for i in range(len(text) + 1)] == [0, 1, 3, 4, 5, 6]


def test_offsets_after_an_emoji_are_shifted_for_javascript() -> None:
    built = demo()
    post_way = built["ways"]["post"]
    assert [(r["start"], r["end"]) for r in post_way] == [(0, 14), (15, 29), (0, 12)]
    assert built["units"][0]["posts"] == [
        {"id": "p1", "start": 0, "end": 14},
        {"id": "p2", "start": 15, "end": 29},
    ]
    assert built["questions"][0]["gold_spans"] == {"u1": {"start": 15, "end": 17}}


def test_same_chunk_text_in_two_ways_is_one_passage() -> None:
    built = demo()
    assert [p["text"] for p in built["passages"]] == PASSAGES
    assert [r["passage"] for r in built["ways"]["whole"]] == [0, 1]
    assert [r["passage"] for r in built["ways"]["post"]] == [2, 3, 1]


def test_whole_unit_chunks_carry_a_translation_but_no_context() -> None:
    passages = demo()["passages"]
    assert [p["context"] for p in passages] == [None, None, "ngữ cảnh", "ngữ cảnh"]
    assert [p["en"] for p in passages] == [f"en {len(t)}" for t in PASSAGES]
    # chỉ chữ cho trang; không usage, mã lô hay output thô
    assert set(passages[0]) == {"unit", "text", "en", "context", "context_en"}


def test_scores_are_rounded_to_six_decimals() -> None:
    question = demo()["questions"][0]
    half_root = 0.707107  # 1/√2 = 0,70710678… (viết tay, không tính bằng `round`)
    # cosine với câu hỏi [1, 0, 1]: tính tay
    assert question["dense"] == [half_root, 0.0, 0.5, half_root]
    assert question["cross_encoder"] == [1.234568, -2.0, 0.5, 3.0]


def test_chunk_cosine_is_the_upper_triangle_by_row() -> None:
    cosine = demo()["cosine"]
    assert cosine["whole"] == [0.0]
    # post: đoạn POST_1, POST_2, FULL_2 → (0,1), (0,2), (1,2)
    assert cosine["post"] == [0.0, 0.707107, 0.0]
    # fixed_300: đoạn FULL_1, POST_2, FULL_2, POST_1 → (0,1) (0,2) (0,3) (1,2) (1,3) (2,3);
    # đọc theo cột sẽ ra [0, 0, 0, 0.707107, 0, 0.707107]
    assert cosine["fixed_300"] == [0.0, 0.0, 0.707107, 0.0, 0.0, 0.707107]


def test_llm_cells_keep_the_checked_quote_and_why_one_was_dropped() -> None:
    cells = demo()["questions"][0]["llm"]
    assert [c["score"] for c in cells] == [3, 1, 2, 2]
    assert cells[0] == {"score": 3, "quote": "Nhà ấm", "quote_en": "en", "quote_dropped": None}
    assert cells[1]["quote"] is None
    dropped = build(
        UNITS,
        BY_WAY,
        [QUESTION],
        outputs()
        | {
            rerank_id(QUESTION, FULL_2): check_output(
                Job.RERANK, {"score": 2, "quote": "không có trong đoạn", "quote_en": "x"}, FULL_2
            )
        },
        logits(),
        VECTORS,
    )["questions"][0]["llm"][1]
    assert dropped == {"score": 2, "quote": None, "quote_en": None, "quote_dropped": "not_verbatim"}


def test_gold_chunks_are_flagged_per_way_and_counted_outside_gold() -> None:
    built = demo()
    assert built["questions"][0]["gold_chunks"] == {
        "whole": {"u1": [0]},
        "post": {"u1": [1]},
        "fixed_300": {"u1": [0, 1]},
    }
    # đoạn đáp án: FULL_1 (0) và POST_2 (3); giữ = điểm ≥ 2 → đoạn 0, 2, 3 → chỉ POST_1 ngoài đáp
    # án. Lấy nhầm mã chunk làm chỉ số đoạn thì đáp án thành {0, 1} và ra 2.
    assert non_gold_kept(built) == {1: 1}
    assert score_counts(built) == {3: 1, 2: 2, 1: 1}


def test_every_written_offset_cuts_the_right_text_in_utf16() -> None:
    built = demo()
    units: dict[str, str] = {u["id"]: u["text"] for u in built["units"]}

    def cut(unit_id: str, start: int, end: int) -> str:
        return units[unit_id].encode("utf-16-le")[2 * start : 2 * end].decode("utf-16-le")

    for records in built["ways"].values():
        for r in records:
            assert cut(r["unit"], r["start"], r["end"]) == built["passages"][r["passage"]]["text"]
    posts = {
        u["id"]: [cut(u["id"], p["start"], p["end"]) for p in u["posts"]] for u in built["units"]
    }
    assert posts == {"u1": [POST_1, POST_2], "u2": [FULL_2]}
    span = built["questions"][0]["gold_spans"]["u1"]
    assert cut("u1", span["start"], span["end"]) == FULL_1[14:16] == "Sư"


QUESTION_2 = Question(
    number=2,
    text="câu thứ hai tự đặt",
    english="second made-up question",
    rule=AnswerRule.SINGLE,
    gold_unit_ids=("u2",),
)


def test_each_question_gets_its_own_row_of_scores() -> None:
    """2 câu hỏi khác hẳn nhau: lấy nhầm vector / mã cặp / output của câu 1 cho câu 2 thì đỏ."""
    results = outputs() | {"tf-q02": TRANSFORM | {"rewrite": "câu 2"}}
    scores = logits()
    q2_llm = [(0, ""), (3, "Bút"), (2, "Nhà ấm"), (0, "")]
    for text, logit, (score, quote) in zip(PASSAGES, [-1.0, 4.0, 0.25, -0.5], q2_llm, strict=True):
        scores[rerank_id(QUESTION_2, text)] = logit
        raw = {"score": score, "quote": quote, "quote_en": quote and "en"}
        results[rerank_id(QUESTION_2, text)] = check_output(Job.RERANK, raw, text)
    vectors = VECTORS | {QUESTION_2.text: [0.0, 1.0, 0.0]}
    built = build(UNITS, BY_WAY, [QUESTION, QUESTION_2], results, scores, vectors)
    first, second = built["questions"]
    assert first["dense"] == [0.707107, 0.0, 0.5, 0.707107]
    # câu 2 [0, 1, 0]: FULL_1 0, FULL_2 1, POST_1 1/√2, POST_2 0
    assert second["dense"] == [0.0, 1.0, 0.707107, 0.0]
    assert second["cross_encoder"] == [-1.0, 4.0, 0.25, -0.5]
    assert [c["score"] for c in second["llm"]] == [0, 3, 2, 0]
    assert second["transforms"]["rewrite"] == "câu 2"
    assert second["gold_chunks"] == {
        "whole": {"u2": [1]},
        "post": {"u2": [2]},
        "fixed_300": {"u2": [2]},
    }
    # câu 2: đáp án = đoạn FULL_2 (1); giữ đoạn 1, 2 → ngoài đáp án chỉ POST_1
    assert non_gold_kept(built) == {1: 1, 2: 1}


def test_a_shared_gold_span_is_converted_per_unit() -> None:
    """Câu 2 bài dùng chung một span (questions.py): emoji đứng trước span ở u1, không ở u2, nên
    vị trí UTF-16 khác nhau giữa 2 bài."""
    both = Question(3, "câu ba tự đặt", "third", AnswerRule.BOTH, ("u1", "u2"), GoldSpan(9, 11))
    results, scores = outputs() | {"tf-q03": dict(TRANSFORM)}, logits()
    for text in PASSAGES:
        scores[rerank_id(both, text)] = 0.0
        raw = {"score": 0, "quote": "", "quote_en": ""}
        results[rerank_id(both, text)] = check_output(Job.RERANK, raw, text)
    vectors = VECTORS | {both.text: [1.0, 1.0, 1.0]}
    built = build(UNITS, BY_WAY, [both], results, scores, vectors)
    spans = built["questions"][0]["gold_spans"]
    assert spans == {"u1": {"start": 10, "end": 12}, "u2": {"start": 9, "end": 11}}
    assert FULL_1[9:11] == "qu" and FULL_2[9:11] == "êm"


def test_provenance_lists_the_parts_still_missing() -> None:
    built = demo()
    assert built["format"] == 2
    # định dạng 2 bỏ "cosine kèm câu ngữ cảnh": lọc gần trùng và MMR dùng cosine chữ gốc
    assert built["provenance"]["pending"] == [
        "dense score of transformed questions",
        "dense score of chunks with their context sentence",
    ]
    assert list(PENDING_PARTS) == built["provenance"]["pending"]
    assert built["provenance"]["offsets"].startswith("utf-16")


@pytest.mark.parametrize(
    ("drop", "message"),
    [
        ("vector", "thiếu vector của 1 chữ"),
        ("logit", "câu 1: thiếu điểm cross-encoder"),
        ("llm", "câu 1: thiếu điểm Haiku"),
        ("context", "bài u1: thiếu câu ngữ cảnh / bản dịch"),
        ("transform", "câu 1: thiếu câu hỏi biến đổi"),
    ],
)
def test_any_missing_cell_stops_the_build(drop: str, message: str) -> None:
    vectors, scores, results = dict(VECTORS), logits(), outputs()
    if drop == "vector":
        del vectors[POST_2]
    elif drop == "logit":
        del scores[rerank_id(QUESTION, POST_2)]
    elif drop == "llm":
        del results[rerank_id(QUESTION, POST_2)]
    elif drop == "context":
        del results[context_key(POST_2)]
    else:
        del results["tf-q01"]
    with pytest.raises(DemoFileError, match=message):
        build(UNITS, BY_WAY, [QUESTION], results, scores, vectors)


# --- chọn kết quả Haiku ---

CHUNKS = [c for chunks in BY_WAY.values() for c in chunks]
REQUESTS = [
    *transform_requests([QUESTION]),
    *context_requests(UNITS, CHUNKS),
    *rerank_requests([QUESTION], CHUNKS),
]


def rows() -> list[dict[str, Any]]:
    built = outputs()
    return [
        {
            "custom_id": r.custom_id,
            "job": r.job.value,
            "ok": True,
            "model": LLM_MODEL,
            "prompt_version": PROMPT_VERSIONS[r.job],
            "output": built[r.custom_id],
        }
        for r in REQUESTS
    ]


def test_select_takes_one_row_per_request_and_ignores_the_rest() -> None:
    extra = [
        {"custom_id": "rr-q01-bai-da-xoa", "job": "rerank", "ok": True},  # bài không còn trong tập
        {"custom_id": REQUESTS[0].custom_id, "job": "transform", "ok": False, "error": "x"},
    ]
    selection = select_outputs([*rows(), *extra], REQUESTS)
    assert set(selection.outputs) == {r.custom_id for r in REQUESTS}
    assert len(REQUESTS) == 1 + 4 + 4
    assert (selection.not_wanted, selection.failed, selection.superseded) == (1, 1, 0)
    assert selection.fingerprinted == 0


def test_select_accepts_old_rows_without_fingerprint_but_checks_new_ones() -> None:
    fresh = [row | {"prompt_fingerprint": prompt_fingerprint(Job(row["job"]))} for row in rows()]
    fresh[0] = rows()[0]  # dòng cũ lẫn dòng mới
    selection = select_outputs(fresh, REQUESTS)
    assert len(selection.outputs) == len(REQUESTS)
    assert selection.fingerprinted == len(REQUESTS) - 1
    fresh[1]["prompt_fingerprint"] = "0" * 64
    with pytest.raises(DemoFileError, match="dấu vân tay request khác code hiện tại"):
        select_outputs(fresh, REQUESTS)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("missing", "chưa có kết quả thành công"),
        ("twice", "2 kết quả thành công cùng phiên bản"),
        ("model", "model 'claude-other'"),
        ("version", "chỉ có prompt 2000-01-01.1, khác hiện tại"),
        ("job", "việc 'context', cần 'rerank'"),
        ("output", "dòng thành công không có output"),
    ],
)
def test_select_stops_instead_of_guessing(change: str, message: str) -> None:
    table = rows()
    target = next(row for row in table if row["job"] == "rerank")
    if change == "missing":
        table.remove(target)
    elif change == "twice":
        table.append(dict(target))
    elif change == "model":
        target["model"] = "claude-other"
    elif change == "version":
        target["prompt_version"] = "2000-01-01.1"
    elif change == "job":
        target["job"] = "context"
    else:
        del target["output"]
    with pytest.raises(DemoFileError, match=message) as error:
        select_outputs(table, REQUESTS)
    assert target["custom_id"] in str(error.value)


def test_a_row_replaced_by_a_new_prompt_version_is_not_a_duplicate() -> None:
    """Tăng phiên bản prompt → lô mới ghi thêm dòng cùng mã cạnh dòng cũ (mã không chứa phiên
    bản): dòng cũ là dòng đã bị thay, file vẫn ghép được và lấy đúng dòng mới."""
    table = rows()
    target = next(row for row in table if row["job"] == "rerank")
    stale = target | {"prompt_version": "2000-01-01.1", "output": {"score": 0}}
    selection = select_outputs([stale, *table], REQUESTS)
    assert selection.outputs[target["custom_id"]] == target["output"]
    assert (selection.not_wanted, selection.failed, selection.superseded) == (0, 0, 1)


# --- chốt chặn cỡ file ---


def test_an_oversized_file_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    with pytest.raises(DemoFileError, match="ngân sách"):
        write_demo({"padding": "x" * DEMO_FILE_MAX_BYTES}, path)
    assert list(tmp_path.iterdir()) == []


def test_budget_is_strictly_below_the_limit(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    payload = {"a": ""}
    size = len(json.dumps(payload, separators=(",", ":")).encode())
    with pytest.raises(DemoFileError):
        write_demo(payload, path, max_bytes=size)
    written, _ = write_demo(payload, path, max_bytes=size + 1)
    assert written == size
    assert [p.name for p in tmp_path.iterdir()] == ["demo.json"]


def test_a_failed_rename_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "demo.json"
    path.write_text("bản cũ", encoding="utf-8")

    def locked(*_: object) -> None:
        raise PermissionError("file đích đang mở")

    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(PermissionError):
        write_demo({"a": 1}, path)
    assert [p.name for p in tmp_path.iterdir()] == ["demo.json"]
    assert path.read_text(encoding="utf-8") == "bản cũ"


def test_written_file_round_trips(tmp_path: Path) -> None:
    built = demo()
    path = tmp_path / "demo.json"
    write_demo(built, path)
    assert json.loads(path.read_text(encoding="utf-8")) == built


def test_a_tiny_negative_score_is_written_as_plain_zero() -> None:
    scores = logits() | {rerank_id(QUESTION, FULL_1): -1e-9}
    built = build(UNITS, BY_WAY, [QUESTION], outputs(), scores, VECTORS)
    assert '"cross_encoder":[0.0,' in encode_demo(built).decode()


def test_rounding_ties_count_only_pairs_made_equal_by_rounding() -> None:
    # 0.1234561 và 0.1234564 → cùng 0.123456 (1 cặp do làm tròn); 0.5 và 0.5 vốn bằng nhau
    assert rounding_ties([0.1234561, 0.1234564, 0.5, 0.5, 0.9]) == 1
    # 3 điểm thô khác nhau cùng một ô → 3 cặp; thêm 1 bản sao của một điểm → 2 cặp mới
    assert rounding_ties([0.2000001, 0.2000002, 0.2000003]) == 3
    assert rounding_ties([0.2000001, 0.2000002, 0.2000003, 0.2000001]) == 5


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"score": "3"}, "điểm '3'"),
        ({"score": True}, "điểm True"),
        ({"keep": False}, "keep không khớp điểm"),
        ({"quote": None}, "câu trích không phải chuỗi"),
        ({"extra": 1}, "khoá"),
        # các bất biến check_output tạo ra: điểm < 2 không mang câu trích, câu trích đã bỏ thì rỗng
        ({"score": 1, "keep": False}, "câu trích ở điểm dưới mức giữ"),
        ({"quote_dropped": True}, "câu trích đã bỏ mà vẫn còn"),
        ({"quote": ""}, "quote_en mà không có quote"),
    ],
)
def test_stored_rerank_output_is_checked_again_at_use(change: dict[str, Any], message: str) -> None:
    table = rows()
    target = next(row for row in table if row["job"] == "rerank" and row["output"]["score"] >= 2)
    target["output"] = target["output"] | change
    with pytest.raises(DemoFileError, match=re.escape(f"output sai dạng ({message}")):
        select_outputs(table, REQUESTS)


def test_stored_transform_output_is_checked_again_at_use() -> None:
    table = rows()
    target = next(row for row in table if row["job"] == "transform")
    del target["output"]["hyde"]
    with pytest.raises(DemoFileError, match="output sai dạng"):
        select_outputs(table, REQUESTS)


def test_a_quote_not_in_the_passage_never_reaches_the_page() -> None:
    results = outputs()
    cell = dict(results[rerank_id(QUESTION, FULL_2)])
    cell["quote"] = "chữ không có trong đoạn"
    results[rerank_id(QUESTION, FULL_2)] = cell
    with pytest.raises(DemoFileError, match="câu trích không nguyên văn trong đoạn"):
        build(UNITS, BY_WAY, [QUESTION], results, logits(), VECTORS)


def test_rounding_ties_in_the_file_count_raw_scores_per_passage_and_per_way() -> None:
    """Giá trị khác 0 và khác nhau giữa dense / cross-encoder: nối nhầm biến hay đổi chỗ thì đỏ."""
    # POST_1 = [1, 5e-4, 0] → cosine với câu hỏi 0,70710669, cùng ô 0,707107 với FULL_1 và POST_2
    # (cả hai đúng 1/√2, bằng nhau từ điểm thô nên không tính)
    vectors = VECTORS | {POST_1: [1.0, 5e-4, 0.0]}
    scores = logits() | {
        rerank_id(QUESTION, FULL_2): 0.1234561,
        rerank_id(QUESTION, POST_1): 0.1234564,
    }
    ties = build(UNITS, BY_WAY, [QUESTION], outputs(), scores, vectors)["provenance"][
        "rounding_ties"
    ]
    # đoạn: FULL_1 0, FULL_2 1, POST_1 2, POST_2 3. whole = [0, 1]; post = [2, 3, 1];
    # fixed_300 = [0, 3, 1, 2]
    assert ties == {
        "dense": {"passages": 2, "by_way": {"whole": 0, "post": 1, "fixed_300": 2}},
        "cross_encoder": {"passages": 1, "by_way": {"whole": 0, "post": 1, "fixed_300": 1}},
    }


def test_provenance_fingerprints_the_vectors_used() -> None:
    first = demo()["provenance"]["embedding_vectors_sha256"]
    changed = build(
        UNITS, BY_WAY, [QUESTION], outputs(), logits(), VECTORS | {POST_2: [0.0, 0.0, 3.0]}
    )
    # cùng hướng nên mọi điểm như cũ, nhưng vector đã dùng khác
    assert changed["questions"] == demo()["questions"]
    assert changed["provenance"]["embedding_vectors_sha256"] != first


@pytest.mark.parametrize("row", [[], "chuỗi", {"job": "rerank", "ok": True}])
def test_a_malformed_results_row_stops_the_build(row: object) -> None:
    with pytest.raises(DemoFileError, match="không phải object có custom_id"):
        select_outputs([*rows(), cast(Any, row)], REQUESTS)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # giá trị có thật (câu 9, đoạn 403): `round` cho -11.039062, `toFixed` của trang -11.039063
        (-11.0390625, -11.039063),
        (1 / 128, 0.007813),  # 1 / (60 + 68), một số hạng RRF; `round` cho 0.007812
        (5e-7, 0.0),  # nhị phân thật < 5e-7: `toFixed` cho 0.000000 (`Decimal(str)` cho 0.000001)
        (-4e-7, 0.0),  # làm tròn ra -0: ghi 0.0, JSON không có "-0.0"
    ],
)
def test_scores_round_half_away_from_zero_like_the_page(raw: float, expected: float) -> None:
    """ADR-0041 Luật chung 5: file làm tròn đúng như `Number(x.toFixed(6))` của trang."""
    scores = logits() | {rerank_id(QUESTION, FULL_1): raw}
    built = build(UNITS, BY_WAY, [QUESTION], outputs(), scores, VECTORS)
    value = built["questions"][0]["cross_encoder"][0]
    assert value == expected
    if value == 0.0:
        assert math.copysign(1.0, value) == 1.0  # +0, không phải -0
    assert "-0.0" not in encode_demo(built).decode()


def test_a_non_finite_score_stops_before_writing() -> None:
    scores = logits() | {rerank_id(QUESTION, FULL_1): math.inf}
    with pytest.raises(DemoFileError, match="điểm không hữu hạn"):
        build(UNITS, BY_WAY, [QUESTION], outputs(), scores, VECTORS)


def test_units_carry_their_month_and_topic_snapshot() -> None:
    built = demo()
    assert [(u["id"], u["month"], u["topic"]) for u in built["units"]] == [
        ("u1", "2026-10", {"id": "topic-3", "label_en": "Housing in France"}),
        ("u2", "2026-11", {"id": None, "label_en": "Unclustered"}),
    ]
    assert built["provenance"]["topics"] == {
        "cluster_run_id": 37,
        "cluster_run_at": "2026-11-10T11:30:42+00:00",
    }


def test_a_unit_without_metadata_stops() -> None:
    partial = TopicSnapshot(37, "2026-11-10T11:30:42+00:00", {"u1": META.units["u1"]})
    with pytest.raises(DemoFileError, match="thiếu tháng đăng / topic của bài u2"):
        build_demo(UNITS, BY_WAY, [QUESTION], outputs(), logits(), VECTORS, metadata=partial)
