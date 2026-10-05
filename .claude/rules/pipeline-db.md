---
paths:
  - "src/pipeline/**"
  - "src/db/**"
  - "scripts/jobs/**"   # sẽ tạo ở Phase C (roadmap) — glob đặt sẵn
  - "scripts/job_health.py"
  - "scripts/configure_jobs.ps1"
---

# Pipeline + SQLite

- DB duy nhất: `data/threads.db` (gitignored). Hiện `DEFAULT_DB_PATH` là đường dẫn **tương đối** (`src/db/schema.py`) → phải chạy từ root repo; mỗi worktree có bản DB riêng (có thể cũ). Phase C thay bằng `src/config.py::db_path()` + `$THREADS_DB_PATH`.
- 2 cron (Windows Task Scheduler) gọi thẳng `pythonw.exe` (không console — ADR-0013): `ThreadsAI_SnapshotJob_4h` → `src.pipeline.scheduled_job`; `ThreadsAI_NLPClusterJob_Daily` (12:30 — máy dùng Modern Standby, job đêm bị đóng băng: ADR-0017) → `src.pipeline.nlp_cluster_job`. Cả 2 chạy cả khi dùng pin. Đổi cấu hình task (Action, lịch, cờ pin) chỉ bằng `scripts/configure_jobs.ps1`, không sửa tay. Job tự ghi log UTF-8 (`--log`, dòng "bắt đầu" + dòng kết thúc có mã thoát). Trước khi tin data mới: `python -m scripts.job_health` (độ tươi từ DB + `LastTaskResult`; hook đầu phiên đã chạy sẵn).
- Lỗi đã biết: job NLP gặp `database is locked` khi chạy chồng snapshot và `HCS_E_CONNECTION_TIMEOUT` khi WSL khởi động chậm — Phase C sửa bằng WAL + `busy_timeout` + `flock` + retry.
- Ghi DB phải **idempotent** (chạy lại không nhân đôi): UNIQUE constraint + upsert. Kết quả cluster: gán bài → topic tính lại toàn bộ mỗi lần, nhưng id `topic_N` + tên topic **bền** (ADR-0018: ghép theo thành viên rồi ngữ nghĩa; chỉ đặt tên cụm mới/tách/nhập, cụm trôi khỏi bản neo lúc đặt tên (`drift`) hoặc đổi model/prompt (`config_change`); topic biến mất ghi `retired`, id không tái dùng; lịch sử trong `topic_label_history`); mỗi lần gom cụm ghi 1 dòng `cluster_runs` (DBCV, nhiễu, ARI, sự kiện topic) và lưu vector vào `embeddings` (ADR-0004). Sửa quy tắc ghép → chạy lại `scripts/topic_identity_eval.py` và cập nhật số trong ADR.
- Snapshot insight là time-series **không hồi cứu được** — không bao giờ xoá/ghi đè `insights_snapshots`.
- Đổi schema: thêm cột có default / bảng mới; không drop cột có data. Ghi ADR nếu đổi ý nghĩa dữ liệu. Bảng đã có thì migrate trong `_migrate()` (`src/db/schema.py`) — idempotent, vì job cron gọi `create_schema()` mỗi lần chạy.
- Batch ≠ serving: pipeline ghi kết quả; `src/main.py` chỉ đọc, không load model.
