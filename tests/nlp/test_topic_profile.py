import numpy as np
import pytest

from src.nlp.topic_profile import (
    adjusted_rand_index,
    class_tfidf_keywords,
    representatives,
    tokenize_segments,
)


def test_tokenize_keeps_vietnamese_syllables_and_drops_urls_numbers() -> None:
    segments = tokenize_segments("Rau muống 3€ ở Paris! Xem https://x.com/a, giá 6€/kg")
    assert segments == [["rau", "muống", "paris"], ["xem"], ["giá", "kg"]]


def test_class_tfidf_prefers_cluster_specific_bigrams_over_shared_words() -> None:
    docs = {
        0: ["mình mua rau muống ở chợ", "rau muống xào tỏi, mình thích", "mình mua rau muống"],
        1: ["mình đi du học Pháp", "du học Pháp cần visa, mình nghĩ", "mình học Master"],
        2: ["mình đi chợ đồ cũ", "chợ đồ cũ cuối tuần, mình mê", "mình săn chợ đồ cũ"],
    }
    keywords = class_tfidf_keywords(docs, k=3)
    assert "rau muống" in keywords[0]
    assert "du học" in keywords[1]
    # "mình" có ở mọi cụm → IDF theo cụm đẩy xuống, không thành từ khoá đặc trưng
    assert all("mình" not in words for words in keywords.values())
    # đã chọn bigram thì không lặp lại từng âm tiết của nó
    assert "rau" not in keywords[0] and "muống" not in keywords[0]


def test_class_tfidf_requires_term_in_two_documents() -> None:
    docs = {0: ["bánh mì giòn", "bánh mì nóng"], 1: ["phở bò", "phở gà"]}
    keywords = class_tfidf_keywords(docs, k=5)
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
    assert class_tfidf_keywords(docs, k=1)[0] == ["hôm nay"]
    with_noise = class_tfidf_keywords(docs, k=1, background_docs=background)
    assert with_noise[0] == ["rau muống"]
    assert -1 not in with_noise  # lớp nhiễu không có từ khoá đầu ra
