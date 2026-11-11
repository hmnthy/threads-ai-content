"""Ảnh chụp hồi quy của engine demo RAG trên file demo thật (ADR-0041 Hệ quả).

Chạy đúng cấu hình đã đo ở Bối cảnh ADR-0041 — BM25 cả hai bên, không rerank, lọc và MMR tắt, câu
ngữ cảnh tắt, k1 = 1,2, b = 0,75 — cho 9 câu có đáp án × 7 cách chia, hai cột: không biến đổi và
expand (câu gốc + câu mở rộng, gộp RRF). Các số này sinh từ chính engine, không phải bài giải độc
lập: test chỉ giữ cho chúng không trôi khi sửa code. Số chính (hạng của bài tìm thấy sau cùng ở câu
3 và 7) tính ở đây bằng vét cạn mọi cách đặt chunk đáp án vào các vị trí của nhóm hoà chứa nó, đúng
định nghĩa mục "Hạng của đáp án" — cách tính độc lập với công thức đóng của engine (`answer.ts`), và
hai cách phải ra cùng số ở mọi ô, kể cả ở các cấu hình có rerank, lọc, MMR (`SWEEP`).

`data/rag_demo/demo.json` gitignored (chứa chữ bài): thiếu file thì bỏ qua — CI không chạy test này.
"""

import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from tests.rag_demo.node_engine import run_driver

DEMO = Path(__file__).parents[2] / "data/rag_demo/demo.json"
WAYS = ["whole", "post", "fixed_300", "fixed_500", "fixed_800", "recursive_500", "semantic"]
# Giới hạn vét cạn: số đo 2026-11-10 tối đa 4 cách đặt mỗi ô; vượt xa thì dữ liệu đã đổi hẳn
MAX_PLACEMENTS = 100_000

# Mỗi ca: danh sách cuối (chunk, khoảng hạng) + số chính engine tính bằng công thức đóng.
DRIVER = """
import { readFileSync } from "node:fs";
const dir = process.argv[2];
const { parseDemoFile } = await import(dir + "demoFile.ts");
const retrieve = await import(dir + "retrieve.ts");
const pipeline = await import(dir + "pipeline.ts");
const answer = await import(dir + "answer.ts");
const { path, cases } = JSON.parse(readFileSync(process.argv[3], "utf8"))[0];
const demo = parseDemoFile(JSON.parse(readFileSync(path, "utf8")));
const indexes = new Map();
const out = cases.map((c) => {
  const config = { ...pipeline.DEFAULT_PIPELINE, retriever: "bm25", ...c.config };
  const key = config.way + "/" + config.context;
  if (!indexes.has(key)) indexes.set(key, retrieve.buildWayIndex(demo, config.way, config.context));
  const question = demo.questions.find((q) => q.number === c.number);
  const result = pipeline.runPipeline(demo, indexes.get(key), { question }, config);
  return {
    list: result.final === null ? null : result.final.map((r) => [r.chunk, r.tiedFrom, r.tiedTo]),
    main: answer.goldAnswer(question, result)?.main ?? null,
  };
});
console.log(JSON.stringify([out]));
"""

Rank = int | tuple[int, int] | str


