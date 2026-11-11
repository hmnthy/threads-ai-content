"""Bước sau bước tìm của engine demo RAG (ADR-0041): lọc, rerank, MMR, top-K, hạng của đáp án, A/B,
mũi tên — dữ liệu tổng hợp, chạy đúng các file TypeScript của sản phẩm bằng node.

Giá trị mong đợi viết tay theo đặc tả, không đọc nhánh hay giá trị từ chính engine. Riêng hạng của
đáp án còn được đối chiếu với cách tính độc lập: vét cạn mọi cách xếp lại trong nhóm hoà, đúng định
nghĩa của mục "Hạng của đáp án" (engine dùng công thức đóng).
"""

import itertools
import random
from pathlib import Path
from typing import Any

import pytest

from tests.rag_demo.demo_fixture import WAYS, make_demo
from tests.rag_demo.node_engine import run_driver

DRIVER = """
import { readFileSync } from "node:fs";
const dir = process.argv[2];
const modules = {
  rank: await import(dir + "rank.ts"),
  demoFile: await import(dir + "demoFile.ts"),
  retrieve: await import(dir + "retrieve.ts"),
  filters: await import(dir + "filters.ts"),
  rerank: await import(dir + "rerank.ts"),
  mmr: await import(dir + "mmr.ts"),
  pipeline: await import(dir + "pipeline.ts"),
  answer: await import(dir + "answer.ts"),
};
const { demoFile, retrieve, pipeline, answer } = modules;
const cases = JSON.parse(readFileSync(process.argv[3], "utf8"));
const rows = (list) => list.map((r) => ({ notReranked: false, tiedAtPick: null, ...r }));
function run(c) {
  if (c.op === "call") return modules[c.module][c.fn](...c.args);
  if (c.op === "compare") return answer.compareAB(c.a, c.b);
  if (c.op === "gold") {
    // Kết quả pipeline dựng tay: chỉ các trường hạng của đáp án đọc
    const result = {
      final: c.final === null ? null : rows(c.final),
      removedAt: new Map(c.removed ?? []),
      retrieval: { plan: { status: c.status ?? "ok" } },
      way: c.way ?? "post",
    };
    return answer.goldAnswer(c.question, result);
  }
  const demo = demoFile.parseDemoFile(c.demo);
  if (c.op === "step") {
    const q = demo.questions[0];
    const way = c.way ?? "post";
    const input = rows(c.rows);
    if (c.fn === "haikuFilter") return modules.filters.haikuFilter(demo, q, way, input);
    const { filters } = modules;
    if (c.fn === "nearDuplicateFilter") return filters.nearDuplicateFilter(demo, way, input, c.arg);
    if (c.fn === "mmr") return modules.mmr.mmr(demo, way, input, c.arg);
    const output = modules.rerank[c.fn](demo, q, way, input, c.arg);
    return { output, arrows: pipeline.arrows({ input, output }) };
  }
  if (c.op === "metadata") {
    return {
      chunks: modules.filters.metadataCandidates(demo, c.way, {
        ...modules.filters.NO_METADATA_FILTER,
        ...c.selection,
      }),
      straddling: modules.filters.straddlingChunks(demo, c.way),
    };
  }
  const config = { ...pipeline.DEFAULT_PIPELINE, ...(c.config ?? {}) };
  const index = retrieve.buildWayIndex(demo, config.way, config.context);
  const question = demo.questions[c.question ?? 0];
  const query = c.freeText !== undefined ? { freeText: c.freeText } : { question };
  const result = pipeline.runPipeline(demo, index, query, config);
  return {
    ...result,
    removedAt: [...result.removedAt].sort((a, b) => a[0] - b[0]),
    gold: c.freeText !== undefined ? null : answer.goldAnswer(question, result),
    summary: answer.listSummary(result),
    arrows: {
      rerank: result.rerank && pipeline.arrows(result.rerank),
      mmr: result.mmr && pipeline.arrows(result.mmr),
    },
  };
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


def engine(tmp_path: Path, cases: list[dict[str, Any]]) -> list[Any]:
    out = run_driver(tmp_path, DRIVER, cases)
    for result in out:
        assert "ok" in result, result
    return [result["ok"] for result in out]


def one(tmp_path: Path, case: dict[str, Any]) -> Any:
    return engine(tmp_path, [case])[0]


def errors(tmp_path: Path, cases: list[dict[str, Any]]) -> list[str | None]:
    return [out.get("error") for out in run_driver(tmp_path, DRIVER, cases)]


def row(
    chunk: int, rank: int, tied: tuple[int, int] | None = None, score: float = 0.0
) -> dict[str, Any]:
    start, end = tied or (rank, rank)
    return {"chunk": chunk, "score": score, "rank": rank, "tiedFrom": start, "tiedTo": end}


def table(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """(chunk, điểm, đầu khoảng, cuối khoảng, not reranked)."""
    return [(r["chunk"], r["score"], r["tiedFrom"], r["tiedTo"], r["notReranked"]) for r in rows]


def scored_demo(
    n: int,
    *,
    cross_encoder: list[float] | None = None,
    llm: list[int] | None = None,
    cosine: dict[tuple[int, int], float] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """make_demo với n chunk, điểm cross-encoder / Haiku theo passage và cosine theo cặp chunk."""
    texts = kwargs.pop("texts", [f"đoạn {i}" for i in range(n)])
    demo = make_demo(texts, **kwargs)
    q = demo["questions"][0]
    q["cross_encoder"] = cross_encoder or [0.0] * n
    q["llm"] = [
        {"score": s, "quote": None, "quote_en": None, "quote_dropped": None}
        for s in (llm or [0] * n)
    ]
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    values = [(cosine or {}).get(pair, 0.0) for pair in pairs]
    demo["cosine"] = {way: list(values) for way in WAYS}
    return demo


# --- Đánh lại hạng sau lọc (Luật chung 6) ---


def test_after_a_filter_tie_groups_keep_their_remaining_members(tmp_path: Path) -> None:
    rows = [
        row(0, 1, (1, 2)),
        row(1, 2, (1, 2)),
        row(2, 3),
        row(3, 4, (4, 6)),
        row(4, 5, (4, 6)),
        row(5, 6, (4, 6)),
    ]
    kept = [rows[0], rows[2], rows[3], rows[5]]  # bỏ đoạn 1 và 4
    out = one(tmp_path, {"op": "call", "module": "rank", "fn": "renumber", "args": [kept]})
    assert [(r["chunk"], r["rank"], r["tiedFrom"], r["tiedTo"]) for r in out] == [
        (0, 1, 1, 1),  # nhóm [1, 2] còn 1 thành viên → hết hoà
        (2, 2, 2, 2),
        (3, 3, 3, 4),  # nhóm [4, 6] còn 2 thành viên → [3, 4]
        (5, 4, 3, 4),
    ]


def test_groups_are_the_carried_members_not_equal_scores(tmp_path: Path) -> None:
    # Hai nhóm liền nhau cùng điểm nhưng khoảng khác nhau (khối đã rerank + đuôi) không gộp lại
    rows = [row(0, 1, score=0.5), row(1, 2, score=0.5)]
    out = one(tmp_path, {"op": "call", "module": "rank", "fn": "renumber", "args": [rows]})
    assert [(r["tiedFrom"], r["tiedTo"]) for r in out] == [(1, 1), (2, 2)]


# --- Lọc metadata ---


def thread_demo() -> dict[str, Any]:
    """u1: 2 post [0, 10) và [11, 20), topic t1, tháng 10.

    u2: 1 post [0, 10), Unclustered, tháng 11.
    """
    demo = make_demo(["a", "b", "c", "d", "e", "f"])
    demo["units"] = [
        {
            "id": "u1",
            "text": "x" * 20,
            "sha256": "",
            "month": "2026-10",
            "topic": {"id": "t1", "label_en": "Jobs"},
            "posts": [{"id": "p1", "start": 0, "end": 10}, {"id": "p2", "start": 11, "end": 20}],
        },
        {
            "id": "u2",
            "text": "y" * 10,
            "sha256": "",
            "month": "2026-11",
            "topic": {"id": None, "label_en": "Unclustered"},
            "posts": [{"id": "p3", "start": 0, "end": 10}],
        },
    ]
    # chunk: 0 mở đầu, 1 viết tiếp, 2 vắt qua cả hai, 3 bài u2, 4 [9, 11) chạm mép post 2 và
    # 5 [10, 15) bắt đầu đúng ở mép cuối post 1 (khoảng nửa mở: cả hai không chạm phần đó)
    spans = [
        ("u1", 0, 10),
        ("u1", 11, 20),
        ("u1", 5, 15),
        ("u2", 0, 10),
        ("u1", 9, 11),
        ("u1", 10, 15),
    ]
    demo["passages"][3]["unit"] = "u2"
    records = [
        {"id": i, "unit": u, "start": s, "end": e, "passage": i}
        for i, (u, s, e) in enumerate(spans)
    ]
    demo["ways"] = {way: [dict(r) for r in records] for way in WAYS}
    return demo


METADATA = [
    ({}, [0, 1, 2, 3, 4, 5]),
    ({"topics": [None]}, [3]),
    ({"topics": ["t1", None]}, [0, 1, 2, 3, 4, 5]),  # OR trong một trường
    ({"parts": ["continuation"]}, [1, 2, 5]),
    ({"parts": ["opening"]}, [0, 2, 3, 4]),
    ({"parts": ["opening"], "months": ["2026-11"]}, [3]),  # AND giữa các trường
    ({"topics": ["t1"], "parts": ["continuation"]}, [1, 2, 5]),
    ({"months": ["2026-09"]}, []),
]


def test_metadata_filter_ors_within_a_field_ands_across_fields_and_matches_by_touch(
    tmp_path: Path,
) -> None:
    demo = thread_demo()
    cases = [{"op": "metadata", "demo": demo, "way": "post", "selection": s} for s, _ in METADATA]
    out = engine(tmp_path, cases)
    assert [o["chunks"] for o in out] == [expected for _, expected in METADATA]
    assert out[0]["straddling"] == 1


# --- Rerank (bảng từng bước, Luật chung 2, 3) ---


def test_cross_encoder_block_takes_the_whole_tie_group_across_n_and_keeps_the_tail(
    tmp_path: Path,
) -> None:
    # Vào: 0..3 hạng 1..4, {4, 5} hoà [5, 6], 6 hạng 7; N = 5 → khối 6 đoạn, đuôi = đoạn 6
    rows = [row(i, i + 1, score=1 - i / 10) for i in range(4)]
    rows += [row(4, 5, (5, 6), 0.55), row(5, 6, (5, 6), 0.55), row(6, 7, score=0.2)]
    demo = scored_demo(7, cross_encoder=[0.1, 0.5, -1.0, 0.5, 2.0, 0.3, 9.9])
    out = one(
        tmp_path, {"op": "step", "demo": demo, "fn": "rerankCrossEncoder", "rows": rows, "arg": 5}
    )
    assert table(out["output"]) == [
        (4, 2.0, 1, 1, False),
        (1, 0.5, 2, 3, False),  # hoà logit, đoạn 1 trước theo mã chunk
        (3, 0.5, 2, 3, False),
        (5, 0.3, 4, 4, False),
        (0, 0.1, 5, 5, False),
        (2, -1.0, 6, 6, False),
        (6, 0.2, 7, 7, True),  # đuôi giữ điểm và hạng của bước trước dù logit 9,9
    ]
    # mũi tên = vị trí vào − vị trí ra; không vẽ khi khoảng chồng nhau (đoạn 1: [2] với [2, 3])
    # và ở đuôi
    assert out["arrows"] == [4, None, 1, 2, -4, -3, None]


def test_rerank_n_at_least_the_list_length_reranks_everything(tmp_path: Path) -> None:
    rows = [row(i, i + 1, score=1 - i / 10) for i in range(3)]
    demo = scored_demo(3, cross_encoder=[0.0, 1.0, 2.0])
    out = one(
        tmp_path, {"op": "step", "demo": demo, "fn": "rerankCrossEncoder", "rows": rows, "arg": 5}
    )
    assert [(r["chunk"], r["notReranked"]) for r in out["output"]] == [
        (2, False),
        (1, False),
        (0, False),
    ]


def test_haiku_keeps_previous_order_and_ties_only_within_a_previous_tie(tmp_path: Path) -> None:
    # Vào: 0 hạng 1, {1, 2} hoà [2, 3], 3, 4, 5; Haiku 1, 2, 2, 3, 2, 0; N = 5 → đuôi = đoạn 5
    rows = [row(0, 1), row(1, 2, (2, 3)), row(2, 3, (2, 3)), row(3, 4), row(4, 5), row(5, 6)]
    demo = scored_demo(6, llm=[1, 2, 2, 3, 2, 0])
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "rerankHaiku", "rows": rows, "arg": 5})
    assert table(out["output"]) == [
        (3, 3, 1, 1, False),
        (1, 2, 2, 3, False),  # cùng 2 điểm VÀ cùng nhóm hoà trước → khoảng các vị trí mới
        (2, 2, 2, 3, False),
        (4, 2, 4, 4, False),  # cùng 2 điểm nhưng khác nhóm trước → giữ thứ tự, một hạng
        (0, 1, 5, 5, False),  # dưới mức giữ vẫn được xếp (nhãn drop)
        (5, 0, 6, 6, True),
    ]
    assert out["arrows"] == [3, None, None, 1, -4, None]


def test_haiku_filter_drops_below_two_including_the_not_reranked_tail(tmp_path: Path) -> None:
    rows = [row(3, 1), row(1, 2, (2, 3)), row(2, 3, (2, 3)), row(4, 4), row(0, 5)]
    rows.append({**row(5, 6), "notReranked": True})
    demo = scored_demo(6, llm=[1, 2, 2, 3, 2, 0])
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "haikuFilter", "rows": rows})
    assert [(r["chunk"], r["tiedFrom"], r["tiedTo"]) for r in out["rows"]] == [
        (3, 1, 1),
        (1, 2, 3),
        (2, 2, 3),
        (4, 4, 4),
    ]
    assert out["dropped"] == [0, 5]


# --- Lọc gần trùng ---


COSINE = {(0, 1): 0.96, (1, 2): 0.97, (0, 2): 0.5, (2, 3): 0.95}


@pytest.mark.parametrize(
    ("threshold", "kept", "dropped"),
    [
        # 1 trùng 0 (0,96); 2 chỉ so với đoạn ĐÃ GIỮ (0: 0,5), không với đoạn 1 đã bỏ;
        # 3 trùng 2 (0,95 ≥ 0,95)
        (95, [0, 2], [1, 3]),
        (96, [0, 2, 3], [1]),
        (100, [0, 1, 2, 3], []),
    ],
)
def test_near_duplicate_filter_compares_only_with_kept_passages(
    tmp_path: Path, threshold: int, kept: list[int], dropped: list[int]
) -> None:
    rows = [row(i, i + 1) for i in range(4)]
    demo = scored_demo(4, cosine=COSINE)
    out = one(
        tmp_path,
        {"op": "step", "demo": demo, "fn": "nearDuplicateFilter", "rows": rows, "arg": threshold},
    )
    assert ([r["chunk"] for r in out["rows"]], out["dropped"]) == (kept, dropped)
    assert [r["rank"] for r in out["rows"]] == list(range(1, len(kept) + 1))


# --- MMR ---


MMR_COSINE = {(0, 1): 0.9, (0, 2): 0.1, (0, 3): 0.0, (1, 2): 0.2, (1, 3): 0.1, (2, 3): 0.3}


def test_mmr_trades_relevance_against_the_most_similar_picked_passage(tmp_path: Path) -> None:
    # rel = min-max(0,9 0,8 0,5 0,1) = 1, 0,875, 0,5, 0; λ = 0,5
    # lượt 1: 0,5 · rel → đoạn 0 (0,5)
    # lượt 2: đoạn 1 0,4375 − 0,45 = −0,0125, đoạn 2 0,25 − 0,05 = 0,2, đoạn 3 0 → đoạn 2
    # lượt 3: đoạn 1 −0,0125, đoạn 3 0 − 0,5 · max(0, 0,3) = −0,15 → đoạn 1; rồi đoạn 3
    rows = [row(0, 1, score=0.9), row(1, 2, score=0.8), row(2, 3, score=0.5), row(3, 4, score=0.1)]
    demo = scored_demo(4, cosine=MMR_COSINE)
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "mmr", "rows": rows, "arg": 50})
    assert [
        (r["chunk"], r["score"], r["rank"], r["tiedFrom"], r["tiedTo"], r["tiedAtPick"])
        for r in out
    ] == [
        (0, 0.5, 1, 1, 1, 0),
        (2, 0.2, 2, 2, 2, 0),
        (1, -0.0125, 3, 3, 3, 0),
        (3, -0.15, 4, 4, 4, 0),
    ]
    arrows = one(
        tmp_path,
        {
            "op": "call",
            "module": "pipeline",
            "fn": "arrows",
            "args": [{"input": with_flags(rows), "output": out}],
        },
    )
    assert arrows == [None, 1, -1, None]  # MMR ra một hạng: chỉ khoảng vào được xét chồng nhau


def with_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**r, "notReranked": False, "tiedAtPick": None} for r in rows]


def test_mmr_tie_at_a_pick_picks_the_earlier_passage_and_counts_the_others(tmp_path: Path) -> None:
    # Cùng điểm → rel = 0 (max = min), cosine 0: mọi lượt cùng giá trị 0
    rows = [row(i, i + 1, (1, 3), 0.7) for i in range(3)]
    demo = scored_demo(3)
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "mmr", "rows": rows, "arg": 50})
    assert [(r["chunk"], r["rank"], r["tiedFrom"], r["tiedTo"], r["tiedAtPick"]) for r in out] == [
        (0, 1, 1, 1, 2),
        (1, 2, 2, 2, 1),
        (2, 3, 3, 3, 0),
    ]


def test_mmr_leaves_a_single_passage_unchanged(tmp_path: Path) -> None:
    rows = [row(4, 1, score=0.3)]
    out = one(
        tmp_path, {"op": "step", "demo": scored_demo(5), "fn": "mmr", "rows": rows, "arg": 50}
    )
    assert [(r["chunk"], r["score"], r["tiedAtPick"]) for r in out] == [(4, 0.3, None)]


# --- Cắt top-K ---


@pytest.mark.parametrize(("k", "shown"), [(1, 1), (2, 2), (3, 5), (5, 5), (20, 6)])
def test_top_k_shows_the_whole_tie_group_across_the_cut(tmp_path: Path, k: int, shown: int) -> None:
    rows = with_flags(
        [row(0, 1), row(1, 2), row(2, 3, (3, 5)), row(3, 4, (3, 5)), row(4, 5, (3, 5)), row(5, 6)]
    )
    out = one(tmp_path, {"op": "call", "module": "pipeline", "fn": "topKCut", "args": [rows, k]})
    assert out == {"k": k, "shown": shown}


# --- Hạng của đáp án ---


def gold_question(rule: str, hits: dict[str, list[int]]) -> dict[str, Any]:
    return {
        "rule": rule,
        "gold_unit_ids": list(hits),
        "gold_chunks": {way: hits for way in WAYS},
    }


def ranked(*groups: tuple[list[int], int]) -> list[dict[str, Any]]:
    """Danh sách cuối từ các nhóm (chunk, vị trí đầu); nhóm 1 chunk = không hoà."""
    rows = []
    for chunks, start in groups:
        end = start + len(chunks) - 1
        rows += [row(c, start + i, (start, end)) for i, c in enumerate(chunks)]
    return rows


def rank(start: int, end: int | None = None) -> dict[str, Any]:
    return {"kind": "rank", "from": start, "to": start if end is None else end}


GOLD = [
    # ADR-0041 mục "Hạng của đáp án": nhóm [5, 7] = {X1, X2, Y1} → [6, 7];
    # bài X [5, 6], bài Y [5, 7]
    (
        gold_question("both", {"X": [10, 11], "Y": [20]}),
        ranked(([0], 1), ([1], 2), ([2], 3), ([3], 4), ([10, 11, 20], 5)),
        rank(6, 7),
        {"X": rank(5, 6), "Y": rank(5, 7)},
    ),
    # X và Y cùng nhóm [5, 6] → 6
    (
        gold_question("both", {"X": [10], "Y": [20]}),
        ranked(([0], 1), ([1], 2), ([2], 3), ([3], 4), ([10, 20], 5)),
        rank(6),
        {"X": rank(5, 6), "Y": rank(5, 6)},
    ),
    # 2 chunk của một bài cùng nhóm [3, 4] → hạng bài 3
    (
        gold_question("single", {"X": [10, 11]}),
        ranked(([0], 1), ([1], 2), ([10, 11], 3)),
        rank(3),
        {"X": rank(3)},
    ),
    # một chunk trúng trong nhóm [2, 3] với một đoạn khác → [2, 3]
    (
        gold_question("single", {"X": [6]}),
        ranked(([0], 1), ([5, 6], 2)),
        rank(2, 3),
        {"X": rank(2, 3)},
    ),
    # X đứng 1, Y trong nhóm [4, 5] với một đoạn khác → số chính [4, 5];
    # chunk Y thứ hai ở sau không tính
    (
        gold_question("both", {"X": [10], "Y": [20, 21]}),
        ranked(([10], 1), ([1], 2), ([2], 3), ([20, 3], 4), ([21], 6)),
        rank(4, 5),
        {"X": rank(1), "Y": rank(4, 5)},
    ),
]


@pytest.mark.parametrize(("question", "final", "main", "units"), GOLD)
def test_gold_rank_is_the_range_over_every_reordering_inside_tie_groups(
    tmp_path: Path,
    question: dict[str, Any],
    final: list[dict[str, Any]],
    main: dict[str, Any],
    units: dict[str, Any],
) -> None:
    out = one(tmp_path, {"op": "gold", "question": question, "final": final})
    assert (out["main"], out["units"], out["bm25Only"]) == (main, units, False)


def test_missing_units_take_the_status_of_the_step_that_removed_their_last_hit(
    tmp_path: Path,
) -> None:
    final = ranked(([10], 1), ([1], 2))
    question = gold_question("both", {"X": [10], "Y": [20, 21]})
    cases: list[dict[str, Any]] = [
        # Y: chunk 20 bị lọc metadata, chunk 21 bị lọc Haiku → bước đứng sau: lọc Haiku
        {
            "op": "gold",
            "question": question,
            "final": final,
            "removed": [[20, "metadata"], [21, "haiku-filter"]],
        },
        # cả hai bài thiếu: X không có điểm BM25, Y bị lọc gần trùng → trạng thái của bước đứng sau
        {
            "op": "gold",
            "question": question,
            "final": ranked(([1], 1)),
            "removed": [[10, "bm25"], [20, "near-duplicate"], [21, "metadata"]],
        },
        # Y: chunk 20 bị lọc Haiku, chunk 21 (còn lại sau cùng) bị lọc gần trùng → lọc gần trùng
        {
            "op": "gold",
            "question": question,
            "final": final,
            "removed": [[20, "haiku-filter"], [21, "near-duplicate"]],
        },
        # cả hai bài thiếu: X bị lọc gần trùng, Y bị lọc Haiku → bước đứng sau: lọc gần trùng
        {
            "op": "gold",
            "question": question,
            "final": ranked(([1], 1)),
            "removed": [[10, "near-duplicate"], [20, "haiku-filter"], [21, "haiku-filter"]],
        },
        # cả hai thiếu cùng bước BM25 → "not found"
        {
            "op": "gold",
            "question": question,
            "final": [],
            "removed": [[10, "bm25"], [20, "bm25"], [21, "metadata"]],
        },
    ]
    first, second, haiku_then_dup, both_late, third = engine(tmp_path, cases)
    assert first["main"] == {"kind": "filtered", "step": "haiku-filter"}
    assert first["units"] == {"X": rank(1), "Y": {"kind": "filtered", "step": "haiku-filter"}}
    assert second["main"] == {"kind": "filtered", "step": "near-duplicate"}
    assert second["units"]["X"] == {"kind": "not-found"}
    assert third["main"] == {"kind": "not-found"}
    assert haiku_then_dup["main"] == {"kind": "filtered", "step": "near-duplicate"}
    assert both_late["main"] == {"kind": "filtered", "step": "near-duplicate"}


def test_in_progress_and_no_gold_and_bm25_only(tmp_path: Path) -> None:
    question = gold_question("single", {"X": [10]})
    cases: list[dict[str, Any]] = [
        {"op": "gold", "question": question, "final": None},
        {"op": "gold", "question": gold_question("none", {}), "final": []},
        {"op": "gold", "question": question, "final": ranked(([10], 1)), "status": "bm25-only"},
    ]
    waiting, none, fallback = engine(tmp_path, cases)
    assert waiting == {
        "main": {"kind": "in-progress"},
        "units": {"X": {"kind": "in-progress"}},
        "bm25Only": False,
    }
    assert none is None
    assert (fallback["main"], fallback["bm25Only"]) == (rank(1), True)


def test_inside_top_k_counts_a_range_that_starts_inside(tmp_path: Path) -> None:
    cases = [
        {"op": "call", "module": "answer", "fn": "insideTopK", "args": [rank(9, 12), 10]},
        {"op": "call", "module": "answer", "fn": "insideTopK", "args": [rank(30), 10]},
        {"op": "call", "module": "answer", "fn": "insideTopK", "args": [{"kind": "not-found"}, 10]},
    ]
    assert engine(tmp_path, cases) == [True, False, False]


def exhaustive(
    final: list[dict[str, Any]], hits: dict[str, list[int]], rule: str
) -> tuple[Any, ...]:
    """Bài giải độc lập theo định nghĩa: mọi cách đặt chunk trúng vào các vị trí nhóm hoà của nó."""
    owner = {c: u for u, chunks in hits.items() for c in chunks}
    groups: dict[tuple[int, int], list[int]] = {}
    for r in final:
        groups.setdefault((r["tiedFrom"], r["tiedTo"]), []).append(r["chunk"])
    # chỉ chunk trúng cần vị trí: mọi cách đặt chúng vào các vị trí của nhóm hoà chứa chúng
    options = []
    for (s, e), members in groups.items():
        golds = [c for c in members if c in owner]
        if golds:
            options.append(
                [
                    dict(zip(golds, p, strict=True))
                    for p in itertools.permutations(range(s, e + 1), len(golds))
                ]
            )
    unit_values: dict[str, set[int]] = {u: set() for u in hits}
    main_values: set[int] = set()
    for combo in itertools.product(*options):
        where = {c: pos for placed in combo for c, pos in placed.items()}
        best = {u: min(where[c] for c in hits[u]) for u in hits}
        for u, value in best.items():
            unit_values[u].add(value)
        main_values.add(max(best.values()) if rule == "both" else best[next(iter(hits))])

    def span(values: set[int]) -> tuple[int, int]:
        return (min(values), max(values))

    return span(main_values), {u: span(v) for u, v in unit_values.items()}


def random_case(rng: random.Random) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Danh sách cuối ngẫu nhiên (nhóm hoà cỡ 1–4), 1 hoặc 2 bài đáp án, mỗi bài 1–3 chunk trúng."""
    sizes = [rng.choice([1, 1, 2, 3, 4]) for _ in range(rng.randint(2, 6))]
    chunks = list(range(sum(sizes)))
    rng.shuffle(chunks)
    groups, start, at = [], 1, 0
    for size in sizes:
        groups.append((chunks[at : at + size], start))
        start += size
        at += size
    order = [c for members, _ in groups for c in members]
    rule = rng.choice(["single", "both"])
    picked = rng.sample(order, rng.randint(2 if rule == "both" else 1, min(len(order), 5)))
    if rule == "single":
        hits = {"X": picked}
    else:
        cut = rng.randint(1, len(picked) - 1)
        hits = {"X": picked[:cut], "Y": picked[cut:]}
    return gold_question(rule, hits), ranked(*groups)


