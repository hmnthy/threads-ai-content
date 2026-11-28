"""Luật xếp hạng, gộp câu con, trộn, bước tìm của engine demo RAG (ADR-0041), dữ liệu tổng hợp.

Chạy đúng các file TypeScript của sản phẩm bằng node. Giá trị mong đợi viết tay (tính theo ADR-0041
Luật chung 5: làm tròn `Decimal(float)` ROUND_HALF_UP, cộng trái → phải, bình phương `d * d`), không
đọc nhánh hay giá trị từ chính engine. Mọi câu là câu tự đặt, không dùng chữ của bài thật.
"""

import random
from pathlib import Path
from typing import Any

from src.rag_demo.demo_file import DEMO_FILE_FORMAT, PENDING_PARTS, SCORE_DECIMALS, _score
from src.rag_demo.llm_jobs import RERANK_KEEP_MIN_SCORE
from tests.rag_demo.demo_fixture import PENDING, WAYS, make_demo, make_demo_v3
from tests.rag_demo.node_engine import run_driver

DRIVER = """
import { readFileSync } from "node:fs";
const dir = process.argv[2];
const modules = {
  rank: await import(dir + "rank.ts"),
  bm25: await import(dir + "bm25.ts"),
  fuse: await import(dir + "fuse.ts"),
  demoFile: await import(dir + "demoFile.ts"),
  retrieve: await import(dir + "retrieve.ts"),
};
const { demoFile, retrieve, bm25 } = modules;
const cases = JSON.parse(readFileSync(process.argv[3], "utf8"));
function run(c) {
  if (c.op === "call") return modules[c.module][c.fn](...c.args);
  if (c.op === "const") return modules[c.module][c.name];
  if (c.op === "negative_zero") return Object.is(modules.rank.roundScore(c.value), -0);
  if (c.op === "parse") return demoFile.parseDemoFile(c.demo).format;
  const demo = demoFile.parseDemoFile(c.demo);
  const config = { ...retrieve.DEFAULT_RETRIEVAL, ...(c.config ?? {}) };
  if (c.bm25) config.bm25 = bm25.bm25Params(c.bm25[0], c.bm25[1]);
  if (c.op === "plan") {
    return retrieve.retrievalPlan(config, demo.provenance.pending, c.free ?? false);
  }
  if (c.op === "texts") return retrieve.chunkTexts(demo, config.way, config.context);
  const index = retrieve.buildWayIndex(
    demo,
    c.indexWay ?? config.way,
    c.indexContext ?? config.context,
  );
  const query =
    c.freeText !== undefined ? { freeText: c.freeText } : { question: demo.questions[0] };
  return retrieve.retrieve(demo, index, query, config, c.candidates);
}
const out = cases.map((c) => {
  try {
    return { ok: run(c) };
  } catch (error) {
    return { error: error.name, message: error.message };
  }
});
console.log(JSON.stringify(out));
"""


def ok(results: list[dict[str, Any]]) -> list[Any]:
    for result in results:
        assert "ok" in result, result
    return [result["ok"] for result in results]


def engine(tmp_path: Path, cases: list[dict[str, Any]]) -> list[Any]:
    return ok(run_driver(tmp_path, DRIVER, cases))


def call(tmp_path: Path, module: str, fn: str, *args: Any) -> Any:
    return engine(tmp_path, [{"op": "call", "module": module, "fn": fn, "args": list(args)}])[0]


def row(
    chunk: int, rank: int, tied: tuple[int, int] | None = None, score: float = 0.0
) -> dict[str, Any]:
    """Một dòng RankedChunk viết tay làm danh sách vào cho bước gộp / trộn."""
    start, end = tied or (rank, rank)
    return {"chunk": chunk, "score": score, "rank": rank, "tiedFrom": start, "tiedTo": end}


def table(ranked: list[dict[str, Any]]) -> list[tuple[int, float, int, int]]:
    return [(r["chunk"], r["score"], r["tiedFrom"], r["tiedTo"]) for r in ranked]


# --- Xếp hạng chung (Luật chung 2, 5) ---


def test_ties_break_by_original_chunk_id_not_input_order(tmp_path: Path) -> None:
    entries = [{"chunk": 9, "score": 0.5}, {"chunk": 2, "score": 0.5}, {"chunk": 5, "score": 0.7}]
    ranked = call(tmp_path, "rank", "rankRange", entries)
    assert [(r["chunk"], r["rank"], r["tiedFrom"], r["tiedTo"]) for r in ranked] == [
        (5, 1, 1, 1),
        (2, 2, 2, 3),
        (9, 3, 2, 3),
    ]


def test_steps_other_than_bm25_rank_zero_and_negative_scores(tmp_path: Path) -> None:
    entries = [{"chunk": 0, "score": -1.5}, {"chunk": 1, "score": 0.0}, {"chunk": 2, "score": -1.5}]
    ranked = call(tmp_path, "rank", "rankRange", entries)
    assert table(ranked) == [(1, 0.0, 1, 1), (0, -1.5, 2, 3), (2, -1.5, 2, 3)]


def test_bm25_drops_scores_that_round_to_zero_and_keeps_only_candidates(tmp_path: Path) -> None:
    ranked = call(tmp_path, "rank", "rankBm25", [0.3, 4e-7, 0.3, 0.9], [3, 2, 1])
    assert table(ranked) == [(3, 0.9, 1, 1), (2, 0.3, 2, 2)]


def test_half_cells_round_away_from_zero(tmp_path: Path) -> None:
    # 1 / 128 = 1 / (60 + 68) là một số hạng RRF có thật; `round` của Python cho 0,007812.
    # 5e-7 viết thập phân nằm đúng mép ô nhưng giá trị nhị phân thật nhỏ hơn → 0.
    values = [1 / 128, -11.0390625, 5e-7, 2.5e-6]
    cases = [{"op": "call", "module": "rank", "fn": "roundScore", "args": [v]} for v in values]
    assert engine(tmp_path, cases) == [0.007813, -11.039063, 0.0, 3e-6]


