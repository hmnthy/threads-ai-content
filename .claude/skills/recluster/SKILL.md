---
name: recluster
description: Re-run the NLP clustering job (embed, UMAP, HDBSCAN, Claude labels) on the real database and report what changed.
disable-model-invocation: true
---

# /recluster — chạy lại clustering trên DB thật

Job này **ghi vào `data/threads.db` thật** (gán lại bài → topic; giữ id + tên topic khi cụm không đổi — ADR-0018) và chỉ gọi Claude API cho cụm mới/tách/nhập, cụm đã trôi khỏi bản neo lúc đặt tên, hoặc khi đổi model/prompt (tốn phí nhỏ). Xem trước sự kiện (`kept/kept_semantic/relabeled/new/split/merged/retired`) mà không ghi kết quả gom cụm, không gọi Claude: `uv run python -m src.pipeline.clustering_import --dry-run` — lưu ý dry-run VẪN migrate schema của DB.

## Trước khi chạy

!`git status -sb`

1. Chạy từ **checkout chính** (không phải worktree — trước Phase C mỗi worktree có DB riêng), và thư mục chính phải **ở `main`, không có code cron chưa commit** (ADR-0019): `uv run python -m scripts.git_hygiene` in WARN → dừng, báo Thy — job ghi DB thật bằng đúng code đang nằm trên đĩa.
2. Tránh chạy chồng job snapshot 4h (gây `database is locked`): `uv run python -m scripts.job_health` — dòng snapshot ghi "task running now" thì chờ (job ~2 phút). Không suy từ dòng cuối log (job bị giết giữa chừng để lại dòng "bắt đầu" mãi — ADR-0013).
3. Ghi lại trạng thái trước: dòng mới nhất của `cluster_runs` (số cụm, nhiễu, `dbcv` = validity_index, `dbcv_relative` = relative_validity_) + tên topic hiện tại (`topics`).

## Chạy

- **Trước Phase C** (hiện tại, Windows + cầu nối WSL2): `uv run python -m src.pipeline.nlp_cluster_job` (in ra màn hình; thêm `--log data/logs/nlp_cluster_job.log` để ghi như cron) — export (Windows) → embed + cluster (WSL2) → import + đặt tên (Windows), dừng ở bước lỗi đầu tiên.
- **Sau Phase C**: `scripts/jobs/run_job.sh nlp` (1 process trong WSL2, có `flock`).

## Báo cáo

- Kết quả từng bước trong log (dòng `{'content_units': ..., 'n_clusters': ..., 'n_noise': ..., 'dbcv_validity_index': ..., 'dbcv_relative_validity': ...}`); lỗi thì dán traceback cuối.
- Trước → sau (đọc 2 dòng mới nhất của `cluster_runs`): số cụm, % nhiễu, `dbcv` (validity_index) và `dbcv_relative` (relative_validity_ — dao động mạnh, không dùng làm ngưỡng), tên + từ khoá cụm mới. Hai lần chạy khác nhau cả dữ liệu lẫn tham số → ghi ARI là hiệu ứng gộp.
- ARI (Adjusted Rand Index — độ giống nhau giữa 2 cách phân cụm) so với lần trước: cột `ari_vs_previous` của `cluster_runs` (ADR-0004).
- Muốn xem trước khi ghi đè topic: `python -m src.pipeline.clustering_import --dry-run` (không ghi, không gọi Claude).
