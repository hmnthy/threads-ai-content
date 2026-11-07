"""7 cách chia đoạn của demo RAG (ADR-0039 D1). Câu tự đặt, không dùng chữ bài thật (repo public).

Vị trí mong đợi tính tay, không suy ra từ code đang kiểm.
"""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from src.rag_demo.chunking import (
    FIXED_SIZES,
    RECURSIVE_MAX_CHARS,
    SEMANTIC_BREAK_PERCENTILE,
    SEMANTIC_MAX_CHARS,
    Chunk,
    ChunkingWay,
    _fixed_spans,
    _recursive_spans,
    _trim,
    build_chunks,
    split_sentences,
)
from src.rag_demo.corpus import PostSpan, Unit

SMILE = "\U0001f600"  # ngoài vùng BMP: Python đếm 1, JavaScript đếm 2
HEART_WITH_STYLE = "❤️"


def make_unit(text: str, unit_id: str = "u1", posts: tuple[PostSpan, ...] = ()) -> Unit:
    return Unit(id=unit_id, full_text=text, posts=posts)


def at_angles(*degrees: float) -> NDArray[np.float64]:
    """Vector 2 chiều theo góc: cosine giữa 2 câu liền kề = cos(hiệu 2 góc), tính tay được."""
    radians = [math.radians(degree) for degree in degrees]
    return np.array([[math.cos(r), math.sin(r)] for r in radians])


def spans(chunks: list[Chunk]) -> list[tuple[int, int]]:
    return [(c.start, c.end) for c in chunks]


# --- Hằng số -----------------------------------------------------------------------------------


def test_constants_match_adr_0039() -> None:
    assert FIXED_SIZES == {
        ChunkingWay.FIXED_300: (300, 40),
        ChunkingWay.FIXED_500: (500, 60),
        ChunkingWay.FIXED_800: (800, 100),
    }
    assert RECURSIVE_MAX_CHARS == 500
    assert SEMANTIC_BREAK_PERCENTILE == 25
    assert SEMANTIC_MAX_CHARS == 800
    assert len(ChunkingWay) == 7


# --- Tách câu ----------------------------------------------------------------------------------


def test_split_sentences_at_end_marks_and_newlines() -> None:
    assert split_sentences("Một câu. Câu hai!\nCâu ba") == [(0, 8), (9, 17), (18, 24)]


def test_split_sentences_keeps_decimal_numbers_whole() -> None:
    assert split_sentences("Bút 1,0 mm. Giá 3.5 euro") == [(0, 11), (12, 24)]


def test_split_sentences_counts_python_code_points() -> None:
    text = f"Đi {SMILE} chợ. Mua rau."
    assert split_sentences(text) == [(0, 9), (10, 18)]
    assert text[10:18] == "Mua rau."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"Câu một.\n{SMILE}\nCâu hai.", [(0, 10), (11, 19)]),  # emoji riêng dòng về câu trước
        (f"Câu một.\n{HEART_WITH_STYLE}\nCâu hai.", [(0, 11), (12, 20)]),  # kèm U+FE0F
        ("Câu một. ▓", [(0, 10)]),  # ký hiệu ở cuối bài
    ],
)
def test_symbol_only_fragment_joins_previous_sentence(
    text: str, expected: list[tuple[int, int]]
) -> None:
    assert split_sentences(text) == expected


def test_symbol_only_fragment_at_the_start_joins_next_sentence() -> None:
    assert split_sentences(f"{SMILE}\nCâu một.") == [(0, 10)]


def test_text_with_only_symbols_is_one_sentence() -> None:
    assert split_sentences(f"{SMILE}\n▓") == [(0, 3)]