def test_demo_file_scores_round_exactly_like_the_engine(tmp_path: Path) -> None:
    # File demo lưu điểm đã làm tròn bằng `_score` (Python); engine làm tròn lại bằng `toFixed`.
    # Hai bên phải ra cùng số, kể cả giá trị đúng nửa ô (j / 128 có 7 chữ số, chữ số cuối là 5).
    rng = random.Random(41)
    values = [rng.uniform(-30, 30) for _ in range(2000)]
    values += [j / 128 for j in range(-400, 400)] + [-11.0390625, 5e-7, -5e-7, 1e-7, -1e-7]
    cases = [{"op": "call", "module": "rank", "fn": "roundScore", "args": [v]} for v in values]
    assert engine(tmp_path, cases) == [_score(v) for v in values]


def test_negative_score_that_rounds_to_zero_is_plain_zero(tmp_path: Path) -> None:
    # Như `_score` của Python (`+ 0.0`): −0 không lọt ra; JSON không phân biệt được nên hỏi node
    assert engine(tmp_path, [{"op": "negative_zero", "value": -1e-7}]) == [False]


def test_slider_complement_is_computed_from_the_integer_position(tmp_path: Path) -> None:
    cases = [{"op": "call", "module": "rank", "fn": "slider", "args": [i]} for i in (10, 30, 70)]
    # i = 70: 1 − 0,7 = 0,30000000000000004, (100 − 70) / 100 = 0,3
    assert engine(tmp_path, cases) == [
        {"value": 0.1, "complement": 0.9},
        {"value": 0.3, "complement": 0.7},
        {"value": 0.7, "complement": 0.3},
    ]


def test_slider_rejects_positions_that_are_not_whole_percent(tmp_path: Path) -> None:
    cases = [{"op": "call", "module": "rank", "fn": "slider", "args": [p]} for p in (0.5, -1)]
    assert [out.get("error") for out in run_driver(tmp_path, DRIVER, cases)] == ["RangeError"] * 2


# --- Gộp câu con (RRF, hạng trung bình) ---


def test_sub_query_merge_uses_the_average_rank_of_a_tie_group(tmp_path: Path) -> None:
    first = [row(0, 1), row(1, 2, (2, 3)), row(2, 3, (2, 3))]
    second = [row(2, 1)]
    merged = call(tmp_path, "fuse", "mergeSubQueries", [first, second])
    # chunk 2: 1 / 62,5 + 1 / 61; chunk 0: 1 / 61; chunk 1: 1 / (60 + 2,5)
    assert table(merged) == [(2, 0.032393, 1, 1), (0, 0.016393, 2, 2), (1, 0.016, 3, 3)]


def test_sub_query_merge_rounds_a_half_cell_term_up(tmp_path: Path) -> None:
    merged = call(tmp_path, "fuse", "mergeSubQueries", [[row(4, 68)]])
    assert table(merged) == [(4, 0.007813, 1, 1)]


def test_empty_sub_query_adds_nothing_and_all_empty_gives_an_empty_list(tmp_path: Path) -> None:
    assert table(call(tmp_path, "fuse", "mergeSubQueries", [[], [row(3, 1)]])) == [
        (3, 0.016393, 1, 1)
    ]
    assert call(tmp_path, "fuse", "mergeSubQueries", [[], []]) == []


# --- Trộn BM25 + dense ---


def test_rrf_structural_tie_gets_a_rank_range(tmp_path: Path) -> None:
    # Hạng (3, 7) và (7, 3) bằng nhau tuyệt đối: 1 / 63 + 1 / 67
    bm25 = [row(0, 3), row(1, 7)]
    dense = [row(1, 3), row(0, 7)]
    assert table(call(tmp_path, "fuse", "fuseRrf", bm25, dense)) == [
        (0, 0.030798, 1, 2),
        (1, 0.030798, 1, 2),
    ]


def test_rrf_chunk_missing_from_bm25_adds_zero(tmp_path: Path) -> None:
    fused = call(tmp_path, "fuse", "fuseRrf", [row(0, 1)], [row(1, 1), row(0, 2)])
    assert table(fused) == [(0, 0.032522, 1, 1), (1, 0.016393, 2, 2)]


def test_weighted_min_max_counts_bm25_zero_and_uses_the_slider_complement(tmp_path: Path) -> None:
    # BM25 {0: 2, 1: 1, 2: vắng = 0} → m = 1, 0,5, 0; dense 0,1 / 0,5 / 0,3 → m = 0, 1, 0,5
    # α = 0,3: 0,7·m(BM25) + 0,3·m(dense)
    bm25 = [row(0, 1, score=2.0), row(1, 2, score=1.0)]
    dense = [row(1, 1, score=0.5), row(2, 2, score=0.3), row(0, 3, score=0.1)]
    fused = call(tmp_path, "fuse", "fuseWeighted", bm25, dense, [0, 1, 2], 30)
    assert table(fused) == [(0, 0.7, 1, 1), (1, 0.65, 2, 2), (2, 0.15, 3, 3)]


def test_weighted_list_with_max_equal_min_adds_zero(tmp_path: Path) -> None:
    dense = [row(1, 1, score=0.5), row(2, 2, score=0.3), row(0, 3, score=0.1)]
    fused = call(tmp_path, "fuse", "fuseWeighted", [], dense, [0, 1, 2], 50)
    assert table(fused) == [(1, 0.5, 1, 1), (2, 0.25, 2, 2), (0, 0.0, 3, 3)]


