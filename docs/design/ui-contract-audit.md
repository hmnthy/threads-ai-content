# Audit mockup theo hợp đồng UI

> Kiểm 2026-10-06 trên gói Claude Design 2026-10-05, theo `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020; mục 1 bổ sung luật ADR-0012).
> **Người đọc:** Claude Design (sửa mockup ở vòng kế tiếp) và Claude Code (khi port). Claude Code **không sửa mockup**
> (ADR-0020). Số liệu cũ trong mockup (số bài, %, median…) không nằm trong audit này — xử lý riêng khi có file xuất
> (brief Việc 4).
> **Mức:** `cấu trúc` = phải đổi component / trạng thái / dạng dữ liệu / luồng; `chữ` = chỉ đổi câu chữ.

## 1. Cảnh báo tự động của sổ luật (bước 0.4)

Nguồn: `uv run python -m scripts.consistency.check --all` — mục "Cảnh báo mockup" (không chặn commit). Hook đầu phiên
in số cảnh báo; khi về 0, hàng này xoá.

| File mockup | Dòng | Luật | Khớp | Xử lý |
|---|---|---|---|---|
| `src/dashboard/mockups/landing.dc.html` | 192, 492, 498–522 (9 dòng), 622, 680 | `ADR0018-cluster-id-display` | id dạng `cluster_N` (13 chỗ) | Đổi sang `topic_N` — xem mục 2 |
| `src/dashboard/mockups/landing.dc.html` | 385 | `ADR0017-nlp-3am` | nhãn lịch giờ đêm của job NLP | "daily 12:30 (machine time)" <!-- consistency: allow ADR0017-nlp-3am --> |
| `src/dashboard/mockups/landing.dc.html` | 524 | `ADR0001-coming-soon` | "sắp có" | **Báo nhầm**: nội dung bài gốc tiếng Việt dùng làm dữ liệu mẫu ("…sắp có thay đổi lớn về học phí…"), không phải nhãn trạng thái. Hết khi mockup lấy dữ liệu từ file xuất <!-- consistency: allow ADR0001-coming-soon --> |
| `src/dashboard/mockups/design-system.dc.html` | 31, 43 | `ADR0009-old-name` | tên sản phẩm cũ | "Unthreaded" |
| `src/dashboard/mockups/overview-amber.dc.html` | 32 | `ADR0009-old-name` | tên sản phẩm cũ | "Unthreaded" |
| `src/dashboard/mockups/overview-cyan.dc.html` | 32 | `ADR0009-old-name` | tên sản phẩm cũ | "Unthreaded" (hoặc bỏ file — hướng không chọn) |
| `src/dashboard/mockups/overview-amber.dc.html` | 400, 414 | `ADR0012-old-label-wording` | nhãn chỉ số chia sẻ cũ (KPI + thẻ chỉ số) | "Share rate" (công thức giữ nguyên) — `UI-0012-share-rate-name` |
| `src/dashboard/mockups/overview-cyan.dc.html` | 373, 384 | `ADR0012-old-label-wording` | nhãn chỉ số chia sẻ cũ | "Share rate" (hoặc bỏ file — hướng không chọn) |
| `src/dashboard/mockups/design-system.dc.html` | 509, 513 | `ADR0012-old-label-wording` | ý nghĩa màu nhắc chỉ số chia sẻ cũ | "share rate" |
| `docs/design/layout-tiers.dc.html` | 57 | `ADR0012-old-label-wording` | nhãn KPI cũ | "Share rate" |
| `src/dashboard/mockups/overview-amber.dc.html` | 412 | `ADR0012-raw-views-as-reach` | thẻ Popularity gọi views thô là "reach" | "Raw views." — chữ "reach" chỉ dành cho tầng reach (`UI-L20260830-insight-fields`) |

## 2. Landing so với hợp đồng (bước 0.5)

`src/dashboard/mockups/landing.dc.html`, đối chiếu mọi dòng hợp đồng có trang `landing` hoặc `all`.

| ui-contract id | Vị trí trong landing (dòng) | Hiện tại | Phải là | Mức |
|---|---|---|---|---|
| UI-L20260903-landing-vs-app-routes | 32, 45, 469 | `<a href="#">View live dashboard</a>` | CTA vào dashboard trỏ `/overview` | cấu trúc (nhẹ) |
| UI-L20260829-mobile | 61–68, 585–597 | Swarm hero xếp chấm theo bề rộng cố định rồi co theo % | Ở ~375px tính lại swarm theo bề rộng thật, hoặc cuộn ngang trong container | cấu trúc |
| UI-L20260903-stack-real-status | 150 | "Groups are compared with an effect size." trong lớp `live` | So sánh nhóm chưa có API (chính dòng 548 ghi "next"): bỏ khỏi lớp `live` hoặc ghi `next` | chữ |
| UI-0018-names-change, UI-0018-label-provenance | 177 | Tên topic viết cứng trong copy | Tên lấy từ dữ liệu theo id `topic_N`, kèm "named by Claude" | cấu trúc |
| UI-0018-id-not-name | 192 | "document · full_text · cluster_N" | `topic_N` | chữ |
| UI-L20260903-stack-real-status | 204, 211, 217, 257, 691 | Panel 1 trình bày như panel dashboard đang chạy, có cột "p, Holm" | Holm chưa có trong code, so sánh theo topic chưa có API: panel gắn `next` / "preview", không trình bày như số live | cấu trúc |
| UI-0018-label-provenance | 215, 226, 289–299, 456 | Tên topic hiện trơn | Tên topic luôn kèm "named by Claude" (hiện chỉ có ở 368, trong panel gập) | chữ |
| UI-0011-excluded | 258 | "N excluded: no views recorded" chỉ nằm trong panel "Method and limits" đang gập | Thấy ngay ở chân khối phân phối, như hero (80, 680) | cấu trúc (nhẹ) |
| UI-0004-noise-basis, UI-0011-two-exclusions | 267 | "For X of Y posts. The other Z fit no cluster" — Y là số bài đo được (sau khi loại views = 0) | Mẫu số gom cụm là `n_units` (bài có `full_text` đã embed); hai điều kiện loại độc lập | cấu trúc |
| UI-0004-noise-basis | 269, 558 | "noise …%" không mẫu số | "noise …% of N embedded posts" | chữ |
| UI-0017-run-time | 263–270, 459 | Không có mốc chạy | Mốc "clustered <ngày giờ>" từ `run_at`, có múi giờ (Câu hỏi mở 4) | cấu trúc |
| UI-0011-two-exclusions | 258, 263–371 | Chỉ có dòng "no views recorded" | Hai dòng loại riêng: "N have no text to embed" và "N excluded from rates: no views recorded" | cấu trúc |
| UI-0018-label-length | 291 | Tên cắt bằng `text-overflow:ellipsis`, không `title` | Cắt thì có tooltip đủ tên (như 226), hoặc xuống dòng | cấu trúc (nhẹ) |
| UI-0018-id-not-name | 300 | `{{ sel.id }}` hiện `cluster_N` | Nếu hiện id thì `topic_N` (hiện hay không: Câu hỏi mở 3) | chữ |
| UI-0011-excluded | 345–358 | Phân phối engagement theo nhóm CMI không có câu loại trừ | "N excluded: no views recorded" khi N > 0 | chữ |
| UI-0016-label-input, UI-0004-representatives | 368 | "Names are written by Claude from the 3 nearest posts" | "up to 15 posts nearest the centre"; tách khỏi khối "3 posts nearest the centre" (bài đại diện để đọc) | chữ |
| UI-0017-nlp-schedule | 385 | Nhãn lịch giờ đêm của khung "WSL2" | "daily 12:30 (machine time)" | chữ |
| UI-L20260829-mobile | 446 | `grid-template-columns:200px minmax(0,1fr)` | Màn hẹp chuyển 1 cột | cấu trúc |
| UI-0018-id-not-name | 492, 498–522 | State chọn và dữ liệu topic khoá theo `cluster_N`, kèm số HDBSCAN `k` | Khoá theo `topic_N`; bỏ `k` (số thứ tự của một lần chạy) | cấu trúc |
| UI-0018-id-not-name | 527–528, 637, 647 | Điểm bản đồ khớp cụm bằng số HDBSCAN (`c === sel.k`) | Mỗi điểm khoá theo `ContentUnitOut.topic.topic_id` (null = nhiễu) | cấu trúc |
| UI-0016-label-input, UI-0018-names-change | 560 | "the 3 posts nearest the centre and the c-TF-IDF keywords are sent to Claude" | Tối đa 15 bài gần tâm, chỉ văn bản bài, không keywords; Claude chỉ được gọi cho cụm cần đặt (lại) tên | chữ |
| UI-0016-label-input | 561 | Stack node Name: `keywords · c-TF-IDF` đứng trước `naming · Claude API` | Keywords là đầu ra hồ sơ cụm, không phải đầu vào của Claude — đổi nhãn hoặc tách | chữ |
| UI-0016-label-input, UI-0018-names-change | 563 | "Called once per cluster, with that cluster's representative posts and keywords." | Chỉ gọi cho cụm cần đặt (lại) tên, với tối đa 15 bài gần tâm, không keywords | chữ |
| UI-0018-id-not-name | 622 | `t.id === 'cluster_N'`; `small = t.v.length < 10` | Khoá theo `topic_N`; ngưỡng mẫu nhỏ đọc cờ từ backend (Câu hỏi mở 1) | cấu trúc |
| UI-0004-ari-two-ways | 650 | ARI "Rerun, same data and seed" | Không code nào tạo ARI này — bỏ | cấu trúc |
| UI-0004-ari-two-ways | 653 | "Across 10 seeds · RQ-01" nằm trong danh sách số, giá trị "—" | Chỉ giữ dạng chú thích research (đã có ở 334), không đặt vào danh sách số | cấu trúc (nhẹ) |
| UI-0018-id-not-name, UI-0018-names-change | 680 | Chú thích hero chế độ Topic: tên cứng + `cluster_N` | Tên và id lấy từ dữ liệu (`topic_N`); câu loại trừ views = 0 vẫn giữ | chữ |
| UI-0018-names-change | 691 | Câu đọc mặc định viết cứng tên topic dẫn đầu | Ghép từ dữ liệu theo id | cấu trúc |
| UI-0020-contract-gate | cả file | Mockup/handoff chưa ghi id `UI-…` nào | Mỗi quyết định cấu trúc trong handoff ghi id hợp đồng mà nó tuân theo | chữ (handoff) |

### Landing đã đạt

UI-0001-dropped-scope (198) · UI-0001-status-labels (148, 169, 187, 343, 423, chú giải 438–440) · UI-0001-kb-next
(187–193, 565–567) · UI-0001-classifier-research (568–570, cạnh chấm 404) · UI-0004-full-text-scope (138, 542) ·
UI-0004-representatives — phần khối (309–315) · UI-0004-dbcv-named (269, 367, 558) · UI-0004-ari-two-ways — nhãn
651–652 · UI-0004-noise-basis — hàng nhiễu riêng (239, 247) · UI-0009-display-name · UI-0009-tagline ·
UI-0009-meta-disclaimer (484, khớp chuỗi test) · UI-0010-sqlite-only (379, 545, 567) · UI-0011-excluded — hero (80,
680) · UI-0016-no-old-model — không tên model · UI-0016-no-caching-claim · UI-0018-label-length — 226 có `title` ·
UI-L20260903-landing-vs-app-routes — navbar riêng (22–33) · UI-L20260903-stack-real-status — thẻ chưa live nhìn rõ
(187, 565, 568) · UI-L20260830-english-ui · UI-L20260830-six-indices · UI-L20260830-insight-fields (103, 540) ·
UI-L20260830-engagement-formula (85) · UI-L20260829-mobile — sơ đồ/bảng cuộn ngang trong container (133, 213, 382) ·
UI-0004-centroid-similarity (177, 313, 367).

### Ghi chú cho vòng thiết kế kế tiếp

1. **Làm mờ topic n < 10** (258, 490, 618, 622) chưa phải vi phạm — chờ Câu hỏi mở 1 của hợp đồng. Dù chốt số nào, UI
   đọc cờ từ backend.
2. **Dữ liệu landing cần mà API chưa trả:** `representative_ids_json`, `dbcv`, ARI, `run_at` — endpoint ở brief Việc 3.
   Mockup chưa có trạng thái null cho DBCV (< 2 cụm) và ARI (< 2 bài để so).
3. **"every 4h" (386, 459)** ngụ ý snapshot đều đặn; thực tế chỉ chạy khi máy thức (UI-0017-night-gaps, áp cho
   overview/analytics). Cân nhắc ghi "every 4h while the machine is awake".
4. Chưa audit `overview-amber.dc.html`, `design-system.dc.html`, `docs/design/layout-tiers.dc.html` theo hợp đồng —
   ngoài cảnh báo tự động ở mục 1. Làm khi các mockup đó vào vòng port.