def test_closed_formula_matches_exhaustive_reordering_on_random_lists(tmp_path: Path) -> None:
    rng = random.Random(41)
    cases = [random_case(rng) for _ in range(400)]
    out = engine(tmp_path, [{"op": "gold", "question": q, "final": f} for q, f in cases])
    for (question, final), got in zip(cases, out, strict=True):
        hits = question["gold_chunks"]["post"]
        main, units = exhaustive(final, hits, question["rule"])
        assert (got["main"]["from"], got["main"]["to"]) == main, (question, final)
        assert {u: (r["from"], r["to"]) for u, r in got["units"].items()} == units
    # bộ ca phải có nhiều bài trong cùng một nhóm hoà — phần dữ liệu thật chưa kiểm được (ADR-0041)
    shared = sum(
        1
        for question, final in cases
        if len(question["gold_unit_ids"]) == 2
        and any(
            len(
                {u for u, cs in question["gold_chunks"]["post"].items() for c in cs if c in members}
            )
            == 2
            for members in [
                [r["chunk"] for r in final if (r["tiedFrom"], r["tiedTo"]) == key]
                for key in {(r["tiedFrom"], r["tiedTo"]) for r in final}
            ]
        )
    )
    assert shared >= 20


# --- So A/B ---


def side(main: dict[str, Any] | None, status: str = "ok", dense: str = "run") -> dict[str, Any]:
    answer = (
        None if main is None else {"main": main, "units": {}, "bm25Only": status == "bm25-only"}
    )
    return {
        "answer": answer,
        "plan": {"bm25": True, "dense": dense, "fuse": dense == "run", "status": status},
    }


