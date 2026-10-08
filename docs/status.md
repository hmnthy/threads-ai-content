# Status — Unthreaded

> Chỉ trạng thái HIỆN TẠI (≤60 dòng). Lịch sử = `git log` + `docs/decisions/`. Cập nhật ở mỗi `/checkpoint`.
> Cập nhật: 2026-10-08

## Now

- `main` (2026-10-05, PR #1 merge commit `e8d645e`, CI xanh lần đầu) gồm: tái cấu trúc "LESS IS MORE" (ADR-0001, 0003); cưỡng chế nhất quán (ADR-0008) + tên **Unthreaded** (ADR-0009); P0 dashboard trung thực — median + n + IQR, heatmap giờ đăng (ADR-0010 SQLite là CSDL duy nhất, ADR-0011 bài views = 0 là dữ liệu thiếu); P1 Bước 1 — ADR-0004 (phân vai reply 353/674/342, `full_text` sạch, lưu embedding, 9 cụm; `/conversation` trả được bình luận follower); các mục dưới đến ADR-0018.
- CI lần đầu (PR #1): job `web` đỏ vì `LayoutProps` (kiểu Next sinh vào `.next/`, máy sạch chưa có) → `npm run typecheck` = `next typegen && tsc --noEmit` (`67c3bf8`).
- Vá lỗ hổng cảnh sát (Thy duyệt 2026-10-01): ADR-0014 (pre-commit quét toàn repo `--commit`, CI GitHub Actions) + ADR-0013 (job snapshot hỏng do cửa sổ console → chạy bằng pythonw, hook đo độ tươi từ DB). ADR-0015 (Thy chọn A + B): bắt buộc review tầng 2 — git hook pre-commit (chỉ commit do Claude chạy) chặn commit chạm logic/ADR khi chưa có dấu review khớp nội dung; dấu do hook SubagentStart/Stop ghi.
- 2026-10-04: key Claude cũ hết hạn 02/10 → key mới (hết hạn 2026-12-04); ADR-0016 — đặt tên cụm bằng `claude-sonnet-5-5` (thay Opus), bỏ lời hứa prompt caching. ADR-0017 — Modern Standby đóng băng tiến trình khi máy ngủ → job NLP chạy 12:30, cả 2 cron chạy khi dùng pin (`scripts/configure_jobs.ps1`); snapshot hở ban đêm (trung vị khoảng trống ~16h) được chấp nhận và ghi trong data-model.md.
- ADR-0018 (Thy chọn phương án B + 4 lựa chọn sau thí nghiệm 10 seed + kiểm tài liệu MONIC/Greene/Palla/BERTopic): danh tính cụm bền `topic_N` — ghép theo thành viên (bỏ nhiễu ở phép thử giữ, lõi giữ tên) rồi ngữ nghĩa (trừ cụm nhập), đặt lại tên khi trôi khỏi bản neo; prompt đặt tên v2. Đổi tên khi data không đổi: 30,6% [21,0; 40,3] → 15,2% [10,7; 19,9] (828 cụm, 90 cặp seed). DB thật đã migrate một phần (id `topic_N`) do job snapshot 21:15 chạy code đang sửa; lần job NLP kế tiếp thêm cột bản neo và đặt lại tên 9 cụm 1 lần.
- ADR-0019 (Thy chọn): quy trình git — thư mục chính luôn ở `main`, mọi thay đổi trong worktree trên nhánh riêng → PR → CI → merge commit; hook đầu phiên nhắc (`scripts/git_hygiene.py`), skill `/git-flow`, tài liệu `docs/claude/git-workflow.md`. Đã merge (PR #2).
- PR #3 (2026-10-06): gói Claude Design 2026-10-05 (landing mockup chốt, design-system v3.2, brief Topics v2) + logo Unknot.
- ADR-0012 (Thy chốt 2026-10-06, PR #5 đã merge): chỉ số (reposts + quotes) / views đổi tên thành `share_rate` (UI "Share rate"); "bài lan rộng" = tầng reach tương đối — "Top 20% reach" (P80) / "Above median reach" (P50) của views ÷ median 20 bài trước, chỉ bài đã chín (P90 thời gian đạt 90% views, đo từ snapshot); `GET /analytics/reach`, số liệu sinh lại bằng `scripts/reach_report.py`. Chưa có giao diện tầng (chờ mockup); ảnh chụp đã làm lại. Hạn chế cửa sổ 20 bài (Thy giữ, 2026-10-07): ghi ở `data-model.md`.
- Gói Claude Design 2026-10-06 (nhánh `design/2026-10-06`): landing mockup sửa theo audit, `landing-handoff.md` §0.5 (quyết định → id `UI-…`); hợp đồng UI chốt 4 câu hỏi mở (1: một ngưỡng mẫu nhỏ = 5, UI đọc cờ backend; 2: giữ hai bộ nhãn trạng thái; 3: id `topic_N` chỉ ở metadata; 4: mốc clustered theo giờ Paris) + 7 đề xuất cột E.
- ADR-0021 (Thy duyệt logo 2026-10-01, chốt vị trí 2026-10-07): logo Unknot qua `BrandLogo.tsx`, hai navbar dùng lockup tĩnh thay chữ "@" giữ chỗ, favicon `app/icon.svg`; chuyển động chỉ ở hero landing.
- PR 10 (nhánh `feat/landing-port`, Thy chọn hướng A + thêm API đọc 2026-10-07): landing port từ mockup đã chốt, mọi số đọc từ API thật. API mới chỉ đọc: `GET /pipeline/summary` (vai reply, unit không chữ, snapshot mới nhất, lần gom cụm mới nhất, phân phối bài nhiễu), `/topics` thêm từ khoá, 3 bài gần tâm, phân phối engagement mô tả + cờ `insufficient_data`; `/content-units` trả `metrics` null khi views = 0 (ADR-0011). δ + p Holm theo topic vẫn `next` (chờ Việc 1), CMI `research` (RQ-04). Navbar pill luôn 1 hàng (sửa lỗi mockup, ghi audit). Chữ landing viết lại theo 2 lượt agent mới `copy-reviewer` (Thy duyệt 2026-10-08): dải thống kê kênh ở hero, câu hỏi "do better than the channel's usual post", thứ hạng so với các bài khác; `/pipeline/summary` trả thêm ngưỡng `min_posts_to_compare`.
- ADR-0020 (Thy chọn: Claude Code = nguồn sự thật kỹ thuật, Claude Design làm UI/UX trên nền đó; mockup chỉ cảnh báo): hợp đồng UI `docs/design/ui-contract.md` (ADR-0001 → 0020, mỗi ràng buộc kèm `file:line`, máy kiểm đường dẫn/luật/test); ADR mới có mục "Hệ quả UI"; mockup bị sổ luật quét ở mức cảnh báo; audit landing ở `docs/design/ui-contract-audit.md`.

## Next

- ADR-0022 (Thy chọn V5 + tách từ trong WSL2, 2026-10-08, nhánh `feat/topic-keywords-segmentation`): từ khoá topic tách theo từ bằng underthesea 9.5.0 (chạy ở bước cluster trong WSL2 — nó kéo torch/transformers) + bigram 2 từ đơn, bỏ stopword có nhãn (`src/nlp/stopwords.py`); trên lần gom cụm 2026-10-07 từ chức năng/đại từ/teencode trong từ khoá 12/72 → 0, mảnh âm tiết ~4 → 0, lấy lại "tiếng anh", "uber eats". **Sau khi merge, trước 12:30: cài `underthesea==9.5.0 underthesea-core==3.3.2` vào `~/threads-clustering-env` (WSL2)** + `uv sync --frozen` ở thư mục chính. Lọc theo từ loại = RQ-10.
0. Việc 1 của brief Topics (Thy chốt 1a–1e: cấu trúc trang tầng A, nhóm so sánh, họ test Holm, mean, lịch sử tên) **gộp** phần còn mở của ADR-0012 (sàn views cho bảng top theo rate; so sánh biến giải thích giữa các tầng reach + Holm) — chung Holm và câu hỏi "so với nhóm nào".
1. Brief Việc 2–4: audit dữ liệu Topics, endpoint `/topics` mở rộng + run + stats, xuất `docs/design/data/topics/` cho Claude Design.
2. Phase C — chuyển toàn bộ Python sang WSL2 (`docs/roadmap.md`).
3. Phần còn lại của D0: ADR-0007 (lưu bình luận follower, pseudonymize) → `audience_replies`, `qa_pairs`.

## Blocked / cần Thy

- Vòng 3 Claude Design (gói 2026-10-07) xong: cảnh báo mockup còn 1 (báo nhầm trong nội dung bài mẫu). Lần gửi tới kèm `ui-contract-audit.md` mới: đổi `RUN_AT_UTC` của landing thành giờ thật `2026-10-01T11:35:06Z`.
- Lần mở phiên tới: duyệt 2 MCP server trong `/mcp` (`context7`, `huggingface` — HF đăng nhập OAuth) và thử pop-up khi Claude xong việc.
- Duyệt bio ở `LandingAuthor.tsx` (copy của mockup, vẫn là nháp). Nút "View the repo" đã bỏ khỏi khối CTA tới khi có repo công khai.
- Phase C cần Thy mở VS Code Remote-WSL (Claude Code chạy trong Linux) — không tự làm được từ phiên Windows.
- RQ-08 cần Thy gán nhãn tay 150 bài (6 nhãn cố định) + gán lại 30 bài sau 2 tuần.

## Job health (kiểm 2026-10-05 — hook đầu phiên tự kiểm bằng `scripts/job_health.py`)

| Job | Kết quả gần nhất | Ghi chú |
|---|---|---|
| `ThreadsAI_SnapshotJob_4h` | OK (data mới nhất ~2h tuổi lúc kiểm, chiều 2026-10-05) | pythonw không console (ADR-0013); chạy cả khi dùng pin (ADR-0017) |
| `ThreadsAI_NLPClusterJob_Daily` | OK (12:30 ngày 2026-10-05, 46 giây — lần chạy thật đầu tiên của ADR-0018) | giờ 12:30 vì máy ngủ đêm cắt job (ADR-0017). `HCS_E_CONNECTION_TIMEOUT` + `database is locked` còn lại cho Phase C |

## Số liệu nhanh

- 152 root post · 1.398 reply của tác giả (367 self_continuation · 681 author_answer · 350 outbound — ADR-0004) · 9 cluster (`validity_index` 0,261, nhiễu 41% — lần gom 2026-10-07; số sống: `GET /pipeline/summary`) · 540 test pass
- `pytest` đầy đủ ~1–1,5 phút (dao động theo tải máy); bộ nhanh (`-m "not slow and not live"`, chạy ở pre-commit) ~20 giây

## Last checkpoint

- Use the Unknot logo from a single asset source with fixed placements (ADR-0021)