def test_dbsf_uses_sample_sigma_and_scores_equal_lists_one_half(tmp_path: Path) -> None:
    # BM25 [4, 2, 0, 0]: μ = 1,5, σ mẫu = √(11 / 3); dense mọi điểm 0,9 → 0,5
    bm25 = [row(0, 1, score=4.0), row(1, 2, score=2.0)]
    dense = [row(c, c + 1, (1, 4), score=0.9) for c in range(4)]
    fused = call(tmp_path, "fuse", "fuseDbsf", bm25, dense, [3, 2, 1, 0])
    assert table(fused) == [
        (0, 1.217597, 1, 1),
        (1, 1.043519, 2, 2),
        (2, 0.869442, 3, 4),
        (3, 0.869442, 3, 4),
    ]


def test_dbsf_does_not_clamp_and_single_chunk_is_one_half(tmp_path: Path) -> None:
    # 10 điểm 0 và một điểm 10: điểm 10 cách μ hơn 3σ → chuẩn hoá 1,002519 > 1
    bm25 = [row(10, 1, score=10.0)]
    dense = [row(c, 1, (1, 11), score=0.2) for c in range(11)]
    fused = call(tmp_path, "fuse", "fuseDbsf", bm25, dense, list(range(11)))
    assert fused[0]["chunk"] == 10
    assert fused[0]["score"] == 1.502519
    assert fused[1]["score"] == 0.949748
    single = call(tmp_path, "fuse", "fuseDbsf", [], [row(7, 1, score=0.3)], [7])
    assert table(single) == [(7, 1.0, 1, 1)]


# --- Bước tìm: câu con, chế độ dấu, trạng thái cấu hình ---

TRANSFORMS = {
    "rewrite": "viết lại",
    "expand": "chủ nhà bán",
    "hyde": "đoạn giả định",
    "multi_query": ["một", "hai", "ba"],
    "decompose": ["phần một"],
    "step_back": "tổng quát",
}


# (câu con theo thứ tự cộng, có qua bước gộp câu con không) — Luật chung 4
SUB_QUERIES = {
    "none": (["chu nha"], False),
    "rewrite": (["viết lại"], False),
    "hyde": (["đoạn giả định"], False),
    "expand": (["chu nha", "chủ nhà bán"], True),
    "step_back": (["chu nha", "tổng quát"], True),
    "multi_query": (["một", "hai", "ba"], True),
    "decompose": (["phần một"], True),
}


def test_sub_queries_follow_the_transform(tmp_path: Path) -> None:
    demo = make_demo(["chủ nhà", "phần một"], question="chu nha", transforms=TRANSFORMS)
    cases = [
        {"op": "retrieve", "demo": demo, "config": {"retriever": "bm25", "transform": t}}
        for t in SUB_QUERIES
    ]
    results = engine(tmp_path, cases)
    got = {
        t: ([sub["text"] for sub in r["bm25"]["subQueries"]], r["bm25"]["merged"] is not None)
        for t, r in zip(SUB_QUERIES, results, strict=True)
    }
    assert got == SUB_QUERIES


def test_expand_picks_the_accent_mode_per_sub_query(tmp_path: Path) -> None:
    demo = make_demo(["chủ nhà", "bàn"], question="chu nha", transforms=TRANSFORMS)
    config = {"retriever": "bm25", "transform": "expand"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "config": config}])[0]
    assert [sub["mode"] for sub in result["bm25"]["subQueries"]] == ["folded", "accented"]


def test_decompose_with_one_sub_query_still_gets_rrf_scores(tmp_path: Path) -> None:
    demo = make_demo(["phần một", "khác"], transforms=TRANSFORMS)
    config = {"retriever": "bm25", "transform": "decompose"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "config": config}])[0]
    assert table(result["list"]) == [(0, 0.016393, 1, 1)]


def test_bm25_without_match_stops_after_bm25_or_after_the_merge(tmp_path: Path) -> None:
    demo = make_demo(["cam", "xoài"], question="zzz", transforms={"multi_query": ["yyy", "qqq"]})
    cases = [
        {"op": "retrieve", "demo": demo, "config": {"retriever": "bm25"}},
        {
            "op": "retrieve",
            "demo": demo,
            "config": {"retriever": "bm25", "transform": "multi_query"},
        },
    ]
    single, merged = engine(tmp_path, cases)
    assert (single["list"], single["emptyAfter"]) == ([], "bm25")
    assert (merged["list"], merged["emptyAfter"]) == ([], "merge")


def plan(bm25: bool, dense: str, fuse: bool, status: str) -> dict[str, Any]:
    return {"bm25": bm25, "dense": dense, "fuse": fuse, "status": status}


HYBRID = plan(True, "run", True, "ok")
FALLBACK = plan(True, "pending", False, "bm25-only")  # "hybrid rơi về BM25"
WAITING = plan(False, "pending", False, "in-progress")  # "dense trần cần phần còn chờ"
BM25_ONLY = plan(True, "off", False, "ok")
# (cấu hình, câu tự gõ, kế hoạch) — Luật chung 8, 9; ở cách "whole" công tắc câu ngữ cảnh coi là tắt
PLANS = [
    ({}, False, HYBRID),
    ({"transform": "expand"}, False, FALLBACK),
    ({"context": True}, False, FALLBACK),
    ({"context": True, "way": "whole"}, False, HYBRID),
    ({"retriever": "dense", "transform": "rewrite"}, False, WAITING),
    ({"retriever": "dense", "context": True, "way": "post"}, False, WAITING),
    (
        {"retriever": "dense", "context": True, "way": "whole"},
        False,
        plan(False, "run", False, "ok"),
    ),
    ({"retriever": "bm25", "transform": "hyde", "context": True}, False, BM25_ONLY),
    ({"retriever": "bm25", "context": True}, True, BM25_ONLY),
]


def test_plan_is_decided_from_the_config_before_running(tmp_path: Path) -> None:
    demo = make_demo(["a"])
    cases = [{"op": "plan", "demo": demo, "config": c, "free": f} for c, f, _ in PLANS]
    assert engine(tmp_path, cases) == [expected for _, _, expected in PLANS]


