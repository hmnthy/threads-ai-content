"""`LanguageInfo` — metadata ngôn ngữ cho MỖI `ContentUnit.full_text`, dùng
`lingua-py` (KHÔNG dùng `langdetect`) theo 3 nguyên tắc từ paper "Challenges of
Computational Processing of Code-Switching" (xem docs/claude/data-model.md "NLP
Pipeline"):

1. Code-switching là metadata, KHÔNG phải routing constraint — module này chạy độc
   lập với `embeddings.py`, KHÔNG có bước "detect ngôn ngữ → chọn model xử lý riêng".
2. `language_mix_score` là continuous score, KHÔNG phải boolean `has_french_mix` —
   ranh giới code-switch vs từ mượn (VD "deploy"/"model"/"production") không rõ
   ràng, kể cả human annotator cũng không thống nhất.
3. Ưu tiên "không chắc" hơn "chắc sai" — `primary_language` cho phép `None` khi
   confidence thấp, không ép argmax.

**Layer 9 (2026-09-03) — Code-Mixing Index thay công thức span-based cũ**:
`language_mix_score` giờ tính bằng **Code-Mixing Index (CMI)**, định nghĩa học
thuật gốc từ Gambäck & Das ("On Measuring the Complexity of Code-Mixing", 2014):

    CMI = 100 * (1 - max(w_i) / (n - u))   nếu n > u
    CMI = 0                                 nếu n = u

trong đó `n` = tổng số token, `u` = số token "language-independent" (LID không
gán được ngôn ngữ nào — tagged "unknown"), `w_i` = số token của ngôn ngữ i,
`max(w_i)` = số token của ngôn ngữ CHIẾM ƯU THẾ (matrix language) trong phần còn
lại. Thang đo 0-100 (KHÁC thang 0.0-1.0 của công thức span-based cũ) — cố tình
giữ đúng thang chuẩn học thuật để so sánh trực tiếp được với benchmark VietMix
(CMI≈21.7 trên data Threads VI-EN thật, xem docs/claude/data-model.md "NLP
Pipeline" mục CMI) — "kênh này CMI=X so với 21.7 của VietMix" là 1 con số citable
thật cho report, khác thang thì không so sánh được.

Vì sao đổi khỏi công thức cũ: `_language_mix_score` bản trước dựa trên
`detect_multiple_languages_of()` — CHÍNH lingua-py gắn nhãn hàm này là
"experimental", kém tin cậy trên đoạn ngắn (social media post điển hình).

**LID cấp từ — hybrid, KHÔNG chỉ dựa vào lingua**: (1) từ điển borrowing chuyên
ngành đã biết trước (`_BORROWED_TERMS` — "alternance", "CDI", "CV", "entretien",
"stage", "titre de séjour"... — từ vựng lặp lại thường xuyên trong nội dung kênh,
tra cứu trực tiếp đáng tin hơn LID thống kê trên 1 từ đơn lẻ rất ngắn); (2) lingua-py
`detect_language_of()` CHẠY PER-TOKEN (API ổn định, KHÁC `detect_multiple_languages_of`
đã bỏ) làm fallback cho từ không có trong dict; (3) fallback cuối `"unknown"` nếu
cả 2 bước trên không gán được ngôn ngữ nào (nguyên tắc 3 ở trên: "không chắc" hơn
"chắc sai" — áp dụng luôn ở cấp từ, không chỉ cấp câu).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from lingua import ConfidenceValue, Language, LanguageDetector, LanguageDetectorBuilder

# Kênh chủ yếu trộn VI/FR/EN (tác giả người Việt sống tại Pháp) — giới hạn candidate
# languages giúp lingua chính xác hơn trên short text so với from_all_languages()
# (~75 ngôn ngữ, dễ nhầm trên câu ngắn). Mở rộng nếu phát hiện ngôn ngữ khác trong data.
_CANDIDATE_LANGUAGES = (Language.VIETNAMESE, Language.FRENCH, Language.ENGLISH)

# Nguyên tắc 3: confidence dưới ngưỡng này → primary_language = None thay vì ép argmax.
# Hypothesis ban đầu, VẪN CHƯA calibrate bằng data thật (Layer 9 chỉ rà soát lại giá
# trị này, KHÔNG có bước calibrate thực nghiệm trong đợt sửa này — cần review tay 1
# mẫu post thật + nhãn confidence kỳ vọng trước khi coi là "đã calibrate", chưa làm).
MIN_CONFIDENCE_FOR_PRIMARY = 0.5

# Hybrid LID — bước 1: dict tra cứu trực tiếp cho từ mượn chuyên ngành lặp lại
# thường xuyên trong nội dung kênh (alternance/CV/xin việc/định cư tại Pháp). Danh
# sách khởi tạo nhỏ, MỞ RỘNG khi phát hiện từ mượn phổ biến khác gây nhiễu LID.
# Key viết thường — tra cứu case-insensitive (xem `_token_language`).
_BORROWED_TERMS: Final[dict[str, str]] = {
    "alternance": "fr",
    "cdi": "fr",
    "cdd": "fr",
    "cv": "fr",
    "entretien": "fr",
    "stage": "fr",
    "stagiaire": "fr",
    "titre": "fr",
    "séjour": "fr",
    "sejour": "fr",  # không dấu — hay gặp khi gõ nhanh trên mobile
    "master": "fr",
    "alternant": "fr",
    "alternante": "fr",
}

# Token = chuỗi ký tự chữ cái Unicode liên tiếp (loại số/dấu câu/emoji/ký hiệu #@ —
# hashtag "#alternance" vẫn bắt được "alternance" làm 1 token, đúng ý "nội dung
# ngôn ngữ thật nằm trong hashtag", không phải bản thân ký hiệu #).
_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class LanguageInfo:
    primary_language: str | None  # ISO 639-1 lowercase (VD "vi"), None nếu confidence thấp
    detected_languages: list[str]  # ngôn ngữ tìm thấy qua hybrid LID cấp từ (xem module docstring)
    confidence: float  # confidence của primary_language (0.0 nếu primary_language=None)
    language_mix_score: float  # Code-Mixing Index, thang 0-100 (0 = thuần 1 ngôn ngữ)


@lru_cache(maxsize=1)
def _detector() -> LanguageDetector:
    return LanguageDetectorBuilder.from_languages(*_CANDIDATE_LANGUAGES).build()


def detect_language_info(text: str) -> LanguageInfo:
    """Chạy trên `ContentUnit.full_text` (raw, chưa qua normalize_text() cũng
    được — lingua tự xử lý whitespace/punctuation)."""
    if not text.strip():
        return LanguageInfo(
            primary_language=None, detected_languages=[], confidence=0.0, language_mix_score=0.0
        )

    detector = _detector()
    confidences: list[ConfidenceValue] = detector.compute_language_confidence_values(text)
    top = confidences[0] if confidences else None
    primary_language = (
        _iso_code(top.language)
        if top is not None and top.value >= MIN_CONFIDENCE_FOR_PRIMARY
        else None
    )
    confidence = top.value if top is not None else 0.0

    tags = [_token_language(token, detector) for token in _WORD_PATTERN.findall(text)]
    detected_languages = sorted({tag for tag in tags if tag != "unknown"})
    mix_score = _code_mixing_index(tags)

    return LanguageInfo(
        primary_language=primary_language,
        detected_languages=detected_languages,
        confidence=confidence,
        language_mix_score=mix_score,
    )


def _iso_code(language: Language) -> str:
    return language.iso_code_639_1.name.lower()


def _token_language(token: str, detector: LanguageDetector) -> str:
    """Hybrid LID cấp từ — xem module docstring cho thứ tự 3 bước.
    `"unknown"` = token đóng vai trò `u` trong công thức CMI (không tính vào ngôn
    ngữ nào, cũng không tính vào mẫu số `n - u`)."""
    borrowed = _BORROWED_TERMS.get(token.lower())
    if borrowed is not None:
        return borrowed
    detected = detector.detect_language_of(token)
    return _iso_code(detected) if detected is not None else "unknown"


def _code_mixing_index(tags: list[str]) -> float:
    """CMI = 100 * (1 - max(w_i) / (n - u)); 0 nếu n == u (không có token nào gán
    được ngôn ngữ) — xem công thức đầy đủ + trích dẫn ở module docstring."""
    n = len(tags)
    if n == 0:
        return 0.0
    u = sum(1 for tag in tags if tag == "unknown")
    if n == u:
        return 0.0
    counts = Counter(tag for tag in tags if tag != "unknown")
    dominant_count = max(counts.values())
    return 100 * (1 - dominant_count / (n - u))
