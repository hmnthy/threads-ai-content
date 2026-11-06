"""BM25 TypeScript của demo RAG: chạy đúng file sản phẩm bằng node, đối chiếu `bm25s` (ADR-0038).

Python ở đây chỉ là bài giải mẫu; bản trong sản phẩm là TypeScript (ADR-0037). Mọi câu trong test
là câu tự đặt, không dùng chữ của bài thật vì repo public.
"""

import functools
import json
import random
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import bm25s
import pytest

ENGINE = Path(__file__).parents[2] / "src/dashboard/src/lib/ragDemo/bm25.ts"
# Node sớm nhất có --experimental-strip-types; thiếu thì test phải hỏng, không được bỏ qua âm thầm
MIN_NODE = (22, 6)
# `bm25s` lưu số 32 bit, điểm tới ~30 sai khác cỡ 1e-6; lấy rộng hơn 1 bậc (ADR-0038 D5).
# Hằng riêng của test, khác SCORE_DECIMALS của sản phẩm.
BM25S_TOLERANCE = 1e-5

DRIVER = """
import { readFileSync } from "node:fs";
const engine = await import(process.argv[2]);
const cases = JSON.parse(readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  if (c.op === "tokenize") return engine.tokenize(c.text);
  if (c.op === "fold") return engine.foldToken(c.token);
  if (c.op === "rank") return engine.rankScores(c.scores);
  if (c.op === "constants") {
    return { k1: engine.BM25_K1, b: engine.BM25_B, decimals: engine.SCORE_DECIMALS };
  }
  const index = engine.buildChunkIndex(c.docs);
  if (c.op === "search") {
    return c.queries.map((q) => engine.searchBm25(index, q));
  }
  return c.queries.map((q) => engine.searchBm25(index, q.text, q.k1, q.b));
});
console.log(JSON.stringify(out));
"""


@functools.cache
def node_binary() -> str:
    node = shutil.which("node")
    assert node, "cần node để chạy engine TypeScript"
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True)
    major, minor = version.stdout.strip().lstrip("v").split(".")[:2]
    assert (int(major), int(minor)) >= MIN_NODE, f"cần node >= {MIN_NODE}, có {version.stdout}"
    return node


def run_engine(tmp_path: Path, cases: list[dict[str, Any]]) -> list[Any]:
    node = node_binary()
    driver = tmp_path / "driver.mjs"
    driver.write_text(DRIVER, encoding="utf-8")
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            node,
            "--experimental-strip-types",
            "--no-warnings",
            str(driver),
            ENGINE.as_uri(),
            str(data),
        ],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return list(json.loads(result.stdout))


# Dấu trên nguyên âm sau → nguyên âm đầu, bảng tay độc lập với engine (Thy chọn 2026-11-06)
TONE_PAIRS = dict(
    zip(
        ["oà", "oá", "oả", "oã", "oạ", "oè", "oé", "oẻ", "oẽ", "oẹ", "uỳ", "uý", "uỷ", "uỹ", "uỵ"],
        ["òa", "óa", "ỏa", "õa", "ọa", "òe", "óe", "ỏe", "õe", "ọe", "ùy", "úy", "ủy", "ũy", "ụy"],
        strict=True,
    )
)


def reference_tokens(text: str) -> list[str]:
    """Bản tham chiếu độc lập: đi từng ký tự theo nhóm Unicode, không dùng cùng regex với engine."""
    spaced = text.replace("\ufe0f\u20e3", " ").replace("\u20e3", " ")
    visible = "".join(c for c in spaced if not 0xFE00 <= ord(c) <= 0xFE0F)
    text = unicodedata.normalize("NFC", unicodedata.normalize("NFC", visible).lower())

    def group(position: int) -> str:
        return unicodedata.category(text[position])[0]

    tokens: list[str] = []
    i = 0
    while i < len(text):
        if group(i) not in "LN":
            i += 1
            continue
        end = i
        while end < len(text) and group(end) == "N":
            end += 1
        decimal = False
        while end + 1 < len(text) and text[end] in ".," and group(end + 1) == "N":
            decimal = True
            end += 1
            while end < len(text) and group(end) == "N":
                end += 1
        if not decimal:
            end = i
            while end < len(text) and group(end) in "LMN":
                end += 1
        token = text[i:end]
        if token[-2:] in TONE_PAIRS and token[:-2][-1:] != "q":
            token = token[:-2] + TONE_PAIRS[token[-2:]]
        tokens.append(token)
        i = end
    return tokens