def test_line_with_only_digits_stays_its_own_sentence() -> None:
    assert split_sentences("Câu một.\n12\nCâu hai.") == [(0, 8), (9, 11), (12, 20)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mục:\n1. Một.\n2. Hai.", [(0, 4), (5, 12), (13, 20)]),  # số riêng dòng về câu sau
        ("1. Mục một.", [(0, 11)]),  # số ở đầu bài
        ("Câu một 2. Câu hai.", [(0, 7), (8, 19)]),  # số ở cuối một câu chưa có dấu chấm
        (f"Câu một. {SMILE} 3. Câu ba.", [(0, 10), (11, 21)]),  # emoji về trước, số về sau
        ("Câu một. 2.", [(0, 11)]),  # không có câu sau: ở lại câu trước
        ("Năm 2026. Câu hai.", [(0, 9), (10, 18)]),  # năm không phải số thứ tự
        ("1.\n2.\nCâu ba.", [(0, 13)]),  # số liên tiếp dồn về câu sau
        ("2.", [(0, 2)]),  # bài chỉ có một số
        (f"2.\n{SMILE}\nCâu.", [(0, 9)]),  # ký hiệu giữa số và câu sau
        (f"{SMILE} 2. Câu.", [(0, 9)]),  # ký hiệu đầu bài rồi mới đến số
        ("Giá 10. Rẻ.", [(0, 3), (4, 11)]),  # giới hạn đã chấp nhận: số thường cũng bị bắt
    ],
)
def test_list_number_joins_the_next_sentence(text: str, expected: list[tuple[int, int]]) -> None:
    assert split_sentences(text) == expected


def test_split_sentences_empty_text() -> None:
    assert split_sentences("") == []
    assert split_sentences(" \n ") == []


# --- Cỡ cố định --------------------------------------------------------------------------------


def test_fixed_breaks_at_spaces_with_overlap() -> None:
    text = "aaaa bbbb cccc dddd eeee"
    assert _fixed_spans(text, 10, 5) == [(0, 9), (5, 14), (10, 19), (15, 24)]


def test_fixed_never_starts_mid_word_when_overlap_has_no_space() -> None:
    text = "aaaa bbbb cccc dddd eeee"
    assert _fixed_spans(text, 10, 3) == [(0, 9), (9, 14), (14, 24)]


def test_fixed_cuts_hard_when_there_is_no_space() -> None:
    assert _fixed_spans("a" * 25, 10, 3) == [(0, 10), (10, 20), (20, 25)]


def test_fixed_ignores_a_space_in_the_first_half_of_the_window() -> None:
    """Dấu cách quá gần đầu cửa sổ sẽ tạo đoạn tí hon, nên chỉ tìm ở nửa sau."""
    assert _fixed_spans("aaaa " + "b" * 20, 10, 3) == [(0, 10), (10, 20), (20, 25)]


@pytest.mark.parametrize(
    ("way", "expected"),
    [
        (ChunkingWay.FIXED_300, [(0, 299), (260, 559), (520, 819), (780, 999)]),
        (ChunkingWay.FIXED_500, [(0, 499), (440, 939), (880, 999)]),
        (ChunkingWay.FIXED_800, [(0, 799), (700, 999)]),
    ],
)
def test_fixed_ways_use_their_own_size_and_overlap(
    way: ChunkingWay, expected: list[tuple[int, int]]
) -> None:
    text = " ".join(["abcd"] * 200)  # dấu cách ở vị trí 4, 9, 14…; dài 999
    assert spans(build_chunks([make_unit(text)], way)) == expected


# --- Recursive ---------------------------------------------------------------------------------

THREE_PARAGRAPHS = "Đoạn một.\n\nĐoạn hai.\n\nĐoạn ba dài hơn. Có hai câu."


def test_recursive_falls_to_sentences_only_for_long_paragraphs() -> None:
    assert _recursive_spans(THREE_PARAGRAPHS, 20) == [(0, 20), (22, 38), (39, 50)]


def test_recursive_keeps_paragraph_that_fits() -> None:
    assert _recursive_spans(THREE_PARAGRAPHS, 30) == [(0, 20), (22, 50)]


def test_recursive_single_newline_is_not_a_paragraph_break() -> None:
    assert _recursive_spans("Một.\nHai.", 20) == [(0, 9)]


