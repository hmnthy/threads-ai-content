"""Bước 2/3 của clustering pipeline — CHỈ chạy trong WSL2 Ubuntu, KHÔNG chạy trên
`.venv` Windows (xem docs/decisions/legacy-log.md, dòng 2026-09-02 — Smart
App Control chặn `scipy.linalg._flapack` không ổn định trên Windows, verify thật
cho thấy có lúc chạy được có lúc không; WSL2 không nằm trong phạm vi Smart App
Control nên ổn định).

Đọc `data/nlp_exchange/texts_export.json` (do `src/pipeline/clustering_export.py`
tạo trên Windows), gọi lại NGUYÊN VẸN `embed_texts()` (`src/nlp/embeddings.py`) và
`cluster_embeddings()` (`src/nlp/topics.py`) — KHÔNG viết lại logic, chỉ đổi môi
trường chạy — để tránh 2 bản logic lệch nhau giữa Windows/WSL. Cũng tách từ cho từ khoá
(`word_segments`, underthesea — ADR-0022) và ghi `keyword_segments`; venv WSL2
`~/threads-clustering-env` phải có `underthesea` (ngoài `uv.lock`).

Chạy trong WSL:
    wsl -d Ubuntu -- bash -c "cd /mnt/c/.../threads-ai-content/.claude/worktrees/<agent> \
        && source ~/threads-clustering-env/bin/activate && python3 -m src.pipeline.cluster_wsl"
"""

from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np

from src.nlp.embeddings import PRIMARY_MODEL_NAME, embed_texts
from src.nlp.topic_profile import word_segments
from src.nlp.topics import (
    CLUSTER_SELECTION_METHOD,
    HDBSCAN_MIN_CLUSTER_SIZE,
    UMAP_N_COMPONENTS,
    UMAP_N_NEIGHBORS,
    UMAP_RANDOM_STATE,
    cluster_embeddings,
)

TEXTS_EXPORT_PATH = Path("data/nlp_exchange/texts_export.json")
RESULTS_PATH = Path("data/nlp_exchange/cluster_results.json")


def run() -> dict[str, int | float | str]:
    export_digest = hashlib.sha256(TEXTS_EXPORT_PATH.read_bytes()).hexdigest()
    with TEXTS_EXPORT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    ids: list[str] = data["ids"]
    texts: list[str] = data["texts"]
    hashes: list[str] = data.get("hashes", [])
    cached: dict[str, list[float]] = data.get("cached_vectors", {})
    if data.get("cached_model_id") != PRIMARY_MODEL_NAME:
        cached = {}

    # ADR-0022: tách từ cho từ khoá ở đây (WSL2), không ở bước import trên Windows — underthesea
    # nạp kèm torch/transformers. Làm TRƯỚC embed: thiếu gói thì lỗi sau vài giây, không phải
    # sau vài phút embed
    keyword_segments = [word_segments(text) for text in texts]

    # lưu vào params → cluster_runs: đổi phiên bản (venv WSL ngoài uv.lock) làm đổi từ khoá —
    # phải truy được về sau
    segmenter = (
        f"underthesea=={version('underthesea')}; underthesea-core=={version('underthesea-core')}"
    )

    # ADR-0004: chỉ embed text mới/đổi (hash khác vector đã lưu); phần còn lại dùng lại
    missing = [i for i, uid in enumerate(ids) if uid not in cached]
    model_name = PRIMARY_MODEL_NAME
    fresh: dict[int, list[float]] = {}
    if missing:
        vectors, model_name = embed_texts([texts[i] for i in missing])
        fresh = {i: vec.tolist() for i, vec in zip(missing, vectors, strict=True)}
        if model_name != PRIMARY_MODEL_NAME:
            # Fallback model → không trộn vector của 2 model: embed lại toàn bộ
            vectors, model_name = embed_texts(texts)
            fresh = {i: vec.tolist() for i, vec in enumerate(vectors)}
            cached = {}
    matrix = np.array([cached.get(uid) or fresh[i] for i, uid in enumerate(ids)])
    result = cluster_embeddings(matrix)

    labels = result.labels
    n_clusters = len({label for label in labels.tolist() if label != -1})
    n_noise = int((labels == -1).sum())
    dbcv = _dbcv(result.umap_coords, labels)

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model_name": model_name,
                # khớp file export của LẦN NÀY — import từ chối kết quả cũ (bước WSL lỗi)
                "export_digest": export_digest,
                "ids": ids,
                "hashes": hashes,
                "cluster_labels": labels.tolist(),
                "umap_coords": result.umap_coords.tolist(),
                "embeddings": matrix.tolist(),
                "dbcv": dbcv,
                "dbcv_relative": result.relative_validity,
                "keyword_segments": keyword_segments,
                "params": {
                    "umap_n_components": UMAP_N_COMPONENTS,
                    "umap_n_neighbors": UMAP_N_NEIGHBORS,
                    "umap_random_state": UMAP_RANDOM_STATE,
                    "hdbscan_min_cluster_size": HDBSCAN_MIN_CLUSTER_SIZE,
                    "cluster_selection_method": CLUSTER_SELECTION_METHOD,
                    "keyword_segmenter": segmenter,
                },
            },
            f,
        )

    return {
        "content_units": len(ids),
        "model_name": model_name,
        "embedded_now": len(fresh),
        "reused_embeddings": len(ids) - len(fresh),
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "dbcv_validity_index": dbcv if dbcv is not None else "n/a",
        "dbcv_relative_validity": result.relative_validity
        if result.relative_validity is not None
        else "n/a",
        "results_path": str(RESULTS_PATH),
    }


def _dbcv(coords: np.ndarray, labels: np.ndarray) -> float | None:
    """DBCV đầy đủ (Moulavi et al. 2014, `hdbscan.validity.validity_index`) — chỉ số
    chất lượng cụm cho phân cụm theo mật độ, -1..1, càng cao càng tốt; tính trên đúng
    không gian HDBSCAN đã gom (toạ độ UMAP). Khác thang với `relative_validity_` (bản
    xấp xỉ dùng lúc calibrate) — luôn ghi tên hàm cạnh con số. < 2 cụm → None."""
    if len({int(label) for label in labels if label != -1}) < 2:
        return None
    from hdbscan.validity import validity_index

    return float(validity_index(coords.astype(np.float64), labels))


if __name__ == "__main__":
    print(run())
