"""Hồ sơ cho từng cụm topic sau khi HDBSCAN gom cụm (ADR-0004). `class_tfidf_keywords`,
`representatives`, `adjusted_rand_index` chạy trên Windows trong bước import (chỉ cần numpy);
`word_segments` (tách từ bằng underthesea) chạy trong WSL2 ở bước cluster (ADR-0022) vì
underthesea nạp kèm torch/transformers — nhóm thư viện chỉ chạy trong WSL2:

- `class_tfidf_keywords`: từ khoá đặc trưng bằng c-TF-IDF (Grootendorst 2022, BERTopic)
  — TF-IDF tính theo CỤM thay vì theo bài: từ nào dày đặc trong cụm này nhưng hiếm ở
  các cụm khác thì điểm cao.
- `representatives`: bài gần tâm cụm nhất (cosine trên embedding đã lưu) — vừa để
  hiện trên dashboard, vừa làm mẫu cho Claude đặt tên cụm (thay cho "15 bài đầu").
- `adjusted_rand_index`: mức giống nhau giữa 2 lần gom cụm (1 = y hệt, ~0 = như ngẫu
  nhiên) — đo tác động của việc sửa dữ liệu D0 và độ ổn định giữa các lần chạy.

Token cho từ khoá (ADR-0022): tách TỪ bằng underthesea (`word_tokenize`, trong WSL2) để từ ghép
("chất lượng", "phỏng vấn") là 1 token thay vì 2 mảnh âm tiết; thêm bigram của 2 từ đơn liền
nhau để giữ cụm có nghĩa mà bộ tách từ không ghép ("đồ cũ", "tiếng pháp"); bỏ stopword có
nhãn (`src/nlp/stopwords.py`). Chỉ ở bước từ khoá — văn bản embed giữ nguyên ("không clean
quá tay", docs/claude/data-model.md); IDF theo cụm vẫn hạ điểm từ có mặt ở mọi cụm.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence

import numpy as np

from src.nlp.stopwords import (
    GLUE_BOTH_EDGES,
    GLUE_RIGHT_EDGE,
    KEYWORD_STOPWORDS,
    PROTECTED_COMPOUNDS,
)

# Hypothesis, chưa calibrate: 8 từ khoá đủ để đọc nhanh 1 cụm trên dashboard mà không
# lặp ý; chỉnh khi review nội dung từng cụm cho thấy thiếu/thừa.
KEYWORDS_PER_TOPIC = 8
# Hypothesis, chưa calibrate: 1 từ phải xuất hiện ở ≥2 bài của cụm mới được làm từ
# khoá — chặn từ chỉ có trong 1 bài (đặc thù 1 bài, không phải của cả cụm).
MIN_DOCS_PER_KEYWORD = 2
# Hypothesis, đo 2026-10-01 trên token ÂM TIẾT (trước ADR-0022), 2 lần gom cụm: từ chức năng
# ("những", "một", "tại", "đó", "nha", "mọi người") có mặt ở 8–9/10 cụm (tham số cũ) và
# 8–9/9 cụm (tham số chốt); từ mang nội dung ("ăn", "học", "ngon", "bán") ở ≤ 7/10 và
# ≤ 6/9; "visa" ở 1/10 và 2/9. Từ có mặt ở ≥ 80% số cụm → không làm từ khoá. Từ ADR-0022
# token là từ đã bỏ stopword có nhãn; bộ lọc này giữ vai trò lưới thứ hai, chưa đo lại.
MAX_CLUSTER_SHARE_FOR_KEYWORD = 0.8
# 3 bài đại diện: đủ để người đọc hình dung cụm; cụm nhỏ nhất hiện có 4 bài.
REPRESENTATIVES_PER_TOPIC = 3

_URL = re.compile(r"https?://\S+")
_SEGMENT_SPLIT = re.compile(r"[\n.!?;:,()\"“”…]+")
# Emoji/ký hiệu → khoảng trắng TRƯỚC khi tách từ: model của underthesea học trên văn bản báo
# chí nên ghép emoji vào từ bên cạnh ("🇨_🇵", "?_trong") — đo 2026-10-08 trên 146 bài
_SYMBOL = re.compile(r"[^\w\s'’-]")
# 1 từ = các âm tiết chữ cái nối bằng "_" (dạng đầu ra của word_tokenize) hoặc "-" (từ Pháp/Anh
# có gạch nối: "île-de-france", "e-mail"); bỏ số, ký hiệu
_WORD = re.compile(r"^[^\W\d_]+(?:[_-][^\W\d_]+)*$")
# Tiền tố lược âm tiếng Pháp ("l'alternance" → "alternance") — word_tokenize giữ nguyên dấu nháy
_ELISION = re.compile(r"^(?:l|d|j|qu|c|n|s|m|t)['’]")
# 1 âm tiết/phần có chữ số ("19", "100k", "b2") → chỗ trống; KHÔNG nối chữ qua chỗ đã xoá
# ("salaire_100k" → "salaire", không phải "salairek"; "delf_b2" → "delf"; "covid-19" → "covid")
_DIGIT_UNIT = re.compile(r"[^_\-]*\d[^_\-]*")

# 1 đoạn văn → danh sách từ, âm tiết trong 1 từ nối bằng "_" ("chất_lượng")
Segmenter = Callable[[str], list[str]]
# Văn bản đã tách: list đoạn, mỗi đoạn là list từ hoặc None (chỗ trống chặn bigram)
Segments = list[list[str | None]]


def underthesea_segment(segment: str) -> list[str]:
    """Bộ tách từ mặc định — chỉ gọi trong WSL2 (`src/pipeline/cluster_wsl.py`). Import trong
    hàm: nạp model mất ~15 giây và kéo torch/transformers; module này vẫn import được trên
    Windows (bước import) mà không đụng underthesea."""
    from underthesea import word_tokenize  # type: ignore[import-untyped]

    tokens: list[str] = word_tokenize(segment, format="text").split()
    return tokens


def word_segments(text: str, segment: Segmenter = underthesea_segment) -> Segments:
    """Tách văn bản thành các đoạn (theo dấu câu/xuống dòng); mỗi đoạn là list từ viết
    thường (âm tiết nối "_") hoặc None ở chỗ có stopword/số/ký hiệu — None chặn bigram ghép
    qua nó. Bigram chỉ ghép trong cùng 1 đoạn, không ghép xuyên câu hay qua 1 đường link.

    Chuẩn hoá NFC trước: `full_text` là văn bản gốc; dạng tách dấu (NFD) sẽ bị `_SYMBOL` băm
    mất dấu thanh."""
    segments: Segments = []
    text = unicodedata.normalize("NFC", text)
    for part in _SEGMENT_SPLIT.split(_URL.sub(".", text)):
        part = _SYMBOL.sub(" ", part)
        if not part.strip():
            continue
        words: list[str | None] = []
        for token in segment(part):
            pieces = _DIGIT_UNIT.sub("|", _ELISION.sub("", token.lower())).split("|")
            for i, piece in enumerate(pieces):
                if i:  # chỗ phần có chữ số vừa bị bỏ
                    words.append(None)
                if piece.strip("_-"):
                    words.extend(_clean_word(piece.strip("_-")))
        if any(word is not None for word in words):
            segments.append(words)
    return segments


def _clean_word(token: str) -> list[str | None]:
    """1 token đã viết thường, không còn chữ số → [từ] hoặc kèm None ở chỗ đã bóc."""
    if not _WORD.match(token):
        return [None]
    syllables = token.split("_")
    # bộ tách từ hay dính teencode / từ chức năng Pháp-Anh vào từ bên cạnh ("tệ_nha", "ko_tệ",
    # "ngon_hông") → bóc chỉ các nhóm "dính keo" (stopwords.py): tiểu từ cuối câu chỉ ở mép phải
    # ("nha_sĩ" giữ), nhóm còn lại ở cả 2 mép; từ ghép trong PROTECTED_COMPOUNDS giữ nguyên.
    # Không bóc từ chức năng tiếng Việt: chúng là âm tiết của từ ghép ("điều_kiện", "chuẩn_bị")
    cut_left = cut_right = False
    if token not in PROTECTED_COMPOUNDS:
        while syllables and syllables[-1] in GLUE_RIGHT_EDGE | GLUE_BOTH_EDGES:
            syllables.pop()
            cut_right = True
        while syllables and syllables[0] in GLUE_BOTH_EDGES:
            syllables.pop(0)
            cut_left = True
    if not syllables:  # cả token là teencode/từ chức năng → 1 chỗ trống
        return [None]
    word = "_".join(syllables)
    keep = word.replace("_", " ") not in KEYWORD_STOPWORDS and len(word) >= 2
    # chỗ đã bóc để lại None: "giá ko_tệ" không được thành bigram "giá tệ" (đảo nghĩa)
    return [*([None] if cut_left else []), word if keep else None, *([None] if cut_right else [])]


def _terms(segments: Segments) -> list[str]:
    terms: list[str] = []
    for words in segments:
        for word, following in zip(words, [*words[1:], None], strict=True):
            if word is None:
                continue
            terms.append(word)
            # bigram chỉ của 2 từ ĐƠN (1 âm tiết): giữ cụm như "đồ cũ" mà bộ tách từ không ghép;
            # cụm từ ghép + từ ghép (3–4 âm tiết) khó đọc trên dashboard nên không tạo. Khoá nối
            # bằng "_" như từ ghép: "đồ cũ" khi bộ tách từ ghép (đồ_cũ) hay không ghép cũng là 1
            # term — không chia đôi tần suất, không ra 2 chip trùng nhau
            if (
                following is not None
                and "_" not in word
                and "_" not in following
                and f"{word} {following}" not in KEYWORD_STOPWORDS
            ):
                terms.append(f"{word}_{following}")
    return terms


def class_tfidf_keywords(
    docs_by_cluster: dict[int, list[Segments]],
    k: int = KEYWORDS_PER_TOPIC,
    *,
    background_docs: list[Segments] | None = None,
) -> dict[int, list[str]]:
    """c-TF-IDF: W(t, c) = tf(t, c) · log(1 + A / f(t)), với tf(t, c) = tần suất của t
    trong cụm c chia tổng số term của cụm, A = số term trung bình mỗi cụm, f(t) = tần
    suất của t trên mọi cụm. Chỉ xét term có mặt ở ≥ MIN_DOCS_PER_KEYWORD bài của cụm.

    Khử trùng lặp: khi đã chọn bigram "rau muống" thì không chọn thêm "rau"/"muống";
    nếu unigram được chọn trước rồi mới gặp bigram chứa nó, bigram thay chỗ unigram.

    `background_docs` (bài nhiễu, nhãn -1): được tính vào f(t) và A như 1 lớp riêng —
    như BERTopic tính cả lớp outlier — để từ phổ biến toàn kênh không được IDF cao giả
    tạo chỉ vì nằm nhiều trong nhiễu; lớp này không có từ khoá đầu ra.

    Mỗi bài vào ở dạng ĐÃ TÁCH (`word_segments`, làm trong WSL2). Term là từ hoặc bigram 2 từ
    đơn, âm tiết nối "_" (1 khoá cho cả 2 dạng); đầu ra đổi "_" thành dấu cách ("chất lượng")."""
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
        # Điểm bằng nhau → ưu tiên term nhiều âm tiết (nghĩa trọn hơn: "hôm nay" thay vì "nay")
        scored = sorted(
            (
                (
                    count / size * math.log(1 + avg_terms / total_freq[term]),
                    term.count("_"),
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
            parts = term.split("_")
            if len(parts) == 1 and any(term in c.split("_") for c in chosen if "_" in c):
                continue
            if len(parts) >= 2:
                chosen = [c for c in chosen if c not in parts]
            chosen.append(term)
        keywords[label] = [term.replace("_", " ") for term in chosen[:k]]
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
