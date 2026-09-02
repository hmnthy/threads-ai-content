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
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from lingua import (
    ConfidenceValue,
    DetectionResult,
    Language,
    LanguageDetector,
    LanguageDetectorBuilder,
)

# Kênh chủ yếu trộn VI/FR/EN (tác giả người Việt sống tại Pháp) — giới hạn candidate
# languages giúp lingua chính xác hơn trên short text so với from_all_languages()
# (~75 ngôn ngữ, dễ nhầm trên câu ngắn). Mở rộng nếu phát hiện ngôn ngữ khác trong data.
_CANDIDATE_LANGUAGES = (Language.VIETNAMESE, Language.FRENCH, Language.ENGLISH)

# Nguyên tắc 3: confidence dưới ngưỡng này → primary_language = None thay vì ép argmax.
# Hypothesis ban đầu, CHƯA calibrate bằng data thật.
MIN_CONFIDENCE_FOR_PRIMARY = 0.5


@dataclass(frozen=True)
class LanguageInfo:
    primary_language: str | None  # ISO 639-1 lowercase (VD "vi"), None nếu confidence thấp
    detected_languages: list[str]  # toàn bộ ngôn ngữ tìm thấy trong text (multi-span)
    confidence: float  # confidence của primary_language (0.0 nếu primary_language=None)
    language_mix_score: float  # continuous, 0.0 = thuần 1 ngôn ngữ, cao hơn = trộn nhiều hơn


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

    spans: list[DetectionResult] = detector.detect_multiple_languages_of(text)
    detected_languages = sorted({_iso_code(span.language) for span in spans})
    mix_score = _language_mix_score(text, spans)

    return LanguageInfo(
        primary_language=primary_language,
        detected_languages=detected_languages,
        confidence=confidence,
        language_mix_score=mix_score,
    )


def _iso_code(language: Language) -> str:
    return language.iso_code_639_1.name.lower()


def _language_mix_score(text: str, spans: list[DetectionResult]) -> float:
    """1 - (độ dài span ngôn ngữ ưu thế / tổng độ dài) — công thức từ
    docs/claude/data-model.md. 0.0 = thuần 1 ngôn ngữ; càng gần 1.0 càng trộn
    nhiều ngôn ngữ khác nhau trong cùng 1 văn bản."""
    total_len = len(text)
    if total_len == 0 or not spans:
        return 0.0
    span_lengths: dict[Language, int] = {}
    for span in spans:
        span_len = span.end_index - span.start_index
        span_lengths[span.language] = span_lengths.get(span.language, 0) + span_len
    dominant_len = max(span_lengths.values())
    return 1 - (dominant_len / total_len)
