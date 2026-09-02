"""Bước 2/3 của clustering pipeline — CHỈ chạy trong WSL2 Ubuntu, KHÔNG chạy trên
`.venv` Windows (xem docs/claude/architecture.md decision log 2026-09-02 — Smart
App Control chặn `scipy.linalg._flapack` không ổn định trên Windows, verify thật
cho thấy có lúc chạy được có lúc không; WSL2 không nằm trong phạm vi Smart App
Control nên ổn định).

Đọc `data/nlp_exchange/texts_export.json` (do `src/pipeline/clustering_export.py`
tạo trên Windows), gọi lại NGUYÊN VẸN `embed_texts()` (`src/nlp/embeddings.py`) và
`cluster_embeddings()` (`src/nlp/topics.py`) — KHÔNG viết lại logic, chỉ đổi môi
trường chạy — để tránh 2 bản logic lệch nhau giữa Windows/WSL.

Chạy trong WSL:
    wsl -d Ubuntu -- bash -c "cd /mnt/c/.../threads-ai-content/.claude/worktrees/<agent> \
        && source ~/threads-clustering-env/bin/activate && python3 -m src.pipeline.cluster_wsl"
"""

from __future__ import annotations

import json
from pathlib import Path

from src.nlp.embeddings import embed_texts
from src.nlp.topics import cluster_embeddings

TEXTS_EXPORT_PATH = Path("data/nlp_exchange/texts_export.json")
RESULTS_PATH = Path("data/nlp_exchange/cluster_results.json")


def run() -> dict[str, int | str]:
    with TEXTS_EXPORT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    ids: list[str] = data["ids"]
    texts: list[str] = data["texts"]

    embeddings, model_name = embed_texts(texts)
    result = cluster_embeddings(embeddings)

    n_clusters = len({label for label in result.labels.tolist() if label != -1})
    n_noise = int((result.labels == -1).sum())

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model_name": model_name,
                "ids": ids,
                "cluster_labels": result.labels.tolist(),
                "umap_coords": result.umap_coords.tolist(),
            },
            f,
        )

    return {
        "content_units": len(ids),
        "model_name": model_name,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "results_path": str(RESULTS_PATH),
    }


if __name__ == "__main__":
    print(run())
