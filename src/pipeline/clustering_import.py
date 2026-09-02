"""Bước 3/3 của clustering pipeline — chạy trên Windows (chỉ cần `anthropic`,
không đụng scipy/umap/hdbscan). Đọc `data/nlp_exchange/cluster_results.json`
(do `src/pipeline/cluster_wsl.py` tạo trong WSL), ghi toạ độ UMAP cho MỌI content
unit (kể cả noise, để vẫn plot được), rồi dùng `label_cluster_with_claude()`
(`src/nlp/topics.py` — LLM CHỈ tóm tắt, không tự classify, xem data-model.md) để
đặt tên tiếng Anh cho từng cluster thật (bỏ qua noise = -1, không tạo topic giả).

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.clustering_import`
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    get_content_unit,
    update_content_unit_embedding_coords,
    upsert_post_topic_label,
    upsert_topic,
)
from src.nlp.topics import label_cluster_with_claude

RESULTS_PATH = Path("data/nlp_exchange/cluster_results.json")


def run_import(db_path: Path = DEFAULT_DB_PATH) -> dict[str, int]:
    with RESULTS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    ids: list[str] = data["ids"]
    cluster_labels: list[int] = data["cluster_labels"]
    umap_coords: list[list[float]] = data["umap_coords"]

    conn = connect(db_path)

    # Toạ độ UMAP: ghi cho MỌI content unit, kể cả noise (-1) — vẫn cần plot được
    # trên Topic Explorer, chỉ khác màu/không gán topic.
    for unit_id, coords in zip(ids, umap_coords, strict=True):
        update_content_unit_embedding_coords(conn, unit_id, x=coords[0], y=coords[1], z=coords[2])
    conn.commit()

    # Gom id theo cluster, bỏ qua noise (-1)
    clusters: dict[int, list[str]] = defaultdict(list)
    for unit_id, label in zip(ids, cluster_labels, strict=True):
        if label != -1:
            clusters[label].append(unit_id)

    for cluster_label, unit_ids in clusters.items():
        topic_id = f"cluster_{cluster_label}"
        sample_texts = [
            row["full_text"] for uid in unit_ids if (row := get_content_unit(conn, uid)) is not None
        ]
        result = label_cluster_with_claude(sample_texts)
        upsert_topic(
            conn,
            topic_id=topic_id,
            label_en=result.label_en,
            description_en=result.description_en,
            method="cluster",
        )
        for uid in unit_ids:
            upsert_post_topic_label(conn, post_id=uid, topic_id=topic_id, method="cluster")
        conn.commit()

    conn.close()
    n_noise = sum(1 for label in cluster_labels if label == -1)
    return {
        "content_units": len(ids),
        "n_clusters_labeled": len(clusters),
        "n_noise": n_noise,
    }


if __name__ == "__main__":
    print(run_import())