def reference_fold(token: str) -> str:
    decomposed = unicodedata.normalize("NFD", token.replace("đ", "d"))
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def bm25s_scores(docs: list[list[str]], query: list[str], k1: float, b: float) -> list[float]:
    retriever = bm25s.BM25(method="lucene", idf_method="lucene", k1=k1, b=b)
    retriever.index(docs, show_progress=False)
    if not query or not any(term in retriever.vocab_dict for term in query):
        return [0.0] * len(docs)
    ids, scores = retriever.retrieve([query], k=len(docs), show_progress=False)
    found = dict(zip(ids[0].tolist(), scores[0].tolist(), strict=True))
    return [float(found[i]) for i in range(len(docs))]


def assert_matches_bm25s(
    docs: list[list[str]], query: list[str], result: dict[str, Any], k1: float, b: float
) -> None:
    expected = bm25s_scores(docs, query, k1, b)
    assert result["scores"] == pytest.approx(expected, abs=BM25S_TOLERANCE)
    assert {row["chunk"] for row in result["ranked"]} == {
        i for i, score in enumerate(expected) if score > BM25S_TOLERANCE
    }
    # Thứ tự: bỏ qua cặp gần nhau hơn sai số, vì `bm25s` chỉ 32 bit (ADR-0038 D5)
    for upper, lower in zip(result["ranked"], result["ranked"][1:], strict=False):
        assert expected[upper["chunk"]] >= expected[lower["chunk"]] - BM25S_TOLERANCE


CORPUS = [
    "Chủ nhà không bật sưởi thì gửi thư nhắc trước, giữ bản sao của thư.",
    "Thuê nhà mùa đông nên kiểm tra độ ẩm và cửa sổ trước khi ký hợp đồng.",
    "Le chauffage de l'appartement ne marche plus depuis lundi.",
    "Đổi ngành ở đại học cần nộp hồ sơ trước tháng năm.",
    "Peut-on changer de filière après la première année ?",
    "Cây bút ngòi 1,0 mm viết êm, mực 0.7 thì mảnh hơn.",
    "Đi chợ cuối tuần mua đồ cũ giá 4€/cái 😱 rẻ hơn hẳn.",
    "Đường đi tới bờ biển mất 15 kms, mùa hè mát.",
    "😱",  # đoạn chỉ có emoji: 0 token, vẫn tính vào số đoạn và độ dài trung bình
]
QUERIES = [
    "chu nha khong bat suoi",
    "Thuê nhà ở đâu, chủ nhà không sưởi thì sưởi thế nào?",
    "Peut-on changer de filière ?",
    "Bút ngòi 1,0 mm",
    "duong di bien",
    "từ không có trong kho zzz",
    "chu nha bán",
    "chu nha khong bat suoi ❤️",
]


def test_constants_are_the_adr_values(tmp_path: Path) -> None:
    constants = run_engine(tmp_path, [{"op": "constants"}])[0]
    assert constants == {"k1": 1.2, "b": 0.75, "decimals": 6}


def test_score_matches_a_hand_computed_value(tmp_path: Path) -> None:
    # N = 3, n = 1, IDF = ln(1 + 2,5 / 1,5); |D| / avgdl = 3 / 2; norm = 0,25 + 0,75 × 1,5 = 1,375
    # điểm = IDF × 2 / (2 + 1,2 × 1,375) = 0,980829 × 2 / 3,65. Tử số không có (k1 + 1).
    docs = ["xoài xoài cam", "cam", "cam chuối"]
    result = run_engine(tmp_path, [{"op": "search", "docs": docs, "queries": ["xoài"]}])[0][0]
    assert result["scores"] == pytest.approx([0.537441, 0, 0], abs=1e-6)


