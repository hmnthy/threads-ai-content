# Status — threads-ai-content

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-09-30

## Now

- Tái cấu trúc "LESS IS MORE" (ADR-0001, ADR-0003) xong và đã merge vào `main` (chưa push).
- Nhánh `chore/consistency-police` (ADR-0008): sổ luật + `check.py` + `consistency-auditor` + `/decision-sweep` + cổng pre-commit; lượt sweep đầu cho ADR-0001/0003/0008 đang hoàn tất.

## Next

1. Push `main` lên `origin` (chờ Thy đồng ý).
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phase G — CI GitHub Actions.
4. Phase D0 — `reply_role`, verify live `/conversation`, persist embeddings.

## Blocked / cần Thy

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
- `pytest` đầy đủ ~51 giây; bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- `6967a99` Gate commits on consistency, fast tests and dashboard checks (nhánh `chore/consistency-police`)
