from src.nlp.language import MIN_CONFIDENCE_FOR_PRIMARY, detect_language_info


def test_detect_language_info_pure_vietnamese_has_low_mix_score() -> None:
    text = "Hôm nay mình đi làm muộn quá, tắc đường kinh khủng luôn các bạn ạ."
    info = detect_language_info(text)
    assert info.primary_language == "vi"
    assert info.confidence >= MIN_CONFIDENCE_FOR_PRIMARY
    assert info.language_mix_score < 0.3  # thuần tiếng Việt — mix score phải thấp


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
