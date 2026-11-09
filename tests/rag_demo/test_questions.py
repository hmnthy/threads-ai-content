"""10 câu hỏi và đáp án đúng của demo RAG (ADR-0037 D10, ADR-0038 D7, ADR-0039 D3).

Giá trị mong đợi viết tay theo ADR, không suy ra từ file đang kiểm. Chữ bài trong test là chữ tự
đặt.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from src.rag_demo.chunking import Chunk
from src.rag_demo.corpus import FROZEN_UNITS, CorpusChangedError, Unit
from src.rag_demo.demo_file import PAID_QUESTION_TEXTS_SHA256, question_texts_sha256
from src.rag_demo.questions import (
    QUESTIONS,
    AnswerRule,
    GoldSpan,
    Question,
    check_gold,
    gold_chunk_ids,
)

DECISIONS = Path(__file__).parents[2] / "docs/decisions"
ADR_0037 = DECISIONS / "0037-rag-pipeline-visualization-static-demo.md"
ADR_0040 = DECISIONS / "0040-rag-demo-deleted-post-and-preregistered-gold.md"

EXPECTED_RULES = {
    1: (AnswerRule.SINGLE, 1),
    2: (AnswerRule.SINGLE, 1),
    3: (AnswerRule.BOTH, 2),
    4: (AnswerRule.SINGLE, 1),  # ADR-0040: bài gần trùng thứ hai bị xoá trên Threads
    5: (AnswerRule.SINGLE, 1),
    6: (AnswerRule.SINGLE, 1),
    7: (AnswerRule.BOTH, 2),
    8: (AnswerRule.SINGLE, 1),
    9: (AnswerRule.SINGLE, 1),
    10: (AnswerRule.NONE, 0),
}


def make_question(
    gold_unit_ids: tuple[str, ...] = ("u1",),
    gold_span: GoldSpan | None = None,
    rule: AnswerRule = AnswerRule.SINGLE,
) -> Question:
    return Question(
        number=1,
        text="câu hỏi",
        english="a question",
        rule=rule,
        gold_unit_ids=gold_unit_ids,
        gold_span=gold_span,
    )


def make_chunk(chunk_id: int, unit_id: str, start: int, end: int) -> Chunk:
    return Chunk(id=chunk_id, unit_id=unit_id, start=start, end=end, text="x" * (end - start))


def test_ten_questions_numbered_in_order_with_english() -> None:
    assert [question.number for question in QUESTIONS] == list(range(1, 11))
    assert all(question.text and question.english for question in QUESTIONS)


def deleted_by_adr_0040() -> str:
    """Mã bài ADR-0040 D1 bỏ, đọc từ chính ADR (không từ code đang kiểm)."""
    match = re.search(r"Bỏ bài `(\d{17})`", ADR_0040.read_text(encoding="utf-8"))
    assert match is not None
    return match[1]


def test_questions_match_the_adr_table_word_for_word() -> None:
    """Chữ, tiếng Anh và mã bài của từng câu: đổi chỗ đáp án 2 câu là hỏng ở đây. Bảng của ADR-0037
    trừ đi đúng bài ADR-0040 bỏ."""
    deleted = deleted_by_adr_0040()
    row = re.compile(r"\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| .+ \|$")
    table = {}
    for line in ADR_0037.read_text(encoding="utf-8").splitlines():
        match = row.fullmatch(line)
        if match is not None:
            gold_ids = tuple(i for i in re.findall(r"\d{17}", match[4]) if i != deleted)
            table[int(match[1])] = (match[2], match[3], gold_ids)
    assert len(table) == 10
    assert deleted in ADR_0037.read_text(encoding="utf-8")  # ADR-0040 bỏ đúng một bài có trong bảng
    assert {q.number: (q.text, q.english, q.gold_unit_ids) for q in QUESTIONS} == table


def test_the_deleted_unit_is_gone_from_corpus_and_gold() -> None:
    deleted = deleted_by_adr_0040()
    assert deleted not in {unit.id for unit in FROZEN_UNITS}
    assert all(deleted not in q.gold_unit_ids for q in QUESTIONS)


def test_answer_rule_and_gold_count_of_each_question() -> None:
    actual = {q.number: (q.rule, len(q.gold_unit_ids)) for q in QUESTIONS}
    assert actual == EXPECTED_RULES


def test_every_gold_unit_is_in_the_frozen_list() -> None:
    frozen = {unit.id for unit in FROZEN_UNITS}
    gold = {unit_id for question in QUESTIONS for unit_id in question.gold_unit_ids}
    assert len(gold) == 9  # 10 trước ADR-0040
    assert gold <= frozen


def test_real_positions_fit_the_frozen_lengths() -> None:
    """CI không có DB: chạy đúng `check_gold` của bước dựng trên bài giả có độ dài đóng băng."""
    stand_ins = [Unit(id=u.id, full_text="x" * u.length, posts=()) for u in FROZEN_UNITS]
    check_gold(stand_ins)


def test_only_questions_5_and_8_have_positions() -> None:
    positions = {q.number: q.gold_span for q in QUESTIONS if q.gold_span is not None}
    assert positions == {5: GoldSpan(979, 1219), 8: GoldSpan(1141, 1363)}


def test_questions_2_and_8_share_a_unit_but_8_needs_the_position() -> None:
    """Lý do của ADR-0038 D7: chỉ tính mã bài thì đoạn nói chuyện khác cũng trúng câu 8."""
    second, eighth = QUESTIONS[1], QUESTIONS[7]
    assert second.gold_unit_ids == eighth.gold_unit_ids
    outside = make_chunk(0, eighth.gold_unit_ids[0], 0, 500)
    inside = make_chunk(1, eighth.gold_unit_ids[0], 1200, 1300)
    unit_id = eighth.gold_unit_ids[0]
    assert gold_chunk_ids(second, [outside, inside]) == {unit_id: (0, 1)}
    assert gold_chunk_ids(eighth, [outside, inside]) == {unit_id: (1,)}


# --- Đánh dấu chunk trúng ----------------------------------------------------------------------


def test_without_a_position_every_chunk_of_the_unit_hits() -> None:
    chunks = [make_chunk(0, "u1", 0, 5), make_chunk(1, "u2", 0, 5), make_chunk(2, "u1", 6, 9)]
    assert gold_chunk_ids(make_question(), chunks) == {"u1": (0, 2)}


@pytest.mark.parametrize(
    ("start", "end", "hit"),
    [
        (0, 10, False),  # chạm đúng mép đầu, nửa mở nên chưa trúng
        (0, 11, True),  # chồng 1 ký tự
        (12, 15, True),  # nằm trong
        (0, 50, True),  # bao trọn
        (19, 25, True),  # chồng 1 ký tự cuối
        (20, 30, False),  # bắt đầu đúng mép cuối
    ],
)
def test_position_uses_half_open_overlap(start: int, end: int, hit: bool) -> None:
    question = make_question(gold_span=GoldSpan(10, 20))
    expected: tuple[int, ...] = (7,) if hit else ()
    assert gold_chunk_ids(question, [make_chunk(7, "u1", start, end)]) == {"u1": expected}


def test_each_gold_unit_gets_a_key_even_when_nothing_hits() -> None:
    question = make_question(("u1", "u2"), rule=AnswerRule.BOTH)
    assert gold_chunk_ids(question, [make_chunk(0, "u1", 0, 5)]) == {"u1": (0,), "u2": ()}


def test_question_without_answer_has_no_hits() -> None:
    question = make_question((), rule=AnswerRule.NONE)
    assert gold_chunk_ids(question, [make_chunk(0, "u1", 0, 5)]) == {}


# --- Kiểm ở bước dựng --------------------------------------------------------------------------


def make_unit(unit_id: str, length: int) -> Unit:
    return Unit(id=unit_id, full_text="x" * length, posts=())


def test_check_gold_passes_when_position_ends_exactly_at_the_text_end() -> None:
    check_gold([make_unit("u1", 20)], [make_question(gold_span=GoldSpan(10, 20))])


def test_check_gold_stops_when_position_runs_past_the_text() -> None:
    with pytest.raises(CorpusChangedError, match="câu 1: vị trí ngoài u1"):
        check_gold([make_unit("u1", 19)], [make_question(gold_span=GoldSpan(10, 20))])


@pytest.mark.parametrize("span", [GoldSpan(5, 5), GoldSpan(6, 5), GoldSpan(-1, 5)])
def test_check_gold_stops_on_an_invalid_position(span: GoldSpan) -> None:
    with pytest.raises(CorpusChangedError, match="vị trí"):
        check_gold([make_unit("u1", 20)], [make_question(gold_span=span)])


def test_check_gold_stops_when_a_gold_unit_is_missing() -> None:
    with pytest.raises(CorpusChangedError, match="u2 không có trong tập"):
        check_gold([make_unit("u1", 20)], [make_question(("u1", "u2"))])


# sha256 của [[số, chữ], …] lúc gửi các lô Haiku 2026-11-07 (chữ không đổi từ đó); ghi lại tay
# ở đây, độc lập với hằng trong code
QUESTION_TEXTS_SHA256 = "d225c86b8f16b99e09164d934db11da7cb70ea1785323002c820607a68af31c0"


def test_question_texts_are_the_ones_the_paid_results_answer() -> None:
    """Mã request `tf-qNN` / `rr-qNN-…` chỉ ghi số câu, không băm chữ câu hỏi: sửa chữ một câu thì
    bước gửi lô vẫn coi là xong và file demo nhận output Haiku chấm theo câu cũ mà không báo. Đổi
    chữ → tăng `PROMPT_VERSIONS` của transform và rerank (gửi lại lô), rồi mới cập nhật hash này."""
    payload = json.dumps([[q.number, q.text] for q in QUESTIONS], ensure_ascii=False)
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == QUESTION_TEXTS_SHA256
    # hằng mà bước dựng (`check`, `assemble`) so lúc chạy thật, và file demo ghi lại
    assert question_texts_sha256(QUESTIONS) == PAID_QUESTION_TEXTS_SHA256 == QUESTION_TEXTS_SHA256
