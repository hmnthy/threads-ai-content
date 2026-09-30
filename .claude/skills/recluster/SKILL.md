---
name: recluster
description: Re-run the NLP clustering job (embed, UMAP, HDBSCAN, Claude labels) on the real database and report what changed.
disable-model-invocation: true
---

# /recluster — chạy lại clustering trên DB thật

Job này **ghi vào `data/threads.db` thật** (xoá + ghi lại các topic `method='cluster'`) và gọi Claude API để đặt tên cluster (tốn phí nhỏ).

## Trước khi chạy

!`git status -sb`

1. Chạy từ **checkout chính** (không phải worktree — trước Phase C mỗi worktree có DB riêng).
2. Tránh chạy chồng job snapshot 4h (gây `database is locked`): xem dòng cuối `data/logs/scheduled_job.log`; nếu job vừa bắt đầu < 5 phút thì chờ.
3. Ghi lại trạng thái trước: số topic + phân bố cluster hiện tại (query `topics` / `post_topic_labels` với `method='cluster'`).

## Chạy

- **Trước Phase C** (hiện tại, Windows + cầu nối WSL2): `cmd //c run_nlp_cluster_job.bat` — export (Windows) → embed + cluster (WSL2) → import + đặt tên (Windows). Log: `data/logs/nlp_cluster_job.log`.
- **Sau Phase C**: `scripts/jobs/run_job.sh nlp` (1 process trong WSL2, có `flock`).

## Báo cáo

- Kết quả từng bước trong log (dòng `{'content_units': ..., 'n_clusters': ..., 'n_noise': ...}`); lỗi thì dán traceback cuối.
- Trước → sau: số cluster, % noise, tên cluster mới.
- ARI (Adjusted Rand Index — độ giống nhau giữa 2 cách phân cụm) giữa lần trước và lần này: **chưa có** cho tới khi embeddings được persist (Phase D0) và RQ-01 thêm tính toán này — ghi rõ là chưa đo được, không ước lượng.