DENSE_ONLY = plan(False, "run", False, "ok")
# Định dạng 3 không còn phần chờ: mọi cấu hình ở trên chạy dense thật (Luật chung 8 không còn áp)
PLANS_V3 = [
    ({"transform": "expand"}, False, HYBRID),
    ({"context": True}, False, HYBRID),
    ({"retriever": "dense", "transform": "rewrite"}, False, DENSE_ONLY),
    ({"retriever": "dense", "context": True, "way": "post"}, False, DENSE_ONLY),
    ({"retriever": "bm25", "context": True}, True, BM25_ONLY),
]


def test_a_format_3_file_never_waits_for_a_pending_part(tmp_path: Path) -> None:
    demo = make_demo_v3(["a"])
    cases = [{"op": "plan", "demo": demo, "config": c, "free": f} for c, f, _ in PLANS_V3]
    assert engine(tmp_path, cases) == [expected for _, _, expected in PLANS_V3]


# Định dạng 3: 3 đoạn, mỗi mảng điểm có thứ tự riêng để nối nhầm mảng là đỏ
V3_DENSE = [0.9, 0.5, 0.1]  # câu gốc, chữ trần: 0 > 1 > 2
V3_CONTEXT = [0.2, 0.8, 0.5]  # câu gốc, kèm câu ngữ cảnh: 1 > 2 > 0
V3_REWRITE = {"plain": [0.1, 0.2, 0.3], "context": [0.3, 0.2, 0.1]}


def v3_demo() -> dict[str, Any]:
    return make_demo_v3(
        ["cam", "xoài", "ổi"],
        contexts=[None, "ngữ cảnh", "ngữ cảnh"],
        dense=V3_DENSE,
        dense_context=V3_CONTEXT,
        transform_dense={"rewrite": V3_REWRITE, "expand": V3_REWRITE},
        transforms={"rewrite": "viết lại", "expand": "mở rộng"},
    )


def test_dense_on_format_3_reads_the_array_of_the_setup(tmp_path: Path) -> None:
    dense = {"retriever": "dense"}
    configs = [
        dense,
        dense | {"context": True, "way": "post"},
        # cách "whole": công tắc coi là tắt → mảng chữ trần
        dense | {"context": True, "way": "whole"},
        dense | {"transform": "rewrite"},
        dense | {"transform": "rewrite", "context": True, "way": "post"},
    ]
    cases = [{"op": "retrieve", "demo": v3_demo(), "config": c} for c in configs]
    lists = [table(result["list"]) for result in engine(tmp_path, cases)]
    assert lists == [
        [(0, 0.9, 1, 1), (1, 0.5, 2, 2), (2, 0.1, 3, 3)],
        [(1, 0.8, 1, 1), (2, 0.5, 2, 2), (0, 0.2, 3, 3)],
        [(0, 0.9, 1, 1), (1, 0.5, 2, 2), (2, 0.1, 3, 3)],
        [(2, 0.3, 1, 1), (1, 0.2, 2, 2), (0, 0.1, 3, 3)],
        [(0, 0.3, 1, 1), (1, 0.2, 2, 2), (2, 0.1, 3, 3)],
    ]