NOT_FOUND = {"kind": "not-found"}
FILTERED = {"kind": "filtered", "step": "haiku-filter"}
WAITING = {"kind": "in-progress"}

AB = [
    (side(None), side(None), {"kind": "no-verdict"}),
    (side(WAITING, "in-progress", "pending"), side(rank(1)), ("in-progress", None)),
    # bước 2 đứng trước bước 3
    (
        side(WAITING, "in-progress", "pending"),
        side(rank(1), "bm25-only", "pending"),
        ("in-progress", None),
    ),
    (side(rank(1), "bm25-only", "pending"), side(rank(5)), ("bm25-only", "A")),
    (side(rank(5), "ok", "run"), side(rank(1), "bm25-only", "pending"), ("bm25-only", "B")),
    # điều 3 đứng trước điều 4: bên rơi về BM25 không có hạng vẫn là "no clear winner", không thua
    (side(NOT_FOUND, "bm25-only", "pending"), side(rank(1)), ("bm25-only", "A")),
    (side(rank(1)), side(FILTERED, "bm25-only", "pending"), ("bm25-only", "B")),
    # rơi về BM25 so với BM25 thật, hoặc cả hai rơi về BM25 → so bình thường
    (side(rank(1), "bm25-only", "pending"), side(rank(5), "ok", "off"), ("A", "lower-rank")),
    (
        side(rank(5), "bm25-only", "pending"),
        side(rank(1), "bm25-only", "pending"),
        ("B", "lower-rank"),
    ),
    (side(rank(9)), side(NOT_FOUND), ("A", "only-ranked")),
    (side(FILTERED), side(rank(9)), ("B", "only-ranked")),
    (side(NOT_FOUND), side(FILTERED), ("unranked", None)),
    (side(rank(3, 4)), side(rank(4, 5)), ("overlap", None)),  # chung một đầu mút
    (side(rank(2)), side(rank(2)), ("overlap", None)),
    (side(rank(3, 4)), side(rank(5)), ("A", "lower-rank")),
    (side(rank(6)), side(rank(2, 5)), ("B", "lower-rank")),
]


