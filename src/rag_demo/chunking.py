"""7 cách chia đoạn của demo RAG (ADR-0039 D1), mỗi chunk giữ vị trí trong `full_text`.

Chunk lấy từ `full_text`, không từ `normalized_text` (bước chuẩn hoá làm méo chữ, ADR-0039). Vị trí
đếm theo điểm mã Unicode của Python; trình duyệt không tự tính vị trí (ADR-0038 D7).

Quyết định của Thy 2026-11-06 cho những chỗ ADR-0039 chưa ghi: mảnh chỉ có emoji / ký hiệu gắn vào
câu đứng trước; ngưỡng semantic tính chung trên mọi cặp câu của cả tập. Một câu dài hơn trần giữ
nguyên, không cắt giữa câu: câu dài nhất của 20 bài lúc đóng băng là 230 ký tự nên chưa gặp.

Số đo trong module này đo 2026-11-06 → 07 trên 20 bài lúc đóng băng, trước khi ADR-0040 bỏ 1 bài.

Ranh giới post không phải điểm ngắt câu cứng (Thy chốt 2026-11-07): post nối bằng dấu cách và
thường không kết thúc bằng dấu câu, nhưng trên 20 bài chỉ 3 / 350 câu chứa chữ của 2 post (28 ca
khác chỉ là ký hiệu cuối post dính sang câu sau); ngắt cứng đo bằng vector thay thế không đổi gì
đáng kể, và giữ nguyên thì số đoạn của 6 cách đã đo trong ADR-0039 (trừ semantic) vẫn đúng.

Số thứ tự danh sách ("2.") gắn vào câu sau (Thy chốt 2026-11-07): dấu chấm của nó khớp luật kết câu,
nên trước khi sửa 20 bài có 6 câu chỉ gồm số thứ tự và 2 câu mang số thứ tự ở cuối. Sửa xong còn 350
câu (trước là 357; một emoji đứng ngay trước số thứ tự gắn về câu trước theo luật trên). Cỡ cố
định không dùng câu, recursive chỉ xuống câu ở đoạn văn dài hơn trần: cả 4 cách giữ nguyên số đoạn.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from src.rag_demo.corpus import Unit

# Vị trí nửa mở [đầu, cuối)
Span = tuple[int, int]
SentenceVectors = Mapping[str, NDArray[np.float64]]


class ChunkingWay(StrEnum):
    WHOLE = "whole"
    POST = "post"
    FIXED_300 = "fixed_300"
    FIXED_500 = "fixed_500"
    FIXED_800 = "fixed_800"
    RECURSIVE_500 = "recursive_500"
    SEMANTIC = "semantic"


# (cỡ, chồng lấn) tính bằng ký tự. 500 ≈ trung vị độ dài post (473); 300 và 800 là một cỡ dưới
# và một cỡ trên post; chồng lấn ~12% nằm trong khoảng 10–15% README repo mẫu gợi ý (ADR-0039 D1).
FIXED_SIZES: dict[ChunkingWay, tuple[int, int]] = {
    ChunkingWay.FIXED_300: (300, 40),
    ChunkingWay.FIXED_500: (500, 60),
    ChunkingWay.FIXED_800: (800, 100),
}
# Chỉ tìm dấu cách ở nửa sau cửa sổ để đoạn không ngắn bất thường. Lựa chọn thiết kế theo script đo
# của ADR-0039, không có bằng chứng tối ưu.
FIXED_BREAK_WINDOW_DIVISOR = 2
RECURSIVE_MAX_CHARS = 500  # theo cỡ cố định giữa (ADR-0039 D1)
# Lựa chọn thiết kế để minh hoạ, không có bằng chứng tối ưu; 800 theo cỡ cố định lớn nhất
# (ADR-0039 D1).
SEMANTIC_BREAK_PERCENTILE = 25
SEMANTIC_MAX_CHARS = 800

_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")
_PARAGRAPH_BREAK = re.compile(r"\n{2,}")
# 1–2 chữ số nên năm ("2026.") không bị coi là số thứ tự. Giới hạn đã chấp nhận: mọi số 1–2 chữ số
# đứng cuối câu (giá, tuổi, "trang 3)") cũng bị coi là số thứ tự. Trên 20 bài đóng băng: 8 lần khớp,
# đều là danh sách thật, đều kết bằng "."; nhánh ")" 0 lần khớp.
_LIST_NUMBER_AT_END = re.compile(r"(?:^|\s)(\d{1,2}[.)])$")


@dataclass(frozen=True)
class Chunk:
    """`id` là vị trí trong danh sách của một cách chia, dùng phân hạng khi hoà (ADR-0038 D4)."""

    id: int
    unit_id: str
    start: int
    end: int
    text: str


def _trim(text: str, span: Span) -> Span | None:
    """Bỏ khoảng trắng ở 2 mép; không đổi token nào. Trả None nếu chỉ có khoảng trắng."""
    start, end = span
    piece = text[start:end]
    stripped = piece.strip()
    if not stripped:
        return None
    left = start + len(piece) - len(piece.lstrip())
    return left, left + len(stripped)


def _pieces_between(text: str, breaks: re.Pattern[str]) -> list[Span]:
    pieces: list[Span] = []
    start = 0
    for match in breaks.finditer(text):
        if match.start() > start:
            pieces.append((start, match.start()))
        start = match.end()
    if start < len(text):
        pieces.append((start, len(text)))
    return pieces


def _list_number_start(text: str, span: Span) -> int | None:
    """Vị trí số thứ tự danh sách ("2.", "3)") đứng cuối mảnh, sau khoảng trắng hoặc ở đầu mảnh."""
    start, end = span
    match = _LIST_NUMBER_AT_END.search(text[start:end])
    return None if match is None else start + match.start(1)


def split_sentences(text: str) -> list[Span]:
    """Tách câu ở dấu kết câu theo sau là khoảng trắng, hoặc ở xuống dòng.

    Mảnh không có chữ hay số (emoji, ký hiệu) gắn vào câu trước, mảnh ở đầu gắn vào câu sau, để mọi
    ký tự đều nằm trong một câu. Số thứ tự danh sách bị dấu chấm tách khỏi mục của nó ("2. Mục") gắn
    vào câu sau; không có câu sau thì ở lại câu trước.
    """
    sentences: list[Span] = []
    # Đầu mảnh đang chờ gắn vào câu sau: ký hiệu ở đầu bài, hoặc số thứ tự danh sách
    pending: int | None = None
    for piece in _pieces_between(text, _SENTENCE_BREAK):
        trimmed = _trim(text, piece)
        if trimmed is None:
            continue
        number_start = _list_number_start(text, trimmed)
        body = trimmed if number_start is None else _trim(text, (trimmed[0], number_start))
        if body is not None:
            start, end = body
            if any(char.isalnum() for char in text[start:end]):
                sentences.append((start if pending is None else pending, end))
                pending = None
            elif sentences and pending is None:
                sentences[-1] = (sentences[-1][0], end)
            elif pending is None:
                pending = start
        if number_start is not None and pending is None:
            pending = number_start
    if pending is not None:
        if not sentences:
            return [(pending, len(text.rstrip()))]
        sentences[-1] = (sentences[-1][0], len(text.rstrip()))
    return sentences


def _fixed_spans(text: str, size: int, overlap: int) -> list[Span]:
    """Cửa sổ cố định, ngắt ở dấu cách cuối cửa sổ; đoạn sau mở đầu ở đầu một từ.

    Chồng lấn thực tế có thể ngắn hơn `overlap` vì phải bắt đầu ở đầu từ. Vùng chồng lấn không có
    dấu cách thì đoạn sau bắt đầu ngay cuối đoạn trước, không cắt giữa từ.

    Dấu cách nằm đúng tại `start + size` không được tính, vì chỉ tìm trong cửa sổ nửa mở: cửa sổ
    kết thúc ngay trước dấu cách thì đoạn ngắt ở dấu cách trước đó và mất một từ cuối (21 / 93
    cửa sổ cỡ 300, 15 / 50 cỡ 500, 4 / 27 cỡ 800 trên 20 bài); từ đó thường vẫn có ở đầu đoạn sau
    nhờ chồng lấn. Thy chốt giữ nguyên 2026-11-07: tính cả dấu cách đó thì hạng BM25 đổi lẫn lộn
    (cỡ 300 câu 6 tốt hơn, cỡ 800 câu 1 từ hạng 1 xuống 3) và số của ADR-0039 không còn khớp.
    """
    spans: list[Span] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + size // FIXED_BREAK_WINDOW_DIVISOR, end)
            end = cut if cut > start else end
        spans.append((start, end))
        if end >= len(text):
            break
        space = text.find(" ", max(end - overlap, start + 1), end)
        start = space + 1 if space != -1 else end
    return spans


def _recursive_spans(text: str, max_chars: int) -> list[Span]:
    """Đoạn văn trước, đoạn văn dài hơn trần thì xuống câu, rồi gộp mảnh liền nhau tới hết trần."""
    pieces: list[Span] = []
    for start, end in _pieces_between(text, _PARAGRAPH_BREAK):
        if end - start <= max_chars:
            pieces.append((start, end))
        else:
            pieces += [
                (start + left, start + right) for left, right in split_sentences(text[start:end])
            ]
    merged: list[Span] = []
    for start, end in pieces:
        if merged and end - merged[-1][0] <= max_chars:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _adjacent_similarities(vectors: NDArray[np.float64]) -> NDArray[np.float64]:
    """Cosine giữa mỗi câu và câu liền sau."""
    if not np.isfinite(vectors).all():
        raise ValueError("vector câu có giá trị không hữu hạn")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("vector câu bằng 0 thì không có cosine")
    unit_vectors = vectors / norms
    similarities: NDArray[np.float64] = np.sum(unit_vectors[:-1] * unit_vectors[1:], axis=1)
    return similarities


def _break_at_similarity(
    sentences: Sequence[Span], similarities: NDArray[np.float64], threshold: float, max_chars: int
) -> list[Span]:
    """Ngắt khi độ giống dưới ngưỡng, hoặc khi thêm câu kế tiếp sẽ vượt trần."""
    spans: list[Span] = []
    start = sentences[0][0]
    for index, similarity in enumerate(similarities):
        next_end = sentences[index + 1][1]
        if similarity < threshold or next_end - start > max_chars:
            spans.append((start, sentences[index][1]))
            start = sentences[index + 1][0]
    spans.append((start, sentences[-1][1]))
    return spans


def _semantic_spans(
    units: Sequence[Unit], sentence_vectors: SentenceVectors
) -> dict[str, list[Span]]:
    """Vector đưa từ ngoài vào: mỗi bài một ma trận, mỗi hàng ứng với một câu của `split_sentences`.

    Ngưỡng tính chung trên mọi cặp câu của cả tập, nên bài liền mạch ít bị cắt hơn bài nhiều ý.
    """
    sentences = {unit.id: split_sentences(unit.full_text) for unit in units}
    similarities: dict[str, NDArray[np.float64]] = {}
    for unit in units:
        vectors = sentence_vectors[unit.id]
        if len(vectors) != len(sentences[unit.id]):
            raise ValueError(f"{unit.id}: {len(vectors)} vector cho {len(sentences[unit.id])} câu")
        similarities[unit.id] = _adjacent_similarities(vectors)
    pooled = np.concatenate(list(similarities.values()))
    threshold = float(np.percentile(pooled, SEMANTIC_BREAK_PERCENTILE)) if pooled.size else 0.0
    return {
        unit.id: _break_at_similarity(
            sentences[unit.id], similarities[unit.id], threshold, SEMANTIC_MAX_CHARS
        )
        for unit in units
    }


def _spans_of(unit: Unit, way: ChunkingWay) -> list[Span]:
    if way is ChunkingWay.WHOLE:
        return [(0, len(unit.full_text))]
    if way is ChunkingWay.POST:
        return [(post.start, post.end) for post in unit.posts]
    if way is ChunkingWay.RECURSIVE_500:
        return _recursive_spans(unit.full_text, RECURSIVE_MAX_CHARS)
    size, overlap = FIXED_SIZES[way]
    return _fixed_spans(unit.full_text, size, overlap)


def build_chunks(
    units: Sequence[Unit],
    way: ChunkingWay,
    sentence_vectors: SentenceVectors | None = None,
) -> list[Chunk]:
    """Chunk theo thứ tự bài rồi theo vị trí trong bài; mã chunk là vị trí trong danh sách."""
    if way is ChunkingWay.SEMANTIC:
        if sentence_vectors is None:
            raise ValueError("cách semantic cần vector của từng câu")
        spans_by_unit = _semantic_spans(units, sentence_vectors)
    else:
        spans_by_unit = {unit.id: _spans_of(unit, way) for unit in units}

    chunks: list[Chunk] = []
    for unit in units:
        for span in spans_by_unit[unit.id]:
            trimmed = _trim(unit.full_text, span)
            if trimmed is None:
                continue
            start, end = trimmed
            chunks.append(
                Chunk(
                    id=len(chunks),
                    unit_id=unit.id,
                    start=start,
                    end=end,
                    text=unit.full_text[start:end],
                )
            )
    return chunks
