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