def verdict(expected: Any) -> dict[str, Any]:
    if isinstance(expected, dict):
        return expected
    first, second = expected
    if first in {"A", "B"}:
        return {"kind": "winner", "side": first, "reason": second}
    return {"kind": "no-clear-winner", "reason": first, "bm25OnlySide": second}


def test_ab_comparison_stops_at_the_first_rule_that_applies(tmp_path: Path) -> None:
    out = engine(tmp_path, [{"op": "compare", "a": a, "b": b} for a, b, _ in AB])
    assert out == [verdict(expected) for _, _, expected in AB]


# --- Cả pipeline trên file tổng hợp ---


def pipeline_demo() -> dict[str, Any]:
    """6 đoạn, câu "cam": BM25 khớp 0..4 (đoạn 5 không khớp); bài đáp án u1, chunk trúng 1 và 3."""
    texts = ["cam cam cam", "cam cam", "cam xoài", "cam mận", "cam ổi chuối", "lê"]
    demo = scored_demo(
        6,
        texts=texts,
        question="cam",
        dense=[0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
        cross_encoder=[0.0, 3.0, 1.0, 2.0, 0.5, 5.0],
        llm=[3, 0, 2, 3, 1, 3],
        cosine={(0, 3): 0.97},
    )
    q = demo["questions"][0]
    q.update(rule="single", gold_unit_ids=["u1"])
    q["gold_chunks"] = {way: {"u1": [1, 3]} for way in WAYS}
    return demo


def test_full_pipeline_on_a_synthetic_file(tmp_path: Path) -> None:
    config = {
        "retriever": "bm25",
        "rerank": "cross_encoder",
        "topN": 5,
        "haikuFilter": True,
        "nearDuplicate": True,
        "mmr": True,
        "topK": 1,
    }
    out = one(tmp_path, {"op": "pipeline", "demo": pipeline_demo(), "config": config})
    bm25 = [r["chunk"] for r in out["retrieval"]["list"]]
    assert sorted(bm25) == [0, 1, 2, 3, 4]  # đoạn 5 không khớp → không có hạng
    # N = 5 = cả danh sách BM25; cross-encoder: 1 (3,0), 3 (2,0), 2 (1,0), 4 (0,5), 0 (0,0)
    assert [r["chunk"] for r in out["rerank"]["output"]] == [1, 3, 2, 4, 0]
    # lọc Haiku bỏ 1 (0) và 4 (1); lọc gần trùng bỏ 0 (cosine 0,97 với 3 đã giữ)
    assert (out["haikuFilter"]["dropped"], out["nearDuplicate"]["dropped"]) == ([1, 4], [0])
    # MMR trên [3, 2]: rel 1, 0 → 3 rồi 2
    assert [r["chunk"] for r in out["final"]] == [3, 2]
    assert out["cut"] == {"k": 1, "shown": 1}
    assert out["removedAt"] == [
        [0, "near-duplicate"],
        [1, "haiku-filter"],
        [4, "haiku-filter"],
        [5, "bm25"],
    ]
    assert out["gold"]["main"] == rank(1)  # chunk 3 còn lại dù chunk 1 bị lọc Haiku
    assert out["emptyAfter"] is None


def test_mmr_after_rerank_only_reorders_the_reranked_block(tmp_path: Path) -> None:
    config = {"retriever": "dense", "rerank": "cross_encoder", "topN": 5, "mmr": True}
    out = one(tmp_path, {"op": "pipeline", "demo": pipeline_demo(), "config": config})
    # dense xếp 0..5; N = 5 → đuôi = đoạn 5; MMR chỉ trên 5 đoạn đầu
    assert [r["chunk"] for r in out["mmr"]["input"]] == [1, 3, 2, 4, 0]
    assert [(r["chunk"], r["notReranked"]) for r in out["final"]][-1] == (5, True)
    assert out["arrows"]["rerank"][-1] is None
    assert len(out["arrows"]["mmr"]) == 5


def test_haiku_filter_that_empties_the_list_is_named_and_later_steps_skip(tmp_path: Path) -> None:
    # Như câu 10: không bài nào trả lời, lọc Haiku bỏ hết
    demo = scored_demo(3, texts=["cam", "cam xoài", "lê"], question="cam", llm=[0, 1, 0])
    config = {"retriever": "bm25", "haikuFilter": True, "mmr": True}
    out = one(tmp_path, {"op": "pipeline", "demo": demo, "config": config})
    assert (out["final"], out["emptyAfter"], out["mmr"]) == ([], "haiku-filter", None)
    assert out["summary"] == {"remaining": 0, "top": None}
    assert out["gold"] is None


def test_metadata_filter_removing_the_answer_and_in_progress_winning(tmp_path: Path) -> None:
    demo = thread_demo()
    q = demo["questions"][0]
    q.update(rule="single", gold_unit_ids=["u2"], dense=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    q["gold_chunks"] = {way: {"u2": [3]} for way in WAYS}
    selection = {"topics": ["t1"], "months": [], "parts": []}
    cases = [
        {
            "op": "pipeline",
            "demo": demo,
            "config": {"way": "post", "retriever": "dense", "metadata": selection},
        },
        {
            "op": "pipeline",
            "demo": demo,
            "config": {
                "way": "post",
                "retriever": "dense",
                "transform": "rewrite",
                "metadata": selection,
            },
        },
    ]
    filtered, waiting = engine(tmp_path, cases)
    assert filtered["candidates"] == [0, 1, 2, 4, 5]
    assert filtered["gold"]["main"] == {"kind": "filtered", "step": "metadata"}
    # "dense trần cần phần còn chờ": khối lọc vẫn có số đoạn còn lại, trạng thái chung "in progress"
    assert (waiting["candidates"], waiting["final"]) == ([0, 1, 2, 4, 5], None)
    assert waiting["gold"]["main"] == {"kind": "in-progress"}
    assert waiting["summary"] == {"remaining": None, "top": None}


def test_rerank_keeps_not_found_for_an_answer_bm25_never_ranked(tmp_path: Path) -> None:
    demo = pipeline_demo()
    q = demo["questions"][0]
    q["gold_chunks"] = {way: {"u1": [5]} for way in WAYS}  # đoạn "lê": BM25 điểm 0
    config = {"retriever": "bm25", "rerank": "cross_encoder", "transform": "expand"}
    out = one(tmp_path, {"op": "pipeline", "demo": demo, "config": config})
    assert out["gold"]["main"] == {"kind": "not-found"}
    # hybrid rơi về BM25: nhãn "BM25 only", rerank vẫn chạy trên danh sách BM25
    fallback = one(
        tmp_path,
        {
            "op": "pipeline",
            "demo": pipeline_demo(),
            "config": {"transform": "expand", "rerank": "haiku"},
        },
    )
    assert fallback["gold"]["bm25Only"] is True
    assert fallback["rerank"] is not None


def test_typed_question_keeps_near_duplicate_and_mmr_on_bm25_scores(tmp_path: Path) -> None:
    config = {"retriever": "bm25", "nearDuplicate": True, "mmr": True}
    out = one(
        tmp_path, {"op": "pipeline", "demo": pipeline_demo(), "config": config, "freeText": "cam"}
    )
    assert out["nearDuplicate"]["dropped"] == [3]  # 3 sau 0 trong danh sách BM25, cosine 0,97
    assert out["mmr"] is not None and out["gold"] is None


def test_pipeline_refuses_settings_a_typed_question_or_the_sliders_do_not_allow(
    tmp_path: Path,
) -> None:
    demo = pipeline_demo()
    bad = [
        ({"retriever": "bm25", "rerank": "haiku"}, "cam"),
        ({"retriever": "bm25", "haikuFilter": True}, "cam"),
        ({"topK": 0}, None),
        ({"topK": 21}, None),
        ({"topN": 4}, None),
        ({"lambda": 101}, None),
        ({"nearDuplicateThreshold": 49}, None),
    ]
    cases = [
        {"op": "pipeline", "demo": demo, "config": c, **({"freeText": t} if t else {})}
        for c, t in bad
    ]
    assert errors(tmp_path, cases) == ["Error", "Error"] + ["RangeError"] * 5


def test_haiku_filter_runs_before_the_near_duplicate_filter(tmp_path: Path) -> None:
    # Đoạn 0 (Haiku 0) gần trùng đoạn 1 (Haiku 3, cosine 0,97). Đúng thứ tự (ADR-0041 Luật chung 1):
    # lọc Haiku bỏ 0 trước, đoạn 1 còn lại. Đảo thứ tự thì lọc gần trùng bỏ 1 (trùng 0 đã giữ),
    # rồi lọc Haiku bỏ 0 → danh sách rỗng.
    demo = scored_demo(
        2, texts=["cam cam", "cam xoài"], question="cam", llm=[0, 3], cosine={(0, 1): 0.97}
    )
    config = {"retriever": "bm25", "haikuFilter": True, "nearDuplicate": True}
    out = one(tmp_path, {"op": "pipeline", "demo": demo, "config": config})
    assert [r["chunk"] for r in out["retrieval"]["list"]] == [0, 1]
    assert ([r["chunk"] for r in out["final"]], out["emptyAfter"]) == ([1], None)
    assert out["nearDuplicate"]["dropped"] == []


def test_mmr_penalty_takes_a_negative_cosine_to_the_first_pick(tmp_path: Path) -> None:
    # rel = min-max(0,9 0,5 0,4) = 1, 0,2, 0; λ = 0,5; cosine với đoạn 0: đoạn 1 −0,4, đoạn 2 0,1;
    # cos(1, 2) = 0. Lượt 2: đoạn 1 0,1 − 0,5 · (−0,4) = 0,3; đoạn 2 0 − 0,05 = −0,05 → đoạn 1.
    # Phần phạt bỏ qua cosine âm (giữ 0) thì đoạn 1 = 0,1 — vẫn thắng nhưng điểm sai.
    rows = [row(0, 1, score=0.9), row(1, 2, score=0.5), row(2, 3, score=0.4)]
    demo = scored_demo(3, cosine={(0, 1): -0.4, (0, 2): 0.1})
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "mmr", "rows": rows, "arg": 50})
    assert [(r["chunk"], r["score"]) for r in out] == [(0, 0.5), (1, 0.3), (2, -0.05)]


