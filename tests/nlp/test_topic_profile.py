import unicodedata

import numpy as np
import pytest

from src.nlp.topic_profile import (
    Segmenter,
    Segments,
    adjusted_rand_index,
    class_tfidf_keywords,
    representatives,
    word_segments,
)


def split_on_spaces(segment: str) -> list[str]:
    """Bộ tách từ giả cho test nhanh: mỗi âm tiết là 1 từ (không nạp model underthesea)."""
    return segment.split()


def seg(
    docs: dict[int, list[str]], segment: Segmenter = split_on_spaces
) -> dict[int, list[Segments]]:
    """Tách sẵn như bước WSL (ADR-0022) rồi mới đưa vào c-TF-IDF."""
    return {label: [word_segments(d, segment) for d in texts] for label, texts in docs.items()}


def test_word_segments_drop_urls_numbers_symbols_and_block_bigrams_at_gaps() -> None:
    segments = word_segments(
        "Rau muống 3€ ở Paris! Xem https://x.com/a, giá 6€/kg", split_on_spaces
    )
    # số, ký hiệu và từ 1 ký tự (ở) thành None (chặn bigram); URL và dấu câu ngắt đoạn
    assert segments == [["rau", "muống", None, None, "paris"], ["xem"], ["giá", None, "kg"]]


def test_word_segments_strip_only_glued_teencode_and_leave_a_gap() -> None:
    def fake(segment: str) -> list[str]:
        # dạng đầu ra thật của word_tokenize trên văn bản mạng xã hội (đo 2026-10-08)
        return ["Chất_lượng", "điều_kiện", "ko_tệ", "đắt_nha", "mn", "tui", "de"]

    (words,) = word_segments("bất kỳ", fake)
    # teencode dính ở mép bị bóc và để lại None; "điều_kiện" GIỮ nguyên dù "điều" là từ chức
    # năng (bóc từ chức năng tiếng Việt ở mép sẽ ra mảnh "kiện" — lỗi code review ADR-0022)
    assert words == ["chất_lượng", "điều_kiện", None, "tệ", "đắt", None, None, None, None]


def test_word_segments_keep_french_elision_and_hyphenated_words() -> None:
    def fake(segment: str) -> list[str]:
        return ["Tìm", "l'alternance", "ở", "Île-de-France", "d’accord"]

    (words,) = word_segments("bất kỳ", fake)
    assert words == ["tìm", "alternance", None, "île-de-france", "accord"]


def test_word_segments_drop_digit_parts_without_gluing_letters() -> None:
    def fake(segment: str) -> list[str]:
        return ["salaire_100k", "a1-a2", "delf_b2", "hậu_covid-19", "m1_khoa"]

    (words,) = word_segments("bất kỳ", fake)
    # phần có chữ số thành None; chữ hai bên KHÔNG bị nối thành "salairek", "a-a", "delf_b"
    assert words == ["salaire", None, None, None, "delf", None, "hậu_covid", None, None, "khoa"]


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("nha_sĩ", ["nha_sĩ"]),  # tiểu từ cuối câu chỉ bóc ở mép phải
        ("đắt_nha", ["đắt", None]),
        ("ngon_hông", ["ngon", None]),  # "hông" ở mép phải là tiểu từ hỏi
        ("lỗ_hổng", ["lỗ_hổng"]),  # từ ghép được bảo vệ
        ("bên_hông", ["bên_hông"]),
        ("tây_ban_nha", ["tây_ban_nha"]),
        ("bồ_đào_nha", ["bồ_đào_nha"]),
        ("ko_tệ", [None, "tệ"]),
    ],
)
def test_glue_stripping_keeps_real_compounds(token: str, expected: list[str | None]) -> None:
    (words,) = word_segments("bất kỳ", lambda segment: [token])
    assert words == expected