def test_tokens_keep_numbers_and_split_on_hyphen_and_apostrophe(tmp_path: Path) -> None:
    text = "Second-hand: l'université, ngòi 1,0 mm và 0.7! ĐỒ 😱 4€/cái"
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": text}])[0]
    assert tokens == [
        "second",
        "hand",
        "l",
        "université",
        "ngòi",
        "1,0",
        "mm",
        "và",
        "0.7",
        "đồ",
        "4",
        "cái",
    ]


def test_both_tone_placements_merge(tmp_path: Path) -> None:
    text = "hoà tuỳ khoẻ HOÀ thuỷ hòa tùy khỏe"
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": text}])[0]
    assert tokens == ["hòa", "tùy", "khỏe", "hòa", "thủy", "hòa", "tùy", "khỏe"]


def test_every_tone_pair_merges_and_stays_after_q(tmp_path: Path) -> None:
    pairs = list(TONE_PAIRS.items())
    cases = [{"op": "tokenize", "text": f"h{old} q{old}"} for old, _ in pairs]
    out = run_engine(tmp_path, cases)
    assert out == [[f"h{new}", f"q{old}"] for old, new in pairs]


def test_tone_merge_leaves_other_words_alone(tmp_path: Path) -> None:
    text = "hoàng quý quỷ poésie toàn"
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": text}])[0]
    assert tokens == ["hoàng", "quý", "quỷ", "poésie", "toàn"]


def test_either_tone_placement_finds_the_same_chunk(tmp_path: Path) -> None:
    docs = ["hoà giải hợp đồng", "giải thích", "xin chào"]
    results = run_engine(
        tmp_path, [{"op": "search", "docs": docs, "queries": ["hòa giải", "hoà giải"]}]
    )[0]
    assert results[0]["ranked"][0]["chunk"] == 0
    assert results[1]["scores"] == results[0]["scores"]


def test_decimal_numbers_do_not_glue_onto_words(tmp_path: Path) -> None:
    text = "Paris,2026 Cancale,15km 2kg 2,5kg"
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": text}])[0]
    assert tokens == ["paris", "2026", "cancale", "15km", "2kg", "2,5", "kg"]


def test_emoji_style_marks_are_not_tokens(tmp_path: Path) -> None:
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": "❤️ ☺️ 1️⃣ ✈️ a❤️b"}])[0]
    assert tokens == ["1", "a", "b"]


def test_word_right_after_a_keycap_stays_a_separate_token(tmp_path: Path) -> None:
    # Giá trị viết tay: bản tham chiếu viết cùng tư duy có thể mang cùng lỗi
    texts = ("1️⃣Lương 2️⃣Visa", "1️⃣2️⃣", "1️⃣,2️⃣", "1\u20e3Lương")
    out = run_engine(tmp_path, [{"op": "tokenize", "text": text} for text in texts])
    assert out == [["1", "lương", "2", "visa"], ["1", "2"], ["1", "2"], ["1", "lương"]]


def test_emoji_does_not_flip_a_query_without_marks(tmp_path: Path) -> None:
    docs = ["chủ nhà không bật sưởi", "giữ bản sao của thư", "❤️❤️❤️❤️ cảm ơn"]
    questions = ["chu nha khong bat suoi ❤️", "chu nha \u2139\ufe0f"]
    results = run_engine(tmp_path, [{"op": "search", "docs": docs, "queries": questions}])[0]
    assert [result["mode"] for result in results] == ["folded", "folded"]
    assert [row["chunk"] for row in results[0]["ranked"]] == [0]