def test_rerank_and_haiku_filter_read_scores_through_the_chunk_passage(tmp_path: Path) -> None:
    # Cách chia "post": chunk 0 → passage 2, chunk 1 → passage 0, chunk 2 → passage 1 (mã chunk khác
    # passage, như file thật). Điểm theo passage: cross-encoder 0,1 0,5 0,9; Haiku 3 0 2.
    # → theo chunk: cross-encoder 0,9 0,1 0,5; Haiku 2 3 0. Đọc nhầm theo mã chunk ra thứ tự khác.
    demo = scored_demo(3, cross_encoder=[0.1, 0.5, 0.9], llm=[3, 0, 2])
    demo["ways"]["post"] = [
        {"id": i, "unit": "u1", "start": 0, "end": 1, "passage": p} for i, p in enumerate([2, 0, 1])
    ]
    rows = [row(0, 1), row(1, 2), row(2, 3)]
    step = {"op": "step", "demo": demo, "rows": rows, "arg": 5}
    cross, haiku, kept = engine(
        tmp_path,
        [
            {**step, "fn": "rerankCrossEncoder"},
            {**step, "fn": "rerankHaiku"},
            {**step, "fn": "haikuFilter"},
        ],
    )
    assert [(r["chunk"], r["score"]) for r in cross["output"]] == [(0, 0.9), (2, 0.5), (1, 0.1)]
    assert [(r["chunk"], r["score"]) for r in haiku["output"]] == [(1, 3), (0, 2), (2, 0)]
    assert ([r["chunk"] for r in kept["rows"]], kept["dropped"]) == ([0, 1], [2])