def main_number(ranked: list[list[int]], gold: dict[str, list[int]], rule: str) -> Rank:
    """Số chính theo định nghĩa: [nhỏ nhất, lớn nhất] trên mọi cách xếp lại trong nhóm hoà."""
    owner = {chunk: unit for unit, chunks in gold.items() for chunk in chunks}
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for chunk, start, end in ranked:
        groups[(start, end)].append(chunk)
    found = {owner[c] for c, _, _ in ranked if c in owner}
    if found != set(gold):
        return "not found"
    # Mỗi nhóm có chunk đáp án: mọi cách đặt các chunk đáp án đó vào vị trí của nhóm
    choices = []
    for (start, end), members in groups.items():
        golds = [c for c in members if c in owner]
        if golds:
            spots = range(start, end + 1)
            choices.append(
                [
                    list(zip(golds, p, strict=True))
                    for p in itertools.permutations(spots, len(golds))
                ]
            )
    total = 1
    for options in choices:
        total *= len(options)
    assert total <= MAX_PLACEMENTS, f"{total} cách đặt"
    values = set()
    for combo in itertools.product(*choices):
        best: dict[str, int] = {}
        for placed in combo:
            for chunk, position in placed:
                unit = owner[chunk]
                best[unit] = min(best.get(unit, position), position)
        # câu 1 bài: hạng bài đó (gold có đúng 1 bài); câu 3 và 7: hạng của bài tìm thấy sau cùng
        values.add(max(best.values()) if rule == "both" else min(best.values()))
    low, high = min(values), max(values)
    return low if low == high else (low, high)


def parse_row(row: str) -> list[Rank]:
    cells: list[Rank] = []
    for cell in row.split():
        if "-" in cell:
            low, high = cell.split("-")
            cells.append((int(low), int(high)))
        else:
            cells.append(int(cell))
    return cells


# Câu → (không biến đổi, expand) theo thứ tự WAYS; "a-b" = khoảng hạng. Đo bằng engine 2026-11-10,
# khớp bảng ở Bối cảnh ADR-0041 (câu 1, 6, 7 ghi đủ ở đó; tổng cột expand 129).
EXPECTED = {
    1: ("1 2 1 1 1 1 1", "3 2 2 4 3 2 1"),
    2: ("1 1 1 1 1 1 1", "1 1 1 1 1 1 1"),
    3: ("2 3 4 3 3 3 3", "2 3 4 3 3 3 3"),
    4: ("1 1 1 1 1 1 1", "1 1 1 1 1 1 1"),
    5: ("1 1 1 1 1 1 1", "1 1 1 1 1 1 1"),
    6: ("8 10-11 10-12 10-11 11 6-7 12", "1 2 1 1 2 1 1"),
    7: ("6 9 11 7 7 4 16", "4 6 11 4 5 5 11"),
    8: ("1 1 1 1 1 1 1", "1 1 2 1 1 1 1"),
    9: ("1 1 1 1 1 1 1", "1 1 1 1 1 1 1"),
}


@pytest.mark.skipif(not DEMO.is_file(), reason="cần data/rag_demo/demo.json (gitignored)")
def test_main_numbers_match_the_measured_snapshot(tmp_path: Path) -> None:
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    questions = [q for q in demo["questions"] if q["gold_unit_ids"]]
    cases = [
        {"number": q["number"], "config": {"way": way, "transform": transform}}
        for q in questions
        for transform in ("none", "expand")
        for way in WAYS
    ]
    out = run_driver(tmp_path, DRIVER, [{"path": str(DEMO), "cases": cases}])[0]
    got: dict[int, tuple[list[Rank], list[Rank]]] = {}
    engine_main: dict[int, tuple[list[Rank], list[Rank]]] = {}
    for q in questions:
        own = [(c, o) for c, o in zip(cases, out, strict=True) if c["number"] == q["number"]]
        cells = [
            main_number(o["list"], q["gold_chunks"][c["config"]["way"]], q["rule"]) for c, o in own
        ]
        formula = [as_rank(o["main"]) for _, o in own]
        got[q["number"]] = (cells[:7], cells[7:])
        engine_main[q["number"]] = (formula[:7], formula[7:])
    expected = {n: (parse_row(a), parse_row(b)) for n, (a, b) in EXPECTED.items()}
    assert got == expected
    # công thức đóng của engine = vét cạn ở mọi ô
    assert engine_main == expected


def as_rank(main: dict[str, Any]) -> Rank:
    """Số chính của engine theo cách viết của `main_number`."""
    if main["kind"] != "rank":
        return "not found"
    return main["from"] if main["from"] == main["to"] else (main["from"], main["to"])


