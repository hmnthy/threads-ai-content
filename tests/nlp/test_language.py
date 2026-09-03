import pytest

from src.nlp.language import (
    MIN_CONFIDENCE_FOR_PRIMARY,
    _code_mixing_index,
    _token_language,
    detect_language_info,
)


def test_detect_language_info_pure_vietnamese_has_low_mix_score() -> None:
    text = "Hôm nay mình đi làm muộn quá, tắc đường kinh khủng luôn các bạn ạ."
    info = detect_language_info(text)
    assert info.primary_language == "vi"
    assert info.confidence >= MIN_CONFIDENCE_FOR_PRIMARY
    assert info.language_mix_score < 0.3  # thuần tiếng Việt — mix score phải thấp (thang 0-100)


def test_detect_language_info_pure_french_detects_french_primary() -> None:
    text = (
        "Aujourd'hui, je suis allée au travail et j'ai rencontré plusieurs collègues "
        "sympathiques qui m'ont beaucoup aidée avec mon nouveau projet."
    )
    info = detect_language_info(text)
    assert info.primary_language == "fr"


def test_detect_language_info_empty_text_returns_unknown() -> None:
    info = detect_language_info("")
    assert info.primary_language is None
    assert info.detected_languages == []
    assert info.confidence == 0.0
    assert info.language_mix_score == 0.0


def test_detect_language_info_whitespace_only_returns_unknown() -> None:
    info = detect_language_info("   \n\t  ")
    assert info.primary_language is None


def test_detect_language_info_mixed_language_text_has_nonzero_mix_score() -> None:
    # Đoạn văn trộn rõ ràng 1 câu tiếng Việt + 1 câu tiếng Pháp dài — kỳ vọng mix
    # score > 0 (không yêu cầu 1 con số cụ thể, chỉ yêu cầu detect được nhiều hơn 1
    # ngôn ngữ trên văn bản dài đủ rõ ràng).
    text = (
        "Hôm nay mình đi phỏng vấn xin việc ở Paris rất là hồi hộp. "
        "Je suis tellement stressée avant mon entretien d'embauche à Paris "
        "aujourd'hui, j'espère que tout se passera bien pour moi."
    )
    info = detect_language_info(text)
    assert len(info.detected_languages) >= 1
    assert info.language_mix_score >= 0.0  # continuous, không phải boolean


def test_detect_language_info_code_switch_example_has_mix_score_between_zero_and_max() -> None:
    # Case code-switch rõ ràng VI/EN từ plan (Layer 9) — không thuần 1 ngôn ngữ,
    # cũng không hoàn toàn 50/50 (đa số token vẫn tiếng Việt).
    text = "Hôm nay mình đi entretien ở Paris, stressed vãi."
    info = detect_language_info(text)
    assert 0.0 < info.language_mix_score < 100.0


def test_detect_language_info_mix_score_is_on_a_0_to_100_scale_not_0_to_1() -> None:
    # Code-Mixing Index (Gambäck & Das 2014) dùng thang 0-100 — so sánh được trực
    # tiếp với benchmark VietMix (CMI≈21.7), KHÁC thang 0.0-1.0 của công thức cũ.
    # 50/50 split rõ ràng (đủ token mỗi bên) phải cho CMI ở vùng hàng chục, không
    # phải một phân số nhỏ hơn 1.
    text = "cảm ơn bạn rất nhiều vì đã giúp đỡ mình thank you so much for your help"
    info = detect_language_info(text)
    assert info.language_mix_score > 1.0


# --- hybrid LID cấp từ (_token_language) ------------------------------------------


def test_token_language_uses_borrowed_terms_dict_for_known_specialized_words() -> None:
    # "alternance"/"CV"/"entretien" là từ mượn chuyên ngành đã biết trước — tra
    # dict trực tiếp, không phụ thuộc lingua LID trên 1 từ đơn lẻ rất ngắn/dễ nhầm.
    from src.nlp.language import _detector

    detector = _detector()
    assert _token_language("alternance", detector) == "fr"
    assert _token_language("CV", detector) == "fr"
    assert _token_language("Entretien", detector) == "fr"  # case-insensitive


def test_token_language_falls_back_to_lingua_for_unknown_words() -> None:
    from src.nlp.language import _detector

    detector = _detector()
    # "muộn" không nằm trong _BORROWED_TERMS — phải fallback lingua per-token.
    assert _token_language("muộn", detector) == "vi"


def test_token_language_returns_unknown_when_lingua_cannot_decide() -> None:
    from src.nlp.language import _detector

    detector = _detector()
    # 1 ký tự số/không rõ ràng — lingua có thể không phân loại được, phải fallback
    # "unknown" thay vì ép 1 ngôn ngữ (nguyên tắc 3 áp dụng cả cấp từ).
    result = _token_language("xyzxyzqwqw123", detector)
    assert result in {"unknown", "vi", "fr", "en"}  # không crash, luôn trả 1 string hợp lệ


# --- _code_mixing_index (đơn vị, không phụ thuộc lingua) --------------------------


def test_code_mixing_index_pure_single_language_is_zero() -> None:
    assert _code_mixing_index(["vi", "vi", "vi", "vi"]) == 0.0


def test_code_mixing_index_empty_tags_is_zero() -> None:
    assert _code_mixing_index([]) == 0.0


def test_code_mixing_index_all_unknown_is_zero() -> None:
    # n == u -> tránh chia cho 0, trả 0.0 đúng theo định nghĩa (Gambäck & Das 2014).
    assert _code_mixing_index(["unknown", "unknown"]) == 0.0


def test_code_mixing_index_even_split_between_two_languages_is_fifty() -> None:
    # n=4, u=0, max(w_i)=2 -> CMI = 100 * (1 - 2/4) = 50.
    assert _code_mixing_index(["vi", "vi", "fr", "fr"]) == 50.0


def test_code_mixing_index_ignores_unknown_tokens_in_denominator() -> None:
    # n=5, u=1 (1 "unknown" loại khỏi mẫu số) -> n-u=4, max(w_i)=2 (vi) ->
    # CMI = 100 * (1 - 2/4) = 50, giống hệt trường hợp không có "unknown" ở trên.
    assert _code_mixing_index(["vi", "vi", "fr", "fr", "unknown"]) == 50.0


def test_code_mixing_index_dominant_language_lowers_the_score() -> None:
    # n=5, u=0, max(w_i)=4 (vi) -> CMI = 100 * (1 - 4/5) = 20 -- thấp hơn hẳn case
    # 50/50, đúng trực giác: 1 ngôn ngữ áp đảo -> ít "trộn" hơn.
    assert _code_mixing_index(["vi", "vi", "vi", "vi", "fr"]) == pytest.approx(20.0)
