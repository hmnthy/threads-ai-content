"""Luật bền cho kết luận về topic (ADR-0036) — hằng số + hàm thuần, dùng chung cho thí nghiệm RQ-01
(`scripts/rq01_seed_stability.py`) và, sau ADR áp luật vào sản phẩm, cho job / API.

Định nghĩa đầy đủ, ca biên và nguồn: `docs/rq/RQ-01-seed-stability.md` (pre-registration). Tóm tắt:
- Lần b (b = 1…K) đổi seed UMAP (= b), đảo thứ tự bài theo `numpy.random.default_rng(b)` và, ở
  nhánh chính P, bỏ ⌈3% · N⌉ bài cuối của hoán vị.
- Topic tham chiếu t "còn sống" ở lần b khi Jaccard lớn nhất với một cụm của lần b > 0.5.
- Kết luận (t, m) **giữ ở lần b theo hướng** khi t còn sống, và dòng của cụm khớp có verdict cùng
  hướng theo `comparison_verdict` (p Holm < `CONCLUSION_ALPHA`, không cờ mẫu nhỏ) với δ cùng dấu
  nghiêm ngặt. Mọi ca thiếu tính là không giữ; mẫu số luôn là K.
- Luật: verdict tham chiếu `higher` / `lower` **và** giữ đúng hướng ở ≥ 75 / 100 lần của nhánh P.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

import numpy as np

from src.analysis.topic_comparison import CONCLUSION_ALPHA

# --- Hằng số chốt TRƯỚC khi chạy (ADR-0036, Thy chốt 2026-11-04) — ADR sau RQ-01 không chọn lại ---
# K: số lần gom cụm lại mỗi nhánh. Nguồn: tài liệu `fpc::clusterboot` "B=100 is recommended"; sai
# số chuẩn Monte Carlo của một tỉ lệ ≤ √(0.25/100) = 0.05
STABILITY_REPLICATES = 100
# Ngưỡng giữ, tính bằng phần trăm số nguyên (so sánh số nguyên, không so số thực): ≥ 75 / 100.
# Quy ước thiết kế (stability selection π_thr ∈ (0.6, 0.9); mốc "bền" 0.75 của `fpc`), không suy ra
# từ dữ liệu này
KEEP_PERCENT = 75
# Mức bỏ bài của nhánh P, phần trăm số nguyên: d = ⌈3 · N / 100⌉. Lựa chọn thiết kế: ≈ mức đổi lớn
# nhất giữa 2 cách chia thật liên tiếp (1–5 bài, ADR-0024 bằng chứng 1)
DROP_PERCENT = 3
# Mốc ghép cụm: còn sống khi J > 0.5 — `dissolution = 0.5` của `fpc::clusterboot` (quy ước phần mềm)
MATCH_JACCARD = 0.5
# Bảng độ nhạy CHỈ để báo cáo (ADR-0036 quyết định 3) — không bao giờ dùng để đổi luật
SENSITIVITY_PERCENTS = (60, 90)

# --- Hằng số báo cáo, không thuộc luật ---
# CI 95% Wilson, không hiệu chỉnh liên tục (pre-registration mục "Kết luận ở một lần xáo trộn")
WILSON_Z = 1.96
# Phân tích lõi thăm dò: nối 2 bài khi tỉ lệ đồng cụm ≥ 0.75 — lựa chọn thiết kế, dùng lại mốc của
# luật, chỉ để thăm dò (pre-registration mục "Phân tích thăm dò")
CORE_CO_CLUSTER = 0.75

Arm = Literal["P", "S"]
ARMS: tuple[Arm, ...] = ("P", "S")
Direction = Literal["higher", "lower"]
DIRECTIONS: tuple[Direction, ...] = ("higher", "lower")
Verdict = Literal["higher", "lower", "not distinguishable", "too few posts", "not tested"]
NOISE = -1


def comparison_verdict(
    p_value_holm: float | None,
    effect_size: float | None,
    insufficient_data: bool,
    *,
    alpha: float = CONCLUSION_ALPHA,
) -> Verdict:
    """Bản Python của `testVerdict()` (`src/dashboard/src/lib/landing.ts`) — cùng thứ tự nhánh,
    test đối chiếu từng ca bằng cách chạy chính hàm TS (`tests/analysis/test_topic_stability.py`).

    Giữ nguyên ca δ = 0 với p Holm < alpha → "lower" như bản TS (ca không xảy ra được: δ = 0 kéo
    theo thống kê Brunner-Munzel bằng 0). Điều kiện "cùng dấu nghiêm ngặt" của luật nằm ở `held()`,
    không ở đây, để hàm này luôn trùng với cái trang đang hiện."""
    if p_value_holm is None or effect_size is None:
        return "not tested"
    if insufficient_data:
        return "too few posts"
    if p_value_holm >= alpha:
        return "not distinguishable"
    return "higher" if effect_size > 0 else "lower"


def n_dropped(n_units: int) -> int:
    """d = ⌈DROP_PERCENT · N / 100⌉ bằng số nguyên (tránh 0.03 · 100 = 3.0000000000000004)."""
    return -(-DROP_PERCENT * n_units // 100)


def replicate_positions(n_units: int, b: int, arm: Arm) -> list[int]:
    """Vị trí (trong thứ tự tham chiếu) của các unit đưa vào lần b, theo đúng thứ tự đưa vào.
    `perm = default_rng(b).permutation(N)`; nhánh S giữ đủ, nhánh P bỏ d phần tử CUỐI của `perm`
    và giữ nguyên thứ tự phần còn lại — lần b của 2 nhánh chỉ khác nhau ở d bài đó."""
    perm = [int(x) for x in np.random.default_rng(b).permutation(n_units)]
    if arm == "S":
        return perm
    return perm[: n_units - n_dropped(n_units)]


@dataclass(frozen=True)
class TopicMatch:
    """Cụm của lần b khớp topic tham chiếu: `cluster` None khi không có cụm nào, hoặc topic không
    còn bài nào có mặt (khi đó `jaccard` = 0). `alive` = J > MATCH_JACCARD."""

    cluster: int | None
    jaccard: float
    alive: bool


def match_reference_topics(
    reference: Mapping[str, Collection[str]], replicate: Mapping[str, int]
) -> dict[str, TopicMatch]:
    """Ghép mỗi topic tham chiếu với cụm có Jaccard lớn nhất ở lần b.

    `reference`: topic → unit thuộc topic ở lần tham chiếu. `replicate`: unit CÓ MẶT ở lần b →
    nhãn (`NOISE` = unclustered, không phải một cụm). J(t, c) = |t ∩ c| ÷ |(t ∩ S_b) ∪ c|.
    J > 0.5 kéo theo cụm khớp là duy nhất (không cần luật phá hoà); hoà ở J ≤ 0.5 lấy nhãn nhỏ
    nhất — chỉ ảnh hưởng `cluster` của topic đã không còn sống."""
    clusters: dict[int, set[str]] = {}
    for unit, label in replicate.items():
        if label != NOISE:
            clusters.setdefault(label, set()).add(unit)
    result: dict[str, TopicMatch] = {}
    for topic, members in reference.items():
        present = {u for u in members if u in replicate}
        best_label: int | None = None
        best = 0.0
        if present:
            for label in sorted(clusters):
                cluster = clusters[label]
                score = len(present & cluster) / len(present | cluster)
                if score > best:
                    best_label, best = label, score
        result[topic] = TopicMatch(cluster=best_label, jaccard=best, alive=best > MATCH_JACCARD)
    return result


def held(
    direction: Direction,
    match: TopicMatch,
    p_value_holm: float | None,
    effect_size: float | None,
    insufficient_data: bool,
) -> bool:
    """Kết luận giữ ở lần b theo `direction`: topic còn sống, verdict của dòng cụm khớp cùng hướng
    (`comparison_verdict`) và δ cùng dấu NGHIÊM NGẶT (δ = 0 không giữ hướng nào). Các trường kiểm
    định là của dòng cụm khớp; khi topic không còn sống chúng không được xét."""
    if not match.alive or effect_size is None:
        return False
    if comparison_verdict(p_value_holm, effect_size, insufficient_data) != direction:
        return False
    return effect_size > 0 if direction == "higher" else effect_size < 0


def passes_rule(reference_verdict: Verdict, direction: Direction, kept: int, total: int) -> bool:
    """Luật ADR-0036: verdict tham chiếu đúng `direction` và giữ hướng đó ở ≥ KEEP_PERCENT % của
    `total` lần (nhánh P, total = STABILITY_REPLICATES). So số nguyên: kept · 100 ≥ 75 · total."""
    return passes_at(reference_verdict, direction, kept, total, KEEP_PERCENT)


def passes_at(
    reference_verdict: Verdict, direction: Direction, kept: int, total: int, percent: int
) -> bool:
    """Như `passes_rule` ở một ngưỡng khác — chỉ cho bảng độ nhạy (`SENSITIVITY_PERCENTS`)."""
    return reference_verdict == direction and kept * 100 >= percent * total


def wilson_interval(successes: int, total: int, z: float = WILSON_Z) -> tuple[float, float]:
    """CI Wilson (không hiệu chỉnh liên tục) cho tỉ lệ successes / total; total = 0 → (0, 1)."""
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, centre - half), min(1.0, centre + half)


def co_cluster_core(
    members: Sequence[str],
    replicates: Sequence[Mapping[str, int]],
    threshold: float = CORE_CO_CLUSTER,
) -> list[str]:
    """Lõi thăm dò của một topic tham chiếu (pre-registration "Phân tích thăm dò").

    Tỉ lệ đồng cụm của cặp bài = số lần cả hai cùng một cụm (không tính unclustered) ÷ số lần cả
    hai cùng có mặt. Lõi = thành phần liên thông lớn nhất của đồ thị nối các cặp có tỉ lệ
    ≥ `threshold`; cặp chưa từng cùng có mặt không có cạnh. Không có cạnh nào → lõi rỗng. Hoà kích
    thước → thành phần có id nhỏ nhất (theo thứ tự chuỗi) — chỉ để kết quả tái lập được."""
    units = sorted(set(members))
    neighbours: dict[str, set[str]] = {u: set() for u in units}
    for a, b in combinations(units, 2):
        both = together = 0
        for labels in replicates:
            if a in labels and b in labels:
                both += 1
                together += labels[a] != NOISE and labels[a] == labels[b]
        if both and together / both >= threshold:
            neighbours[a].add(b)
            neighbours[b].add(a)
    seen: set[str] = set()
    best: list[str] = []
    for start in units:
        if start in seen or not neighbours[start]:
            continue
        component, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(neighbours[node] - component)
        seen |= component
        if len(component) > len(best):
            best = sorted(component)
    return best
