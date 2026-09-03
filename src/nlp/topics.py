"""Unsupervised topic discovery — UMAP (giảm chiều → 3D) rồi HDBSCAN (cluster
TRÊN toạ độ UMAP đó, không phải embedding gốc) + Claude (Bước labeling cluster
thành tên/mô tả TIẾNG ANH). Đã verify thật trên 135 content unit thật (post rỗng
`REPOST_FACADE` đã loại ở bước export trước đó) — không còn DRAFT. Chi tiết đầy
đủ + số liệu thực nghiệm tại docs/claude/data-model.md "Methodology log:
clustering space cho HDBSCAN" và decision log tại docs/claude/architecture.md
(2026-09-02).

QUAN TRỌNG (2026-09-02) — môi trường chạy: `cluster_embeddings()` (`hdbscan`/
`umap-learn`, phụ thuộc `scipy.linalg` ở tầng import) bị Smart App Control chặn
trên Windows — verify thật trong WSL2 Ubuntu (`~/threads-clustering-env`) thành
công, không bị chặn (Linux không nằm trong phạm vi Smart App Control). Gọi hàm
này từ `src/pipeline/cluster_wsl.py`, chạy bằng Python trong WSL, KHÔNG chạy
trên `.venv` Windows. `label_cluster_with_claude()` (chỉ cần `anthropic`, không
đụng scipy) vẫn chạy trên Windows bình thường.

Tham số HDBSCAN/UMAP đã calibrate bằng sweep 24 tổ hợp + review nội dung thật
từng cluster (2026-09-03) — xem docs/claude/data-model.md "Methodology log:
hiệu chỉnh tham số HDBSCAN cho số lượng topic" cho đầy đủ bằng chứng 3 ứng viên
đã so sánh (7/8/12 cluster) và lý do chọn 8 cluster (DBCV cao nhất + nội dung
mạch lạc nhất, không chỉ dựa trên số lượng khớp kỳ vọng domain).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from anthropic import Anthropic

if TYPE_CHECKING:
    import numpy as np

# Đã calibrate bằng sweep 24 tổ hợp + review nội dung thật từng cluster (2026-09-03)
# — chốt ứng viên "B" (8 cluster, DBCV=0.205 cao nhất trong 3 ứng viên so sánh, nội
# dung mạch lạc nhất). Chi tiết đầy đủ: docs/claude/data-model.md "Methodology log:
# hiệu chỉnh tham số HDBSCAN cho số lượng topic".
HDBSCAN_MIN_CLUSTER_SIZE = 4
UMAP_N_COMPONENTS = 3
UMAP_RANDOM_STATE = 42
UMAP_N_NEIGHBORS = 10
CLUSTER_SELECTION_METHOD = "leaf"  # 'eom' (mặc định hdbscan) luôn hội tụ về 2-3 cluster
# lớn trên dataset này — 'leaf' mới cho granularity khớp domain, xem methodology log.

# Chốt 2026-09-03 (xem docs/claude/architecture.md decision log): giữ claude-opus-5,
# cập nhật lại bảng Tech Stack cho khớp thay vì đổi model.
CLUSTER_LABELING_MODEL = "claude-opus-5"


@dataclass(frozen=True)
class ClusterResult:
    labels: np.ndarray  # -1 = noise (HDBSCAN), theo thứ tự input embeddings
    umap_coords: np.ndarray  # shape (n, 3) — dùng để visualize VÀ làm input cho HDBSCAN


def cluster_embeddings(embeddings: np.ndarray) -> ClusterResult:
    """UMAP giảm chiều trước, HDBSCAN cluster TRÊN toạ độ UMAP đó — KHÔNG phải
    trên embedding gốc 1024D.

    Quyết định đảo ngược thiết kế ban đầu (từng cluster trên embedding gốc với lý
    do "giữ đúng density thật, không bị méo bởi UMAP") sau thực nghiệm thật trên
    135 content unit (2026-09-02, xem docs/claude/data-model.md "Methodology log"):
    cluster trên embedding gốc 1024D suy biến nặng (curse of dimensionality — 1
    cluster chiếm 82% dữ liệu ban đầu; sau khi loại nhiễu vẫn không ổn định, noise
    tăng 13%→59%). Cluster trên UMAP coords cho kết quả cân đối và ổn định hơn hẳn
    (noise 9%→3% khi loại cùng nhiễu). Bằng chứng thực nghiệm > lý thuyết ban đầu.
    """
    import hdbscan
    import umap

    reducer = umap.UMAP(
        n_components=UMAP_N_COMPONENTS,
        n_neighbors=min(UMAP_N_NEIGHBORS, max(len(embeddings) - 1, 2)),
        random_state=UMAP_RANDOM_STATE,
    )
    coords = reducer.fit_transform(embeddings)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=HDBSCAN_MIN_CLUSTER_SIZE,
        cluster_selection_method=CLUSTER_SELECTION_METHOD,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(coords)

    return ClusterResult(labels=labels, umap_coords=coords)


@dataclass(frozen=True)
class TopicLabelResult:
    label_en: str
    description_en: str


def label_cluster_with_claude(
    sample_texts: list[str], client: Anthropic | None = None
) -> TopicLabelResult:
    """Tóm tắt 1 cluster thành tên + mô tả TIẾNG ANH bằng Claude — LLM CHỈ dùng ở
    bước labeling (đã có cấu trúc thật từ HDBSCAN), KHÔNG dùng để classify trực
    tiếp (xem data-model.md "Vì sao LLM chỉ dùng ở bước labeling cluster")."""
    anthropic_client = client or Anthropic()
    joined = "\n---\n".join(sample_texts[:15])
    prompt = (
        "You are labeling a topic cluster discovered by unsupervised clustering "
        "(HDBSCAN) on Vietnamese/French/English mixed social media posts from a "
        "single Threads creator (a Vietnamese person living in France, posting "
        "about work, job hunting, alternance, and lifestyle). Below are sample "
        'posts from ONE cluster. Return a JSON object with exactly two keys: "label" '
        '(a short English topic name, 2-5 words) and "description" (one English '
        "sentence describing what this cluster is about). Only return the JSON "
        "object, nothing else — no markdown fences, no extra text.\n\n"
        f"Sample posts:\n{joined}"
    )
    response = anthropic_client.messages.create(
        model=CLUSTER_LABELING_MODEL,
        max_tokens=500,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    parsed = json.loads(_extract_json_object(text))
    return TopicLabelResult(label_en=parsed["label"], description_en=parsed["description"])


def _extract_json_object(text: str) -> str:
    """Claude được yêu cầu trả JSON thuần, nhưng phòng trường hợp lẫn markdown
    fence/text thừa — cắt từ '{' đầu tiên tới '}' cuối cùng."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in Claude response: {text!r}")
    return text[start : end + 1]