def test_recursive_keeps_a_sentence_longer_than_the_cap() -> None:
    assert _recursive_spans("x" * 30, 20) == [(0, 30)]


def test_recursive_keeps_a_paragraph_of_exactly_the_cap_whole() -> None:
    paragraph = "Bbbbbbb. Ccccccccccc"
    assert len(paragraph) == 20
    assert _recursive_spans("aaaaa\n\n" + paragraph, 20) == [(0, 5), (7, 27)]


def test_recursive_merges_up_to_exactly_the_cap() -> None:
    fits = "a" * 400 + "\n\n" + "b" * 98
    assert len(fits) == 500
    over = "a" * 400 + "\n\n" + "b" * 99
    assert spans(build_chunks([make_unit(fits)], ChunkingWay.RECURSIVE_500)) == [(0, 500)]
    assert spans(build_chunks([make_unit(over)], ChunkingWay.RECURSIVE_500)) == [
        (0, 400),
        (402, 501),
    ]


# --- Semantic ----------------------------------------------------------------------------------


def test_semantic_breaks_where_similarity_is_in_lowest_quarter() -> None:
    # Hiệu góc 20, 80, 30, 40 → cos ≈ 0,94 / 0,17 / 0,87 / 0,77; phân vị 25 ≈ 0,62: chỉ ngắt ở 80.
    unit = make_unit("Một. Hai. Ba. Bốn. Năm.")
    chunks = build_chunks([unit], ChunkingWay.SEMANTIC, {"u1": at_angles(0, 20, 100, 130, 170)})
    assert [c.text for c in chunks] == ["Một. Hai.", "Ba. Bốn. Năm."]


def test_semantic_ignores_vector_length() -> None:
    """Cùng góc với test trên, chỉ khác độ dài vector: cosine không đổi nên cách ngắt không đổi."""
    unit = make_unit("Một. Hai. Ba. Bốn. Năm.")
    lengths = np.array([[1.0], [100.0], [0.01], [5.0], [2.0]])
    vectors = at_angles(0, 20, 100, 130, 170) * lengths
    chunks = build_chunks([unit], ChunkingWay.SEMANTIC, {"u1": vectors})
    assert [c.text for c in chunks] == ["Một. Hai.", "Ba. Bốn. Năm."]


def test_semantic_threshold_is_shared_across_all_units() -> None:
    # Bài A liền mạch (cos ≈ 0,98 / 0,94 / 0,87), bài B rời rạc (0,17 / 0,09). Phân vị 25 chung =
    # 0,17 nên A không bị ngắt; ngưỡng riêng từng bài sẽ ngắt A ở cặp 0,87.
    smooth = make_unit("Một. Hai. Ba. Bốn.", "a")
    rough = make_unit("Một. Hai. Ba.", "b")
    chunks = build_chunks(
        [smooth, rough],
        ChunkingWay.SEMANTIC,
        {"a": at_angles(0, 10, 30, 60), "b": at_angles(0, 80, 165)},
    )
    assert [(c.unit_id, c.text) for c in chunks] == [
        ("a", "Một. Hai. Ba. Bốn."),
        ("b", "Một. Hai."),
        ("b", "Ba."),
    ]


def test_semantic_breaks_at_the_cap_even_when_sentences_are_alike() -> None:
    sentence = "a" * 299 + "."
    text = " ".join([sentence] * 3)  # câu ở (0, 300), (301, 601), (602, 902)
    chunks = build_chunks([make_unit(text)], ChunkingWay.SEMANTIC, {"u1": at_angles(0, 0, 0)})
    assert spans(chunks) == [(0, 601), (602, 902)]


def test_semantic_cap_is_inclusive() -> None:
    text = "a" * 398 + ". " + "b" * 399 + "."
    assert len(text) == 800
    chunks = build_chunks([make_unit(text)], ChunkingWay.SEMANTIC, {"u1": at_angles(0, 0)})
    assert spans(chunks) == [(0, 800)]