def test_list_summary_counts_before_the_cut_and_shows_position_one(tmp_path: Path) -> None:
    # Câu không có đáp án (điều 1 của A/B): số đoạn còn lại đếm TRƯỚC khi cắt top-K, đoạn đứng đầu
    # mang khoảng hạng của nó. Dense 0,1 0,6 0,3 0,6 0,2 0,4 → chunk 1 và 3 hoà ở [1, 2].
    demo = scored_demo(6, dense=[0.1, 0.6, 0.3, 0.6, 0.2, 0.4])
    out = one(
        tmp_path, {"op": "pipeline", "demo": demo, "config": {"retriever": "dense", "topK": 2}}
    )
    assert out["cut"] == {"k": 2, "shown": 2}
    assert out["summary"] == {
        "remaining": 6,
        "top": {
            "chunk": 1,
            "score": 0.6,
            "rank": 1,
            "tiedFrom": 1,
            "tiedTo": 2,
            "notReranked": False,
            "tiedAtPick": None,
        },
    }


def test_haiku_rerank_moves_a_whole_tie_group_and_its_arrows(tmp_path: Path) -> None:
    # Vào: 0 hạng 1, 1 hạng 2, {2, 3} hoà [3, 4]; Haiku 0 0 3 3 → ra: 2, 3 hoà [1, 2], rồi 0, 1.
    # Mũi tên = vị trí vào − vị trí ra: 3 − 1, 4 − 2, 1 − 3, 2 − 4.
    rows = [row(0, 1), row(1, 2), row(2, 3, (3, 4)), row(3, 4, (3, 4))]
    demo = scored_demo(4, llm=[0, 0, 3, 3])
    out = one(tmp_path, {"op": "step", "demo": demo, "fn": "rerankHaiku", "rows": rows, "arg": 5})
    assert [(r["chunk"], r["rank"], r["tiedFrom"], r["tiedTo"]) for r in out["output"]] == [
        (2, 1, 1, 2),
        (3, 2, 1, 2),
        (0, 3, 3, 3),
        (1, 4, 4, 4),
    ]
    assert out["arrows"] == [2, 2, -2, -2]


