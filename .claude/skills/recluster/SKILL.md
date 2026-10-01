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
3. Ghi lại trạng thái trước: dòng mới nhất của `cluster_runs` (số cụm, nhiễu, `dbcv` = validity_index, `dbcv_relative` = relative_validity_) + tên topic hiện tại (`topics`).

## Chạy

- **Trước Phase C** (hiện tại, Windows + cầu nối WSL2): `cmd //c run_nlp_cluster_job.bat` — export (Windows) → embed + cluster (WSL2) → import + đặt tên (Windows). Log: `data/logs/nlp_cluster_job.log`.
- **Sau Phase C**: `scripts/jobs/run_job.sh nlp` (1 process trong WSL2, có `flock`).

## Báo cáo

- Kết quả từng bước trong log (dòng `{'content_units': ..., 'n_clusters': ..., 'n_noise': ..., 'dbcv_validity_index': ..., 'dbcv_relative_validity': ...}`); lỗi thì dán traceback cuối.
- Trước → sau (đọc 2 dòng mới nhất của `cluster_runs`): số cụm, % nhiễu, `dbcv` (validity_index) và `dbcv_relative` (relative_validity_ — dao động mạnh, không dùng làm ngưỡng), tên + từ khoá cụm mới. Hai lần chạy khác nhau cả dữ liệu lẫn tham số → ghi ARI là hiệu ứng gộp.
- ARI (Adjusted Rand Index — độ giống nhau giữa 2 cách phân cụm) so với lần trước: cột `ari_vs_previous` của `cluster_runs` (ADR-0004).
- Muốn xem trước khi ghi đè topic: `python -m src.pipeline.clustering_import --dry-run` (không ghi, không gọi Claude).