def test_dense_sub_queries_are_merged_like_bm25_on_format_3(tmp_path: Path) -> None:
    # expand = câu gốc [0.9, 0.5, 0.1] rồi câu mở rộng [0.1, 0.2, 0.3], gộp RRF k = 60:
    # đoạn 0: 1/61 + 1/63 = 0,0322665 → 0,032266; đoạn 2: 1/63 + 1/61 → cùng ô (hoà, hạng 1–2);
    # đoạn 1: 1/62 + 1/62 = 0,0322581 → 0,032258
    config = {"retriever": "dense", "transform": "expand"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": v3_demo(), "config": config}])[0]
    assert [sub["text"] for sub in result["dense"]["subQueries"]] == ["câu hỏi", "mở rộng"]
    assert [sub["mode"] for sub in result["dense"]["subQueries"]] == [None, None]
    assert table(result["list"]) == [(0, 0.032266, 1, 2), (2, 0.032266, 1, 2), (1, 0.032258, 3, 3)]
    assert result["list"] == result["dense"]["merged"]


# Mỗi mảng điểm một bộ giá trị riêng (không 2 mảng nào chung một số), để bảng hạng của từng câu con
# chỉ ra đúng mảng engine đã đọc: nối nhầm khoá / nhầm chữ trần ↔ kèm câu / đảo thứ tự câu con → đỏ
# (code-reviewer PR 3a vòng 1: fixture cũ để 4 biến đổi toàn số 0)
def sub(plain: list[float], context: list[float]) -> dict[str, list[float]]:
    return {"plain": plain, "context": context}


WIRING: dict[str, Any] = {
    "rewrite": sub([0.11, 0.21, 0.31], [0.32, 0.22, 0.12]),
    "expand": sub([0.13, 0.23, 0.33], [0.34, 0.24, 0.14]),
    "hyde": sub([0.15, 0.25, 0.35], [0.36, 0.26, 0.16]),
    "step_back": sub([0.17, 0.27, 0.37], [0.38, 0.28, 0.18]),
    "multi_query": [
        sub([0.41, 0.51, 0.61], [0.62, 0.52, 0.42]),
        sub([0.63, 0.53, 0.43], [0.44, 0.54, 0.64]),
    ],
    "decompose": [
        sub([0.45, 0.55, 0.65], [0.66, 0.56, 0.46]),
        sub([0.67, 0.57, 0.47], [0.48, 0.58, 0.68]),
    ],
}
WIRING_TEXTS: dict[str, Any] = {
    "rewrite": "viết lại",
    "expand": "mở rộng",
    "hyde": "giả định",
    "step_back": "tổng quát",
    "multi_query": ["một", "hai"],
    "decompose": ["phần một", "phần hai"],
}
UP = [(2, 1, 1), (1, 2, 2), (0, 3, 3)]  # mảng tăng dần: đoạn 2 hạng 1
DOWN = [(0, 1, 1), (1, 2, 2), (2, 3, 3)]  # mảng giảm dần: đoạn 0 hạng 1
ORIG_PLAIN_ORDER = DOWN  # V3_DENSE [0.9, 0.5, 0.1]
ORIG_CONTEXT_ORDER = [(1, 1, 1), (2, 2, 2), (0, 3, 3)]  # V3_CONTEXT [0.2, 0.8, 0.5]


def ranked_rows(order: list[tuple[int, int, int]], scores: list[float]) -> list[tuple[Any, ...]]:
    # (đoạn, điểm, hạng từ, hạng tới): điểm đọc từ đúng ô của mảng mong đợi
    return [(chunk, scores[chunk], start, end) for chunk, start, end in order]


def expected_subs(transform: str, context: bool) -> list[tuple[str, list[tuple[Any, ...]]]]:
    key = "context" if context else "plain"
    original = (
        "câu hỏi",
        ranked_rows(
            *((ORIG_CONTEXT_ORDER, V3_CONTEXT) if context else (ORIG_PLAIN_ORDER, V3_DENSE))
        ),
    )

    def one(text: str, scores: dict[str, list[float]]) -> tuple[str, list[tuple[Any, ...]]]:
        # chữ trần tăng dần, kèm câu giảm dần ở mọi câu con đơn; danh sách: đọc theo giá trị
        values = scores[key]
        order = UP if values[0] < values[2] else DOWN
        return (text, ranked_rows(order, values))

    if transform == "none":
        return [original]
    if transform in ("rewrite", "hyde"):
        return [one(WIRING_TEXTS[transform], WIRING[transform])]
    if transform in ("expand", "step_back"):
        return [original, one(WIRING_TEXTS[transform], WIRING[transform])]
    return [one(t, s) for t, s in zip(WIRING_TEXTS[transform], WIRING[transform], strict=True)]


def test_dense_reads_the_array_of_each_sub_query_for_every_transform(tmp_path: Path) -> None:
    demo = make_demo_v3(
        ["cam", "xoài", "ổi"],
        contexts=[None, "ngữ cảnh", "ngữ cảnh"],
        dense=V3_DENSE,
        dense_context=V3_CONTEXT,
        transform_dense=WIRING,
        transforms=WIRING_TEXTS,
    )
    transforms = ["none", "rewrite", "expand", "hyde", "multi_query", "decompose", "step_back"]
    setups = [(t, c) for t in transforms for c in (False, True)]
    cases = [
        {
            "op": "retrieve",
            "demo": demo,
            "config": {"retriever": "dense", "transform": t, "context": c, "way": "post"},
        }
        for t, c in setups
    ]
    got = [
        [(s["text"], table(s["ranked"])) for s in result["dense"]["subQueries"]]
        for result in engine(tmp_path, cases)
    ]
    assert got == [expected_subs(t, c) for t, c in setups]


def test_hybrid_with_a_rewrite_fuses_bm25_and_dense_on_format_3(tmp_path: Path) -> None:
    # format 2 thì đây là "hybrid rơi về BM25"; format 3 trộn thật
    config = {"transform": "rewrite"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": v3_demo(), "config": config}])[0]
    assert result["plan"]["status"] == "ok"
    assert result["dense"] is not None and result["fused"] == result["list"]
    assert table(result["dense"]["list"]) == [(2, 0.3, 1, 1), (1, 0.2, 2, 2), (0, 0.1, 3, 3)]


def test_typed_question_refuses_dense_and_transforms(tmp_path: Path) -> None:
    configs = [{"retriever": "hybrid"}, {"retriever": "bm25", "transform": "rewrite"}]
    cases = [{"op": "plan", "demo": make_demo(["a"]), "config": c, "free": True} for c in configs]
    assert [out.get("error") for out in run_driver(tmp_path, DRIVER, cases)] == ["Error"] * 2


def test_hybrid_falling_back_to_bm25_returns_the_merged_bm25_list(tmp_path: Path) -> None:
    # "bán" chỉ có ở đoạn 1 và chỉ câu mở rộng (có dấu) khớp được nó
    demo = make_demo(
        ["chủ nhà", "bán gấp"], question="chu nha", transforms=TRANSFORMS, dense=[0.9, 0.8]
    )
    result = engine(
        tmp_path, [{"op": "retrieve", "demo": demo, "config": {"transform": "expand"}}]
    )[0]
    assert result["plan"]["status"] == "bm25-only"
    assert (result["dense"], result["fused"]) == (None, None)
    assert result["list"] == result["bm25"]["merged"]
    # đoạn 0: hạng 1 ở cả hai câu con → 2 / 61; đoạn 1: chỉ hạng 2 ở câu mở rộng → 1 / 62
    assert table(result["list"]) == [(0, 0.032787, 1, 1), (1, 0.016129, 2, 2)]


def test_metadata_filter_that_removes_every_chunk_is_named_as_the_empty_step(
    tmp_path: Path,
) -> None:
    # Dense xếp mọi chunk còn lại nên ở hybrid "cả hai bộ tìm rỗng" chỉ xảy ra khi lọc đã loại hết
    demo = make_demo(["cam", "xoài"], question="cam", dense=[0.1, 0.2])
    configs = [
        {},
        {"retriever": "bm25"},
        {"retriever": "dense"},
        {"retriever": "dense", "transform": "rewrite"},
    ]
    cases = [{"op": "retrieve", "demo": demo, "config": c, "candidates": []} for c in configs]
    assert [(r["list"], r["emptyAfter"]) for r in engine(tmp_path, cases)] == [
        ([], "metadata"),
        ([], "metadata"),
        ([], "metadata"),
        (None, None),  # "dense trần cần phần còn chờ": "in progress" thắng trạng thái của bước lọc
    ]


def test_bare_dense_with_a_pending_part_has_no_list(tmp_path: Path) -> None:
    config = {"retriever": "dense", "transform": "rewrite"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": make_demo(["a"]), "config": config}])[0]
    assert (result["list"], result["bm25"], result["dense"]) == (None, None, None)
    assert result["plan"]["status"] == "in-progress"


def test_hybrid_with_an_empty_bm25_list_still_fuses_dense(tmp_path: Path) -> None:
    # BM25 rỗng: RRF chỉ còn dense 1 / 61, 1 / 62, 1 / 63; weighted m(BM25) = 0; DBSF BM25 = 0,5
    expected = {
        "rrf": [(1, 0.016393, 1, 1), (2, 0.016129, 2, 2), (0, 0.015873, 3, 3)],
        "weighted": [(1, 0.5, 1, 1), (2, 0.25, 2, 2), (0, 0.0, 3, 3)],
        "dbsf": [(1, 1.166667, 1, 1), (2, 1.0, 2, 2), (0, 0.833333, 3, 3)],
    }
    demo = make_demo(["cam", "xoài", "mận"], question="zzz", dense=[0.1, 0.5, 0.3])
    cases = [{"op": "retrieve", "demo": demo, "config": {"fusion": f}} for f in expected]
    results = engine(tmp_path, cases)
    assert all(r["bm25"]["list"] == [] and r["emptyAfter"] is None for r in results)
    assert {f: table(r["list"]) for f, r in zip(expected, results, strict=True)} == expected


def test_dense_reads_the_stored_score_through_the_chunk_passage(tmp_path: Path) -> None:
    demo = make_demo(["a", "b", "c"], dense=[0.1, -0.2, 0.3])
    demo["ways"]["post"] = [
        {"id": 0, "unit": "u1", "start": 0, "end": 1, "passage": 2},
        {"id": 1, "unit": "u1", "start": 1, "end": 2, "passage": 1},
    ]
    demo["cosine"]["post"] = [0.0]
    config = {"retriever": "dense", "way": "post"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "config": config}])[0]
    assert table(result["list"]) == [(0, 0.3, 1, 1), (1, -0.2, 2, 2)]


# --- Câu ngữ cảnh, lọc, câu tự gõ ---


def test_context_sentence_goes_before_the_chunk_only_when_effective(tmp_path: Path) -> None:
    demo = make_demo(["chunk một", "chunk hai"], contexts=["ngữ cảnh", None])
    cases = [
        {"op": "texts", "demo": demo, "config": {"way": "post", "context": True}},
        {"op": "texts", "demo": demo, "config": {"way": "post", "context": False}},
        {"op": "texts", "demo": demo, "config": {"way": "whole", "context": True}},
    ]
    assert engine(tmp_path, cases) == [
        ["ngữ cảnh\nchunk một", "chunk hai"],
        ["chunk một", "chunk hai"],
        ["chunk một", "chunk hai"],
    ]


def test_typed_question_matches_through_the_context_sentence(tmp_path: Path) -> None:
    demo = make_demo(["cam", "xoài"], contexts=["sưởi", None])
    config = {"retriever": "bm25", "way": "post", "context": True}
    result = engine(
        tmp_path, [{"op": "retrieve", "demo": demo, "config": config, "freeText": "suoi"}]
    )
    assert [r["chunk"] for r in result[0]["list"]] == [0]
    assert result[0]["plan"]["status"] == "ok"


def test_candidates_only_remove_chunks_and_keep_corpus_statistics(tmp_path: Path) -> None:
    # Lọc trước bước tìm chỉ loại đoạn: điểm BM25 của đoạn còn lại như khi không lọc (ADR-0041)
    demo = make_demo(["cam cam", "cam xoài", "mận"], question="cam")
    cases: list[dict[str, Any]] = [
        {"op": "retrieve", "demo": demo, "config": {"retriever": "bm25"}},
        {"op": "retrieve", "demo": demo, "config": {"retriever": "bm25"}, "candidates": [1, 2]},
    ]
    full, filtered = engine(tmp_path, cases)
    assert [r["chunk"] for r in full["list"]] == [0, 1]
    assert table(filtered["list"]) == [(1, full["list"][1]["score"], 1, 1)]


# --- Bộ đọc file demo ---


def test_engine_constants_match_the_python_file_builder(tmp_path: Path) -> None:
    # Hằng có 2 bản (Python dựng file, TS đọc file): lệch nhau thì bộ đọc từ chối mọi file thật
    names = [
        ("demoFile", "PENDING_PARTS"),
        ("demoFile", "DEMO_FILE_FORMAT"),
        ("rank", "SCORE_DECIMALS"),
        ("demoFile", "RERANK_KEEP_MIN_SCORE"),
        ("demoFile", "FORMAT_2_PENDING_PARTS"),
    ]
    cases = [{"op": "const", "module": m, "name": n} for m, n in names]
    assert engine(tmp_path, cases) == [
        list(PENDING_PARTS),
        DEMO_FILE_FORMAT,
        SCORE_DECIMALS,
        RERANK_KEEP_MIN_SCORE,
        # định dạng 2 (bản còn trên Blob tới lần publish kế tiếp) ghi đúng 2 mục của fixture
        list(PENDING),
    ]
    # định dạng 3 (RAG PR 3a): không còn phần chờ; định dạng 2 ghi đúng 2 mục
    assert (PENDING_PARTS, DEMO_FILE_FORMAT) == ((), 3)
    assert PENDING == (
        "dense score of transformed questions",
        "dense score of chunks with their context sentence",
    )


def test_reader_accepts_a_minimal_format_2_file(tmp_path: Path) -> None:
    gold = make_demo(["a", "b"])
    question = gold["questions"][0]
    question.update(rule="single", gold_unit_ids=["u1"])
    question["gold_chunks"] = {way: {"u1": [1]} for way in WAYS}
    cases = [{"op": "parse", "demo": make_demo(["a", "b"])}, {"op": "parse", "demo": gold}]
    assert engine(tmp_path, cases) == [2, 2]


def test_reader_accepts_a_minimal_format_3_file(tmp_path: Path) -> None:
    demo = make_demo_v3(["a", "b"], transforms={"multi_query": ["một", "hai"]})
    assert engine(tmp_path, [{"op": "parse", "demo": demo}]) == [3]


def broken_v3(change: str) -> dict[str, Any]:
    demo = make_demo_v3(["a", "b"], transforms={"multi_query": ["một", "hai"]})
    question = demo["questions"][0]
    if change == "v3_pending":
        # định dạng 3 mà vẫn ghi phần chờ của định dạng 2
        demo["provenance"]["pending"] = list(PENDING)
    elif change == "v2_without_pending":
        demo["format"] = 2
    elif change == "dense_context_missing":
        del question["dense_context"]
    elif change == "dense_context_length":
        question["dense_context"] = [0.1]
    elif change == "transform_dense_missing":
        del question["transform_dense"]
    elif change == "transform_dense_key":
        del question["transform_dense"]["hyde"]
    elif change == "transform_dense_context":
        del question["transform_dense"]["rewrite"]["context"]
    elif change == "transform_dense_value":
        question["transform_dense"]["expand"]["plain"] = [0.1, None]
    elif change == "transform_dense_count":
        # 2 câu multi-query nhưng chỉ 1 dòng điểm: điểm câu này sẽ rơi vào câu kia
        question["transform_dense"]["multi_query"] = question["transform_dense"]["multi_query"][:1]
    return demo


BROKEN_V3 = [
    "v3_pending",
    "v2_without_pending",
    "dense_context_missing",
    "dense_context_length",
    "transform_dense_missing",
    "transform_dense_key",
    "transform_dense_context",
    "transform_dense_value",
    "transform_dense_count",
]


def test_reader_refuses_a_broken_format_3_file(tmp_path: Path) -> None:
    cases = [{"op": "parse", "demo": broken_v3(change)} for change in BROKEN_V3]
    errors = [out.get("error") for out in run_driver(tmp_path, DRIVER, cases)]
    assert errors == ["DemoFileError"] * len(BROKEN_V3)


def broken(change: str) -> dict[str, Any]:
    demo = make_demo(["a", "b"])
    if change == "format":
        demo["format"] = 1
    elif change == "decimals":
        demo["provenance"]["score_decimals"] = 4
    elif change == "provenance":
        del demo["provenance"]
    elif change == "chunk_id":
        demo["ways"]["semantic"][1]["id"] = 0
    elif change == "passage":
        demo["ways"]["post"][0]["passage"] = 2
    elif change == "dense":
        demo["questions"][0]["dense"] = [0.1]
    elif change == "cosine":
        demo["cosine"]["fixed_300"] = []
    elif change == "way":
        del demo["ways"]["fixed_800"]
    elif change == "pending":
        demo["provenance"]["pending"] = list(PENDING[:1])
    elif change == "dense_value":
        demo["questions"][0]["dense"] = [None, 0.1]
    elif change == "sub_query_list":
        demo["questions"][0]["transforms"]["multi_query"] = "cam xoài"
    elif change == "sub_query":
        demo["questions"][0]["transforms"]["step_back"] = ["tổng quát"]
    elif change == "question_text":
        demo["questions"][0]["text"] = 5
    elif change == "context_missing":
        del demo["passages"][0]["context"]
    elif change == "passage_text":
        demo["passages"][1]["text"] = None
    elif change == "sub_query_empty":
        demo["questions"][0]["transforms"]["decompose"] = []
    elif change == "unit_repeated":
        demo["units"].append(dict(demo["units"][0], month="2026-01"))
    elif change == "keep_min_score":
        demo["provenance"]["llm_keep_min_score"] = 1
    elif change == "unit_month":
        demo["units"][0]["month"] = "2026-13"
    elif change == "unit_topic":
        demo["units"][0]["topic"] = {"id": 3, "label_en": "Jobs"}
    elif change == "unit_posts":
        demo["units"][0]["posts"] = [
            {"id": "p1", "start": 5, "end": 20},
            {"id": "p2", "start": 4, "end": 9},
        ]
    elif change == "post_outside":
        demo["units"][0]["posts"] = [{"id": "p1", "start": 0, "end": 21}]
    elif change == "chunk_unit":
        demo["ways"]["post"][0]["unit"] = "u9"
    elif change == "chunk_span":
        demo["ways"]["post"][0]["end"] = 0
    elif change == "passage_unit":
        demo["passages"][0]["unit"] = "u9"
    elif change == "cross_encoder_value":
        demo["questions"][0]["cross_encoder"] = [0.1, "0.2"]
    elif change == "llm_score":
        demo["questions"][0]["llm"] = [{"score": 0}, {"score": 4}]
    elif change == "llm_cell":
        demo["questions"][0]["llm"] = [{"score": 0}, None]
    elif change == "cosine_value":
        demo["cosine"]["semantic"] = [1.5]
    elif change == "gold_count":
        demo["questions"][0]["rule"] = "single"
    elif change == "gold_units":
        q = demo["questions"][0]
        q.update(rule="single", gold_unit_ids=["u1"])
        q["gold_chunks"] = {way: {"u1": [0]} for way in WAYS}
        q["gold_chunks"]["fixed_500"] = {}
    elif change == "gold_chunk":
        q = demo["questions"][0]
        q.update(rule="single", gold_unit_ids=["u1"])
        q["gold_chunks"] = {way: {"u1": [0]} for way in WAYS}
        q["gold_chunks"]["fixed_500"] = {"u1": [2]}
    return demo


BROKEN = [
    "format",
    "decimals",
    "provenance",
    "pending",
    "chunk_id",
    "passage",
    "dense",
    "dense_value",
    "cosine",
    "way",
    "sub_query_list",
    "sub_query",
    "question_text",
    "context_missing",
    "passage_text",
    "keep_min_score",
    "unit_repeated",
    "sub_query_empty",
    "unit_month",
    "unit_topic",
    "unit_posts",
    "post_outside",
    "chunk_unit",
    "chunk_span",
    "passage_unit",
    "cross_encoder_value",
    "llm_score",
    "llm_cell",
    "cosine_value",
    "gold_count",
    "gold_units",
    "gold_chunk",
]


def test_reader_rejects_files_the_engine_cannot_rank_correctly(tmp_path: Path) -> None:
    # Mỗi ca chỉ vi phạm đúng một điều kiện (ca dương ở test trên)
    out = run_driver(tmp_path, DRIVER, [{"op": "parse", "demo": broken(c)} for c in BROKEN])
    assert {c: o.get("error") for c, o in zip(BROKEN, out, strict=True)} == dict.fromkeys(
        BROKEN, "DemoFileError"
    )


# --- Ca bổ sung (NIT của review commit engine đầu tiên) ---


def test_hybrid_with_candidates_ranks_dense_inside_the_subset(tmp_path: Path) -> None:
    # Lọc bỏ đoạn 0 (dense cao nhất): dense xếp lại trong tập còn lại nên đoạn 2 đứng 1, không 2.
    # BM25 "cam": đoạn 3 ("cam cam") 1, đoạn 1 2; dense: 2, 3, 1 → RRF:
    # đoạn 3 = 1/61 + 1/62, đoạn 1 = 1/62 + 1/63, đoạn 2 = 1/61 (BM25 điểm 0 góp 0)
    demo = make_demo(
        ["cam", "cam xoài", "mận", "cam cam"], question="cam", dense=[0.9, 0.1, 0.5, 0.3]
    )
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "candidates": [1, 2, 3]}])[0]
    assert table(result["dense"]["list"]) == [(2, 0.5, 1, 1), (3, 0.3, 2, 2), (1, 0.1, 3, 3)]
    assert table(result["list"]) == [(3, 0.032522, 1, 1), (1, 0.032002, 2, 2), (2, 0.016393, 3, 3)]


