# Status — threads-ai-content

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-09-30

## Now

- Tái cấu trúc "LESS IS MORE" (ADR-0001, ADR-0003) đã merge vào `main` (chưa push).
- Nhánh `chore/consistency-police` (ADR-0008) xong: sổ luật `invariants.toml` + `check.py` + `consistency-auditor` + `/decision-sweep` + 7 cổng pre-commit. Lượt sweep đầu cho ADR-0001/0003/0008: tầng 1 = 0 vi phạm, auditor lượt 3 xác nhận. Chờ Thy duyệt merge vào `main`.

## Next

1. Thy duyệt → merge `chore/consistency-police` vào `main`, push `origin` (chưa push từ 2026-09-03).
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phase G — CI GitHub Actions (chạy cả `scripts.consistency.check --all`).
4. Phase D0 — `reply_role`, verify live `/conversation`, persist embeddings.

## Blocked / cần Thy

- Quyết định còn mở từ lượt sweep đầu (chưa sửa, chờ Thy):
  - Tên sản phẩm "Threads AI Content" (chữ "AI Content" gợi ý tính năng sinh nội dung đã bỏ).
  - Landing ghi "This site, deployed on Vercel" — hiện có bản deploy cố định không?
  - "SQLite → PostgreSQL planned" (README ×3, landing) — giữ hay bỏ?
  - Topic `method='fixed'` trong schema và `/topics` (xem roadmap D0).
  - Chữ "audience" trong phân tích reply (`reply_thread.py`, `topic_affinity.py`) — luôn = 0 cho tới Phase D0.
- Lần mở phiên tới: duyệt 2 MCP server trong `/mcp` (`context7`, `huggingface` — HF đăng nhập OAuth) và thử pop-up khi Claude xong việc.
- Duyệt bio `LandingAuthor.tsx` + sub-headline tagline `LandingHero.tsx` (còn treo từ 2026-09-03).
- Phase C cần Thy mở VS Code Remote-WSL (Claude Code chạy trong Linux) — không tự làm được từ phiên Windows.
- RQ-08 cần Thy gán nhãn tay 150 bài (6 nhãn cố định) + gán lại 30 bài sau 2 tuần.

## Job health (kiểm 2026-09-30)

| Job | Kết quả gần nhất | Ghi chú |
|---|---|---|
| `ThreadsAI_SnapshotJob_4h` | OK (0) | 10.481 snapshot, dữ liệu tới 2026-09-30 |
| `ThreadsAI_NLPClusterJob_Daily` | **Lỗi chập chờn** (267014) | WSL `HCS_E_CONNECTION_TIMEOUT` + `database is locked` khi chạy chồng snapshot — sửa ở Phase C |

## Số liệu nhanh

- 150 root post · 1.368 reply của tác giả (362 self-continuation · 664 trả lời follower · 342 ở bài người khác) · 9 cluster · 217 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- `64ba35f` Run the first decision sweep for ADR-0001, 0003 and 0008 (nhánh `chore/consistency-police`)
