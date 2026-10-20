"""Lịch sử "đạt ở k trong m cách chia" của mỗi topic × chỉ số (ADR-0024 quyết định 3) — hàm thuần,
API gọi khi đọc từ kết quả đã lưu (`cluster_runs.labels_json` + `topic_comparisons`), không thêm
bảng, không sửa job (Thy chốt 2026-10-20).

Định nghĩa (Thy chốt 2026-10-20, số thật lúc chốt ở `docs/claude/data-model.md`):
- **Cách chia** = chuỗi lần gom cụm liên tiếp có nhãn của MỌI unit giống hệt lần trước (cùng tập
  unit, cùng nhãn). Không dùng `ari_vs_previous` = 1: ARI chỉ tính trên unit chung, lần có thêm
  bài vẫn ra 1 (ADR-0024 bằng chứng 1).
- **Đại diện của 1 cách chia** = lần so sánh MỚI NHẤT trong cách chia đó (số views đầy đủ nhất).
  Mỗi cách chia đếm đúng 1 lần — các ngày chạy lại trên cùng cách chia là cùng 1 bằng chứng; lấy
  "đạt ở bất kỳ ngày nào" sẽ thổi phồng (nhìn nhiều lần → dễ gặp 1 lần đạt do may).
- **m** = số cách chia mà topic **kiểm định được**: có p Holm và đủ bài (`insufficient_data` = 0,
  ≥ `MIN_N_PER_BUCKET` bài đo được mỗi phía). Cách chia thiếu bài không có kết luận nên không tính
  là "không đạt" — đếm riêng ở `too_few_posts` để UI ghi rõ.
- **k** tách theo hướng: `higher` (p Holm < ngưỡng, δ > 0) và `lower` (δ < 0) — đạt theo hướng
  ngược lại không cộng vào lịch sử của hướng kia.
- Ghép topic qua các cách chia bằng id bền `topic_N` (ADR-0018). Topic gộp/tách nhận id mới nên
  lịch sử bắt đầu lại; cùng 1 id vẫn có thể ứng với số bài khác nhau nhiều giữa các cách chia.
- Mọi số đếm chỉ trên cách chia **có kết quả so sánh đã lưu** — bước so sánh lỗi suốt 1 cách chia
  thì cách chia đó không có mặt; UI nói "tested on N clusterings", không nói "clustered N ways".
- "Cùng cách chia" so nhãn thô: cùng cách chia mà HDBSCAN đánh số cụm khác (hoán vị) sẽ thành cách
  chia mới — không xảy ra với seed cố định + dữ liệu y hệt; xem lại nếu đổi engine gom cụm.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from src.analysis.topic_comparison import Metric


class LabelledRun(Protocol):
    """1 lần gom cụm: id tăng dần theo thời gian + nhãn của từng unit (-1 = nhiễu)."""

    @property
    def id(self) -> int: ...

    @property
    def labels(self) -> Mapping[str, int]: ...


def distinct_partitions[R: LabelledRun](runs: Iterable[R]) -> list[list[R]]:
    """Gom các lần gom cụm liên tiếp có nhãn giống hệt lần trước (cùng tập unit, cùng nhãn).
    Quay lại đúng nhãn của 1 cách chia cũ sau 1 cách chia khác vẫn là cách chia mới ("khác lần
    trước", ADR-0024)."""
    groups: list[list[R]] = []
    for run in sorted(runs, key=lambda r: r.id):
        if groups and run.labels == groups[-1][-1].labels:
            groups[-1].append(run)
        else:
            groups.append([run])
    return groups


@dataclass(frozen=True)
class RunLabels:
    id: int
    labels: Mapping[str, int]


def partition_run_ids(runs: Iterable[tuple[int, Mapping[str, int]]]) -> list[list[int]]:
    """Như `distinct_partitions` trên cặp (id, nhãn) — trả id lần gom cụm theo cách chia."""
    groups = distinct_partitions(RunLabels(run_id, labels) for run_id, labels in runs)
    return [[run.id for run in group] for group in groups]


@dataclass(frozen=True)
class StoredComparison:
    """1 dòng `topic_comparisons` loại topic đã kiểm định (`tested` = 1) + mốc lần gom cụm."""

    cluster_run_id: int
    run_at: str
    group_id: str
    metric: Metric
    effect_size: float | None
    p_value_holm: float | None
    insufficient_data: bool


@dataclass(frozen=True)
class PartitionHistory:
    # m — số cách chia kiểm định được
    clusterings: int
    # k theo hướng
    higher: int
    lower: int
    # cách chia có topic nhưng thiếu bài — không tính vào m. Gồm cả ca hiếm p không xác định dù đủ
    # bài (mọi giá trị bằng nhau → p NaN → p Holm None): chấp nhận gộp, UI gọi chung "too few"
    too_few_posts: int
    # `run_at` của lần so sánh ĐẠI DIỆN (mới nhất) của cách chia đầu tiên có topic này — không phải
    # lần gom cụm đầu tiên topic xuất hiện (cách chia đó có thể đã bắt đầu vài ngày trước)
    since: str


def display_direction(
    history: PartitionHistory, current_effect: float | None
) -> Literal["higher", "lower"] | None:
    """Hướng của số k hiển thị (k không trộn 2 hướng). Chưa đạt lần nào → None (k = 0 không có
    hướng — gắn "below" là nói quá dữ liệu). Chỉ 1 hướng từng đạt → hướng đó, bất kể δ hiện tại.
    Đạt cả 2 hướng → dấu δ hiện tại; δ không có (ẩn vì `stale`) hoặc = 0 → hướng nhiều lần hơn,
    hoà → higher (lựa chọn hiển thị; UI luôn ghi hướng bằng mũi tên nên không ngầm hiểu)."""
    if history.higher == 0 and history.lower == 0:
        return None
    if history.lower == 0:
        return "higher"
    if history.higher == 0:
        return "lower"
    if current_effect is not None and current_effect != 0:
        return "higher" if current_effect > 0 else "lower"
    return "lower" if history.lower > history.higher else "higher"


def representatives(
    partitions: Sequence[Sequence[int]], compared_run_ids: Container[int]
) -> list[int]:
    """Lần so sánh đại diện của mỗi cách chia (cũ → mới) = lần gom cụm mới nhất trong cách chia có
    kết quả so sánh. Cách chia không có lần nào (trước khi có bước so sánh, hoặc bước so sánh lỗi
    suốt cách chia đó) bị bỏ."""
    result: list[int] = []
    for run_ids in partitions:
        compared = [run_id for run_id in run_ids if run_id in compared_run_ids]
        if compared:
            result.append(max(compared))
    return result


def partition_history(
    partitions: Sequence[Sequence[int]],
    comparisons: Iterable[StoredComparison],
    *,
    alpha: float,
) -> dict[tuple[str, Metric], PartitionHistory]:
    """`partitions` = id lần gom cụm theo cách chia (đầu ra `partition_run_ids`, cũ → mới).
    Trả lịch sử cho mọi (topic, chỉ số) xuất hiện ở ít nhất 1 lần so sánh đại diện."""
    by_run: dict[int, list[StoredComparison]] = {}
    for row in comparisons:
        by_run.setdefault(row.cluster_run_id, []).append(row)

    counts: dict[tuple[str, Metric], list[int]] = {}  # [m, higher, lower, too_few]
    since: dict[tuple[str, Metric], str] = {}
    for run_id in representatives(partitions, by_run):
        for row in by_run[run_id]:
            key = (row.group_id, row.metric)
            tally = counts.setdefault(key, [0, 0, 0, 0])
            since.setdefault(key, row.run_at)
            if row.insufficient_data or row.p_value_holm is None or row.effect_size is None:
                tally[3] += 1
                continue
            tally[0] += 1
            if row.p_value_holm < alpha and row.effect_size > 0:
                tally[1] += 1
            elif row.p_value_holm < alpha and row.effect_size < 0:
                tally[2] += 1
    return {
        key: PartitionHistory(
            clusterings=m, higher=higher, lower=lower, too_few_posts=too_few, since=since[key]
        )
        for key, (m, higher, lower, too_few) in counts.items()
    }
