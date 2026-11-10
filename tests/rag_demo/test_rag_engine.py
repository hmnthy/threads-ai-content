"""Luật xếp hạng, gộp câu con, trộn, bước tìm của engine demo RAG (ADR-0041), dữ liệu tổng hợp.

Chạy đúng các file TypeScript của sản phẩm bằng node. Giá trị mong đợi viết tay (tính theo ADR-0041
Luật chung 5: làm tròn `Decimal(float)` ROUND_HALF_UP, cộng trái → phải, bình phương `d * d`), không
đọc nhánh hay giá trị từ chính engine. Mọi câu là câu tự đặt, không dùng chữ của bài thật.
"""

import random
from pathlib import Path
from typing import Any

from src.rag_demo.demo_file import DEMO_FILE_FORMAT, PENDING_PARTS, SCORE_DECIMALS, _score
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
  if (c.op === "plan") return retrieve.retrievalPlan(config, c.free ?? false);
  if (c.op === "texts") return retrieve.chunkTexts(demo, config.way, config.context);
  const index = retrieve.buildWayIndex(demo, config.way, config.context);
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

# Đúng 2 mục bản Python ghi (`src/rag_demo/demo_file.py` PENDING_PARTS)
PENDING = (
    "dense score of transformed questions",
    "dense score of chunks with their context sentence",
)
WAYS = ["whole", "post", "fixed_300", "fixed_500", "fixed_800", "recursive_500", "semantic"]


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


def make_demo(
    texts: list[str],
    *,
    contexts: list[str | None] | None = None,
    dense: list[float] | None = None,
    question: str = "câu hỏi",
    transforms: dict[str, Any] | None = None,
    **changes: Any,
) -> dict[str, Any]:
    """File demo định dạng 2 tối thiểu: mỗi cách chia có cùng các chunk, chunk i = passage i."""
    n = len(texts)
    contexts = contexts if contexts is not None else [None] * n
    chunks = [{"id": i, "unit": "u1", "start": 0, "end": 1, "passage": i} for i in range(n)]
    base_transforms: dict[str, Any] = {
        "rewrite": question,
        "expand": question,
        "hyde": question,
        "multi_query": [question],
        "decompose": [question],
        "step_back": question,
    }
    base_transforms.update(transforms or {})
    for key in list(base_transforms):
        base_transforms[f"{key}_en"] = base_transforms[key]
    demo: dict[str, Any] = {
        "format": 2,
        "provenance": {
            "score_decimals": 6,
            "pending": list(PENDING),
            "llm_keep_min_score": 2,
            "topics": {"cluster_run_id": 1, "cluster_run_at": "2026-11-10T00:00:00+00:00"},
        },
        "units": [],
        "passages": [
            {"unit": "u1", "text": t, "en": t, "context": c, "context_en": c}
            for t, c in zip(texts, contexts, strict=True)
        ],
        "ways": {way: [dict(c) for c in chunks] for way in WAYS},
        "cosine": {way: [0.0] * (n * (n - 1) // 2) for way in WAYS},
        "questions": [
            {
                "number": 1,
                "text": question,
                "english": question,
                "rule": "single",
                "gold_unit_ids": [],
                "gold_spans": {},
                "gold_chunks": {way: {} for way in WAYS},
                "transforms": base_transforms,
                "dense": dense if dense is not None else [0.0] * n,
                "cross_encoder": [0.0] * n,
                "llm": [{"score": 0, "quote": None, "quote_en": None, "quote_dropped": None}] * n,
            }
        ],
    }
    demo.update(changes)
    return demo


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
    assert (merged["list"], merged["emptyAfter"]) == ([], "sub-query merge")


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
        ([], "metadata filter"),
        ([], "metadata filter"),
        ([], "metadata filter"),
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
    ]
    cases = [{"op": "const", "module": m, "name": n} for m, n in names]
    assert engine(tmp_path, cases) == [list(PENDING_PARTS), DEMO_FILE_FORMAT, SCORE_DECIMALS]
    assert tuple(PENDING) == PENDING_PARTS


def test_reader_accepts_a_minimal_format_2_file(tmp_path: Path) -> None:
    assert engine(tmp_path, [{"op": "parse", "demo": make_demo(["a", "b"])}]) == [2]


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
]


def test_reader_rejects_files_the_engine_cannot_rank_correctly(tmp_path: Path) -> None:
    # Mỗi ca chỉ vi phạm đúng một điều kiện (ca dương ở test trên)
    out = run_driver(tmp_path, DRIVER, [{"op": "parse", "demo": broken(c)} for c in BROKEN])
    assert {c: o.get("error") for c, o in zip(BROKEN, out, strict=True)} == dict.fromkeys(
        BROKEN, "DemoFileError"
    )
