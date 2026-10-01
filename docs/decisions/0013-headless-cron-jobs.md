# ADR-0013: Chạy cron job bằng pythonw (không console), job tự ghi log, hook đo độ tươi từ DB

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-01
- **Người quyết**: đề xuất bởi Claude (Thy yêu cầu sửa lỗi job snapshot), Thy duyệt 2026-10-01

## Bối cảnh

Job `ThreadsAI_SnapshotJob_4h` hỏng mọi lần chạy tự động từ 17:17 ngày 2026-09-30 tới trưa 2026-10-01 (gần 1 ngày không có snapshot), nhưng hook đầu phiên không báo. Điều tra 2026-10-01:

- **Không do code hay `.venv`**: cùng lệnh chạy tay OK; Task Scheduler kích hoạt 2 lần liền nhau → lần 1 chết sau < 8 giây với `0xC000013A`, lần 2 xong `0x0`. Lỗi **chập chờn**.
- **Thủ phạm là cửa sổ console**: LogonType `Interactive` + action là file `.bat` → Windows mở 1 cửa sổ console, do Windows Terminal tiếp quản (thấy tiến trình `OpenConsole.exe` + `WindowsTerminal.exe` sinh ra cùng task). Cửa sổ đó đóng (người dùng đóng, hoặc máy vừa thức dậy từ Modern Standby — lần hỏng 10:13 trùng lúc máy thức 10:14) → cả nhóm tiến trình nhận tín hiệu đóng console → `0xC000013A` (STATUS_CONTROL_C_EXIT). Job NLP có thể cùng nguyên nhân: `0x41306` (SCHED_S_TASK_TERMINATED — task bị dừng, không phải mã đóng console) lúc 03:24 đúng lúc máy thức; chưa tái hiện được.
- **Quyết định cũ chẩn đoán nhầm**: `legacy-log.md` (2026-09-01) gặp đúng `STATUS_CONTROL_C_EXIT` và quy cho lỗi quoting, rồi chọn launcher `.bat` — `.bat` vẫn mở console nên lỗi chỉ thưa đi, không hết.
- **Log không kể được gì**: job chỉ in 1 dòng khi chạy xong; redirect `>>` của cmd dùng cp1252: chữ "Ỗ" trong dòng lỗi (stderr) bị in thành chuỗi escape `\u1ed6`, còn `print` tiếng Việt ra stdout thì ném `UnicodeEncodeError`. Job bị giết giữa chừng không để lại dấu, dòng cuối cũ trông như OK — hook in dòng cuối đó.

## Quyết định

1. Task Scheduler gọi thẳng `.venv\Scripts\pythonw.exe -m <module> --log <file>` (không console, không `.bat`, không quoting lồng). Cấu hình bằng `scripts/set_job_actions.ps1` (từ chối chạy trong worktree — cron phải trỏ checkout chính).
2. Job tự mở log UTF-8 (`src/pipeline/job_log.py`): dòng "bắt đầu", dòng kết thúc kèm mã thoát, traceback đầy đủ. Job NLP 3 bước chuyển thành `src/pipeline/nlp_cluster_job.py` (dừng ở bước lỗi đầu tiên, bước con chạy `python.exe` + `CREATE_NO_WINDOW`). Bỏ `run_snapshot_job.bat`, `run_nlp_cluster_job.bat`.
3. Hook đầu phiên đo sức khoẻ job bằng `scripts/job_health.py`: độ tươi lấy từ DB (`MAX(insights_snapshots.fetched_at)`, `MAX(cluster_runs.run_at)`) so với ngưỡng = chu kỳ + ân hạn (5h, 26h), cộng `LastTaskResult` lỗi (khác 0, `0x41301` = đang chạy, `0x41303` = chưa tới lượt) mà chưa có lần chạy **thành công** nào kết thúc sau lần đó → dòng `WARN`. "Thành công" lấy từ dòng `<job> xong` mà `run_logged` ghi kèm giờ kết thúc (luôn ghi vào log chuẩn của job, kể cả khi chạy tay không `--log`) — không lấy timestamp dữ liệu, vì chính lần chạy lỗi có thể đã kịp ghi snapshot trước khi hỏng. Lỗi ở trước khi mở log được tránh bằng thứ tự: mở log → parse tham số → import module dự án (`src/pipeline/job_log.py::run_job`).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ `.bat`, đổi terminal mặc định về conhost | 1 thay đổi cài đặt | Vẫn có cửa sổ để bị đóng / bị standby giết; phụ thuộc cài đặt máy | Không sửa gốc |
| LogonType S4U ("chạy cả khi chưa đăng nhập") | Không console, chạy cả khi khoá máy | Thường cần quyền admin để đăng ký; Phase C sẽ đổi cron sang WSL | Đắt hơn, giá trị ngắn hạn |
| `pythonw` + job tự ghi log (chọn) | Không console; log UTF-8 có dấu bắt đầu/kết thúc; chỉ đổi Action | Chạy tay muốn thấy output phải bỏ `--log` | — |
| Hook đọc dòng cuối log (cũ) | Đơn giản | Job chết giữa chừng không ghi gì → báo sai là OK | Đã chứng minh sai 2026-10-01 |

## Hệ quả

- Đổi: `src/pipeline/{scheduled_job,nlp_cluster_job,job_log}.py`, `scripts/{job_health.py,set_job_actions.ps1}`, `.claude/hooks/session_status.py`; xoá 2 file `.bat`; cập nhật `.claude/rules/pipeline-db.md`, skill `recluster`, `docs/claude/architecture.md`, `docs/roadmap.md` (Phase C).
- Kiểm chứng 2026-10-01: Task Scheduler kích hoạt → chỉ `pythonw.exe` chạy, không cửa sổ, `0x0`, log có dòng bắt đầu + kết thúc tiếng Việt đúng. Bước WSL chạy được từ `pythonw` (thử bằng lệnh import vô hại). Job NLP thật được kiểm chứng ở lần chạy 03:00 kế tiếp (hook báo).
- Còn lại (không do ADR này sửa): job chạy trúng lúc máy ngủ/thức vẫn có thể bị dừng (`0x41306`) — nay ít ra log có dòng "bắt đầu" không có dòng kết thúc, hook báo; `database is locked` khi 2 job chồng nhau; WSL khởi động chậm — đều thuộc Phase C (`flock`, `busy_timeout`, retry).
- Luật: `ADR0013-bat-launcher` cấm nhắc 2 file `.bat` như launcher hiện hành.
- Xem lại khi: Phase C chuyển cron sang WSL (`scripts/jobs/run_job.sh`) — khi đó launcher Windows này bị thay.
