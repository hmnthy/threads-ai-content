# Status — Unthreaded

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-10-01

## Now

- `main` đã gồm và đã push lên `origin` (2026-09-30):
  - tái cấu trúc "LESS IS MORE" (ADR-0001, ADR-0003);
  - cưỡng chế nhất quán (ADR-0008): sổ luật `invariants.toml` + `check.py` + `consistency-auditor` + `/decision-sweep` + 7 cổng pre-commit;
  - tên hiển thị **Unthreaded** (ADR-0009, slug `threads-ai-content` giữ nguyên) + câu miễn trừ Meta.
- Sweep ADR-0009: tầng 1 = 0 vi phạm, auditor lượt 2 = 0 phát hiện.
- Nhánh `feat/dashboard-honesty-p0`: P0 của bản phản biện dashboard (median + n + IQR lên UI, heatmap giờ đăng, Topic Explorer 1 màu nhấn + banner dữ liệu tạm) + ADR-0010 (SQLite là CSDL duy nhất) + ADR-0011 (bài views = 0 là dữ liệu thiếu — 6/150 bài bị loại khỏi phân phối rate, UI ghi số bị loại). Sweep 0010 + 0011: tầng 1 = 0, auditor xác nhận. Đã commit (`7de4444`, `94e8361`).
- Nhánh `feat/dashboard-p1` (tách từ P0, chưa merge/push): Bước 1 xong — ADR-0004 (phân vai reply 353/674/342, `full_text` sạch, lưu embedding, calibrate lại n_neighbors 8 → 9 cụm, nhiễu 36%; `/conversation` trả được bình luận follower). Commit `ae8494c`, `a47e35d`.
- Vá lỗ hổng cảnh sát (Thy duyệt 2026-10-01): ADR-0014 (pre-commit quét toàn repo `--commit`, CI GitHub Actions) + ADR-0013 (job snapshot hỏng do cửa sổ console → chạy bằng pythonw, hook đo độ tươi từ DB). ADR-0015 (Thy chọn A + B): bắt buộc review tầng 2 — git hook pre-commit (chỉ commit do Claude chạy) chặn commit chạm logic/ADR khi chưa có dấu review khớp nội dung; dấu do hook SubagentStart/Stop ghi.

## Next

1. Dashboard P1 Bước 2 — nhãn viral (Thy đã chốt: P90 toàn lịch sử + sàn views P25, dùng chung cho bảng top; Mann-Whitney trên biến giải thích + Holm) → ADR-0012. Rồi Bước 3–4: API NLP (CMI, topic stats) + UI + tab Knowledge base (DAG RAG).
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phase G — CI: file `.github/workflows/ci.yml` đã có (ADR-0014), chạy lần đầu khi push lên GitHub.
4. Phần còn lại của D0: ADR-0007 (lưu bình luận follower, pseudonymize) → `audience_replies`, `qa_pairs`.

## Blocked / cần Thy

- File brand-assets.md của Thy (docs/design, chưa track) nhắc 2 file chưa tạo (BrandLogo.tsx, icon.svg) → `check --all` báo 2 đường dẫn chết; commit file đó cần tạo 2 file hoặc thêm vào `planned_paths`.
- Landing ghi "This site, deployed on Vercel" — giữ tới khi deploy thật (Thy: chỉnh nội dung thêm 1 vòng rồi mới deploy).
- Lần mở phiên tới: duyệt 2 MCP server trong `/mcp` (`context7`, `huggingface` — HF đăng nhập OAuth) và thử pop-up khi Claude xong việc.
- Duyệt bio `LandingAuthor.tsx` + sub-headline tagline `LandingHero.tsx` (còn treo từ 2026-09-03).
- Phase C cần Thy mở VS Code Remote-WSL (Claude Code chạy trong Linux) — không tự làm được từ phiên Windows.
- RQ-08 cần Thy gán nhãn tay 150 bài (6 nhãn cố định) + gán lại 30 bài sau 2 tuần.

## Job health (kiểm 2026-10-01 — hook đầu phiên tự kiểm bằng `scripts/job_health.py`)

| Job | Kết quả gần nhất | Ghi chú |
|---|---|---|
| `ThreadsAI_SnapshotJob_4h` | OK (0x0, 14:11 ngày 2026-10-01, qua Task Scheduler) | Hỏng 30/09 17:17 → 01/10 trưa do cửa sổ console bị đóng (0xC000013A); giờ chạy bằng pythonw, không console (ADR-0013) |
| `ThreadsAI_NLPClusterJob_Daily` | **Lỗi chập chờn** (0x41306 lúc 03:24 ngày 2026-10-01, đúng lúc máy thức) | Đã chuyển sang `nlp_cluster_job.py` + pythonw (ADR-0013) — lần 03:00 kế tiếp là lần kiểm chứng đầu; WSL `HCS_E_CONNECTION_TIMEOUT` + `database is locked` còn lại cho Phase C |

## Số liệu nhanh

- 150 root post · 1.369 reply của tác giả (353 self_continuation · 674 author_answer · 342 outbound — ADR-0004) · 9 cluster (`validity_index` 0,317, nhiễu 36%) · 397 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- Require a content-matched tier-2 review before commits (ADR-0015)
