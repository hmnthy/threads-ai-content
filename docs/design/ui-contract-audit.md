# Audit mockup theo hợp đồng UI

> Kiểm 2026-10-07 (vòng 3) trên gói Claude Design 2026-10-07, theo `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020;
> gồm luật ADR-0012).
> **Người đọc:** Claude Design (sửa mockup ở vòng kế tiếp) và Claude Code (khi port). Claude Code **không sửa mockup**
> (ADR-0020). Số liệu cũ trong mockup (số bài, %, median…) không nằm trong audit này — xử lý riêng khi có file xuất
> (brief Việc 4).
> **Mức:** `cấu trúc` = phải đổi component / trạng thái / dạng dữ liệu / luồng; `chữ` = chỉ đổi câu chữ.

## 1. Cảnh báo tự động của sổ luật

Nguồn: `uv run python -m scripts.consistency.check --all` — mục "Cảnh báo mockup" (không chặn commit). Hook đầu phiên
in số cảnh báo; khi về 0, hàng này xoá. Hiện: **3** (1 báo nhầm + 2 theo ADR-0021). 8 cảnh báo ADR-0012 của vòng 2
đã hết.

| File mockup | Dòng | Luật | Khớp | Xử lý |
|---|---|---|---|---|
| `src/dashboard/mockups/landing.dc.html` | 533 | `ADR0001-coming-soon` | "sắp có" | **Báo nhầm**: nội dung bài gốc tiếng Việt dùng làm dữ liệu mẫu, không phải nhãn trạng thái. Hết khi mockup lấy dữ liệu từ file xuất <!-- consistency: allow ADR0001-coming-soon --> |
| `src/dashboard/mockups/overview-amber.dc.html` | 30 | `ADR0021-placeholder-logo` | logo giữ chỗ bằng icon "at" trong vòng tròn amber | `../public/brand/unthreaded-lockup.svg` cao 28px, tagline chữ HTML bên dưới (`UI-0021-logo-placement`) |
| `src/dashboard/mockups/overview-cyan.dc.html` | 30 | `ADR0021-placeholder-logo` | như trên | như trên (hoặc bỏ file — hướng không chọn) |

## 2. Landing so với hợp đồng

`src/dashboard/mockups/landing.dc.html` bản 2026-10-07. 3 điểm của vòng 2 đã sửa — Claude Code kiểm lại bằng tìm chuỗi:
không còn `lowN`, "under 10"; có "Paris time" (mốc đọc `RUN_AT_UTC`, đổi sang `Europe/Paris`), cờ `insufficient_data`
(n < 5), "not computed (fewer than 2 posts to compare)" cho ARI và "not computed (fewer than 2 clusters)" cho DBCV (xem
bằng tweak `ariNull`, `dbcvNull`). Không còn nhãn cũ của ADR-0012 ở mockup nào (hai luật `ADR0012-old-label-wording`, `ADR0012-raw-views-as-reach` hết cảnh báo). Còn lại:

| ui-contract id | Vị trí trong landing (dòng) | Hiện tại | Phải là | Mức |
|---|---|---|---|---|
| UI-0017-run-time | 500 (`RUN_AT_UTC`) | Giờ giữ chỗ `2026-10-01T12:30:00Z` (hiện 14:30 Paris time) | `run_at` thật của lần gom cụm cho số liệu mockup: `2026-10-01T11:35:06Z` → "2026-10-01 13:35 Paris time" (`cluster_runs.id = 3`, ghi ở handoff §0.5) | chữ |
| UI-L20260903-landing-vs-app-routes | 46, 473, 474 | "Read the methodology", "View the repo" trỏ `#` | URL thật khi deploy (handoff §3.7) — chưa phải lỗi | — |

### Ghi chú cho vòng thiết kế kế tiếp

1. **Dữ liệu landing cần mà API chưa trả:** `representative_ids_json`, `dbcv`, ARI, `run_at`, cờ n nhỏ theo topic —
   endpoint ở brief Việc 3. Lần gom cụm mới nhất (2026-10-07, `cluster_runs.id = 7`) có số khác mockup: nhiễu 41,1%,
   validity_index (DBCV) 0,261 — mockup sẽ đổi số khi có file xuất (Việc 4).
2. **Chưa audit theo hợp đồng** `overview-amber.dc.html`, `overview-cyan.dc.html`, `design-system.dc.html`,
   `docs/design/layout-tiers.dc.html` — ngoài cảnh báo tự động ở mục 1. Làm khi các mockup đó vào vòng port.
   `design-system.dc.html` ghi màu Blue cho "follower geography": dữ liệu đó chưa có trong DB hay API — chỉ là ý nghĩa
   màu, không phải lời hứa tính năng.
3. **Claude Code đã sửa trong tài liệu của Claude Design (dữ kiện kỹ thuật):** 2026-10-06 — `landing-handoff.md`
   `src/main.py:258` → `:270`, 4 chỗ "chờ Câu hỏi mở" → id hợp đồng; `topics-brief-for-claude-code.md` 2 dòng "Câu hỏi
   mở 1 / 2" → "Đã chốt"; `brief-ui-contract-review-2026-10-06.md` gắn `consistency: allow ADR0001-coming-soon`.
   2026-10-07 — `landing-handoff.md` §0.5 dòng UI-0017-run-time: thêm `run_at` thật (`cluster_runs.id = 3`).
4. **Tầng reach (ADR-0012)** chưa có trên mockup nào: `UI-0012-reach-tiers`, `UI-0012-raw-views-reference`,
   `UI-0012-not-tiered` là ràng buộc cho lần thiết kế Analytics / Topics tới; mốc so sánh mô tả là "the channel's recent
   level (median of up to 20 prior posts)" (hạn chế cửa sổ 20 bài: `docs/claude/data-model.md`).
5. **Còn mở (Thy chốt ở Việc 1b):** nhóm so sánh theo topic — "phần còn lại của kênh" hay "median kênh".