def test_typed_question_without_any_match_stops_after_bm25(tmp_path: Path) -> None:
    demo = make_demo(["cam", "xoài"])
    config = {"retriever": "bm25"}
    result = engine(
        tmp_path, [{"op": "retrieve", "demo": demo, "config": config, "freeText": "zzz"}]
    )[0]
    assert (result["list"], result["emptyAfter"]) == ([], "bm25")


def test_three_sub_queries_add_their_rrf_terms_in_file_order(tmp_path: Path) -> None:
    # "cam": đoạn 0 (ngắn hơn) 1, đoạn 2 2; "xoài": đoạn 1; "mận": đoạn 2 →
    # đoạn 2 = 1/62 + 1/61 = 0,032522; đoạn 0 và 1 cùng 1/61 → hoà [2, 3], đoạn 0 trước (mã chunk)
    transforms = {"multi_query": ["cam", "xoài", "mận"]}
    demo = make_demo(["cam", "xoài", "mận cam"], transforms=transforms)
    config = {"retriever": "bm25", "transform": "multi_query"}
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "config": config}])[0]
    assert [len(sub["ranked"]) for sub in result["bm25"]["subQueries"]] == [2, 1, 1]
    assert table(result["list"]) == [(2, 0.032522, 1, 1), (0, 0.016393, 2, 3), (1, 0.016393, 2, 3)]


