"""So sánh từng topic với phần còn lại của kênh (ADR-0023) — hàm thuần, job NLP gọi sau bước import
(`src/pipeline/compare_topics.py`), API chỉ đọc kết quả đã lưu.

Phương pháp (ADR-0023, không lặp lại lập luận ở đây):
- Đơn vị = content unit trong lần gom cụm (unit có chữ lúc export); bài views = 0 bị loại khỏi mọi
  phân phối và được đếm riêng (ADR-0011, `split_measurable`).
- Mỗi topic so với **phần còn lại gồm bài nhiễu** (mọi unit khác trong lần gom cụm) bằng
  `compare_groups()` — Brunner-Munzel hoán vị + Cliff's delta + CI 95% của delta (chưa hiệu chỉnh).
- **Họ Holm = mọi phép so có p xác định** (không None/NaN), kể cả topic n < `MIN_N_PER_BUCKET`:
  hiện là số topic × 3 chỉ số. Kích thước họ đi kèm kết quả để UI không tự nhân.
- Dòng nhiễu và dòng kênh chỉ mô tả (`tested = False`) — không kiểm định.
- Số mô tả (median, IQR, n) và số kiểm định của 1 dòng tính từ CÙNG 1 tập giá trị, trong cùng 1
  lần chạy. (Landing ghép median/chấm của dữ liệu mới nhất với δ/p của lần chạy này và ghi rõ 2
  mốc giờ — chữ Thy duyệt 2026-10-09; trang Topics dùng thẳng dòng này.)
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from src.analysis.conversation import conversation_rate
from src.analysis.share_rate import share_rate
from src.analysis.significance import (
    DEFAULT_N_PERMUTATIONS,
    TestMethod,
    compare_groups,
    holm_adjust,
)
from src.analysis.stats import DistributionStats, distribution_stats
from src.api.models import PostInsights

Metric = Literal["engagement", "share_rate", "conversation"]
GroupKind = Literal["topic", "noise", "channel"]

# 3 chỉ số của trang Topics (ADR-0023 1c) — thứ tự = thứ tự hiển thị
METRICS: dict[Metric, Callable[[PostInsights], float]] = {
    "engagement": lambda item: item.engagement_rate,
    "share_rate": share_rate,
    "conversation": conversation_rate,
}
# Chỉ được khẳng định khi p Holm < ngưỡng này (ADR-0023 1c)
CONCLUSION_ALPHA = 0.05
NOISE_GROUP = "noise"
CHANNEL_GROUP = "channel"
# Seed cố định: p hoán vị có sai số Monte Carlo — cùng dữ liệu phải ra cùng số ở mọi nơi trình
# bày (ADR-0023). Trùng seed của `scripts/topic_method_report.py` để 2 nơi in cùng 1 con số.
COMPARISON_SEED = 0


@dataclass(frozen=True)
class UnitObservation:
    """1 content unit của lần gom cụm: topic của nó (None = nhiễu) và snapshot mới nhất (None =
    chưa có snapshot nào — không vào phân tích, không đếm là bị loại, như `split_measurable`)."""

    unit_id: str
    topic_id: str | None
    insights: PostInsights | None


@dataclass(frozen=True)
class GroupComparison:
    """1 dòng: 1 nhóm (topic / nhiễu / kênh) × 1 chỉ số.

    `group` mô tả chính nhóm; `rest` mô tả phần còn lại của kênh (chỉ dòng topic). Các trường kiểm
    định None khi `tested = False` hoặc khi 1 nhóm rỗng; `p_value_holm` None khi p không xác định
    (không vào họ Holm). `effect_size` > 0 = bài của topic có xu hướng cao hơn phần còn lại.
    """

    group_id: str
    kind: GroupKind
    metric: Metric
    group: DistributionStats
    group_excluded_no_views: int
    rest: DistributionStats | None
    rest_excluded_no_views: int | None
    tested: bool
    effect_size: float | None
    effect_size_ci_low: float | None
    effect_size_ci_high: float | None
    p_value: float | None
    p_value_holm: float | None
    p_value_mann_whitney: float | None
    test_method: TestMethod | None
    insufficient_data: bool


@dataclass(frozen=True)
class TopicComparisonSet:
    rows: list[GroupComparison]
    holm_family_size: int
    n_permutations: int
    random_seed: int


def _measurable(units: Sequence[UnitObservation]) -> tuple[list[PostInsights], int]:
    """(insights đo được, số bài views = 0) — cùng quy tắc `split_measurable` (ADR-0011)."""
    with_snapshot = [unit.insights for unit in units if unit.insights is not None]
    measurable = [item for item in with_snapshot if item.views > 0]
    return measurable, len(with_snapshot) - len(measurable)


def _descriptive(
    group_id: str, kind: GroupKind, metric: Metric, units: Sequence[UnitObservation]
) -> GroupComparison:
    measurable, excluded = _measurable(units)
    stats = distribution_stats([METRICS[metric](item) for item in measurable])
    return GroupComparison(
        group_id=group_id,
        kind=kind,
        metric=metric,
        group=stats,
        group_excluded_no_views=excluded,
        rest=None,
        rest_excluded_no_views=None,
        tested=False,
        effect_size=None,
        effect_size_ci_low=None,
        effect_size_ci_high=None,
        p_value=None,
        p_value_holm=None,
        p_value_mann_whitney=None,
        test_method=None,
        insufficient_data=stats.insufficient_data,
    )


def compare_topics(
    units: Sequence[UnitObservation],
    *,
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    random_seed: int = COMPARISON_SEED,
) -> TopicComparisonSet:
    """Mọi topic × 3 chỉ số so với phần còn lại, cộng dòng nhiễu và dòng kênh (mô tả); p Holm
    trên họ = mọi phép so có p xác định. Thứ tự dòng: theo chỉ số, trong mỗi chỉ số theo topic_id
    rồi nhiễu rồi kênh."""
    topic_ids = sorted({unit.topic_id for unit in units if unit.topic_id is not None})
    noise = [unit for unit in units if unit.topic_id is None]
    rows: list[GroupComparison] = []
    for metric, value_of in METRICS.items():
        for topic_id in topic_ids:
            members = [unit for unit in units if unit.topic_id == topic_id]
            rest_units = [unit for unit in units if unit.topic_id != topic_id]
            topic_measurable, topic_excluded = _measurable(members)
            rest_measurable, rest_excluded = _measurable(rest_units)
            topic_values = [value_of(item) for item in topic_measurable]
            rest_values = [value_of(item) for item in rest_measurable]
            result = compare_groups(
                topic_values,
                rest_values,
                n_permutations=n_permutations,
                random_seed=random_seed,
            )
            rows.append(
                GroupComparison(
                    group_id=topic_id,
                    kind="topic",
                    metric=metric,
                    group=distribution_stats(topic_values),
                    group_excluded_no_views=topic_excluded,
                    rest=distribution_stats(rest_values),
                    rest_excluded_no_views=rest_excluded,
                    tested=True,
                    effect_size=result.effect_size,
                    effect_size_ci_low=result.effect_size_ci_low,
                    effect_size_ci_high=result.effect_size_ci_high,
                    p_value=result.p_value,
                    p_value_holm=None,  # điền sau khi đủ họ
                    p_value_mann_whitney=result.p_value_mann_whitney,
                    test_method=result.test_method,
                    insufficient_data=result.insufficient_data,
                )
            )
        rows.append(_descriptive(NOISE_GROUP, "noise", metric, noise))
        rows.append(_descriptive(CHANNEL_GROUP, "channel", metric, units))

    # Họ Holm: mọi phép so có p xác định — p None (nhóm rỗng) hoặc NaN (nhánh dự phòng Mann-Whitney:
    # đầu vào NaN, hoặc mọi giá trị bằng nhau) không phải 1 phép so thực hiện được, nên ngoài họ
    family = {
        index: row.p_value
        for index, row in enumerate(rows)
        if row.tested and row.p_value is not None and not math.isnan(row.p_value)
    }
    adjusted = dict(zip(family, holm_adjust(list(family.values())), strict=True))
    rows = [
        replace(row, p_value_holm=adjusted[index]) if index in adjusted else row
        for index, row in enumerate(rows)
    ]
    return TopicComparisonSet(
        rows=rows,
        holm_family_size=len(family),
        n_permutations=n_permutations,
        random_seed=random_seed,
    )
