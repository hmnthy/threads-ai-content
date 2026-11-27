"""Hàm chữ / số của trang /rag-pipeline (`src/dashboard/src/lib/ragPage.ts`).

PR 2a (Thy chốt 2026-11-25). Chạy đúng file TypeScript của sản phẩm bằng node (như các test
engine). Giá trị mong đợi viết tay, không đọc từ chính hàm đang thử; `nonGoldKept` còn được đối
chiếu với bản Python `non_gold_kept` (một định nghĩa cho trang và bước dựng file).
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from src.rag_demo.demo_file import non_gold_kept
from tests.rag_demo.demo_fixture import WAYS, make_demo
from tests.rag_demo.node_engine import run_driver

DRIVER = """
import { readFileSync } from "node:fs";
const dir = process.argv[2];
const page = await import(dir + "../ragPage.ts");
const demoFile = await import(dir + "demoFile.ts");
const cases = JSON.parse(readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  if (c.fn === "nonGoldKept") return page.nonGoldKept(demoFile.parseDemoFile(c.demo), c.max);
  if (c.fn === "chunkStats") return page.chunkStats(demoFile.parseDemoFile(c.demo), c.way);
  if (c.fn === "cosineSpread") return page.cosineSpread(demoFile.parseDemoFile(c.demo), c.way);
  if (c.fn === "cosinePairs") return page.cosinePairs(demoFile.parseDemoFile(c.demo), c.way);
  if (c.fn === "nearestPassages") {
    return page.nearestPassages(demoFile.parseDemoFile(c.demo), c.way, c.chunk, c.count);
  }
  if (c.fn === "honestExamples") {
    return page.honestExamples(demoFile.parseDemoFile(c.demo)).map((e) => [e.question, e.passage]);
  }
  return page[c.fn](...c.args);
});
process.stdout.write(JSON.stringify(out));
"""


def call(tmp_path: Path, cases: list[dict[str, Any]]) -> list[Any]:
    return run_driver(tmp_path, DRIVER, cases)


def test_quartiles_inclusive_method(tmp_path: Path) -> None:
    # statistics.quantiles([1, 2, 3, 4], n=4, method="inclusive") = [1.75, 2.5, 3.25];
    # đầu vào chưa sắp xếp
    got = call(
        tmp_path,
        [
            {"fn": "quartiles", "args": [[4, 1, 3, 2]]},
            {"fn": "quartiles", "args": [[7]]},
        ],
    )
    assert got[0] == {"q1": 1.75, "median": 2.5, "q3": 3.25}
    assert got[1] == {"q1": 7, "median": 7, "q3": 7}


def test_character_count_counts_code_points_not_utf16_units(tmp_path: Path) -> None:
    # 🇨🇵 = 2 điểm mã (4 đơn vị UTF-16): "🇨🇵a" có `.length` = 5 trong JS,
    # nhưng 3 ký tự như len() của Python
    got = call(tmp_path, [{"fn": "characterCount", "args": ["🇨🇵a"]}])
    assert got == [len("🇨🇵a")] == [3]


def test_show_emoji_spaces_glued_placeholders_and_names_flags(tmp_path: Path) -> None:
    got = call(
        tmp_path,
        [
            {"fn": "showEmoji", "args": ["▓But this"]},  # dính chữ sau → chèn 1 dấu cách
            {"fn": "showEmoji", "args": ["rice ▓) and"]},  # dính dấu câu cũng tách
            {"fn": "showEmoji", "args": ["end ▓ next"]},  # đã có dấu cách → không nhân đôi
            {"fn": "showEmoji", "args": ["▓▓x"]},  # 2 emoji liền nhau → chỉ tách trước chữ
            {"fn": "showEmoji", "args": ["the end▓"]},
            {"fn": "showEmoji", "args": ["France 🇨🇵 and 🇫🇷!"]},
            {"fn": "showEmoji", "args": ["Hanoi 🇻🇳"]},  # cờ khác → nhãn chung
            {"fn": "showEmoji", "args": ["no placeholder"]},
        ],
    )
    assert got == [
        "[emoji] But this",
        "rice [emoji] ) and",
        "end [emoji] next",
        "[emoji][emoji] x",
        "the end[emoji]",
        "France [French flag] and [French flag]!",
        "Hanoi [flag]",
        "no placeholder",
    ]


def test_score_text_haiku_is_a_whole_number(tmp_path: Path) -> None:
    got = call(
        tmp_path,
        [
            {"fn": "scoreText", "args": [3, "haiku", False]},
            {"fn": "scoreText", "args": [0, "haiku", False]},
            # dòng "not reranked" giữ điểm của bước trước → 6 chữ số
            {"fn": "scoreText", "args": [0.0163934426, "haiku", True]},
            {"fn": "scoreText", "args": [-2.5, "cross_encoder", False]},
            {"fn": "scoreText", "args": [3, "none", False]},
        ],
    )
    assert got == ["3", "0", "0.016393", "-2.500000", "3.000000"]


def test_outcome_text_every_kind_and_the_k_boundary(tmp_path: Path) -> None:
    rank = {"kind": "rank"}
    got = call(
        tmp_path,
        [
            {"fn": "outcomeText", "args": [{**rank, "from": 3, "to": 3}, 10]},
            {"fn": "outcomeText", "args": [{**rank, "from": 10, "to": 10}, 10]},
            {"fn": "outcomeText", "args": [{**rank, "from": 11, "to": 11}, 10]},
            # khoảng hoà vắt mốc K → tính là trong top-K khi đầu khoảng ≤ K (ADR-0041)
            {"fn": "outcomeText", "args": [{**rank, "from": 9, "to": 12}, 10]},
            {"fn": "outcomeText", "args": [{"kind": "not-found"}, 10]},
            {"fn": "outcomeText", "args": [{"kind": "filtered", "step": "haiku-filter"}, 10]},
            {"fn": "outcomeText", "args": [{"kind": "filtered", "step": "near-duplicate"}, 10]},
            {"fn": "outcomeText", "args": [{"kind": "filtered", "step": "metadata"}, 10]},
            {"fn": "outcomeText", "args": [{"kind": "in-progress"}, 10]},
        ],
    )
    assert got == [
        "rank 3, inside the top 10",
        "rank 10, inside the top 10",
        "rank 11 (outside top 10)",
        "rank 9–12 (tied), inside the top 10",
        "not found: BM25 gives it a score of 0, because it shares no word with the question",
        "filtered out at: Haiku relevance filter",
        "filtered out at: near-duplicate filter",
        "filtered out at: metadata filter",
        "in progress",
    ]


def _question(rule: str, number: int = 4, spans: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"number": number, "rule": rule, "gold_spans": spans or {}, "gold_unit_ids": []}


def test_answer_sentence_is_grammatical_for_every_outcome(tmp_path: Path) -> None:
    one = _question("single")
    both = _question("both")

    def sentence(question: dict[str, Any], main: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "fn": "answerSentence",
            "args": [question, None if main is None else {"main": main}, 10],
        }

    got = call(
        tmp_path,
        [
            sentence(one, {"kind": "rank", "from": 2, "to": 2}),
            sentence(both, {"kind": "rank", "from": 14, "to": 14}),
            sentence(one, {"kind": "not-found"}),
            sentence(both, {"kind": "not-found"}),
            sentence(one, {"kind": "filtered", "step": "near-duplicate"}),
            sentence(one, {"kind": "in-progress"}),
            sentence(_question("none", number=10), None),
        ],
    )
    assert got == [
        "The correct answer is at rank 2, inside the top 10.",
        "The answer needs 2 content units; the later one to appear is at rank 14 (outside top 10).",
        "The correct answer is not found: BM25 gives it a score of 0, "
        "because it shares no word with the question.",
        "The answer needs 2 content units; the later one to appear is not found: "
        "BM25 gives it a score of 0, because it shares no word with the question.",
        "The correct answer was removed by the near-duplicate filter.",
        "The correct answer cannot be ranked yet: this setup is in progress.",
        "No content unit answers Q10, so there is no correct passage to rank. "
        "The list shows what retrieval returns anyway: the top passage is only the closest match.",
    ]
    # nhánh cũ ghép "is at" với câu not-found → "is at not found" (lỗi reviewer 2026-11-12)
    assert not any("at not found" in s for s in got)


def test_gold_rank_note_by_question_rule(tmp_path: Path) -> None:
    got = call(
        tmp_path,
        [
            {"fn": "goldRankNote", "args": [_question("none"), 10]},
            {"fn": "goldRankNote", "args": [_question("both"), 10]},
            {"fn": "goldRankNote", "args": [_question("single", spans={"u1": [[0, 5]]}), 10]},
            {"fn": "goldRankNote", "args": [_question("single"), 7]},
        ],
    )
    assert got == [
        "This question has no answer in the content units.",
        "The answer needs 2 content units: this is the rank of the one found later "
        "(each counted at its best-ranked passage), before the top-10 cut.",
        "Rank of the best-ranked passage that contains part of the answering text, "
        "before the top-10 cut.",
        "Rank of the best-ranked passage from the answering content unit, before the top-7 cut.",
    ]


def _scored_demo() -> dict[str, Any]:
    """2 câu hỏi × 4 đoạn.

    Câu 1: đáp án = đoạn 1 ở cách chia "whole", đoạn 0 ở mọi cách khác (đáp án gộp qua mọi cách
    chia → đoạn 0 và 1); Haiku chấm 3, 2, 3, 1 → ngoài đáp án giữ đoạn 2 (điểm 3).
    Câu 2: không đáp án, chấm 2, 0, 3, 2."""
    demo = make_demo(["a", "b", "c", "d"])
    first = demo["questions"][0]
    first["rule"] = "single"
    first["gold_unit_ids"] = ["u1"]
    first["gold_chunks"] = {way: {"u1": [0]} for way in WAYS}
    first["gold_chunks"]["whole"] = {"u1": [1]}

    def llm(scores: list[int]) -> list[dict[str, Any]]:
        return [
            {"score": s, "quote": None, "quote_en": None, "quote_dropped": None} for s in scores
        ]

    first["llm"] = llm([3, 2, 3, 1])
    second = copy.deepcopy(first)
    second.update(number=2, rule="none", gold_unit_ids=[], gold_chunks={way: {} for way in WAYS})
    second["llm"] = llm([2, 0, 3, 2])
    demo["questions"] = [first, second]
    return demo


def test_non_gold_kept_denominator_is_pairs_outside_the_answers(tmp_path: Path) -> None:
    demo = _scored_demo()
    [got] = call(tmp_path, [{"fn": "nonGoldKept", "demo": demo, "max": 3}])
    # câu 1: ngoài đáp án = đoạn 2, 3 → giữ 1 (đoạn 2, điểm 3);
    # câu 2: cả 4 đoạn → giữ 3 (một ở điểm 3)
    assert got == {"total": 4, "top": 2, "pairs": 2 + 4, "allPairs": 2 * 4}
    # một định nghĩa với bản Python mà bước dựng file dùng
    assert got["total"] == sum(non_gold_kept(demo).values())


# Khoá của 2 ví dụ (`HONEST_EXAMPLES` trong ragPage.ts) — viết tay ở đây, không đọc từ code đang thử
UNIT_55 = "18153699859548704"
UNIT_52 = "18645332647003724"


def _example_demo(
    *,
    score_2: int = 2,
    score_7: int = 2,
    gold_7: bool = False,
    unit_55: str = UNIT_55,
    text_52: str = "Có trên Amazon. Lượt đánh giá cỡ này chỉ có thể là cây bút quốc dân.",
) -> dict[str, Any]:
    """Đủ 56 đoạn để chạm 2 cặp cố định (câu 2 · đoạn 55, câu 7 · đoạn 52).

    Đoạn 55 thuộc bài `unit_55`, đoạn 52 thuộc bài UNIT_52; câu tự đặt, chỉ mang mẩu chữ neo."""
    demo = make_demo([f"t{i}" for i in range(56)])
    base_unit = demo["units"][0]
    for uid in {unit_55, UNIT_52} - {"u1"}:
        demo["units"].append(
            {
                **copy.deepcopy(base_unit),
                "id": uid,
                "posts": [{"id": f"p{uid}", "start": 0, "end": 20}],
            }
        )
    for index, uid, text in (
        (55, unit_55, "Chợ có đồ marque của Gant, Tommy kiểu déstockage."),
        (52, UNIT_52, text_52),
    ):
        demo["passages"][index].update(unit=uid, text=text, en=text)
        for way in WAYS:
            demo["ways"][way][index]["unit"] = uid
    base = demo["questions"][0]
    questions = []
    for number, passage, score in ((2, 55, score_2), (7, 52, score_7)):
        q = copy.deepcopy(base)
        q["number"] = number
        q["llm"] = [dict(cell) for cell in base["llm"]]
        q["llm"][passage] = {**q["llm"][passage], "score": score}
        questions.append(q)
    if gold_7:
        questions[1].update(rule="single", gold_unit_ids=[UNIT_52])
        questions[1]["gold_chunks"] = {way: {UNIT_52: [52]} for way in WAYS}
    demo["questions"] = questions
    return demo


def test_honest_examples_keep_only_pairs_that_still_match_their_key(tmp_path: Path) -> None:
    cases = [
        _example_demo(score_7=3),
        _example_demo(score_2=1),  # câu 2 chấm 1 < mức giữ → bỏ
        _example_demo(gold_7=True),  # đoạn 52 nay là đáp án câu 7 → bỏ
        # file dựng lại: đoạn số 55 nay thuộc bài khác (vẫn được giữ, ngoài đáp án) → bỏ
        _example_demo(unit_55="u1"),
        # đoạn 52 vẫn đúng bài nhưng không còn mẩu chữ neo → bỏ
        _example_demo(text_52="Một đoạn khác của cùng bài."),
        make_demo(["only"]),  # không có câu 2 / 7 → không ví dụ nào
    ]
    got = call(tmp_path, [{"fn": "honestExamples", "demo": demo} for demo in cases])
    assert got == [[[2, 55], [7, 52]], [[7, 52]], [[2, 55]], [[7, 52]], [[2, 55]], []]


def test_example_count_words_follow_how_many_examples_are_shown(tmp_path: Path) -> None:
    got = call(
        tmp_path,
        [
            {"fn": "examplesHeading", "args": [2, 43]},
            {"fn": "examplesHeading", "args": [1, 43]},
            {"fn": "examplesHeading", "args": [2, 1043]},
            {"fn": "examplesPointer", "args": [2]},
            {"fn": "examplesPointer", "args": [1]},
            {"fn": "examplesPointer", "args": [0]},
        ],
    )
    assert got == [
        "Two of the 43 extra “partly answers”",
        "One of the 43 extra “partly answers”",
        "Two of the 1,043 extra “partly answers”",
        " (real examples below)",
        " (a real example below)",
        "",
    ]


def _chunking_demo() -> dict[str, Any]:
    """4 đoạn dài 2, 3, 4, 8 ký tự (đoạn 1 có cờ: 3 điểm mã nhưng 5 đơn vị UTF-16), đoạn 1 và 3
    có câu ngữ cảnh. Cách "post" dùng cả 4; "whole" chỉ đoạn 3; "semantic" không có đoạn nào."""
    demo = make_demo(["ab", "🇨🇵a", "abcd", "abcdefgh"], contexts=[None, "c1", None, "c3"])
    demo["ways"]["whole"] = [{"id": 0, "unit": "u1", "start": 0, "end": 8, "passage": 3}]
    demo["cosine"]["whole"] = []
    demo["ways"]["semantic"] = []
    demo["cosine"]["semantic"] = []
    return demo


def test_chunk_stats_counts_code_points_per_way(tmp_path: Path) -> None:
    demo = _chunking_demo()
    got = call(
        tmp_path,
        [{"fn": "chunkStats", "demo": demo, "way": way} for way in ("post", "whole", "semantic")],
    )
    # statistics.quantiles([2, 3, 4, 8], n=4, method="inclusive") = [2.75, 3.5, 5.0];
    # độ dài cờ = 3, không 5
    assert got[0] == {
        "count": 4,
        "withContext": 2,
        "lengths": {"q1": 2.75, "median": 3.5, "q3": 5, "min": 2, "max": 8},
    }
    # chỉ đoạn của cách đang hỏi: "whole" có 1 đoạn (đoạn 3, có câu ngữ cảnh)
    assert got[1] == {
        "count": 1,
        "withContext": 1,
        "lengths": {"q1": 8, "median": 8, "q3": 8, "min": 8, "max": 8},
    }
    # cách chia rỗng: không in median của tập rỗng (trang hiện "—")
    assert got[2] == {"count": 0, "withContext": 0, "lengths": None}


def test_unit_passages_note_follows_the_passages_shown(tmp_path: Path) -> None:
    # code-reviewer PR 2b vòng 1: bài chỉ có 1 đoạn = cả bài (vd bài #13) không có câu ngữ cảnh
    # nào — câu "each passage with its context sentence" sai ở ca 0 đoạn có câu
    got = call(
        tmp_path,
        [
            {"fn": "unitPassagesNote", "args": ["recursive_500", False, 3, 3]},
            {"fn": "unitPassagesNote", "args": ["recursive_500", True, 3, 3]},
            {"fn": "unitPassagesNote", "args": ["recursive_500", True, 0, 1]},
            {"fn": "unitPassagesNote", "args": ["semantic", True, 2, 3]},
            # số ít: động từ + đại từ theo số đoạn có câu (NIT PR 2b "1 of the N passages are")
            {"fn": "unitPassagesNote", "args": ["fixed_300", True, 1, 3]},
            {"fn": "unitPassagesNote", "args": ["fixed_300", True, 1, 1]},
            # "No chunking" không cắt gì → không viết "Cut with No chunking"
            {"fn": "unitPassagesNote", "args": ["whole", False, 0, 1]},
        ],
    )
    assert got == [
        "Cut with Recursive 500.",
        "Cut with Recursive 500; all 3 passages have a context sentence, shown above them.",
        "Cut with Recursive 500. This content unit stays one passage, the whole unit, "
        "so it has no context sentence.",
        "Cut with Semantic; 2 of 3 passages have a context sentence, shown above them.",
        "Cut with Fixed 300; 1 of 3 passages has a context sentence, shown above it.",
        "Cut with Fixed 300; its one passage has a context sentence, shown above it.",
        "Kept whole with No chunking.",
    ]


def test_chunking_answer_does_not_say_no_chunking_cuts(tmp_path: Path) -> None:
    # 3 reviewer PR 2b: "No chunking cuts the 19 content units into …" tự mâu thuẫn
    got = call(
        tmp_path,
        [
            {"fn": "chunkingAnswer", "args": ["whole", 19, 19, 1277]},
            {"fn": "chunkingAnswer", "args": ["fixed_300", 19, 102, 290.6]},
            {"fn": "chunkingAnswer", "args": ["semantic", 19, 1102, 182.5]},
            {"fn": "chunkingAnswer", "args": ["post", 19, 0, None]},
        ],
    )
    assert got == [
        "No chunking keeps the 19 content units whole: 19 passages, "
        "with a median length of 1,277 characters.",
        "Fixed 300 cuts the 19 content units into 102 passages, "
        "with a median length of 291 characters.",
        "Semantic cuts the 19 content units into 1,102 passages, "
        "with a median length of 183 characters.",
        "One per post gives no passages.",
    ]


def test_ranked_note_follows_the_list_actually_ranked(tmp_path: Path) -> None:
    # Hybrid rơi về BM25 → `rankedBy` trả "bm25" → ghi chú của BM25,
    # không câu "dense similarity ranks every passage"
    got = call(
        tmp_path,
        [
            {"fn": "rankedNote", "args": ["bm25"]},
            {"fn": "rankedNote", "args": ["dense"]},
            {"fn": "rankedNote", "args": ["hybrid"]},
        ],
    )
    assert got[0] == "BM25 leaves out passages that share no word with the question."
    assert got[1] == "Dense similarity ranks every passage."
    assert got[2].startswith("Hybrid ranks every passage")
    assert "BM25 leaves out" not in got[2]


def _cosine_demo() -> dict[str, Any]:
    """4 đoạn; cosine của cách "post" theo cặp (0,1) (0,2) (0,3) (1,2) (1,3) (2,3), tam giác trên
    theo hàng; cặp (0,2) và (2,3) cùng 0.5 (hoà). Cách "whole" chỉ 1 đoạn: không có cặp nào."""
    demo = make_demo(["a", "b", "c", "d"])
    demo["cosine"]["post"] = [0.1, 0.5, 0.3, 0.9, 0.2, 0.5]
    demo["ways"]["whole"] = [{"id": 0, "unit": "u1", "start": 0, "end": 1, "passage": 0}]
    demo["cosine"]["whole"] = []
    return demo


def test_cosine_spread_reads_the_upper_triangle(tmp_path: Path) -> None:
    demo = _cosine_demo()
    got = call(
        tmp_path,
        [{"fn": "cosineSpread", "demo": demo, "way": way} for way in ("post", "whole")],
    )
    # 6 giá trị đã sắp: 0.1 0.2 0.3 0.5 0.5 0.9 → quantiles inclusive = [0.225, 0.4, 0.5]
    assert got[0]["pairs"] == 6
    assert got[0]["q1"] == pytest.approx(0.225)
    assert got[0]["median"] == pytest.approx(0.4)
    assert got[0]["q3"] == pytest.approx(0.5)
    # thấp nhất = cặp (0,1), cao nhất = cặp (1,2): vị trí đúng trong tam giác trên
    assert got[0]["low"] == {"value": 0.1, "a": 0, "b": 1}
    assert got[0]["high"] == {"value": 0.9, "a": 1, "b": 2}
    # 1 đoạn: không có cặp → null (trang không in median của tập rỗng)
    assert got[1] is None


def test_nearest_passages_sort_by_cosine_then_passage_order(tmp_path: Path) -> None:
    demo = _cosine_demo()
    got = call(
        tmp_path,
        [
            {"fn": "nearestPassages", "demo": demo, "way": "post", "chunk": 0, "count": 2},
            # đoạn 2: với 0 = 0.5, với 1 = 0.9, với 3 = 0.5 → hoà 0.5 giữa đoạn 0 và 3: đoạn 0 trước
            {"fn": "nearestPassages", "demo": demo, "way": "post", "chunk": 2, "count": 3},
            {"fn": "nearestPassages", "demo": demo, "way": "whole", "chunk": 0, "count": 5},
            {"fn": "cosineText", "args": [0.693652]},
        ],
    )
    assert got[0] == [{"chunk": 2, "cosine": 0.5}, {"chunk": 3, "cosine": 0.3}]
    assert got[1] == [
        {"chunk": 1, "cosine": 0.9},
        {"chunk": 0, "cosine": 0.5},
        {"chunk": 3, "cosine": 0.5},
    ]
    assert got[2] == []
    assert got[3] == "0.694"


def test_cosine_pairs_sort_highest_first_and_ties_by_row_order(tmp_path: Path) -> None:
    # bảng "Show as table" của heatmap: cặp (0,2) và (2,3) cùng 0.5 → (0,2) trước (hàng nhỏ hơn)
    demo = _cosine_demo()
    got = call(
        tmp_path,
        [
            {"fn": "cosinePairs", "demo": demo, "way": "post"},
            {"fn": "cosinePairs", "demo": demo, "way": "whole"},
        ],
    )
    assert got[0] == [
        {"value": 0.9, "a": 1, "b": 2},
        {"value": 0.5, "a": 0, "b": 2},
        {"value": 0.5, "a": 2, "b": 3},
        {"value": 0.3, "a": 0, "b": 3},
        {"value": 0.2, "a": 1, "b": 3},
        {"value": 0.1, "a": 0, "b": 1},
    ]
    assert got[1] == []


def test_ranked_by_names_bm25_only_when_hybrid_falls_back(tmp_path: Path) -> None:
    got = call(
        tmp_path,
        [
            {"fn": "rankedBy", "args": ["hybrid", "bm25-only"]},
            {"fn": "rankedBy", "args": ["hybrid", "ok"]},
            {"fn": "rankedBy", "args": ["dense", "in-progress"]},
            {"fn": "rankedBy", "args": ["dense", "ok"]},
            {"fn": "rankedBy", "args": ["bm25", "ok"]},
        ],
    )
    assert got == ["bm25", "hybrid", "dense", "dense", "bm25"]
