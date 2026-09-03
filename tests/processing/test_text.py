import unicodedata

from src.processing.text import normalize_text


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("hello   world\n\nnew line") == "hello world new line"


def test_normalize_text_strips_leading_trailing_whitespace() -> None:
    assert normalize_text("  hello  ") == "hello"


def test_normalize_text_preserves_emoji_and_hashtag() -> None:
    # Nguyên tắc "không clean quá tay" — emoji/hashtag là tín hiệu thật, giữ nguyên.
    text = "Đi làm muộn 😭🔥 #alternance #Paris"
    assert normalize_text(text) == text


def test_normalize_text_strips_trailing_punctuation_glued_to_url() -> None:
    text = "check this out https://example.com/a."
    assert normalize_text(text) == "check this out https://example.com/a"


def test_normalize_text_keeps_url_query_params_intact() -> None:
    text = "link: https://example.com/a?x=1&y=2"
    assert normalize_text(text) == text


def test_normalize_text_empty_string_returns_empty_string() -> None:
    assert normalize_text("") == ""


def test_normalize_text_composes_nfd_input_into_nfc() -> None:
    # "ề" typed as decomposed NFD (e + combining circumflex + combining grave) —
    # a real artifact of some input methods/copy-paste sources — must collapse to
    # the single precomposed NFC codepoint, so two visually-identical strings
    # compare/embed as the same string.
    nfd_text = unicodedata.normalize("NFD", "đi làm về")
    assert normalize_text(nfd_text) == unicodedata.normalize("NFC", "đi làm về")


def test_normalize_text_unifies_old_style_oa_tone_mark_to_new_style() -> None:
    assert normalize_text("hoà bình") == "hòa bình"
    assert normalize_text("Hoà Bình") == "Hòa Bình"


def test_normalize_text_unifies_old_style_uy_tone_mark_to_new_style() -> None:
    assert normalize_text("thuý kiều") == "thúy kiều"
    assert normalize_text("luỹ tre") == "lũy tre"


def test_normalize_text_leaves_already_new_style_tone_marks_unchanged() -> None:
    assert normalize_text("hòa bình, thúy kiều") == "hòa bình, thúy kiều"
