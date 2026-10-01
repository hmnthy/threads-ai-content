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

## Next

1. Dashboard P1 Bước 2 — nhãn viral (Thy đã chốt: P90 toàn lịch sử + sàn views P25, dùng chung cho bảng top; Mann-Whitney trên biến giải thích + Holm) → ADR-0012. Rồi Bước 3–4: API NLP (CMI, topic stats) + UI + tab Knowledge base (DAG RAG).
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phase G — CI GitHub Actions (chạy cả `scripts.consistency.check --all`).
4. Phần còn lại của D0: ADR-0007 (lưu bình luận follower, pseudonymize) → `audience_replies`, `qa_pairs`.

## Blocked / cần Thy

- Landing ghi "This site, deployed on Vercel" — giữ tới khi deploy thật (Thy: chỉnh nội dung thêm 1 vòng rồi mới deploy).
- Lần mở phiên tới: duyệt 2 MCP server trong `/mcp` (`context7`, `huggingface` — HF đăng nhập OAuth) và thử pop-up khi Claude xong việc.
- Duyệt bio `LandingAuthor.tsx` + sub-headline tagline `LandingHero.tsx` (còn treo từ 2026-09-03).
- Phase C cần Thy mở VS Code Remote-WSL (Claude Code chạy trong Linux) — không tự làm được từ phiên Windows.
- RQ-08 cần Thy gán nhãn tay 150 bài (6 nhãn cố định) + gán lại 30 bài sau 2 tuần.

## Job health (kiểm 2026-10-01)

| Job | Kết quả gần nhất | Ghi chú |
|---|---|---|
| `ThreadsAI_SnapshotJob_4h` | **Lỗi** (1 lúc 10:13, 0xC000013A lúc 13:15 ngày 2026-10-01) | Hỏng mọi lần chạy tự động từ tối 2026-09-30, không ghi log; chạy tay OK — chưa rõ nguyên nhân |
| `ThreadsAI_NLPClusterJob_Daily` | **Lỗi chập chờn** (267014) | WSL `HCS_E_CONNECTION_TIMEOUT` + `database is locked` khi chạy chồng snapshot — sửa ở Phase C |

## Số liệu nhanh

- 150 root post · 1.369 reply của tác giả (353 self_continuation · 674 author_answer · 342 outbound — ADR-0004) · 9 cluster (`validity_index` 0,317, nhiễu 36%) · 277 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- `b914d41` Regenerate README screenshots with the Unthreaded name (sau `ad36131` ADR-0009; fast-forward vào `main`)
