# ADR-0017: Chạy job NLP lúc 12:30, cho cả 2 cron chạy khi dùng pin, chấp nhận snapshot hở ban đêm

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-04
- **Người quyết**: Thy (chọn "đổi giờ chạy" 12:30 + "chấp nhận và ghi rõ" lỗ hổng snapshot ban đêm), Claude chẩn đoán, code-reviewer bổ sung bằng chứng snapshot

## Bối cảnh

Sau ADR-0013 (pythonw, không console), job `ThreadsAI_NLPClusterJob_Daily` lỗi **3/3 đêm**: 2026-10-02 và 2026-10-04 bị Task Scheduler cắt ở giới hạn 30 phút (`0x41306`); 2026-10-03 lỗi 401 vì key Claude hết hạn (ADR-0016).

Bằng chứng (log `data/logs/*.log` + nhật ký System, Kernel-Power 507 = thoát chế độ chờ, 506 = vào lại):
- `powercfg /a`: máy chỉ có **Standby (S0 Low Power Idle)** — Modern Standby đóng băng tiến trình desktop khi ngủ; task có `WakeToRun` = False, chỉ chạy được trong các lần thức bảo trì ngắn.
- 2026-10-04: 507 và 506 **cùng giây** 03:08:54, job bắt đầu ngay sau đó; log có kết quả bước export nhưng **không có** `-- bước cluster_wsl` → tiến trình đứng sau bước 1. Còn 1 lần thức bảo trì 05:39:53, rồi lần thức của người dùng 12:05:21 — task bị cắt (giờ sửa cuối của file log lúc đó là 12:05; nay đã đổi do lần chạy tay).
- 2026-10-02: cùng mẫu — 507/506 lúc 03:11:57, job bắt đầu 03:11:59, chỉ có bước export; người dùng thức lúc 09:10:54.
- 2026-10-03: job tiến được qua 2 lần thức ngắn (03:40:48, 03:55:27), ~16 phút mới tới bước import → bằng chứng rõ nhất "job chỉ chạy được trong lúc máy thức".
- Khi máy thức: chạy qua Task Scheduler 2026-10-04 18:15 hết **68 giây**, exit 0.
- **Snapshot cũng bị** (code-reviewer phát hiện): `ThreadsAI_SnapshotJob_4h` chạy ~1,5–2 phút; các lượt ban đêm (VD 2026-10-03 21:39, 2026-10-04 01:39 và 05:39 giờ Paris) chỉ có dòng "bắt đầu", không có dòng kết thúc. `python -m scripts.snapshot_coverage` (2026-09-10 → 2026-10-04): 60 lượt snapshot = 2,4 lượt/ngày (lịch là 6); lượt theo giờ Paris dồn vào 13h (16), 17h (14), 21h (9), 9h (6); 1h–3h chỉ 4 lượt (1 lượt chỉ ghi 2 dòng — bị đóng băng giữa chừng), 4h–8h không có; khoảng trống > 5h: n = 29, trung vị 15,7h (thường từ tối hôm trước tới trưa hôm sau); số snapshot trong 24h đầu của 1 root post: n = 6 bài, trung vị 2 (từ 2026-08-31: n = 11, trung vị 2) → chuỗi thời gian **đã luôn hở ban đêm** theo giờ máy ngủ (không phải lỗi mới).
- Cả 2 task đặt `DisallowStartIfOnBatteries` + `StopIfGoingOnBatteries` = True → máy chạy pin là bỏ lượt; với snapshot (không thu thập bù được) bỏ lượt là mất hẳn.

## Quyết định

1. Job NLP chạy **12:30 hằng ngày theo giờ máy** (giờ máy thường đang mở; `StartWhenAvailable` chạy bù khi lỡ).
2. Cả 2 job được chạy và chạy tiếp khi dùng pin.
3. **Chấp nhận** snapshot hở ban đêm, ghi rõ giới hạn này cho mọi phân tích chuỗi thời gian (`docs/claude/data-model.md`, Velocity) — không thêm cơ chế giữ máy thức. Số liệu độ phủ lấy từ `scripts/snapshot_coverage.py` (tái lập được, kèm n), không ước lượng tay.
4. Toàn bộ cấu hình task đặt bằng `scripts/configure_jobs.ps1` (đổi tên từ `set_job_actions.ps1`): Action, lịch NLP (`StartBoundary` không offset → theo đổi giờ), cờ pin, giới hạn 30 phút, IgnoreNew, StartWhenAvailable.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ giờ đêm + job tự xin Windows "đừng ngủ" (`PowerSetRequest` ExecutionRequired/SystemRequired) + `WakeToRun` | Giữ giờ đêm; có thể lấp snapshot đêm | Chưa chắc Modern Standby tôn trọng khi màn hình tắt — phải thử nhiều đêm; thêm code ctypes + test; máy thức ~2 phút mỗi 4h ban đêm | Thy chọn cách chắc chắn cho NLP và chấp nhận hở snapshot |
| Cả hai (12:30 + power request làm lưới an toàn) | Bền nhất | Nhiều việc nhất | Chưa cần |
| Tăng giới hạn 30 phút | Dễ | Tiến trình đóng băng không chạy tiếp dù giới hạn dài bao nhiêu | Không sửa nguyên nhân |

