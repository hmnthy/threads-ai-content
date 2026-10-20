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
- Khoá ghi (2026-10-17): `connect()` chờ khoá tới `LOCK_WAIT_S` (2 phút) thay vì 5 giây — không mở `sqlite3.connect`/`PRAGMA busy_timeout` riêng trong `src/` (trừ đọc `mode=ro`); **không giữ transaction ghi qua lời gọi mạng (API Threads, Claude) hay tính toán dài** — làm xong mới ghi + commit (job snapshot từng giữ khoá suốt ~160 lần gọi API → job NLP `database is locked` 10–11/10). Hàm mới/được sửa vừa gọi mạng vừa ghi DB cần test dò khoá bằng `BEGIN IMMEDIATE` với `timeout=0` (mẫu: `tests/pipeline/test_snapshot.py`). Còn lại cho Phase C: WAL + `flock` + retry, và `HCS_E_CONNECTION_TIMEOUT` khi WSL khởi động chậm.
- `job_health` cảnh báo khi lần so sánh topic mới nhất dùng số liệu cũ hơn ngưỡng tươi của job snapshot (4h + 1h) so với lúc tính — VD job snapshot hỏng, hoặc chạy chồng sau một lần ngủ dài. Dòng "NLP recluster OK" chỉ đo lần gom cụm, không đo số liệu nó dùng.
- "Cùng cách chia cụm" giữa 2 lần gom cụm = nhãn của mọi unit giống hệt (cùng tập unit, cùng nhãn) — **không** dùng `cluster_runs.ari_vs_previous` = 1: ARI chỉ tính trên unit chung, lần có thêm bài vẫn ra 1 (ADR-0024; `distinct_partitions` trong `src/analysis/partition_history.py`, dùng chung cho API lịch sử "k of m" và `scripts/topic_stability_report.py`).
- Ghi DB phải **idempotent** (chạy lại không nhân đôi): UNIQUE constraint + upsert. Kết quả cluster: gán bài → topic tính lại toàn bộ mỗi lần, nhưng id `topic_N` + tên topic **bền** (ADR-0018: ghép theo thành viên rồi ngữ nghĩa; chỉ đặt tên cụm mới/tách/nhập, cụm trôi khỏi bản neo lúc đặt tên (`drift`) hoặc đổi model/prompt (`config_change`); topic biến mất ghi `retired`, id không tái dùng; lịch sử trong `topic_label_history`); mỗi lần gom cụm ghi 1 dòng `cluster_runs` (DBCV, nhiễu, ARI, sự kiện topic) và lưu vector vào `embeddings` (ADR-0004); bước cuối `compare` ghi `topic_comparison_runs` + `topic_comparisons` (giữ lịch sử theo lần gom cụm, chạy lại thì thay — ADR-0023); bước này lỗi → API trả `stale`, `job_health` cảnh báo. Sửa quy tắc ghép → chạy lại `scripts/topic_identity_eval.py` và cập nhật số trong ADR.
- Snapshot insight là time-series **không hồi cứu được** — không bao giờ xoá/ghi đè `insights_snapshots`.
- Đổi schema: thêm cột có default / bảng mới; không drop cột có data. Ghi ADR nếu đổi ý nghĩa dữ liệu. Bảng đã có thì migrate trong `_migrate()` (`src/db/schema.py`) — idempotent, vì job cron gọi `create_schema()` mỗi lần chạy.
- Batch ≠ serving: pipeline ghi kết quả; `src/main.py` chỉ đọc, không load model. API không gọi `create_schema` → hàm đọc bảng MỚI phải coi "no such table" là "chưa có kết quả" (DB chưa migrate sau merge), kèm test. Helper `src/db/schema.py` để người gọi commit; helper nào tự commit (`with conn:`) phải chặn khi connection đang có transaction mở (`replace_topic_comparisons`).
- Thêm/đổi thư viện mà job cron import → sau khi merge, **trước** lần chạy job kế tiếp: Windows `uv sync --frozen` ở
  thư mục chính; WSL2 (`~/threads-clustering-env`, ngoài `uv.lock`) `pip install` đúng phiên bản trong `pyproject.toml`
  (VD `underthesea` cho bước cluster, ADR-0022). Thư viện kéo torch/transformers/sklearn chỉ được import ở bước WSL2 —
  kiểm import gián tiếp (`python -X importtime -c "import <gói>"`) trước khi đặt vào bước chạy trên Windows.
