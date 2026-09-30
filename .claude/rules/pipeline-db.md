---
paths:
  - "src/pipeline/**"
  - "src/db/**"
  - "scripts/jobs/**"   # sẽ tạo ở Phase C (roadmap) — glob đặt sẵn
  - "run_*.bat"
---

# Pipeline + SQLite

- DB duy nhất: `data/threads.db` (gitignored). Hiện `DEFAULT_DB_PATH` là đường dẫn **tương đối** (`src/db/schema.py`) → phải chạy từ root repo; mỗi worktree có bản DB riêng (có thể cũ). Phase C thay bằng `src/config.py::db_path()` + `$THREADS_DB_PATH`.
- 2 cron (Windows Task Scheduler): `ThreadsAI_SnapshotJob_4h` → `run_snapshot_job.bat`; `ThreadsAI_NLPClusterJob_Daily` (3h sáng) → `run_nlp_cluster_job.bat`. Kiểm `LastTaskResult` + `data/logs/*.log` trước khi tin data mới.
- Lỗi đã biết: job NLP gặp `database is locked` khi chạy chồng snapshot và `HCS_E_CONNECTION_TIMEOUT` khi WSL khởi động chậm — Phase C sửa bằng WAL + `busy_timeout` + `flock` + retry.
- Ghi DB phải **idempotent** (chạy lại không nhân đôi): UNIQUE constraint + upsert. Kết quả cluster: xoá toàn bộ `method='cluster'` rồi ghi lại (label HDBSCAN không ổn định giữa các lần chạy); **không đụng** `method='fixed'`.
- Snapshot insight là time-series **không hồi cứu được** — không bao giờ xoá/ghi đè `insights_snapshots`.
- Đổi schema: thêm cột có default / bảng mới; không drop cột có data. Ghi ADR nếu đổi ý nghĩa dữ liệu.
- Batch ≠ serving: pipeline ghi kết quả; `src/main.py` chỉ đọc, không load model.