## Hệ quả

- Task Scheduler đã áp dụng (2026-10-04): NLP `StartBoundary 2026-10-04T12:30:00` hằng ngày (không offset); snapshot giữ chu kỳ 4h (xx:15); cả 2: chạy khi dùng pin, PT30M, IgnoreNew, StartWhenAvailable. Mốc "lần chạy kế tiếp 2026-10-05 03:00" trong ADR-0016 nay là 2026-10-05 12:30.
- Docs/code: `.claude/rules/pipeline-db.md`, `docs/claude/architecture.md`, `docs/claude/data-model.md` (giới hạn lấy mẫu), `docs/roadmap.md` (Phase C mang theo lịch + cờ pin), `docs/status.md`, docstring `src/pipeline/nlp_cluster_job.py` và `src/analysis/velocity.py`, comment `src/nlp/topics.py`, copy "View velocity" trong `MetricArchitectureGrid.tsx`; script mới `scripts/snapshot_coverage.py` + test.
- Sổ luật: `ADR0017-nlp-3am` (cấm mô tả job NLP/đặt tên cụm chạy 3h sáng / hằng đêm), `ADR0017-old-script` (cấm nhắc `set_job_actions.ps1`) — ngoài `docs/decisions/`; test hit/miss trong `tests/scripts/test_consistency.py`.
- `scripts/job_health.py` giữ ngưỡng 26h (NLP) và 5h (snapshot): lỡ lượt vì máy tắt/ngủ → hook đầu phiên báo WARN như cũ. Snapshot ban đêm lỡ là bình thường theo quyết định 3; WARN snapshot đầu phiên sáng không còn là tín hiệu lỗi riêng.
- Rủi ro chấp nhận:
  - Máy ngủ lúc 12:30 → `StartWhenAvailable` khởi động job ở lần thức bảo trì kế tiếp → job lại bị đóng băng và bị cắt (đúng cơ chế đêm 2026-10-04). `job_health` bắt được qua ngưỡng 26h.
  - Máy ngủ giữa lúc job đang chạy → lượt đó bị cắt.
  - Job NLP (~1 phút, tải model bge-m3 trong WSL) chạy lúc Thy đang dùng máy.
  - Velocity/longevity: khoảng trống đêm trung vị ~16h; slope qua khoảng đó là nội suy, không phải quan sát; `window_velocity` 24h (cần ≥ 3 điểm) thường không tính được (trung vị 2 điểm/24h đầu).
  - Máy ngủ qua cả 12:30 lẫn lượt snapshot kế tiếp (13:15) → khi thức, `StartWhenAvailable` chạy bù cả 2 cùng lúc → có thể gặp lại `database is locked` (lỗi đã biết, Phase C sửa bằng WAL + `busy_timeout` + `flock`). Lịch 3h cũ có cùng rủi ro.
  - `job_health` sẽ WARN snapshot ở hầu hết phiên buổi sáng (khoảng trống ~16h > ngưỡng 5h) → WARN snapshot buổi sáng mất giá trị báo động; WARN đáng xem là khi `LastTaskResult` ≠ 0 lúc máy đang thức.
- Xem lại khi: Phase C (job sang WSL `run_job.sh`, roadmap) — giờ chạy + cờ pin phải mang sang `wsl_job.ps1`; `job_health` WARN NLP ≥ 2 lần/tuần vì lỡ lượt (khi đó thêm power request); hoặc khi một câu hỏi nghiên cứu cần snapshot ban đêm (VD RQ về giờ audience Việt Nam thức — đêm Paris là sáng/trưa Việt Nam); hoặc khi WARN snapshot buổi sáng làm chìm cảnh báo thật (khi đó cho `job_health` phân biệt "lỡ lượt vì máy ngủ" với "lượt chạy lúc máy thức mà lỗi").
