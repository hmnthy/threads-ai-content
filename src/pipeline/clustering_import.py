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

**Danh tính cụm bền (ADR-0018)**: cụm mới được ghép với topic đang lưu theo thành viên rồi
theo ngữ nghĩa (`src/nlp/topic_identity.py`). Cụm `kept` mang tiếp id `topic_N` + tên cũ —
KHÔNG gọi Claude — trừ khi nội dung đã trôi khỏi bản neo lúc đặt tên (`drift`, so cùng quy
tắc với ghép) hoặc tên được đặt bằng model/phiên bản prompt khác hiện tại (`config_change`).
Cụm `new`/`split`/`merged` nhận id mới + tên mới. Topic biến mất ghi 1 dòng `retired` (để id
không bao giờ bị tái dùng). Mỗi lần đặt tên ghi 1 dòng `topic_label_history`; sự kiện của lần
chạy ghi vào `cluster_runs.topic_events_json`.

Claude được gọi cho mọi cụm CẦN tên trước; chỉ khi đặt tên xong hết mới ghi topic +
`cluster_runs` trong 1 transaction — Claude lỗi giữa chừng thì topic cũ còn nguyên.

`dry_run=True`: tính và trả mọi số liệu (kể cả ARI, từ khoá, sự kiện topic dự kiến) nhưng
không ghi kết quả gom cụm và KHÔNG gọi Claude — VẪN migrate schema qua `create_schema`
(lần đầu sau ADR-0018: đổi id `cluster_N` → `topic_N`).
`baseline_db`: lấy nhãn "lần trước" từ 1 DB khác (VD bản sao lưu trước ADR-0004) thay
vì từ `cluster_runs`. Nếu 2 lần khác nhau ở hơn 1 yếu tố (dữ liệu VÀ tham số), ARI là
hiệu ứng GỘP — muốn tách phải có 1 lần chạy chỉ đổi 1 yếu tố (RQ-00).

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.clustering_import [--dry-run]
[--baseline-db PATH]`

Gán bài → topic vẫn tính lại toàn bộ mỗi lần (`replace_cluster_topics`: xoá mọi
`post_topic_labels` rồi gán lại, xoá topic không còn); chỉ id + tên topic là bền.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    content_hash,
    create_schema,
    get_content_unit,
    insert_cluster_run,
    insert_topic_label_history,
    latest_cluster_run,
    next_topic_number,
    replace_cluster_topics,
    topic_assignments,
    topic_label_states,
    update_content_unit_embedding_coords,
    upsert_embedding,
    upsert_post_topic_label,
    upsert_topic,
)
from src.nlp.topic_identity import TopicMatch, anchor_holds, match_topics, semantic_reference
from src.nlp.topic_profile import (
    REPRESENTATIVES_PER_TOPIC,
    adjusted_rand_index,
    class_tfidf_keywords,
    representatives,
)
from src.nlp.topics import (
    CLUSTER_LABELING_MODEL,
    LABEL_PROMPT_VERSION,
    TopicLabelResult,
    label_cluster_with_claude,
)

RESULTS_PATH = Path("data/nlp_exchange/cluster_results.json")
EXPORT_PATH = Path("data/nlp_exchange/texts_export.json")


@dataclass(frozen=True)
class TopicPlan:
    topic_id: str
    event: str  # kept | new | split | merged (topic_identity)
    # Lý do đặt tên lần này: new | split | merged | drift | config_change; None = giữ tên cũ
    reason: str | None
    sources: tuple[str, ...]
    via: str | None = None  # membership | semantic khi kept


def plan_topic_names(
    matches: dict[int, TopicMatch],
    states: dict[str, Any],
    first_new_number: int,
    drifted: set[int],
) -> dict[int, TopicPlan]:
    """Quyết định id + có gọi Claude hay không cho từng cụm mới (ADR-0018). `states`: trạng
    thái tên của topic đang lưu (`topic_label_states`); `drifted`: cụm `kept` đã trôi khỏi bản
    neo lúc đặt tên (`anchor_holds` = False). Cụm `kept` chỉ đặt tên lại khi tên chưa có mốc
    (DB trước ADR-0018), đặt bằng model/phiên bản prompt khác, hoặc đã trôi."""
    plans: dict[int, TopicPlan] = {}
    number = first_new_number
    for cluster in sorted(matches):
        match = matches[cluster]
        if match.event == "kept" and match.topic_id is not None:
            state = states.get(match.topic_id)
            if (
                state is None
                or state["labeled_at"] is None
                or state["label_model"] != CLUSTER_LABELING_MODEL
                or state["label_prompt_version"] != LABEL_PROMPT_VERSION
            ):
                reason: str | None = "config_change"
            elif cluster in drifted:
                reason = "drift"
            else:
                reason = None
            plans[cluster] = TopicPlan(match.topic_id, "kept", reason, match.sources, match.via)
        else:
            plans[cluster] = TopicPlan(f"topic_{number}", match.event, match.event, match.sources)
            number += 1
    return plans


def topic_events(plans: dict[int, TopicPlan], retired: list[str]) -> dict[str, str]:
    """{topic_id: sự kiện} của 1 lần chạy — ghi vào `cluster_runs.topic_events_json`."""
    events: dict[str, str] = {}
    for plan in plans.values():
        if plan.event != "kept":
            events[plan.topic_id] = plan.event
        elif plan.reason is not None:
            events[plan.topic_id] = "relabeled"
        else:
            events[plan.topic_id] = "kept_semantic" if plan.via == "semantic" else "kept"
    events.update({topic_id: "retired" for topic_id in retired})
    return events


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

    # ADR-0018: ghép với topic đang lưu (thành viên → ngữ nghĩa) → id bền; chỉ gọi Claude
    # cho cụm cần tên (mới/tách/nhập, đã trôi khỏi bản neo, hoặc đổi model/prompt)
    vectors = dict(zip(ids, embeddings, strict=True)) if embeddings is not None else None
    previous_topics = topic_assignments(conn)
    reference = semantic_reference(previous_topics, vectors) if vectors is not None else None
    matches = match_topics(previous_topics, new_by_id, vectors, reference)
    states = topic_label_states(conn)
    drifted = {
        c
        for c, m in matches.items()
        if m.topic_id is not None
        and (state := states.get(m.topic_id)) is not None
        and state["label_anchor_json"] is not None
        and not anchor_holds(
            set(profiles[c]["unit_ids"]),
            set(json.loads(state["label_anchor_json"])),
            new_by_id,
            vectors,
            reference,
        )
    }
    plans = plan_topic_names(matches, states, next_topic_number(conn), drifted)
    kept_ids = {plan.topic_id for plan in plans.values() if plan.event == "kept"}
    retired = sorted(set(states) - kept_ids)
    events = topic_events(plans, retired)
    summary["topic_events"] = events
    summary["n_named_now"] = sum(1 for plan in plans.values() if plan.reason is not None)
    summary["semantic_reference"] = reference
    if dry_run:
        summary["keywords"] = {plans[k].topic_id: v["keywords"] for k, v in profiles.items()}
        conn.close()
        return summary

    # Đặt tên TRƯỚC khi đụng vào DB — Claude lỗi thì topic cũ còn nguyên
    names: dict[int, TopicLabelResult] = {
        label: label_cluster_with_claude(
            [full_texts.get(uid, "") for uid in profiles[label]["ordered_ids"]]
        )
        for label, plan in plans.items()
        if plan.reason is not None
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
    # Topic biến mất: ghi `retired` vào lịch sử TRƯỚC khi xoá — `next_topic_number` đọc lịch sử
    # nên id không bao giờ bị tái dùng (kể cả topic chưa từng được đặt tên lại sau migration)
    for topic_id in retired:
        state = states[topic_id]
        insert_topic_label_history(
            conn,
            topic_id=topic_id,
            label_en=state["label_en"],
            description_en=state["description_en"],
            labeled_at=now,
            label_model=state["label_model"] or "unknown",
            label_prompt_version=state["label_prompt_version"] or 0,
            reason="retired",
            sources=[],
        )
    replace_cluster_topics(conn, kept_ids)
    for label, profile in profiles.items():
        plan = plans[label]
        topic_id = plan.topic_id
        if plan.reason is None:  # giữ tên + bản neo: chỉ cập nhật hồ sơ cụm
            state = states[topic_id]
            label_en, description_en = state["label_en"], state["description_en"]
            labeled_at, label_model = state["labeled_at"], state["label_model"]
            prompt_version = state["label_prompt_version"]
            anchor = json.loads(state["label_anchor_json"]) if state["label_anchor_json"] else None
        else:
            result = names[label]
            label_en, description_en = result.label_en, result.description_en
            labeled_at, label_model = now, CLUSTER_LABELING_MODEL
            prompt_version = LABEL_PROMPT_VERSION
            anchor = profile["unit_ids"]  # bản neo mới = thành viên lúc đặt tên
            insert_topic_label_history(
                conn,
                topic_id=topic_id,
                label_en=label_en,
                description_en=description_en,
                labeled_at=now,
                label_model=CLUSTER_LABELING_MODEL,
                label_prompt_version=LABEL_PROMPT_VERSION,
                reason=plan.reason,
                sources=list(plan.sources),
            )
        upsert_topic(
            conn,
            topic_id=topic_id,
            label_en=label_en,
            description_en=description_en,
            method="cluster",
            centroid_embedding=profile["centroid"],
            keywords=profile["keywords"],
            representative_ids=profile["representatives"],
            labeled_at=labeled_at,
            label_model=label_model,
            label_prompt_version=prompt_version,
            label_anchor=anchor,
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
        topic_events=events,
    )
    conn.commit()
    conn.close()
    return summary


if __name__ == "__main__":
    args = sys.argv[1:]
    baseline = Path(args[args.index("--baseline-db") + 1]) if "--baseline-db" in args else None
    print(run_import(dry_run="--dry-run" in args, baseline_db=baseline))
