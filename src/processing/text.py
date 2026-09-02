"""`raw_text` bất biến + `normalize_text()`.

Theo nguyên tắc 2 tại docs/claude/data-model.md ("Giữ nguyên ngữ liệu, không clean
quá tay") — normalize CHỈ whitespace + URL, KHÔNG strip emoji/hashtag/"từ nước
ngoài". Social media text: emoji/hashtag mang tín hiệu sentiment/virality thật.

`raw_text` không có hàm riêng — nó chính là `ContentUnit.full_text` chưa qua biến
đổi gì (xem `src/db/schema.py` `update_content_unit_text`, gọi hàm này để tạo
`normalized_text` rồi lưu song song cả 2 cột).
"""

from __future__ import annotations

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")
_URL_PATTERN = re.compile(r"https?://\S+")
_URL_TRAILING_PUNCTUATION = ".,!?)];:\"'"


def normalize_text(text: str) -> str:
    """Chuẩn hoá tối thiểu: gộp mọi whitespace liên tiếp (space/tab/newline) thành
    1 space + trim 2 đầu; với URL, bỏ dấu câu tiếng Việt/Anh thường bị dính vào
    cuối URL do người viết gõ liền (VD "...xem thêm tại a.com." → dấu "." cuối câu
    không phải 1 phần URL). KHÔNG động vào emoji/hashtag/nội dung khác.
    """
    collapsed = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return _URL_PATTERN.sub(_strip_url_trailing_punctuation, collapsed)


def _strip_url_trailing_punctuation(match: re.Match[str]) -> str:
    return match.group(0).rstrip(_URL_TRAILING_PUNCTUATION)
