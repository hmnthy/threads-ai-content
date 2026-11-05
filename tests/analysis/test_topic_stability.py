"""Luật bền ADR-0036 (`src/analysis/topic_stability.py`) — dữ liệu giả, không đọc DB."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import binomtest

from src.analysis import topic_stability as ts
from src.analysis.topic_comparison import CONCLUSION_ALPHA

REPO = Path(__file__).resolve().parents[2]
LANDING_TS = REPO / "src" / "dashboard" / "src" / "lib" / "landing.ts"

# (p Holm, δ, insufficient_data, verdict) — mọi nhánh của testVerdict, cả biên alpha và δ = 0
VERDICT_CASES: list[tuple[float | None, float | None, bool, str]] = [
    (None, 0.3, False, "not tested"),
    (0.01, None, False, "not tested"),
    (None, None, True, "not tested"),  # null đứng trước cờ mẫu nhỏ
    (0.01, 0.4, True, "too few posts"),
    (1.0, 0.0, True, "too few posts"),
    (CONCLUSION_ALPHA, 0.4, False, "not distinguishable"),  # biên: p = alpha không đạt
    (0.9, -0.1, False, "not distinguishable"),
    (0.0499, 0.4, False, "higher"),
    (0.0, 1.0, False, "higher"),
    (0.0499, -0.4, False, "lower"),
    (0.01, 0.0, False, "lower"),  # δ = 0: bản TS ra "lower" — bản Python giữ y nguyên
]


def test_preregistered_constants_are_unchanged() -> None:
    # Chốt trước khi chạy (ADR-0036 quyết định 3): đổi bất kỳ số nào = ADR mới, không sửa ở đây
    assert ts.STABILITY_REPLICATES == 100
    assert ts.KEEP_PERCENT == 75
    assert ts.DROP_PERCENT == 3
    assert ts.MATCH_JACCARD == 0.5
    assert ts.SENSITIVITY_PERCENTS == (60, 90)
    assert CONCLUSION_ALPHA == 0.05


@pytest.mark.parametrize(("p_holm", "delta", "insufficient", "expected"), VERDICT_CASES)
def test_comparison_verdict_cases(
    p_holm: float | None, delta: float | None, insufficient: bool, expected: str
) -> None:
    assert ts.comparison_verdict(p_holm, delta, insufficient) == expected


def _ts_verdict_source() -> str:
    """Thân hàm `testVerdict` của landing.ts, bỏ chú thích kiểu ở chữ ký → JS chạy được bằng node
    mọi phiên bản. Thân hàm có cú pháp TS thì node báo lỗi → test hỏng, buộc cập nhật."""
    source = LANDING_TS.read_text(encoding="utf-8")
    match = re.search(
        r"export function testVerdict\(\s*row[^)]*\)\s*:[^{]*\{(?P<body>.*?)\n\}", source, re.S
    )
    assert match, "không tìm thấy testVerdict trong landing.ts"
    return f"function testVerdict(row, method) {{{match['body']}\n}}"


def test_python_verdict_matches_the_dashboard_testverdict_case_by_case(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("không có node — không chạy được testVerdict")
    cases = [
        {"p_value_holm": p, "effect_size": d, "insufficient_data": i}
        for p, d, i, _ in VERDICT_CASES
    ]
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    script = tmp_path / "verdict.mjs"
    script.write_text(
        _ts_verdict_source()
        + "\nimport { readFileSync } from 'node:fs';\n"
        + "const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
        + f"const method = {{ conclusion_alpha: {CONCLUSION_ALPHA} }};\n"
        + "const out = cases.map((c) => testVerdict(c, method));\n"
        + "out.push(testVerdict(undefined, method));\n"  # không có dòng → "not tested"
        + "console.log(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [node, str(script), str(tmp_path / "cases.json")],
        capture_output=True,
        text=True,
        check=True,
    )
    from_ts = json.loads(result.stdout)
    from_python = [ts.comparison_verdict(p, d, i) for p, d, i, _ in VERDICT_CASES]
    assert from_ts == [*from_python, "not tested"]
    assert from_python == [expected for *_, expected in VERDICT_CASES]


@pytest.mark.parametrize(("n", "dropped"), [(165, 5), (100, 3), (33, 1), (34, 2), (1, 1), (0, 0)])
def test_n_dropped_is_the_integer_ceiling_of_three_percent(n: int, dropped: int) -> None:
    assert ts.n_dropped(n) == dropped


def test_replicate_positions_pair_the_two_arms_on_the_same_permutation() -> None:
    n = 40
    s = ts.replicate_positions(n, 7, "S")
    p = ts.replicate_positions(n, 7, "P")
    assert sorted(s) == list(range(n))  # S: đủ N bài, đảo thứ tự
    assert s != list(range(n))
    assert p == s[: n - ts.n_dropped(n)]  # P: bỏ d phần tử CUỐI, giữ thứ tự phần còn lại
    assert s == [int(x) for x in np.random.default_rng(7).permutation(n)]
    assert ts.replicate_positions(n, 7, "S") == s  # tất định
    assert ts.replicate_positions(n, 8, "S") != s  # b khác → hoán vị khác


REFERENCE = {"t1": {"a", "b", "c", "d"}, "t2": {"e", "f", "g", "h"}}


def test_match_uses_jaccard_over_present_units_and_needs_more_than_half() -> None:
    replicate = {"a": 0, "b": 0, "c": 0, "x": 0, "d": -1, "e": 1, "f": 1, "g": -1, "h": -1}
    matches = ts.match_reference_topics(REFERENCE, replicate)
    # J(t1, c0) = |{a,b,c}| / |{a,b,c,d} ∪ {a,b,c,x}| = 3/5; bài unclustered vẫn ở mẫu số
    assert matches["t1"] == ts.TopicMatch(cluster=0, jaccard=0.6, alive=True)
    # J(t2, c1) = 2/4 = 0.5 — đúng mốc thì KHÔNG còn sống (J > 0.5)
    assert matches["t2"] == ts.TopicMatch(cluster=1, jaccard=0.5, alive=False)


def test_match_ignores_units_absent_from_the_replicate() -> None:
    # d bị bỏ ở lần này: J = 3 / |{a,b,c} ∪ {a,b,c,x}| = 0.75
    replicate = {"a": 0, "b": 0, "c": 0, "x": 0}
    assert ts.match_reference_topics(REFERENCE, replicate)["t1"].jaccard == 0.75


def test_match_scores_zero_when_no_cluster_or_no_member_is_present() -> None:
    all_noise = {u: -1 for u in "abcdefgh"}
    matches = ts.match_reference_topics(REFERENCE, all_noise)
    assert matches["t1"] == ts.TopicMatch(cluster=None, jaccard=0.0, alive=False)
    only_t1 = {"a": 0, "b": 0, "c": 0, "d": 0}
    assert ts.match_reference_topics(REFERENCE, only_t1)["t2"] == ts.TopicMatch(None, 0.0, False)


def test_matched_cluster_is_never_shared_by_two_reference_topics() -> None:
    # 1 cụm ôm cả 2 topic: J của mỗi topic = 4/8 = 0.5 → không topic nào sống
    replicate = {u: 0 for u in "abcdefgh"}
    matches = ts.match_reference_topics(REFERENCE, replicate)
    assert not matches["t1"].alive and not matches["t2"].alive


ALIVE = ts.TopicMatch(cluster=0, jaccard=0.8, alive=True)
DEAD = ts.TopicMatch(cluster=0, jaccard=0.5, alive=False)


@pytest.mark.parametrize(
    ("match", "p_holm", "delta", "insufficient", "higher", "lower"),
    [
        (ALIVE, 0.01, 0.5, False, True, False),
        (ALIVE, 0.01, -0.5, False, False, True),
        (DEAD, 0.01, 0.5, False, False, False),  # topic không còn sống
        (ALIVE, 0.01, 0.5, True, False, False),  # cờ mẫu nhỏ
        (ALIVE, 0.05, 0.5, False, False, False),  # p Holm = alpha
        (ALIVE, None, 0.5, False, False, False),  # p không xác định
        (ALIVE, 0.01, None, False, False, False),  # không có δ
        (ALIVE, 0.01, 0.0, False, False, False),  # δ = 0: không giữ hướng nào (verdict nói "lower")
    ],
)
def test_held_requires_alive_verdict_and_strict_sign(
    match: ts.TopicMatch,
    p_holm: float | None,
    delta: float | None,
    insufficient: bool,
    higher: bool,
    lower: bool,
) -> None:
    assert ts.held("higher", match, p_holm, delta, insufficient) is higher
    assert ts.held("lower", match, p_holm, delta, insufficient) is lower


def test_rule_needs_the_reference_verdict_and_75_of_100_in_that_direction() -> None:
    assert ts.passes_rule("higher", "higher", 75, 100)
    assert not ts.passes_rule("higher", "higher", 74, 100)
    assert ts.passes_rule("lower", "lower", 100, 100)
    assert not ts.passes_rule("lower", "higher", 100, 100)  # hướng khác verdict tham chiếu
    assert not ts.passes_rule("not distinguishable", "higher", 100, 100)
    assert not ts.passes_rule("too few posts", "lower", 100, 100)
    assert ts.passes_at("higher", "higher", 60, 100, 60)
    assert not ts.passes_at("higher", "higher", 89, 100, 90)


@pytest.mark.parametrize(("k", "n"), [(0, 10), (10, 10), (75, 100), (3, 100), (50, 100)])
def test_wilson_interval_matches_scipy(k: int, n: int) -> None:
    low, high = ts.wilson_interval(k, n)
    expected = binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
    # scipy dùng z = 1.95996…, ở đây z = 1.96 (pre-registration) → lệch < 1e-4
    assert low == pytest.approx(expected.low, abs=1e-4)
    assert high == pytest.approx(expected.high, abs=1e-4)


def test_wilson_interval_known_values_and_empty_total() -> None:
    assert ts.wilson_interval(0, 10)[1] == pytest.approx(0.2775, abs=1e-4)
    low, high = ts.wilson_interval(75, 100)
    assert low < 0.75 < high
    assert ts.wilson_interval(0, 0) == (0.0, 1.0)


def test_core_is_the_largest_component_of_pairs_clustered_together_often() -> None:
    replicates = [
        {"a": 0, "b": 0, "c": 0, "d": 1},
        {"a": 0, "b": 0, "c": 1, "d": -1},
        {"a": 2, "b": 2, "c": 2},  # d vắng mặt: không vào mẫu số của cặp có d
        {"a": 0, "b": 0, "c": -1, "d": -1},  # cùng unclustered KHÔNG tính là cùng cụm
    ]
    # a–b 4/4, a–c và b–c 2/4, mọi cặp có d 0/3
    assert ts.co_cluster_core(["a", "b", "c", "d"], replicates) == ["a", "b"]
    assert ts.co_cluster_core(["a", "b", "c", "d"], replicates, threshold=0.5) == ["a", "b", "c"]
    assert ts.co_cluster_core(["c", "d"], replicates) == []


def test_core_ties_break_on_the_smallest_id() -> None:
    replicates = [{"a": 0, "b": 0, "c": 1, "d": 1}]
    assert ts.co_cluster_core(["d", "c", "b", "a"], replicates) == ["a", "b"]
