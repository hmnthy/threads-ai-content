"""Danh tính cụm bền qua các lần gom cụm (ADR-0018).

HDBSCAN đánh số cụm lại mỗi lần chạy (`cluster_3` hôm nay ≠ `cluster_3` hôm sau), nên
"cụm có đổi không" phải trả lời bằng thành viên và nội dung, không bằng số thứ tự.

Quy tắc (Thy chốt 2026-10-04 sau thí nghiệm 10 seed — `scripts/topic_identity_eval.py`):

1. **Thành viên, đa số hai chiều** ("đa số" = > 1/2, theo định nghĩa — không tham số):
   - *con* của topic cũ P = cụm mới C có > 1/2 thành viên đến từ P (mẫu số: MỌI thành viên
     của C, kể cả bài mới);
   - *cha* của C = topic cũ P gửi > 1/2 thành viên vào C. Mẫu số chỉ gồm thành viên của P
     **đang nằm trong 1 cụm** ở lần này — bài rơi vào nhiễu HDBSCAN không tính là "rời đi"
     (nhiễu = "không thuộc cụm nào được chọn lần này", không phải "đổi chủ đề").
   - **giữ** (`kept`, via `membership`): C có đúng 1 cha P và C là con của P.
   - **nhập** (`merged`): ≥ 2 topic cũ gửi > 1/2 thành viên vào C → id + tên mới. Phép thử
     nhập TÍNH CẢ nhiễu ở mẫu số: phần sót của 1 topic đã tan vào nhiễu (VD 1/10 bài) không
     phải "nhập" (code-reviewer 2026-10-04: 20/63 ca nhập trên 10 seed là giả theo cách này).
   - **lõi giữ tên**: P tách ra nhiều con thì con nào nhận > 1/2 của P giữ danh tính (đã là
     `kept`); mảnh còn lại là `new` (ghi nguồn P). Chỉ khi KHÔNG con nào nhận > 1/2 của P mới
     là **tách** (`split`) → id + tên mới (MONIC/Greene/Palla đều cho danh tính gốc sống tiếp).
2. **Ngữ nghĩa** (`kept`, via `semantic`), cho cụm `new`/`split` (KHÔNG cho `merged` — cụm
   nuốt thêm chủ đề khác không được giữ tên cũ): giữ id của topic cũ chưa ai giữ có tâm
   embedding gần nhất, khi cosine > `semantic_reference` = cosine LỚN NHẤT giữa tâm 2 topic
   khác nhau của lần trước (ngưỡng suy từ data mỗi lần, như mốc chín tầng reach — không hằng số).
   Ghép tham lam theo cosine giảm dần, mỗi topic cũ trao id tối đa 1 lần.

Lý do có bước 2: trên 10 seed cùng data, 85–89% cụm bị quy tắc thành viên đổi tên có tâm
gần topic cũ hơn mọi cặp chủ đề khác nhau — HDBSCAN xáo thành viên mạnh hơn nội dung đổi.
Tiền lệ: BERTopic `merge_models` (cosine embedding topic), BERTilda (thành viên + ngữ nghĩa).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

Event = Literal["kept", "new", "split", "merged"]
Via = Literal["membership", "semantic"]
Vectors = Mapping[str, np.ndarray]  # {unit_id: embedding}
# Sự kiện của 1 lần chạy (`cluster_runs.topic_events_json`) mà topic giữ nguyên id VÀ tên
KEPT_EVENTS = frozenset({"kept", "kept_semantic"})


@dataclass(frozen=True)
class TopicMatch:
    cluster: int  # nhãn HDBSCAN của lần này
    event: Event
    topic_id: str | None  # id topic cũ được mang tiếp — chỉ khi event == "kept"
    sources: tuple[str, ...]  # topic cũ liên quan (cha khi nhập, P khi tách/mảnh/giữ)
    via: Via | None = None  # cách được giữ
    similarity: float | None = None  # cosine tâm, khi via == "semantic"


def _majority(part: int, whole: int) -> bool:
    return whole > 0 and 2 * part > whole  # > 1/2, tránh so float


def centroid(uids: Iterable[str], vectors: Vectors) -> np.ndarray | None:
    """Tâm đã chuẩn hoá L2 của các bài có embedding; None nếu không bài nào có."""
    rows = [vectors[u] / np.linalg.norm(vectors[u]) for u in uids if u in vectors]
    if not rows:
        return None
    c = np.mean(rows, axis=0)
    norm = float(np.linalg.norm(c))
    return c / norm if norm > 0 else None


def _groups(labels: Mapping[str, object], skip: object) -> dict[object, set[str]]:
    out: dict[object, set[str]] = defaultdict(set)
    for uid, label in labels.items():
        if label != skip:
            out[label].add(uid)
    return out


def semantic_reference(previous: Mapping[str, str], vectors: Vectors) -> float | None:
    """Cosine lớn nhất giữa tâm 2 topic KHÁC nhau của lần trước — 'giống hơn mức này' nghĩa là
    giống topic cũ hơn mọi cặp chủ đề khác nhau. None khi < 2 topic có embedding."""
    tops = [c for m in _groups(previous, None).values() if (c := centroid(m, vectors)) is not None]
    if len(tops) < 2:
        return None
    return max(float(a @ b) for i, a in enumerate(tops) for b in tops[i + 1 :])


def match_topics(
    previous: Mapping[str, str],
    current: Mapping[str, int],
    vectors: Vectors | None = None,
    reference: float | None = None,
    *,
    exclude_noise: bool = True,
    core_keeps: bool = True,
    semantic: bool = True,
    merge_counts_noise: bool = True,
    semantic_for_merged: bool = False,
) -> dict[int, TopicMatch]:
    """`previous`: {unit_id: topic_id} của topic đang lưu. `current`: {unit_id: nhãn HDBSCAN}
    (-1 = nhiễu). `vectors` + `reference` cho bước ngữ nghĩa (bỏ qua nếu thiếu).

    Các cờ chỉ để thí nghiệm (`scripts/topic_identity_eval.py`) tái lập bảng so sánh — mặc
    định là quy tắc đã chốt. `merge_counts_noise`: phép thử NHẬP dùng mẫu số có cả bài ở nhiễu
    (topic tan gần hết vào nhiễu, sót 1 bài vào cụm khác, không phải "nhập" — code-reviewer
    2026-10-04: 20/63 ca nhập trên 10 seed là giả theo cách này). Phép thử GIỮ vẫn bỏ nhiễu."""
    new_members: dict[int, set[str]] = defaultdict(set)
    for uid, label in current.items():
        if label != -1:
            new_members[label].add(uid)
    old_members: dict[str, set[str]] = defaultdict(set)
    for uid, topic in previous.items():
        if uid in current:  # thành viên không còn trong lần chạy này không tính
            old_members[topic].add(uid)
    clustered_now = {p: {u for u in pm if current[u] != -1} for p, pm in old_members.items()}
    keep_denominator = clustered_now if exclude_noise else old_members
    merge_denominator = old_members if merge_counts_noise else keep_denominator

    children: dict[str, list[int]] = defaultdict(list)  # cụm mới > 1/2 từ P
    keep_parents: dict[int, list[str]] = defaultdict(list)  # P gửi > 1/2 (phép thử giữ)
    merge_parents: dict[int, list[str]] = defaultdict(list)  # P gửi > 1/2 (phép thử nhập)
    for c, cm in new_members.items():
        for p, pm in old_members.items():
            if _majority(len(cm & pm), len(cm)):
                children[p].append(c)
            if _majority(len(cm & keep_denominator[p]), len(keep_denominator[p])):
                keep_parents[c].append(p)
            if _majority(len(cm & merge_denominator[p]), len(merge_denominator[p])):
                merge_parents[c].append(p)

    def keeps(c: int, p: str) -> bool:
        # C giữ P: C là con của P, P gửi đa số vào C, và không topic nào KHÁC nhập vào C
        return c in children[p] and p in keep_parents[c] and set(merge_parents[c]) <= {p}

    result: dict[int, TopicMatch] = {}
    for c in sorted(new_members):
        src = next((p for p, kids in children.items() if c in kids), None)  # ≤ 1 P
        if len(merge_parents[c]) >= 2:
            result[c] = TopicMatch(c, "merged", None, tuple(sorted(merge_parents[c])))
        elif src is not None and keeps(c, src) and (core_keeps or len(children[src]) < 2):
            result[c] = TopicMatch(c, "kept", src, (src,), "membership")
        elif (
            src is not None
            and len(children[src]) >= 2
            and not (core_keeps and any(keeps(k, src) for k in children[src]))
        ):
            result[c] = TopicMatch(c, "split", None, (src,))
        else:
            result[c] = TopicMatch(c, "new", None, (src,) if src is not None else ())

    if semantic and vectors is not None and reference is not None:
        taken = {m.topic_id for m in result.values() if m.topic_id is not None}
        rescuable: tuple[Event, ...] = ("new", "split")
        if semantic_for_merged:
            rescuable += ("merged",)
        else:
            # Topic đã NHẬP vào cụm khác không trao id cho cụm thứ ba (giữ đúng dòng danh tính)
            taken |= {p for m in result.values() if m.event == "merged" for p in m.sources}
        old_centroids = {
            str(p): oc
            for p, members in _groups(previous, None).items()
            if (oc := centroid(members, vectors)) is not None
        }
        candidates: list[tuple[float, int, str]] = []
        for c, m in result.items():
            if m.event in rescuable:
                cc = centroid(new_members[c], vectors)
                if cc is not None:
                    candidates += [(float(cc @ oc), c, str(p)) for p, oc in old_centroids.items()]
        for cos, c, p in sorted(candidates, reverse=True):
            if cos <= reference:
                break
            if result[c].event == "kept" or p in taken:
                continue
            result[c] = TopicMatch(c, "kept", p, (p,), "semantic", cos)
            taken.add(p)
    return result


def anchor_holds(
    cluster: set[str],
    anchor: set[str],
    current: Mapping[str, int],
    vectors: Vectors | None = None,
    reference: float | None = None,
) -> bool:
    """Cụm hiện tại còn là 'cùng nội dung' với lúc đặt tên (bản neo) không — cùng quy tắc như
    ghép: đa số hai chiều theo thành viên (bỏ bài neo đang ở nhiễu) HOẶC tâm gần bản neo hơn
    `reference`. False → đặt lại tên (`drift`): bắt trôi TÍCH LUỸ mà ghép từng lần không thấy."""
    anchor_now = {u for u in anchor if current.get(u, -1) != -1}
    overlap = len(cluster & anchor)
    if _majority(overlap, len(cluster)) and _majority(len(cluster & anchor_now), len(anchor_now)):
        return True
    if vectors is None or reference is None:
        return False
    a, c = centroid(anchor, vectors), centroid(cluster, vectors)
    return a is not None and c is not None and float(a @ c) > reference


def runs_keeping_label(events_by_run: Sequence[dict[str, str] | None], topic_id: str) -> int:
    """Số lần chạy LIÊN TIẾP gần nhất mà topic có sự kiện giữ tên (`KEPT_EVENTS`), đếm ngược từ lần
    mới nhất; dừng ở lần đặt/đổi tên gần nhất hoặc lần chưa ghi sự kiện (trước ADR-0018).
    Trang Topics hiện số này cạnh ngày đặt tên (ADR-0023 1e)."""
    count = 0
    for events in reversed(events_by_run):
        if events is None or events.get(topic_id) not in KEPT_EVENTS:
            break
        count += 1
    return count