def test_word_segments_normalise_decomposed_unicode() -> None:
    nfd = unicodedata.normalize("NFD", "Chất lượng phỏng vấn")
    assert word_segments(nfd, split_on_spaces) == [["chất", "lượng", "phỏng", "vấn"]]


def test_class_tfidf_prefers_cluster_specific_bigrams_over_shared_words() -> None:
    docs = {
        0: ["mình mua rau muống ở chợ", "rau muống xào tỏi, mình thích", "mình mua rau muống"],
        1: ["mình đi du học Pháp", "du học Pháp cần visa, mình nghĩ", "mình học Master"],
        2: ["mình đi chợ đồ cũ", "chợ đồ cũ cuối tuần, mình mê", "mình săn chợ đồ cũ"],
    }
    keywords = class_tfidf_keywords(seg(docs, split_on_spaces), k=3)
    assert "rau muống" in keywords[0]
    assert "du học" in keywords[1]
    # "mình" có ở mọi cụm → IDF theo cụm đẩy xuống, không thành từ khoá đặc trưng
    assert all("mình" not in words for words in keywords.values())
    # đã chọn bigram thì không lặp lại từng âm tiết của nó
    assert "rau" not in keywords[0] and "muống" not in keywords[0]


def test_class_tfidf_requires_term_in_two_documents() -> None:
    docs = {0: ["bánh mì giòn", "bánh mì nóng"], 1: ["phở bò", "phở gà"]}
    keywords = class_tfidf_keywords(seg(docs, split_on_spaces), k=5)
    assert "giòn" not in keywords[0]  # chỉ có trong 1 bài
    assert "bánh mì" in keywords[0]


def test_representatives_pick_posts_closest_to_centroid() -> None:
    vectors = np.array([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0], [0.6, 0.8]])
    centroid, reps = representatives(["a", "b", "c", "d"], vectors, k=2)
    assert pytest.approx(float(np.linalg.norm(centroid))) == 1.0
    assert set(reps) == {"b", "d"}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ([0, 0, 1, 1], [5, 5, 7, 7], 1.0),  # đổi tên nhãn không đổi cách chia
        ([0, 0, 0, 1, 1, 1], [0, 0, 1, 1, 2, 2], 0.24242424),  # ví dụ chuẩn của sklearn
    ],
)
def test_adjusted_rand_index_known_values(a: list[int], b: list[int], expected: float) -> None:
    assert adjusted_rand_index(a, b) == pytest.approx(expected)


def test_adjusted_rand_index_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        adjusted_rand_index([0, 1], [0])


def test_noise_background_lowers_idf_of_channel_wide_terms() -> None:
    # "hôm nay" dày hơn "rau muống" trong cụm 0 → không có nền nhiễu thì đứng đầu;
    # nhưng nó cũng dày đặc trong nhiễu (phổ biến toàn kênh) → có nền thì tụt hạng
    docs = {
        0: ["rau muống hôm nay", "rau muống luộc hôm nay", "hôm nay ăn gì hôm nay"],
        1: ["du học Pháp visa", "du học Pháp Master"],
        2: ["chợ đồ cũ", "chợ đồ cũ cuối tuần"],
    }
    background = ["hôm nay trời đẹp", "hôm nay đi làm", "hôm nay mệt", "hôm nay nghỉ"] * 3
    assert class_tfidf_keywords(seg(docs, split_on_spaces), k=1)[0] == ["hôm nay"]
    with_noise = class_tfidf_keywords(seg(docs), k=1, background_docs=seg({-1: background})[-1])
    assert with_noise[0] == ["rau muống"]
    assert -1 not in with_noise  # lớp nhiễu không có từ khoá đầu ra