def test_pipeline_passes_its_own_lambda_to_mmr(tmp_path: Path) -> None:
    # λ = 0 (α giữ mặc định 50): giá trị = −max cos. Lượt 1: mọi đoạn 0 → đoạn 0 (đứng trước), hoà
    # với 2 đoạn khác; lượt 2: đoạn 1 −0,9, đoạn 2 −0,1 → đoạn 2;
    # lượt 3: đoạn 1 −max(0,9, 0) = −0,9.
    # λ = 0,5 sẽ ra 0, 1, 2 (rel đoạn 1 = 0,875).
    demo = scored_demo(3, dense=[0.9, 0.8, 0.1], cosine={(0, 1): 0.9, (0, 2): 0.1})
    config = {"retriever": "dense", "mmr": True, "lambda": 0}
    out = one(tmp_path, {"op": "pipeline", "demo": demo, "config": config})
    assert [(r["chunk"], r["score"], r["tiedAtPick"]) for r in out["final"]] == [
        (0, 0.0, 2),
        (2, -0.1, 0),
        (1, -0.9, 0),
    ]


def test_pipeline_haiku_filter_also_drops_from_the_not_reranked_tail(tmp_path: Path) -> None:
    # Dense xếp 0..5; rerank N = 5 → đuôi = đoạn 5, Haiku 0 → lọc Haiku bỏ cả đoạn ở đuôi
    demo = scored_demo(6, dense=[0.6, 0.5, 0.4, 0.3, 0.2, 0.1], llm=[3, 3, 3, 3, 3, 0])
    config = {"retriever": "dense", "rerank": "cross_encoder", "topN": 5, "haikuFilter": True}
    out = one(tmp_path, {"op": "pipeline", "demo": demo, "config": config})
    assert [(r["chunk"], r["notReranked"]) for r in out["rerank"]["output"]][-1] == (5, True)
    assert out["haikuFilter"]["dropped"] == [5]
    assert out["removedAt"] == [[5, "haiku-filter"]]
    assert all(not r["notReranked"] for r in out["final"])
