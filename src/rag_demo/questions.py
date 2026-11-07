"""10 câu hỏi cố định và đáp án đúng của demo RAG: bản gốc duy nhất (ADR-0037 D10, ADR-0038 D6–D7).

Bước dựng (chặng 3, chưa có) sẽ chép các câu này vào file dữ liệu demo; trình duyệt đọc từ đó,
không có bản thứ hai. Câu hỏi và mã bài đã công khai trong ADR-0037; vị trí ghi bằng số, không chép
chữ của bài (repo public).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from src.rag_demo.chunking import Chunk
from src.rag_demo.corpus import CorpusChangedError, Unit


class AnswerRule(StrEnum):
    """Bài nào phải tìm thấy (ADR-0038 D7–D8)."""

    SINGLE = "single"
    ANY_OF_TWO = "any_of_two"  # câu 4: hai bài gần trùng, một trong hai là đủ
    BOTH = "both"  # câu 3, 7: phải đọc tới hạng của bài tìm thấy sau cùng
    NONE = "none"  # câu 10: không có bài nào chứa đáp án


@dataclass(frozen=True)
class GoldSpan:
    """Chỗ chứa đáp án trong `full_text`, nửa mở, đếm theo điểm mã của Python (ADR-0039 D3)."""

    start: int
    end: int


@dataclass(frozen=True)
class Question:
    number: int
    text: str
    english: str
    rule: AnswerRule
    gold_unit_ids: tuple[str, ...]
    gold_span: GoldSpan | None = None  # chỉ câu 5, 8; có span thì mọi mã bài dùng chung span này


QUESTIONS: tuple[Question, ...] = (
    Question(
        number=1,
        text="chu nha khong chiu bat suoi thi phai lam sao",
        english="What can I do if my landlord won't turn the heating on?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("17899007316608496",),
    ),
    Question(
        number=2,
        text="Mua đồ hiệu second-hand giá rẻ ở Pháp ở đâu?",
        english="Where can I buy cheap second-hand designer clothes in France?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("18042552590841773",),
    ),
    Question(
        number=3,
        text=(
            "Thuê nhà mùa đông ở Pháp cần để ý gì về sưởi và độ ẩm, chủ nhà không sưởi thì làm sao?"
        ),
        english=(
            "Renting in winter: what to check about heating and humidity, "
            "and what if the landlord won't heat?"
        ),
        rule=AnswerRule.BOTH,
        gold_unit_ids=("18128851717831169", "17899007316608496"),
    ),
    Question(
        number=4,
        text="Nên chọn mentor / coach thế nào cho du học sinh?",
        english="How should an international student choose a mentor or coach?",
        rule=AnswerRule.ANY_OF_TWO,
        gold_unit_ids=("17923191900443021", "18117744790996401"),
    ),
    Question(
        number=5,
        text="Từ Cancale đi Saint-Malo bao xa, nên đi mùa nào?",
        english="How far is Saint-Malo from Cancale, and when is the best season to go?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("18156311638533948",),
        gold_span=GoldSpan(start=979, end=1219),
    ),
    Question(
        number=6,
        text="Peut-on changer de filière facilement à l'université en France ?",
        english="Can you easily switch your field of study at a French university?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("18128894426508078",),
    ),
    Question(
        number=7,
        text="Nhớ đồ ăn Việt quá, ở Pháp có cách nào không?",
        english="I miss Vietnamese food a lot; what are my options in France?",
        rule=AnswerRule.BOTH,
        gold_unit_ids=("18102395354566129", "18133654129644298"),
    ),
    Question(
        number=8,
        text="Đi brocante ở Versailles có rẻ hơn Paris không?",
        english="Is a brocante in Versailles cheaper than Paris?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("18042552590841773",),
        gold_span=GoldSpan(start=1141, end=1363),
    ),
    Question(
        number=9,
        text="Bút ngòi 1,0 mm nào viết êm tay?",
        english="Which 1.0 mm pen writes smoothly?",
        rule=AnswerRule.SINGLE,
        gold_unit_ids=("18645332647003724",),
    ),
    Question(
        number=10,
        text="Gia hạn titre de séjour cần giấy tờ gì?",
        english="What documents do I need to renew a residence permit?",
        rule=AnswerRule.NONE,
        gold_unit_ids=(),
    ),
)


def check_gold(units: Sequence[Unit], questions: Sequence[Question] = QUESTIONS) -> None:
    """Mọi mã bài đáp án có trong tập, mọi vị trí nằm trong `full_text`.

    CI không có DB thật nên chạy hàm này trên bài giả có đúng độ dài đóng băng (kiểm mã bài và 2
    vị trí); bước dựng (chặng 3, chưa có) chạy lại trên bài thật."""
    texts = {unit.id: unit.full_text for unit in units}
    for question in questions:
        for unit_id in question.gold_unit_ids:
            if unit_id not in texts:
                raise CorpusChangedError(f"câu {question.number}: {unit_id} không có trong tập")
            span = question.gold_span
            if span is not None and not 0 <= span.start < span.end <= len(texts[unit_id]):
                raise CorpusChangedError(f"câu {question.number}: vị trí ngoài {unit_id}")


def gold_chunk_ids(question: Question, chunks: Sequence[Chunk]) -> dict[str, tuple[int, ...]]:
    """Với mỗi bài đáp án, các chunk trúng (ADR-0038 D7). Python chỉ đánh dấu, không xếp hạng.

    Câu có vị trí: chunk phải chạm đoạn đó, chạm một phần cũng tính. Mọi bài đáp án đều có khoá, kể
    cả khi không chunk nào trúng, để bước sau phân biệt được "không tìm thấy".
    """
    span = question.gold_span
    hits: dict[str, list[int]] = {unit_id: [] for unit_id in question.gold_unit_ids}
    for chunk in chunks:
        if chunk.unit_id not in hits:
            continue
        if span is None or (chunk.start < span.end and chunk.end > span.start):
            hits[chunk.unit_id].append(chunk.id)
    return {unit_id: tuple(ids) for unit_id, ids in hits.items()}
