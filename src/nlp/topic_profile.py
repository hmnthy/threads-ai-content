"""Hồ sơ cho từng cụm topic sau khi HDBSCAN gom cụm (ADR-0004) — chạy trên Windows
trong bước import (chỉ cần numpy, không đụng scipy/umap/hdbscan):

- `class_tfidf_keywords`: từ khoá đặc trưng bằng c-TF-IDF (Grootendorst 2022, BERTopic)
  — TF-IDF tính theo CỤM thay vì theo bài: từ nào dày đặc trong cụm này nhưng hiếm ở
  các cụm khác thì điểm cao.
- `representatives`: bài gần tâm cụm nhất (cosine trên embedding đã lưu) — vừa để
  hiện trên dashboard, vừa làm mẫu cho Claude đặt tên cụm (thay cho "15 bài đầu").
- `adjusted_rand_index`: mức giống nhau giữa 2 lần gom cụm (1 = y hệt, ~0 = như ngẫu
  nhiên) — đo tác động của việc sửa dữ liệu D0 và độ ổn định giữa các lần chạy.

Token: tiếng Việt viết tách âm tiết bằng dấu cách, nên 1 token = 1 âm tiết; dùng thêm
bigram để bắt từ ghép ("du học", "rau muống"). Không xoá stop word: thành phần IDF
theo cụm đã tự hạ điểm từ có mặt ở mọi cụm (giữ nguyên tắc "không clean quá tay" của
NLP pipeline, xem docs/claude/data-model.md).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

import numpy as np

# Hypothesis, chưa calibrate: 8 từ khoá đủ để đọc nhanh 1 cụm trên dashboard mà không
# lặp ý; chỉnh khi review nội dung từng cụm cho thấy thiếu/thừa.
KEYWORDS_PER_TOPIC = 8
# Hypothesis, chưa calibrate: 1 từ phải xuất hiện ở ≥2 bài của cụm mới được làm từ
# khoá — chặn từ chỉ có trong 1 bài (đặc thù 1 bài, không phải của cả cụm).
MIN_DOCS_PER_KEYWORD = 2
# Hypothesis, đo 2026-10-01 trên văn bản sạch (ADR-0004), 2 lần gom cụm: từ chức năng
# ("những", "một", "tại", "đó", "nha", "mọi người") có mặt ở 8–9/10 cụm (tham số cũ) và
# 8–9/9 cụm (tham số chốt); từ mang nội dung ("ăn", "học", "ngon", "bán") ở ≤ 7/10 và
# ≤ 6/9; "visa" ở 1/10 và 2/9. Từ có mặt ở ≥ 80% số cụm → không làm từ khoá.
MAX_CLUSTER_SHARE_FOR_KEYWORD = 0.8
# 3 bài đại diện: đủ để người đọc hình dung cụm; cụm nhỏ nhất hiện có 4 bài.
REPRESENTATIVES_PER_TOPIC = 3

_URL = re.compile(r"https?://\S+")
_SEGMENT_SPLIT = re.compile(r"[\n.!?;:,()\"“”…]+")
_TOKEN = re.compile(r"[^\W\d_]+")


def tokenize_segments(text: str) -> list[list[str]]:
    """Tách văn bản thành các đoạn (theo dấu câu/xuống dòng), mỗi đoạn là list âm
    tiết/từ viết thường. Bigram chỉ ghép trong cùng 1 đoạn — không ghép xuyên câu."""
    # URL thay bằng ngắt đoạn: không để bigram ghép 2 phía của 1 đường link
    cleaned = _URL.sub(".", text.lower())
    segments = []
    for segment in _SEGMENT_SPLIT.split(cleaned):
        tokens = [token for token in _TOKEN.findall(segment) if len(token) >= 2]
        if tokens:
            segments.append(tokens)
    return segments


def _terms(text: str) -> list[str]:
    terms: list[str] = []
    for tokens in tokenize_segments(text):
        terms.extend(tokens)
        terms.extend(f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False))
    return terms


def class_tfidf_keywords(
    docs_by_cluster: dict[int, list[str]],
    k: int = KEYWORDS_PER_TOPIC,
    *,
    background_docs: list[str] | None = None,
) -> dict[int, list[str]]:
    """c-TF-IDF: W(t, c) = tf(t, c) · log(1 + A / f(t)), với tf(t, c) = tần suất của t
    trong cụm c chia tổng số term của cụm, A = số term trung bình mỗi cụm, f(t) = tần
    suất của t trên mọi cụm. Chỉ xét term có mặt ở ≥ MIN_DOCS_PER_KEYWORD bài của cụm.

    Khử trùng lặp: khi đã chọn bigram "rau muống" thì không chọn thêm "rau"/"muống";
    nếu unigram được chọn trước rồi mới gặp bigram chứa nó, bigram thay chỗ unigram.

    `background_docs` (bài nhiễu, nhãn -1): được tính vào f(t) và A như 1 lớp riêng —
    như BERTopic tính cả lớp outlier — để từ phổ biến toàn kênh không được IDF cao giả
    tạo chỉ vì nằm nhiều trong nhiễu; lớp này không có từ khoá đầu ra."""
    tf: dict[int, Counter[str]] = {}
    doc_freq: dict[int, Counter[str]] = {}
    for label, docs in docs_by_cluster.items():
        tf[label] = Counter()
        doc_freq[label] = Counter()
        for doc in docs:
            terms = _terms(doc)
            tf[label].update(terms)
            doc_freq[label].update(set(terms))
    total_freq: Counter[str] = Counter()
    for counts in tf.values():
        total_freq.update(counts)
    n_classes = len(tf)
    if background_docs:
        background: Counter[str] = Counter()
        for doc in background_docs:
            background.update(_terms(doc))
        total_freq.update(background)
        n_classes += 1
    if not total_freq:
        return {label: [] for label in docs_by_cluster}
    avg_terms = sum(total_freq.values()) / n_classes
    # Từ có mặt ở hầu hết các cụm (khi có ≥ 3 cụm) không đặc trưng cho cụm nào — thường
    # là từ chức năng ("những", "tại", "nha"). IDF theo cụm đã đẩy chúng xuống, nhưng cụm
    # ít ứng viên vẫn có thể "lấp chỗ" bằng chúng → loại hẳn.
    clusters_with_term: Counter[str] = Counter()
    for counts in tf.values():
        clusters_with_term.update(counts.keys())
    cutoff = math.ceil(MAX_CLUSTER_SHARE_FOR_KEYWORD * len(tf))
    ubiquitous = (
        {term for term, n in clusters_with_term.items() if n >= cutoff} if len(tf) >= 3 else set()
    )

    keywords: dict[int, list[str]] = {}
    for label, counts in tf.items():
        size = sum(counts.values()) or 1
        min_docs = min(MIN_DOCS_PER_KEYWORD, len(docs_by_cluster[label]))
        # Điểm bằng nhau → ưu tiên bigram (nghĩa trọn hơn: "hôm nay" thay vì "nay")
        scored = sorted(
            (
                (
                    count / size * math.log(1 + avg_terms / total_freq[term]),
                    term.count(" "),
                    term,
                )
                for term, count in counts.items()
                if doc_freq[label][term] >= min_docs and term not in ubiquitous
            ),
            reverse=True,
        )
        chosen: list[str] = []
        for _, _, term in scored:
            if len(chosen) >= k:
                break
            words = term.split(" ")
            if len(words) == 1 and any(term in c.split(" ") for c in chosen if " " in c):
                continue
            if len(words) == 2:
                chosen = [c for c in chosen if c not in words]
            chosen.append(term)
        keywords[label] = chosen[:k]
    return keywords


def representatives(
    ids: Sequence[str], vectors: np.ndarray, k: int = REPRESENTATIVES_PER_TOPIC
) -> tuple[list[float], list[str]]:
    """(tâm cụm đã chuẩn hoá, id của k bài gần tâm nhất theo cosine). `vectors` là
    embedding đã chuẩn hoá L2 của các bài trong cụm, cùng thứ tự với `ids`."""
    centroid = vectors.mean(axis=0)
    norm = float(np.linalg.norm(centroid))
    if norm > 0:
        centroid = centroid / norm
    similarity = vectors @ centroid
    order = np.argsort(-similarity, kind="stable")
    return [float(x) for x in centroid], [ids[int(i)] for i in order[:k]]


def adjusted_rand_index(labels_a: Sequence[int], labels_b: Sequence[int]) -> float:
    """ARI (Hubert & Arabie 1985) giữa 2 cách chia cùng 1 tập bài. Nhiễu (-1) được
    coi là 1 nhóm riêng — đổi bài từ cụm sang nhiễu cũng là thay đổi cần đo."""
    if len(labels_a) != len(labels_b):
        raise ValueError("2 cách chia phải có cùng số phần tử")
    n = len(labels_a)
    if n < 2:
        return 1.0

    def pairs(count: int) -> float:
        return count * (count - 1) / 2

    contingency = Counter(zip(labels_a, labels_b, strict=True))
    sum_cells = sum(pairs(c) for c in contingency.values())
    sum_a = sum(pairs(c) for c in Counter(labels_a).values())
    sum_b = sum(pairs(c) for c in Counter(labels_b).values())
    expected = sum_a * sum_b / pairs(n)
    max_index = (sum_a + sum_b) / 2
    if max_index == expected:
        return 1.0
    return (sum_cells - expected) / (max_index - expected)
