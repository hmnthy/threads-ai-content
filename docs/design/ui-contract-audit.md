# Audit mockup theo hợp đồng UI

> Kiểm 2026-10-06 (vòng 2) trên gói Claude Design 2026-10-06, theo `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020;
> gồm luật ADR-0012 — gói được đóng trước khi ADR-0012 merge).
> **Người đọc:** Claude Design (sửa mockup ở vòng kế tiếp) và Claude Code (khi port). Claude Code **không sửa mockup**
> (ADR-0020). Số liệu cũ trong mockup (số bài, %, median…) không nằm trong audit này — xử lý riêng khi có file xuất
> (brief Việc 4).
> **Mức:** `cấu trúc` = phải đổi component / trạng thái / dạng dữ liệu / luồng; `chữ` = chỉ đổi câu chữ.

## 1. Cảnh báo tự động của sổ luật

Nguồn: `uv run python -m scripts.consistency.check --all` — mục "Cảnh báo mockup" (không chặn commit). Hook đầu phiên
in số cảnh báo; khi về 0, hàng này xoá. Hiện: **9** (1 báo nhầm + 8 theo ADR-0012).

| File mockup | Dòng | Luật | Khớp | Xử lý |
|---|---|---|---|---|
| `src/dashboard/mockups/landing.dc.html` | 532 | `ADR0001-coming-soon` | "sắp có" | **Báo nhầm**: nội dung bài gốc tiếng Việt dùng làm dữ liệu mẫu, không phải nhãn trạng thái. Hết khi mockup lấy dữ liệu từ file xuất <!-- consistency: allow ADR0001-coming-soon --> |
| `src/dashboard/mockups/overview-amber.dc.html` | 400, 414 | `ADR0012-old-label-wording` | nhãn chỉ số chia sẻ cũ (KPI + thẻ chỉ số) | "Share rate" (công thức giữ nguyên) — `UI-0012-share-rate-name` |
| `src/dashboard/mockups/overview-amber.dc.html` | 412 | `ADR0012-raw-views-as-reach` | thẻ Popularity gọi views thô là "reach" | "Raw views." — chữ "reach" chỉ dành cho tầng reach (`UI-L20260830-insight-fields`) |
| `src/dashboard/mockups/overview-cyan.dc.html` | 373, 384 | `ADR0012-old-label-wording` | nhãn chỉ số chia sẻ cũ | "Share rate" (hoặc bỏ file — hướng không chọn) |
| `src/dashboard/mockups/design-system.dc.html` | 509, 513 | `ADR0012-old-label-wording` | ý nghĩa màu nhắc chỉ số chia sẻ cũ | "share rate" |
| `docs/design/layout-tiers.dc.html` | 57 | `ADR0012-old-label-wording` | nhãn KPI cũ | "Share rate" |

## 2. Landing so với hợp đồng

`src/dashboard/mockups/landing.dc.html` bản 2026-10-06. 30 điểm lệch của bản 2026-10-05 đã được sửa — Claude Code kiểm
lại bằng tìm chuỗi: không còn `cluster_N`, "n < 10", ARI "rerun same seed", keywords là đầu vào Claude; có "up to 15
posts", "for reading", "named by Claude", "daily 12:30 (machine time)", "every 4h while the machine is awake", hai dòng
loại có mẫu số, mẫu số "of N embedded posts", CTA dashboard trỏ `/overview`, pill `next` + "Preview" ở panel 1, beeswarm
dùng `ResizeObserver`. Còn lại:

| ui-contract id | Vị trí trong landing (dòng) | Hiện tại | Phải là | Mức |
|---|---|---|---|---|
| UI-0017-run-time | 499 (`RUN_AT`), 271, 462 | "2026-10-01 UTC", chỉ có ngày | "clustered <ngày> <giờ> Paris time" (Thy chốt 2026-10-06: lưu UTC, hiện giờ Paris kèm nhãn) | chữ |
| UI-L20260903-small-n-flag | 497–518 (`lowN`) | Cờ giả lập tên `lowN`, chú thích còn trỏ "open question 1" | Cờ mang tên trường backend `insufficient_data` (n < `MIN_N_PER_BUCKET` = 5, không có ngưỡng 10); bỏ chú thích câu hỏi mở | chữ |
| UI-0004-ari-two-ways, UI-0004-dbcv-named | 683–684, khối DBCV | Thiếu trạng thái null | ARI null → "not computed (fewer than 2 posts to compare)"; DBCV null → "not computed (fewer than 2 clusters)" | cấu trúc (nhẹ) |
| UI-L20260903-landing-vs-app-routes | 46, 473, 474 | "Read the methodology", "View the repo" trỏ `#` | URL thật khi deploy (handoff §3.7) — chưa phải lỗi | — |

### Ghi chú cho vòng thiết kế kế tiếp

1. **Dữ liệu landing cần mà API chưa trả:** `representative_ids_json`, `dbcv`, ARI, `run_at`, cờ n nhỏ theo topic —
   endpoint ở brief Việc 3.
2. **Chưa audit theo hợp đồng** `overview-amber.dc.html`, `overview-cyan.dc.html`, `design-system.dc.html`,
   `docs/design/layout-tiers.dc.html` — ngoài cảnh báo tự động ở mục 1. Làm khi các mockup đó vào vòng port.
3. **Claude Code đã sửa trong tài liệu của Claude Design (dữ kiện kỹ thuật, 2026-10-06):** `landing-handoff.md` —
   `src/main.py:258` → `:270` (gói được đóng trước PR #5, làm mất sửa của Claude Code); 4 chỗ "chờ Câu hỏi mở 1 / 3 / 4"
   → id hợp đồng đã chốt. `topics-brief-for-claude-code.md` — 2 dòng "Câu hỏi mở 1 / 2" → "Đã chốt 2026-10-06".
   `brief-ui-contract-review-2026-10-06.md` — gắn `consistency: allow ADR0001-coming-soon` cho 2 dòng trích "sắp có".
4. **Tầng reach (ADR-0012)** chưa có trên mockup nào: `UI-0012-reach-tiers`, `UI-0012-raw-views-reference`,
   `UI-0012-not-tiered` là ràng buộc cho lần thiết kế Analytics / Topics tới.
