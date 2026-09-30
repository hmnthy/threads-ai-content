# Status — Unthreaded

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-09-30

## Now

- `main` đã gồm và đã push lên `origin` (2026-09-30):
  - tái cấu trúc "LESS IS MORE" (ADR-0001, ADR-0003);
  - cưỡng chế nhất quán (ADR-0008): sổ luật `invariants.toml` + `check.py` + `consistency-auditor` + `/decision-sweep` + 7 cổng pre-commit;
  - tên hiển thị **Unthreaded** (ADR-0009, slug `threads-ai-content` giữ nguyên) + câu miễn trừ Meta.
- Sweep ADR-0009: tầng 1 = 0 vi phạm, auditor lượt 2 = 0 phát hiện.

## Next

1. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
2. Phase G — CI GitHub Actions (chạy cả `scripts.consistency.check --all`).
3. Phase D0 — `reply_role`, verify live `/conversation`, persist embeddings.

## Blocked / cần Thy

- Quyết định còn mở từ lượt sweep đầu (chưa sửa, chờ Thy):
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

- 150 root post · 1.368 reply của tác giả (362 self-continuation · 664 trả lời follower · 342 ở bài người khác) · 9 cluster · 225 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- `b914d41` Regenerate README screenshots with the Unthreaded name (sau `ad36131` ADR-0009; fast-forward vào `main`)
