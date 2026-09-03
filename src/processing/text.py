"""`raw_text` bất biến + `normalize_text()`.

Theo nguyên tắc 2 tại docs/claude/data-model.md ("Giữ nguyên ngữ liệu, không clean
quá tay") — normalize CHỈ whitespace + URL + chuẩn hoá Unicode/chính tả (không đổi
nghĩa), KHÔNG strip emoji/hashtag/"từ nước ngoài". Social media text: emoji/hashtag
mang tín hiệu sentiment/virality thật.

`raw_text` không có hàm riêng — nó chính là `ContentUnit.full_text` chưa qua biến
đổi gì (xem `src/db/schema.py` `update_content_unit_text`, gọi hàm này để tạo
`normalized_text` rồi lưu song song cả 2 cột).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

_WHITESPACE_PATTERN = re.compile(r"\s+")
_URL_PATTERN = re.compile(r"https?://\S+")
_URL_TRAILING_PUNCTUATION = ".,!?)];:\"'"

# Layer 9 (2026-09-03) — gộp 2 cách đặt dấu thanh tiếng Việt cho cụm "oa"/"uy":
# kiểu CŨ đặt dấu trên nguyên âm SAU ("hoà", "thuý"), kiểu MỚI (chuẩn chính tả cải
# cách 1980, dùng trong từ điển hiện hành/corpus NLP tiếng Việt như VLSP) đặt dấu
# trên nguyên âm ĐẦU ("hòa", "thúy"). Cả 2 vẫn phổ biến trên social media thật —
# không unify sẽ khiến 2 lần gõ khác nhau của CÙNG 1 từ bị embedding/tokenize
# thành 2 chuỗi ký tự khác nhau. Canonical hoá về kiểu MỚI (chọn 1 chiều duy nhất,
# không giữ cả 2 dạng). Chỉ liệt kê 2 cụm "oa"/"uy" (nguồn research đã xác nhận
# đây là 2 cụm phổ biến nhất gây khác biệt) — mở rộng nếu phát hiện cụm khác.
_TONE_MARK_UNIFICATION: Final[tuple[tuple[str, str], ...]] = (
    ("oà", "òa"),
    ("oá", "óa"),
    ("oả", "ỏa"),
    ("oã", "õa"),
    ("oạ", "ọa"),
    ("uý", "úy"),
    ("uỳ", "ùy"),
    ("uỷ", "ủy"),
    ("uỹ", "ũy"),
    ("uỵ", "ụy"),
    ("Oà", "Òa"),
    ("Oá", "Óa"),
    ("Oả", "Ỏa"),
    ("Oã", "Õa"),
    ("Oạ", "Ọa"),
    ("Uý", "Úy"),
    ("Uỳ", "Ùy"),
    ("Uỷ", "Ủy"),
    ("Uỹ", "Ũy"),
    ("Uỵ", "Ụy"),
    ("OÀ", "ÒA"),
    ("OÁ", "ÓA"),
    ("OẢ", "ỎA"),
    ("OÃ", "ÕA"),
    ("OẠ", "ỌA"),
    ("UÝ", "ÚY"),
    ("UỲ", "ÙY"),
    ("UỶ", "ỦY"),
    ("UỸ", "ŨY"),
    ("UỴ", "ỤY"),
)


def normalize_text(text: str) -> str:
    """Chuẩn hoá tối thiểu: Unicode NFC (gộp tổ hợp base+combining-mark thành 1
    codepoint sẵn có — 1 số nguồn gõ/copy-paste tạo ra dạng NFD phân rã, khiến 2
    chuỗi NHÌN giống hệt nhau nhưng khác byte, hỏng string matching/embedding) +
    gộp dấu thanh cũ/mới cho cụm "oa"/"uy" (`_TONE_MARK_UNIFICATION`, PHẢI chạy
    SAU NFC — cần dạng precomposed để so khớp) + gộp whitespace liên tiếp
    (space/tab/newline) thành 1 space + trim 2 đầu; với URL, bỏ dấu câu tiếng
    Việt/Anh thường bị dính vào cuối URL do người viết gõ liền (VD "...xem thêm
    tại a.com." → dấu "." cuối câu không phải 1 phần URL). KHÔNG động vào
    emoji/hashtag/nội dung khác.
    """
    nfc = unicodedata.normalize("NFC", text)
    unified = _unify_tone_marks(nfc)
    collapsed = _WHITESPACE_PATTERN.sub(" ", unified).strip()
    return _URL_PATTERN.sub(_strip_url_trailing_punctuation, collapsed)


def _unify_tone_marks(text: str) -> str:
    for old, new in _TONE_MARK_UNIFICATION:
        text = text.replace(old, new)
    return text


def _strip_url_trailing_punctuation(match: re.Match[str]) -> str:
    return match.group(0).rstrip(_URL_TRAILING_PUNCTUATION)