def test_semantic_with_only_one_sentence_per_unit() -> None:
    chunks = build_chunks(
        [make_unit("Một câu.", "a"), make_unit("Câu khác.", "b")],
        ChunkingWay.SEMANTIC,
        {"a": at_angles(0), "b": at_angles(90)},
    )
    assert [c.text for c in chunks] == ["Một câu.", "Câu khác."]


def test_semantic_needs_vectors() -> None:
    with pytest.raises(ValueError, match="vector"):
        build_chunks([make_unit("Một.")], ChunkingWay.SEMANTIC)


def test_semantic_rejects_wrong_vector_count() -> None:
    with pytest.raises(ValueError, match="1 vector cho 2 câu"):
        build_chunks([make_unit("Một. Hai.")], ChunkingWay.SEMANTIC, {"u1": at_angles(0)})


def test_semantic_rejects_nan_vector() -> None:
    """Một NaN làm ngưỡng chung thành NaN, mọi phép so sai, và cả tập âm thầm không ngắt nữa."""
    vectors = at_angles(0, 90, 180)
    vectors[1, 0] = float("nan")
    with pytest.raises(ValueError, match="không hữu hạn"):
        build_chunks([make_unit("Một. Hai. Ba.")], ChunkingWay.SEMANTIC, {"u1": vectors})


def test_semantic_rejects_zero_vector() -> None:
    with pytest.raises(ValueError, match="bằng 0"):
        build_chunks([make_unit("Một. Hai.")], ChunkingWay.SEMANTIC, {"u1": np.zeros((2, 2))})


# --- Không chia, theo post, tính chất chung ----------------------------------------------------


def test_whole_unit_is_one_chunk() -> None:
    assert spans(build_chunks([make_unit("Một. Hai.")], ChunkingWay.WHOLE)) == [(0, 9)]


def test_post_way_follows_post_spans() -> None:
    unit = make_unit("Post một. Post hai.", posts=(PostSpan("p1", 0, 9), PostSpan("p2", 10, 19)))
    assert [c.text for c in build_chunks([unit], ChunkingWay.POST)] == ["Post một.", "Post hai."]


def test_chunk_ids_follow_unit_order_then_position() -> None:
    first = make_unit("Bài một.", "newer", (PostSpan("p1", 0, 3), PostSpan("p2", 4, 8)))
    second = make_unit("Bài hai.", "older", (PostSpan("p3", 0, 8),))
    chunks = build_chunks([first, second], ChunkingWay.POST)
    assert [(c.id, c.unit_id, c.start) for c in chunks] == [
        (0, "newer", 0),
        (1, "newer", 4),
        (2, "older", 0),
    ]


def test_trim_removes_only_edge_whitespace() -> None:
    assert _trim("  ab c\n ", (0, 8)) == (2, 6)
    assert _trim("ab", (0, 2)) == (0, 2)
    assert _trim("   ", (0, 3)) is None


@pytest.mark.parametrize("way", list(ChunkingWay))
def test_every_way_keeps_offsets_and_covers_every_visible_character(way: ChunkingWay) -> None:
    text = (
        f"Câu đầu khá dài để có chỗ ngắt. \n\n{SMILE}\n\n"
        "Câu hai có số 1,0 mm. Câu ba!\n▓\nCâu bốn ở cuối. ▓"
    )
    unit = make_unit(text, posts=(PostSpan("p1", 0, len(text)),))
    sentence_count = len(split_sentences(text))
    assert sentence_count >= 4
    vectors = {"u1": at_angles(*[index * 70 for index in range(sentence_count)])}
    chunks = build_chunks([unit], way, vectors)

    covered: set[int] = set()
    for chunk in chunks:
        assert chunk.text == text[chunk.start : chunk.end]
        assert chunk.text == chunk.text.strip()
        covered.update(range(chunk.start, chunk.end))
    missing = [i for i, char in enumerate(text) if not char.isspace() and i not in covered]
    assert missing == []
