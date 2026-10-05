# Status — Unthreaded

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-10-05

## Now

- `main` đã gồm và đã push lên `origin` (2026-09-30):
  - tái cấu trúc "LESS IS MORE" (ADR-0001, ADR-0003);
  - cưỡng chế nhất quán (ADR-0008): sổ luật `invariants.toml` + `check.py` + `consistency-auditor` + `/decision-sweep` + 7 cổng pre-commit;
  - tên hiển thị **Unthreaded** (ADR-0009, slug `threads-ai-content` giữ nguyên) + câu miễn trừ Meta.
- Sweep ADR-0009: tầng 1 = 0 vi phạm, auditor lượt 2 = 0 phát hiện.
- Nhánh `feat/dashboard-honesty-p0`: P0 của bản phản biện dashboard (median + n + IQR lên UI, heatmap giờ đăng, Topic Explorer 1 màu nhấn + banner dữ liệu tạm) + ADR-0010 (SQLite là CSDL duy nhất) + ADR-0011 (bài views = 0 là dữ liệu thiếu — 6/150 bài bị loại khỏi phân phối rate, UI ghi số bị loại). Sweep 0010 + 0011: tầng 1 = 0, auditor xác nhận. Đã commit (`7de4444`, `94e8361`).
- Nhánh `feat/dashboard-p1` (tách từ P0, chưa merge/push): Bước 1 xong — ADR-0004 (phân vai reply 353/674/342, `full_text` sạch, lưu embedding, calibrate lại n_neighbors 8 → 9 cụm, nhiễu 36%; `/conversation` trả được bình luận follower). Commit `ae8494c`, `a47e35d`.
- Vá lỗ hổng cảnh sát (Thy duyệt 2026-10-01): ADR-0014 (pre-commit quét toàn repo `--commit`, CI GitHub Actions) + ADR-0013 (job snapshot hỏng do cửa sổ console → chạy bằng pythonw, hook đo độ tươi từ DB). ADR-0015 (Thy chọn A + B): bắt buộc review tầng 2 — git hook pre-commit (chỉ commit do Claude chạy) chặn commit chạm logic/ADR khi chưa có dấu review khớp nội dung; dấu do hook SubagentStart/Stop ghi.
- 2026-10-04: key Claude cũ hết hạn 02/10 → key mới (hết hạn 2026-12-04); ADR-0016 — đặt tên cụm bằng `claude-sonnet-5-5` (thay Opus), bỏ lời hứa prompt caching. ADR-0017 — Modern Standby đóng băng tiến trình khi máy ngủ → job NLP chạy 12:30, cả 2 cron chạy khi dùng pin (`scripts/configure_jobs.ps1`); snapshot hở ban đêm (trung vị khoảng trống ~16h) được chấp nhận và ghi trong data-model.md.
- ADR-0018 (Thy chọn phương án B + 4 lựa chọn sau thí nghiệm 10 seed + kiểm tài liệu MONIC/Greene/Palla/BERTopic): danh tính cụm bền `topic_N` — ghép theo thành viên (bỏ nhiễu ở phép thử giữ, lõi giữ tên) rồi ngữ nghĩa (trừ cụm nhập), đặt lại tên khi trôi khỏi bản neo; prompt đặt tên v2. Đổi tên khi data không đổi: 30,6% [21,0; 40,3] → 15,2% [10,7; 19,9] (828 cụm, 90 cặp seed). DB thật đã migrate một phần (id `topic_N`) do job snapshot 21:15 chạy code đang sửa; lần job NLP kế tiếp thêm cột bản neo và đặt lại tên 9 cụm 1 lần.
- ADR-0019 (Thy chọn): quy trình git — thư mục chính luôn ở `main`, mọi thay đổi trong worktree trên nhánh riêng → PR → CI → merge commit; hook đầu phiên nhắc (`scripts/git_hygiene.py`), skill `/git-flow`, tài liệu `docs/claude/git-workflow.md`.

## Next

0. PR `feat/dashboard-p1` → `main` (CI chạy lần đầu) → merge commit → chuyển thư mục chính về `main`; rồi PR `chore/git-workflow` (ADR-0019, xếp chồng).
1. Dashboard P1 Bước 2 — nhãn viral (Thy đã chốt: P90 toàn lịch sử + sàn views P25, dùng chung cho bảng top; Mann-Whitney trên biến giải thích + Holm) → ADR-0012. Rồi Bước 3–4: API NLP (CMI, topic stats) + UI + tab Knowledge base (DAG RAG).
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phase G — CI: file `.github/workflows/ci.yml` đã có (ADR-0014), chạy lần đầu khi mở PR `feat/dashboard-p1` → `main` (CI chỉ chạy khi mở PR hoặc push vào `main`).
4. Phần còn lại của D0: ADR-0007 (lưu bình luận follower, pseudonymize) → `audience_replies`, `qa_pairs`.

## Blocked / cần Thy

- File brand-assets.md của Thy (docs/design, chưa track) nhắc 2 file chưa tạo (BrandLogo.tsx, icon.svg) → `check --all` báo 2 đường dẫn chết; commit file đó cần tạo 2 file hoặc thêm vào `planned_paths`.
- Landing ghi "This site, deployed on Vercel" — giữ tới khi deploy thật (Thy: chỉnh nội dung thêm 1 vòng rồi mới deploy).
- Lần mở phiên tới: duyệt 2 MCP server trong `/mcp` (`context7`, `huggingface` — HF đăng nhập OAuth) và thử pop-up khi Claude xong việc.
- Duyệt bio `LandingAuthor.tsx` + sub-headline tagline `LandingHero.tsx` (còn treo từ 2026-09-03).
- Phase C cần Thy mở VS Code Remote-WSL (Claude Code chạy trong Linux) — không tự làm được từ phiên Windows.
- RQ-08 cần Thy gán nhãn tay 150 bài (6 nhãn cố định) + gán lại 30 bài sau 2 tuần.

## Job health (kiểm 2026-10-04 — hook đầu phiên tự kiểm bằng `scripts/job_health.py`)

| Job | Kết quả gần nhất | Ghi chú |
|---|---|---|
| `ThreadsAI_SnapshotJob_4h` | OK (0x0, 17:15 ngày 2026-10-04) | pythonw không console (ADR-0013); từ 2026-10-04 chạy cả khi dùng pin (ADR-0017) |
| `ThreadsAI_NLPClusterJob_Daily` | OK (0x0, chạy qua Task Scheduler 18:15 ngày 2026-10-04, 68 giây) | 02/10 + 04/10 bị cắt (0x41306) vì máy ngủ giữa job, 03/10 lỗi 401 key hết hạn → giờ chạy 12:30 (ADR-0017); lần 12:30 ngày 2026-10-05 là lần kiểm chứng đầu. `HCS_E_CONNECTION_TIMEOUT` + `database is locked` còn lại cho Phase C |

## Số liệu nhanh

- 152 root post · 1.390 reply của tác giả (367 self_continuation · 680 author_answer · 343 outbound — ADR-0004) · 9 cluster (`validity_index` 0,261, nhiễu 41% — lần gom 2026-10-04) · 475 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- Keep topic identities stable across reclustering runs (ADR-0018)
