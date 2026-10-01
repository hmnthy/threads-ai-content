"""Bước 3/3 của clustering pipeline — chạy trên Windows (chỉ cần `anthropic` + numpy,
không đụng scipy/umap/hdbscan). Đọc `data/nlp_exchange/cluster_results.json` (do
`src/pipeline/cluster_wsl.py` tạo trong WSL) và ghi:

1. Vector embedding vào bảng `embeddings` (ADR-0004 — trước đây tính xong rồi bỏ).
2. Toạ độ UMAP cho MỌI content unit (kể cả noise, để vẫn plot được).
3. Mỗi cụm thật (bỏ noise = -1): từ khoá c-TF-IDF, 3 bài gần tâm cụm nhất, tâm cụm,
   và tên/mô tả tiếng Anh từ `label_cluster_with_claude()` — Claude nhận bài GẦN TÂM
   NHẤT trước (thay cho "15 bài đầu tiên"); LLM chỉ đặt tên, không phân loại.
4. 1 dòng `cluster_runs`: tham số, số cụm, tỉ lệ nhiễu, DBCV (2 thước đo, ghi rõ tên
   hàm), ARI so với lần trước (có tính nhiễu + chỉ trên bài có cụm) và số bài chuyển
   giữa cụm ↔ nhiễu.

Claude được gọi cho MỌI cụm trước; chỉ khi đặt tên xong hết mới xoá topic cũ và ghi
topic mới + `cluster_runs` trong 1 transaction — Claude lỗi giữa chừng thì topic cũ còn
nguyên, không có trạng thái nửa vời.

`dry_run=True`: tính và trả mọi số liệu (kể cả ARI, từ khoá) nhưng không ghi dữ liệu
gom cụm và KHÔNG gọi Claude (vẫn có thể migrate schema qua `create_schema`).
`baseline_db`: lấy nhãn "lần trước" từ 1 DB khác (VD bản sao lưu trước ADR-0004) thay
vì từ `cluster_runs`. Nếu 2 lần khác nhau ở hơn 1 yếu tố (dữ liệu VÀ tham số), ARI là
hiệu ứng GỘP — muốn tách phải có 1 lần chạy chỉ đổi 1 yếu tố (RQ-00).

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.clustering_import [--dry-run]
[--baseline-db PATH]`

**Full-recompute** (Layer 10, 2026-09-03): mỗi lần chạy XOÁ SẠCH `topics`/
`post_topic_labels` `method='cluster'` rồi ghi lại — `topic_id = f"cluster_{n}"` theo
vị trí nhãn HDBSCAN, không ổn định giữa các lần chạy (xem `delete_cluster_topics`).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    content_hash,
    create_schema,
    delete_cluster_topics,
    get_content_unit,
    insert_cluster_run,
    latest_cluster_run,
    update_content_unit_embedding_coords,
    upsert_embedding,
    upsert_post_topic_label,
    upsert_topic,
)
from src.nlp.topic_profile import (
    REPRESENTATIVES_PER_TOPIC,
    adjusted_rand_index,
    class_tfidf_keywords,
    representatives,
)
from src.nlp.topics import label_cluster_with_claude

RESULTS_PATH = Path("data/nlp_exchange/cluster_results.json")
EXPORT_PATH = Path("data/nlp_exchange/texts_export.json")


def _previous_labels(conn: Any, *, use_runs: bool = True) -> dict[str, int]:
    """Nhãn của lần gom cụm trước: lấy từ `cluster_runs` nếu có, nếu chưa có (hoặc
    `use_runs=False`) thì dựng lại từ `post_topic_labels` — bài có toạ độ UMAP nhưng
    không có nhãn là noise (-1). Chỉ dùng để tính ARI."""
    run = latest_cluster_run(conn) if use_runs else None
    if run is not None:
        return {uid: int(label) for uid, label in json.loads(run["labels_json"]).items()}
    labels: dict[str, int] = {}
    topic_index: dict[str, int] = {}
    for row in conn.execute(
        "SELECT cu.id, ptl.topic_id FROM content_units cu "
        "LEFT JOIN post_topic_labels ptl ON ptl.post_id = cu.id AND ptl.method = 'cluster' "
        "WHERE cu.umap_x IS NOT NULL"
    ):
        topic_id = row["topic_id"]
        labels[row["id"]] = (
            -1 if topic_id is None else topic_index.setdefault(topic_id, len(topic_index))
        )
    return labels


def compare_with_previous(
    previous: dict[str, int], current: dict[str, int]
) -> tuple[float | None, float | None, dict[str, int]]:
    """(ARI coi nhiễu là 1 nhóm, ARI chỉ trên bài có cụm ở cả 2 lần, số bài chuyển).

    ARI có tính nhiễu lẫn 2 hiệu ứng: đổi cách chia VÀ bài chuyển sang/ra khỏi nhiễu —
    nên luôn báo kèm bảng chuyển và ARI chỉ trên bài có cụm."""
    common = [uid for uid in current if uid in previous]
    ari_all = (
        adjusted_rand_index([previous[u] for u in common], [current[u] for u in common])
        if len(common) >= 2
        else None
    )
    both = [u for u in common if previous[u] != -1 and current[u] != -1]
    ari_clustered = (
        adjusted_rand_index([previous[u] for u in both], [current[u] for u in both])
        if len(both) >= 2
        else None
    )
    transitions = {
        "cluster_to_cluster": len(both),
        "cluster_to_noise": sum(1 for u in common if previous[u] != -1 and current[u] == -1),
        "noise_to_cluster": sum(1 for u in common if previous[u] == -1 and current[u] != -1),
        "noise_to_noise": sum(1 for u in common if previous[u] == -1 and current[u] == -1),
        "new_units": len(current) - len(common),
    }
    return ari_all, ari_clustered, transitions


def run_import(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    dry_run: bool = False,
    baseline_db: Path | None = None,
) -> dict[str, Any]:
    with RESULTS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    # Bước WSL lỗi thì file kết quả là của lần trước: import lại sẽ ghi 1 dòng
    # cluster_runs "ổn định hoàn hảo" giả và đặt lại tên topic → từ chối
    if "export_digest" in data and EXPORT_PATH.exists():
        current = hashlib.sha256(EXPORT_PATH.read_bytes()).hexdigest()
        if data["export_digest"] != current:
            raise RuntimeError(
                "cluster_results.json không khớp texts_export.json hiện tại — "
                "bước WSL của lần này chưa chạy xong"
            )
    ids: list[str] = data["ids"]
    cluster_labels: list[int] = data["cluster_labels"]
    umap_coords: list[list[float]] = data["umap_coords"]
    embeddings = np.array(data["embeddings"]) if "embeddings" in data else None
    model_id: str = data.get("model_name", "unknown")

    conn = connect(db_path)
    create_schema(conn)
    full_texts = {
        uid: row["full_text"] for uid in ids if (row := get_content_unit(conn, uid)) is not None
    }

    if baseline_db is not None:
        baseline = connect(baseline_db)
        previous = _previous_labels(baseline, use_runs=False)
        baseline.close()
    else:
        previous = _previous_labels(conn)
    new_by_id = dict(zip(ids, cluster_labels, strict=True))
    ari, ari_clustered, transitions = compare_with_previous(previous, new_by_id)

    clusters: dict[int, list[int]] = defaultdict(list)  # nhãn → vị trí trong `ids`
    for index, label in enumerate(cluster_labels):
        if label != -1:
            clusters[label].append(index)
    # Nhiễu vào làm "nền" cho IDF (như BERTopic tính cả lớp -1) nhưng không có từ khoá
    keywords = class_tfidf_keywords(
        {
            label: [full_texts.get(ids[i], "") for i in members]
            for label, members in clusters.items()
        },
        background_docs=[
            full_texts.get(uid, "")
            for uid, label in zip(ids, cluster_labels, strict=True)
            if label == -1
        ],
    )

    profiles: dict[int, dict[str, Any]] = {}
    for label, members in clusters.items():
        member_ids = [ids[i] for i in members]
        if embeddings is not None:
            centroid, ordered = representatives(member_ids, embeddings[members], k=len(members))
            similarity = dict(
                zip(member_ids, (embeddings[members] @ np.array(centroid)).tolist(), strict=True)
            )
        else:
            centroid, ordered, similarity = None, member_ids, {}
        profiles[label] = {
            "unit_ids": member_ids,
            "ordered_ids": ordered,
            "representatives": ordered[:REPRESENTATIVES_PER_TOPIC],
            "centroid": centroid,
            "similarity": similarity,
            "keywords": keywords.get(label, []),
        }

    n_noise = sum(1 for label in cluster_labels if label == -1)
    summary: dict[str, Any] = {
        "content_units": len(ids),
        "n_clusters_labeled": len(clusters),
        "n_noise": n_noise,
        "noise_ratio": n_noise / len(ids) if ids else 0.0,
        "dbcv_validity_index": data.get("dbcv"),
        "dbcv_relative_validity": data.get("dbcv_relative"),
        "ari_vs_previous": ari,
        "ari_clustered_only": ari_clustered,
        "transitions": transitions,
        "cluster_sizes": sorted((len(m) for m in clusters.values()), reverse=True),
    }
    if dry_run:
        summary["keywords"] = {f"cluster_{k}": v["keywords"] for k, v in profiles.items()}
        conn.close()
        return summary

    # Đặt tên TRƯỚC khi đụng vào DB — Claude lỗi thì topic cũ còn nguyên
    names = {
        label: label_cluster_with_claude(
            [full_texts.get(uid, "") for uid in profile["ordered_ids"]]
        )
        for label, profile in profiles.items()
    }

    now = datetime.now(UTC).isoformat()
    hashes: list[str] = data.get("hashes") or [content_hash(full_texts.get(uid, "")) for uid in ids]
    if embeddings is not None:
        for uid, text_hash, vector in zip(ids, hashes, embeddings.tolist(), strict=True):
            upsert_embedding(
                conn,
                object_type="content_unit",
                object_id=uid,
                model_id=model_id,
                text_hash=text_hash,
                vector=vector,
                created_at=now,
            )

    # Bài từng được gom cụm nhưng nay không còn chữ → bỏ toạ độ cũ (khỏi hiện trên bản đồ)
    placeholders = ",".join("?" * len(ids))
    conn.execute(
        f"UPDATE content_units SET umap_x = NULL, umap_y = NULL, umap_z = NULL "
        f"WHERE umap_x IS NOT NULL AND id NOT IN ({placeholders})",
        ids,
    )
    for unit_id, coords in zip(ids, umap_coords, strict=True):
        update_content_unit_embedding_coords(conn, unit_id, x=coords[0], y=coords[1], z=coords[2])
    delete_cluster_topics(conn)
    for label, profile in profiles.items():
        topic_id = f"cluster_{label}"
        result = names[label]
        upsert_topic(
            conn,
            topic_id=topic_id,
            label_en=result.label_en,
            description_en=result.description_en,
            method="cluster",
            centroid_embedding=profile["centroid"],
            keywords=profile["keywords"],
            representative_ids=profile["representatives"],
        )
        for uid in profile["unit_ids"]:
            # cột `confidence` lưu cosine giữa bài và tâm cụm (None nếu không có embedding);
            # API trả với tên `centroid_similarity` để không bị đọc thành xác suất
            upsert_post_topic_label(
                conn,
                post_id=uid,
                topic_id=topic_id,
                method="cluster",
                confidence=profile["similarity"].get(uid),
            )

    insert_cluster_run(
        conn,
        run_at=now,
        model_id=model_id,
        params=data.get("params", {}),
        n_units=len(ids),
        n_clusters=len(clusters),
        noise_ratio=summary["noise_ratio"],
        dbcv=data.get("dbcv"),
        dbcv_relative=data.get("dbcv_relative"),
        ari_vs_previous=ari,
        ari_clustered_only=ari_clustered,
        transitions=transitions,
        labels=new_by_id,
    )
    conn.commit()
    conn.close()
    return summary


if __name__ == "__main__":
    args = sys.argv[1:]
    baseline = Path(args[args.index("--baseline-db") + 1]) if "--baseline-db" in args else None
    print(run_import(dry_run="--dry-run" in args, baseline_db=baseline))