def test_fusion_scores_that_differ_only_before_rounding_are_tied(tmp_path: Path) -> None:
    # weighted α 0,5, BM25 rỗng (m = 0): dense −1 … 1 → m(đoạn 0) = 1,999999 / 2; điểm thô
    # 0,49999975 khác 0,5 nhưng làm tròn 6 chữ số cùng 0,5 → hoà [1, 2], phá hoà theo mã chunk
    demo = make_demo(["cam", "xoài", "mận"], question="zzz", dense=[0.999999, 1.0, -1.0])
    result = engine(tmp_path, [{"op": "retrieve", "demo": demo, "config": {"fusion": "weighted"}}])[
        0
    ]
    assert table(result["list"]) == [(0, 0.5, 1, 2), (1, 0.5, 1, 2), (2, 0.0, 3, 3)]


def test_retrieve_refuses_bad_candidates_and_an_index_of_another_way(tmp_path: Path) -> None:
    demo = make_demo(["cam", "xoài"])
    cases: list[dict[str, Any]] = [
        {"op": "retrieve", "demo": demo, "candidates": [0, 0]},
        {"op": "retrieve", "demo": demo, "candidates": [2]},
        {"op": "retrieve", "demo": demo, "candidates": [0.5]},
        {"op": "retrieve", "demo": demo, "indexWay": "post"},
        {
            "op": "retrieve",
            "demo": demo,
            "config": {"way": "post", "context": True},
            "indexContext": False,
        },
    ]
    errors = [out.get("error") for out in run_driver(tmp_path, DRIVER, cases)]
    assert errors == ["RangeError", "RangeError", "RangeError", "Error", "Error"]


def test_slider_positions_have_an_upper_bound(tmp_path: Path) -> None:
    cases = [
        {"op": "call", "module": "rank", "fn": "slider", "args": [101]},
        {"op": "call", "module": "bm25", "fn": "bm25Params", "args": [301, 75]},
        {"op": "call", "module": "bm25", "fn": "bm25Params", "args": [300, 100]},
    ]
    out = run_driver(tmp_path, DRIVER, cases)
    assert [o.get("error") for o in out] == ["RangeError", "RangeError", None]
    assert out[2]["ok"] == {"k1": 3, "b": 1, "oneMinusB": 0}