def test_tokens_merge_decomposed_and_composed_spelling(tmp_path: Path) -> None:
    decomposed = unicodedata.normalize("NFD", "Phở sưởi")
    tokens = run_engine(tmp_path, [{"op": "tokenize", "text": decomposed}])[0]
    assert tokens == ["phở", "sưởi"]


def test_tokens_and_folding_match_the_python_reference(tmp_path: Path) -> None:
    extra = [
        "Hôm nay 12.5.2026, giá 1.000,50€",
        "Œuvre Ñandú ﬁn",
        "a,b 1,a 2.",
        "😱đ🇫🇷",
        "Paris,2026 Cancale,15km 2kg 2,5kg v1.2",
        "1️⃣ ❤️ ☺️ 👩\u200d💻 x\ufe0fy",
        "a \u0301 b \u0301c",  # dấu đứng riêng không mở đầu token
        "x\ufe0ey x\ufe00y x\ufe10y",  # hai đầu dải bỏ, U+FE10 ngoài dải
        "hoà tuỳ khoẻ quý quỷ hoàng poésie thuỷ hoàn toàn",
    ]
    texts = CORPUS + QUERIES + extra
    cases: list[dict[str, Any]] = [{"op": "tokenize", "text": text} for text in texts]
    tokens = [token for text in texts for token in reference_tokens(text)]
    cases += [{"op": "fold", "token": token} for token in tokens]
    out = run_engine(tmp_path, cases)
    assert out[: len(texts)] == [reference_tokens(text) for text in texts]
    assert out[len(texts) :] == [reference_fold(token) for token in tokens]


def test_folding_handles_every_vietnamese_mark_and_d_stroke(tmp_path: Path) -> None:
    pairs = {"đường": "duong", "ộ": "o", "sưởi": "suoi", "être": "etre", "ç": "c", "mm": "mm"}
    out = run_engine(tmp_path, [{"op": "fold", "token": token} for token in pairs])
    assert out == list(pairs.values())


def test_query_without_marks_matches_the_folded_index(tmp_path: Path) -> None:
    results = run_engine(tmp_path, [{"op": "search", "docs": CORPUS, "queries": QUERIES}])[0]
    assert results[0]["mode"] == "folded"
    assert results[0]["query"][:2] == ["chu", "nha"]
    assert results[0]["ranked"][0]["chunk"] == 0


def test_query_with_one_mark_stays_on_the_accented_index(tmp_path: Path) -> None:
    docs = ["bán nhà", "bàn gỗ"]
    results = run_engine(tmp_path, [{"op": "search", "docs": docs, "queries": ["bán", "ban"]}])[0]
    assert results[0]["mode"] == "accented"
    assert [row["chunk"] for row in results[0]["ranked"]] == [0]
    # Cùng chữ không dấu: khớp cả hai đoạn qua bản bỏ dấu
    assert results[1]["mode"] == "folded"
    assert sorted(row["chunk"] for row in results[1]["ranked"]) == [0, 1]


def test_one_marked_word_switches_the_whole_question(tmp_path: Path) -> None:
    docs = ["bán nhà", "bàn gỗ"]
    result = run_engine(tmp_path, [{"op": "search", "docs": docs, "queries": ["ban nha bán"]}])
    assert result[0][0]["mode"] == "accented"
    assert result[0][0]["query"] == ["ban", "nha", "bán"]


def test_french_accent_counts_as_a_mark(tmp_path: Path) -> None:
    results = run_engine(tmp_path, [{"op": "search", "docs": CORPUS, "queries": ["filière"]}])[0]
    assert results[0]["mode"] == "accented"


def test_chunks_with_no_matching_term_are_not_ranked(tmp_path: Path) -> None:
    results = run_engine(
        tmp_path, [{"op": "search", "docs": ["cam", "xoài"], "queries": ["cam", "", "zzz"]}]
    )[0]
    assert [row["chunk"] for row in results[0]["ranked"]] == [0]
    assert results[1]["ranked"] == []
    assert results[2]["ranked"] == []