# Cấu hình phủ mọi bước sau bước tìm (rerank, lọc, MMR, cắt K) — số chính phải bằng vét cạn trên
# danh sách cuối của chính engine, và engine không được crash ở cấu hình nào.
SWEEP: list[dict[str, Any]] = [
    {},
    {"retriever": "hybrid"},
    {"retriever": "dense"},
    {"retriever": "hybrid", "fusion": "weighted", "alpha": 30},
    {"retriever": "hybrid", "fusion": "dbsf"},
    {"retriever": "hybrid", "rerank": "cross_encoder", "topN": 5},
    {"retriever": "hybrid", "rerank": "haiku", "topN": 10},
    {"retriever": "hybrid", "rerank": "haiku", "haikuFilter": True},
    {"retriever": "hybrid", "nearDuplicate": True, "nearDuplicateThreshold": 70},
    {"retriever": "hybrid", "mmr": True, "lambda": 30},
    {"retriever": "hybrid", "rerank": "cross_encoder", "mmr": True, "topN": 5},
    {"transform": "multi_query", "rerank": "haiku", "topN": 5, "mmr": True},
    {"transform": "decompose", "haikuFilter": True},
    {"retriever": "hybrid", "transform": "step_back", "context": True},
    {"retriever": "dense", "transform": "hyde"},
]


@pytest.mark.skipif(not DEMO.is_file(), reason="cần data/rag_demo/demo.json (gitignored)")
def test_closed_formula_matches_exhaustive_reordering_on_the_real_file(tmp_path: Path) -> None:
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    questions = {q["number"]: q for q in demo["questions"]}
    cases = [
        {"number": n, "config": {"way": way, **config}}
        for n in questions
        for way in WAYS
        for config in SWEEP
    ]
    out = run_driver(tmp_path, DRIVER, [{"path": str(DEMO), "cases": cases}])[0]
    compared = 0
    for c, o in zip(cases, out, strict=True):
        q = questions[c["number"]]
        if q["rule"] == "none" or o["list"] is None:
            assert o["main"] is None or o["main"]["kind"] == "in-progress"
            continue
        exhaustive = main_number(o["list"], q["gold_chunks"][c["config"]["way"]], q["rule"])
        if o["main"]["kind"] == "rank":
            assert as_rank(o["main"]) == exhaustive, c
            compared += 1
        else:
            assert exhaustive == "not found", c
    assert compared > 0.8 * len(cases)


def test_exhaustive_main_number_on_hand_built_tie_groups() -> None:
    # Nhóm hoà [5, 7] = {X1, X2, Y1} → [6, 7] (ví dụ của ADR-0041 mục "Hạng của đáp án")
    ranked = [[0, 1, 1], [1, 2, 2], [2, 3, 3], [3, 4, 4], [10, 5, 7], [11, 5, 7], [20, 5, 7]]
    assert main_number(ranked, {"X": [10, 11], "Y": [20]}, "both") == (6, 7)
    # X và Y cùng trong nhóm hoà [5, 6] → 6; 2 chunk của một bài ở [3, 4] → hạng bài là 3
    pair = [[0, 1, 1], [1, 2, 2], [2, 3, 3], [3, 4, 4], [10, 5, 6], [20, 5, 6]]
    assert main_number(pair, {"X": [10], "Y": [20]}, "both") == 6
    same = [[0, 1, 1], [1, 2, 2], [10, 3, 4], [11, 3, 4]]
    assert main_number(same, {"X": [10, 11]}, "single") == 3
    # một chunk trúng trong nhóm hoà [2, 3] với một chunk khác → khoảng [2, 3]
    assert main_number([[0, 1, 1], [5, 2, 3], [6, 2, 3]], {"X": [6]}, "single") == (2, 3)
    assert main_number([[0, 1, 1]], {"X": [6]}, "single") == "not found"
    assert main_number([[6, 1, 1]], {"X": [6], "Y": [9]}, "both") == "not found"