def test_stopwords_never_become_keywords_and_compounds_display_with_spaces() -> None:
    def fake(segment: str) -> list[str]:
        return ["chất_lượng" if token == "chấtlượng" else token for token in segment.split()]

    docs = {
        0: ["tui thấy chấtlượng ko tốt nha", "chấtlượng hàng tui mua ko ổn", "tui chê chấtlượng"],
        1: ["de la phở bò", "phở bò ngon nha", "phở gà de"],
    }
    keywords = class_tfidf_keywords(seg(docs, fake), k=4)
    assert "chất lượng" in keywords[0]  # từ ghép hiện bằng dấu cách, không "_"
    for words in keywords.values():
        assert not {"tui", "ko", "nha", "de"} & set(words)


def test_bigrams_skip_stopword_phrases_and_never_bridge_a_stripped_word() -> None:
    def fake(segment: str) -> list[str]:
        if "giá" in segment:
            return ["giá", "ko_tệ"]  # bộ tách từ dính "ko" vào "tệ"
        return segment.split()

    docs = {
        0: ["mọi người ơi giá ko tệ", "mọi người ơi giá ko tệ"],
        1: ["phở bò ngon", "phở bò nóng"],
        2: ["chợ đồ cũ", "chợ đồ cũ"],
    }
    keywords = class_tfidf_keywords(seg(docs, fake), k=8)
    assert "mọi người" not in keywords[0]  # cụm đại từ trong danh sách stopword
    assert "giá tệ" not in keywords[0]  # "giá ko tệ" không được thành "giá tệ" (đảo nghĩa)


def test_compound_and_bigram_forms_share_one_key() -> None:
    def fake(segment: str) -> list[str]:
        # bộ tách từ lúc ghép "đồ_cũ", lúc tách rời — phụ thuộc ngữ cảnh
        return ["chợ", "đồ_cũ"] if segment.startswith("chợ") else segment.split()

    docs = {
        0: ["chợ đồ cũ", "săn đồ cũ", "mua đồ cũ"],
        1: ["phở bò ngon", "phở bò nóng", "phở bò"],
        2: ["du học visa", "du học", "du học Pháp"],
    }
    keywords = class_tfidf_keywords(seg(docs, fake), k=8)
    assert keywords[0].count("đồ cũ") == 1  # 1 chip, tần suất gộp từ cả 2 dạng


@pytest.mark.slow
def test_underthesea_keeps_core_channel_vocabulary_intact() -> None:
    # Danh sách đáp án cố định cho underthesea 9.5.0 trên từ lõi của kênh: phải ra ĐÚNG từ ghép,
    # không mảnh âm tiết (ADR-0022). Nâng phiên bản underthesea → chạy lại test này.
    text = (
        "Chuẩn bị hồ sơ đủ điều kiện, bị từ chối visa. Học tiếng Anh và tiếng Pháp. "
        "Theo dõi thế giới, bạn bè. Phỏng vấn alternance, chia sẻ kinh nghiệm. "
        "Chất lượng siêu thị ko tệ nha mn. Tìm l'alternance ở Île-de-France. "
        "Đi nha sĩ đắt lắm, lấp lỗ hổng kiến thức, du lịch Tây Ban Nha và Bồ Đào Nha. "
        "Hậu covid-19."
    )
    words = {w for segment in word_segments(text) for w in segment if w is not None}
    expected = {
        "chuẩn_bị", "hồ_sơ", "điều_kiện", "từ_chối", "visa", "tiếng", "anh", "pháp",
        "theo_dõi", "thế_giới", "bạn_bè", "phỏng_vấn", "alternance", "chia_sẻ",
        "kinh_nghiệm", "chất_lượng", "siêu_thị", "île-de-france", "nha_sĩ", "lỗ_hổng",
        "tây_ban_nha", "bồ_đào_nha", "covid",
    }  # fmt: skip
    assert expected <= words
    assert (
        not {
            "kiện",
            "chối",
            "dõi",
            "giới",
            "bè",
            "sĩ",
            "lỗ",
            "tây_ban",
            "bồ_đào",
            "ko",
            "nha",
            "mn",
        }
        & words
    )