def test_equal_scores_keep_chunk_order_and_report_the_rank_range(tmp_path: Path) -> None:
    docs = ["cam chuối", "xoài cam", "cam chuối", "cam cam cam cam mận"]
    result = run_engine(tmp_path, [{"op": "search", "docs": docs, "queries": ["chuối"]}])[0][0]
    assert result["ranked"] == [
        {"chunk": 0, "score": result["ranked"][0]["score"], "rank": 1, "tiedFrom": 1, "tiedTo": 2},
        {"chunk": 2, "score": result["ranked"][0]["score"], "rank": 2, "tiedFrom": 1, "tiedTo": 2},
    ]


def test_ties_are_decided_after_rounding_so_they_are_transitive(tmp_path: Path) -> None:
    # So ngưỡng 5e-7 thì A ≈ B, B ≈ C mà A không ≈ C; làm tròn 6 chữ số: A = B, C ở nhóm riêng
    scores = [1.0000001, 1.0000004, 1.0000008, 0.0]
    ranked = run_engine(tmp_path, [{"op": "rank", "scores": scores}])[0]
    assert [(r["chunk"], r["score"], r["tiedFrom"], r["tiedTo"]) for r in ranked] == [
        (2, 1.000001, 1, 1),
        (0, 1.0, 2, 3),
        (1, 1.0, 2, 3),
    ]


def test_score_rounding_to_zero_is_not_ranked(tmp_path: Path) -> None:
    assert run_engine(tmp_path, [{"op": "rank", "scores": [4e-7, 2e-6]}])[0] == [
        {"chunk": 1, "score": 2e-06, "rank": 1, "tiedFrom": 1, "tiedTo": 1}
    ]


@pytest.mark.parametrize(
    ("k1", "b"), [(1.2, 0.75), (1.5, 0.75), (0.5, 0.3), (2.0, 1.0), (1.2, 0.0)]
)
def test_scores_match_bm25s_on_the_sample_corpus(tmp_path: Path, k1: float, b: float) -> None:
    queries = [{"text": q, "k1": k1, "b": b} for q in QUERIES]
    results = run_engine(tmp_path, [{"op": "search_params", "docs": CORPUS, "queries": queries}])[0]
    docs = [reference_tokens(text) for text in CORPUS]
    for question, result in zip(QUERIES, results, strict=True):
        tokens = reference_tokens(question)
        # Chế độ tính độc lập theo D3, không lấy từ engine đang được kiểm
        marked = any(reference_fold(t) != t for t in tokens)
        assert result["mode"] == ("accented" if marked else "folded")
        if marked:
            index_docs, query = docs, tokens
        else:
            index_docs = [[reference_fold(t) for t in doc] for doc in docs]
            query = [reference_fold(t) for t in tokens]
        assert result["query"] == query
        assert_matches_bm25s(index_docs, query, result, k1, b)


def test_scores_match_bm25s_on_a_random_corpus(tmp_path: Path) -> None:
    rng = random.Random(38)
    vocabulary = [f"từ{i}" for i in range(40)]
    weights = [1 / (rank + 1) for rank in range(len(vocabulary))]  # có từ phổ biến và từ hiếm
    texts = [" ".join(rng.choices(vocabulary, weights, k=rng.randint(3, 40))) for _ in range(60)]
    questions = [" ".join(rng.sample(vocabulary, k=rng.randint(1, 6))) for _ in range(25)]
    # Từ `từ…` có dấu nên mọi câu ở chế độ accented
    results = run_engine(tmp_path, [{"op": "search", "docs": texts, "queries": questions}])[0]
    docs = [reference_tokens(text) for text in texts]
    for question, result in zip(questions, results, strict=True):
        assert result["mode"] == "accented"
        assert_matches_bm25s(docs, reference_tokens(question), result, 1.2, 0.75)


def test_engine_stays_runnable_by_node_without_a_bundler() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*import\s", source, re.M), "engine phải là một file, không import"
    assert not re.search(r"^\s*(export\s+)?enum\s", source, re.M), "enum không xoá được kiểu"
