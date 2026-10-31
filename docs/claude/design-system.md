# Design System — Unthreaded

> **Đọc khi**: làm việc trong `src/dashboard/`, hoặc bất kỳ UI/frontend/mockup/artifact nào của dự án.
> **Đây là nguồn sự thật DUY NHẤT về design.**
> **Phiên bản**: v3.2 — 2026-10-01 (Amber, giữ nguyên sau khi so 4 palette; thêm token dải tối + cấu trúc landing tầng B). v3.1 — 2026-09-03 thay violet của v3. Lý do đầy đủ ở [§13 Decision log](#13-decision-log).
> Tagline chính thức: **"The algorithm, read back to you."**
> Trang xem được: `src/dashboard/mockups/design-system.dc.html` (style guide), `src/dashboard/mockups/overview-amber.dc.html` (hướng chốt app, timeline kéo được), `src/dashboard/mockups/landing.dc.html` (landing tầng B đã chốt, 2026-10-01).

---

## 0. Thứ tự ưu tiên khi có mâu thuẫn

1. File này (v3.2).
2. [`../design/dashboard-reference.png`](../design/dashboard-reference.png) — **chỉ còn dùng cho cấu trúc/hình khối** (tầng A app shell vs tầng B landing, §7), KHÔNG còn dùng cho màu — xem §13 vì sao rời khỏi violet mà PNG gợi ý.
3. Bất kỳ nguồn nào khác, kể cả default palette của model.

**Light mode là chế độ duy nhất trong scope.** Không tự thêm block `@media (prefers-color-scheme: dark)` khi chưa có yêu cầu. Không hex rời — mọi màu là CSS variable khai báo ở §2.

---

## 1. Vì sao rời khỏi violet

Reference PNG dùng violet/indigo — v3 làm theo. **v3.1 bỏ violet, dùng amber.** Lý do: violet/indigo là màu mặc định của gần như mọi AI SaaS 2024–2026. Reference PNG vốn là một landing page SaaS generic, nên đi theo nó là thừa hưởng cái generic từ nguồn. Sản phẩm này cần đọc như **công cụ đo đạc**, không đọc như AI productivity app.

Hai hướng đã dựng thật để so sánh (không phải chọn trên giấy):

| Hướng | File | Kết quả |
|---|---|---|
| Electric cyan trên nền gần đen | `src/dashboard/mockups/overview-cyan.dc.html` | Không chọn. Giữ lại để đối chiếu. |
| **Amber trên neutral lạnh** | `src/dashboard/mockups/overview-amber.dc.html` | **Chọn.** |

Ràng buộc phát hiện khi dựng: cam rực `#F59E0B` **không dùng được cho chữ** trên nền sáng. Accent tương tác phải hạ xuống `#B45309`. Cam rực chỉ còn dùng cho fill/bar.

---

## 2. Color tokens

### 2.1 Neutral lạnh

| Token | Hex | Dùng |
|---|---|---|
| `--bg-page` | `#FBFBFC` | Nền trang |
| `--bg-card` | `#FFFFFF` | Card tầng A |
| `--bg-surface` | `#F1F3F6` | Nút phụ, input, header bảng, track bar |
| `--bg-sunken` | `#FAFAFB` | Card trạng thái deferred/disabled |
| `--border-hairline` | `rgba(17,24,39,0.10)` | Viền tầng A |
| `--rule` | `#E4E8ED` | Đường timeline, vạch mốc |
| `--chart-dot` | `#9AA3AE` | Chấm trung tính trên strip/bản đồ landing (không dùng cho chữ) |
| `--chart-dot-faint` | `#CBD2DA` | Chấm nền mờ (mini map), viền thẻ `next` |

### 2.2 Chữ — đã kiểm contrast trên `#FBFBFC`

| Token | Hex | Tỉ lệ | Dùng |
|---|---|---|---|
| `--text-primary` | `#111827` | 16.1:1 | Body, số liệu, tiêu đề |
| `--text-secondary` | `#4B5563` | 7.0:1 | Mô tả, nhãn phụ, tab chưa chọn |
| `--text-muted` | `#6B7280` | 4.8:1 | Công thức mono, metadata, nhãn trục |

**Sự cố đã xảy ra, đừng lặp lại:** bản amber đầu tiên được tạo bằng cách thay thế cơ học màu từ bản cyan, kéo theo `#8892A0` (3.15:1) làm tier muted → fail AA. Token muted của nền tối KHÔNG dùng lại được trên nền sáng.

### 2.3 Amber

| Token | Hex | Tỉ lệ | Dùng |
|---|---|---|---|
| `--amber-soft` | `#FEF3C7` | — | Nền badge active |
| `--amber-fill` | `rgba(245,158,11,0.42)` | — | Bar, fill chart |
| `--amber-600` | `#B45309` | 4.9:1 | **Tương tác** — nút chính, link, focus ring, tay cầm timeline. Đo lại 2026-10-01 trên `#FBFBFC` (bản cũ ghi 5.9:1 là sai) — vẫn đạt AA, không dùng dưới 12px |
| `--amber-700` | `#92400E` | 8.2:1 | Link hover |

Trên nền gradient tối, nhãn dùng `#FFF6EC` (~4.7:1). `#FDE7C7` từng dùng chỉ đạt 4.17:1 → đã bỏ.

### 2.4 Trạng thái

| Nghĩa | Hex | Tỉ lệ |
|---|---|---|
| Dương / live | `#15803D` | 4.9:1 |
| Âm / lỗi | `#C42A2F` | 5.1:1 |

**Màu không bao giờ là tín hiệu duy nhất.** Delta kèm ↑↓, trạng thái kèm chữ.

### 2.5 Gradient — đúng một lần trong toàn hệ thống

```css
linear-gradient(135deg, #7C2D12 0%, #B45309 52%, #9A3412 100%)
```

Dùng ở **dải hero đầu trang Overview**, chứa chỉ số engagement rate của cửa sổ đang chọn. Cả ba stop đủ tối để chữ trắng đạt AA. Không dùng gradient ở bất kỳ chỗ nào khác (kể cả tầng B landing) — sang trọng đến từ sự hiếm; trải khắp card là mất ngay.

### 2.6 Dải tối (chỉ tầng B landing)

Dùng cho đúng 2 dải trên landing: sơ đồ "How it works" và khối CTA cuối. Đây là đổi nền để phân tầng, không phải dark mode.

| Token | Giá trị | Tỉ lệ trên `#111827` | Dùng |
|---|---|---|---|
| `--dark-bg` | `#111827` | — | Nền dải (= `--text-primary`) |
| `--dark-text` | `#FFFFFF` | 17.7:1 | Tiêu đề, tên node |
| `--dark-text-secondary` | `rgba(255,255,255,0.78)` | ~11:1 | Đoạn mô tả |
| `--dark-text-muted` | `rgba(255,255,255,0.72)` | ~9.6:1 | Nhãn mono, nhãn cạnh |
| `--dark-node` | `rgba(255,255,255,0.06)` | — | Nền node |
| `--dark-line` | `rgba(255,255,255,0.14)` / `0.32` | — | Viền node / cạnh chưa chọn |
| `--amber-on-dark` | `#F59E0B` | 8.3:1 | Eyebrow, cạnh + node đang chọn, nút chính CTA (chữ `#111827`) |
| `--amber-on-dark-fill` | `rgba(245,158,11,0.14)` | — | Nền node đang chọn |
| `--amber-on-dark-text` | `#FFF6EC` | — | Giá trị mono trong bảng stack |

---

## 3. Typography

Inter cho UI. **IBM Plex Mono cho công thức, ID, timestamp** — đây là dấu ấn typographic của sản phẩm, không phải trang trí.

**Một thang chữ cho toàn sản phẩm** — landing và mọi trang app (Thy chốt 2026-10-30, sau khi thấy landing và
/topics ra 2 "giọng" vì thang cũ chỉ viết cho tầng A: tiêu đề khối landing 13px, nhỏ hơn câu trả lời 24px nó dẫn). Mở rộng thang tầng A
Thy chốt 2026-10-29 sau 2 lần bác bản /topics: **tiêu đề luôn lớn hơn nội dung nó dẫn**, để người đọc nhanh quét
theo tiêu đề mà không sót khối. Mỗi cỡ một vai, không cỡ nào khác (luật T1–T4 ở §3b); hằng số `TYPE` trong
`src/dashboard/src/components/AppBlock.tsx`. Landing chỉ thêm 2 bậc trưng bày ở đỉnh thang (display-1, display-2 —
danh sách trắng X1), không thêm bậc giữa.

```
vai               cỡ                          độ đậm         tag app / landing   dùng
display-1         clamp(44px, 6.4vw, 76px)    w800 -0.04em   — / h1              H1 hero landing (duy nhất)
display-2         clamp(32px, 3.6vw, 46px)    w800 -0.035em  — / h2              tiêu đề section landing, kể cả About + CTA
metric-hero       56px tabular                w700 -0.03em   không phải heading  số trong dải hero gradient Overview
h1 page title     40px                        w700 -0.025em  h1 / —              tiêu đề trang app, đầu trang căn giữa (Thy 2026-10-29) —
                                                                                 trên nó eyebrow trang (label 12px w600 amber), dưới câu hỏi
                                                                                 trang 18px, chip mốc dữ liệu, dải mục lục khối 15px
metric            28px tabular                w700 -0.02em   không phải heading  số KPI (strip Overview, hàng số hero landing), số chính
                                                                                 trong hộp Key numbers (K2)
h2 block title    26px                        w700 -0.02em   h2 / h3             tiêu đề khối (app) = tiêu đề panel/khối của landing: trên nó
                                                                                 eyebrow khối = số mono 12.5px + tên ngắn label 12px (cùng chữ với
                                                                                 mục lục); dưới câu mục đích 15px + kẻ đậm 2px
h3 section        20px                        w600           h3 / h4             mục trong khối (kẻ mảnh phía trên), chữ trơn — link định nghĩa
                                                                                 đặt ở dòng ghi chú dưới
answer · lead     18px                        w600 · w400    —                   câu trả lời (khung nhấn viền trái amber + nhãn "ANSWER") · câu
                                                                                 dẫn dưới h1 / display-2
h4 box title      17px                        w600           h4 / h5             tiêu đề hộp con (Key numbers, What to know, How it is computed,
                                                                                 Limits)
body              15px  lh 1.6                w400 · w600    —                   thân bài, gạch đầu dòng, nhãn hàng của bảng số · nhãn dưới
                                                                                 số trong hộp Key numbers
note · cell · control 13px                    w400 · w600    —                   ô bảng, ghi chú phụ, chú giải · chữ trên nút/tab/pill bấm được
                                                                                 (như nút "Method and limits" của `AppBlock.tsx`)
mono · eyebrow số 12.5px mono lh 1.7          w400 · w600    —                   công thức, ID, số trong bảng · eyebrow có số, amber: số khối,
                                                                                 `01 · Problem` của section landing — chỉ mono
label · th        12px                        w500–600       —                   header cột bảng, nhãn nhỏ, pill trạng thái, nhãn trục biểu đồ,
                                                                                 eyebrow chữ (eyebrow trang "TOPIC ANALYSIS", tên ngắn của khối)
formula script    0.8em (≈10px)               —              `sub`/`sup`         chỉ số dưới/trên trong `Formula` — không dùng ngoài công thức
```

Tập cỡ hợp lệ (px): **12 · 12.5 · 13 · 15 · 17 · 18 · 20 · 26 · 28 · 40 · 56**, cộng 2 khoảng display trên h1/h2 của
landing. Tag landing lệch 1 cấp so với app vì landing có thêm tầng section (display-2 là `h2`): cùng **vai** thì cùng
cỡ, độ đậm, màu, dù tag khác. Chữ trong SVG biểu đồ cũng thuộc thang (nhãn trục 12px). Cỡ fluid (`clamp`) chỉ dành
cho display-1/2 — mọi vai khác cố định, kể cả trên 375px (body 15px ≥ 14px tối thiểu của §12).

Khoảng cách: khối cách nhau 40px; trong khối, mục h3 cách nhau 28px có kẻ mảnh. Chữ chạy hết bề rộng khung chứa —
không chừa khoảng trắng bên phải (Thy 2026-10-29, thay quy tắc 72ch). Không hộp viền lồng trong hộp.

**Ba lớp màu nền trên trang app** (Thy 2026-10-29) — mỗi lớp một vai, người đọc biết đang ở lớp nào:
- **Kết quả** — khung ANSWER, hộp Key numbers: `--warm-surface` `#FFFAF0` + viền `--warm-border` `#F3DFB5` (ANSWER
  thêm viền trái amber 4px). Hộp số cao theo nội dung và dính theo khi cuộn (luật K3).
- **Kỹ thuật** — nội dung "Method and limits", chú giải bảng: `--bg-sunken` + viền hairline. Cách tính rồi giới hạn,
  xếp dọc (không 2 cột song song).
- **Bằng chứng** — biểu đồ, bảng: nền trắng của card.

**Nhấn chữ**: nhãn trong hộp số in đậm (w600); trong gạch đầu dòng, in đậm tối đa 1 cụm then chốt mỗi ý bằng `**…**`
(hàm `rich` trong `AppBlock.tsx`) — không in đậm cả câu, không tô màu chữ để nhấn. Trang phân tích dài có dải mục lục
khối (số + tên) dưới tiêu đề trang.

Mọi con số dùng `font-variant-numeric: tabular-nums`, định dạng **en** (`18,420`) — thay cho `toLocaleString('vi-VN')` từng dùng ở v3 (xem §13, quyết định 2026-09-02: UI hướng ra ngoài dùng tiếng Anh, nội dung post giữ tiếng Việt). Không uppercase tiếng Việt.

---

## 3b. Sổ luật UI/UX — áp cho MỌI trang

Thy chốt 2026-10-30: một bộ luật cho landing và mọi trang app, để chất lượng trình bày không phụ thuộc phiên làm việc
nào dựng trang. Mỗi luật có mã — `@agent-ux-reviewer` trích mã ở mọi lỗi; mã không đổi nghĩa khi sửa file này (thêm
luật = mã mới). Cách kiểm:

- **[máy]**: `src/dashboard/scripts/ux-shots.mjs` đo trên trang đã render, ghi vào `violations` (từng trang,
  từng khổ) và `crossRoute` (T3 giữa các trang) của `report.json`; mỗi mục có `key` ổn định (luật + vị trí) để gộp
  giữa các khổ. Còn ≥ 1 vi phạm [máy] thì UX gate FAIL — reviewer không được hạ.
- **[máy·gợi ý]**: script ghi vào `warnings`. Đây là phép đo gần đúng; reviewer nhìn ảnh rồi xác nhận hoặc bác.
- **[mắt]**: reviewer chấm trên ảnh chụp và code.

Cổng chặn commit cho các luật này **chưa** bật (Thy 2026-10-30: 2 lớp — reviewer + máy đo trong script chụp ảnh).

### T — Chữ

- **T1 [máy]** Chỉ dùng cỡ trong thang §3. Cỡ fluid chỉ cho `h1`/`h2` của landing, nằm trong khoảng display-1/2.
- **T2 [máy]** Không chữ < 12px. Ngoại lệ duy nhất: `sub`/`sup` trong công thức.
- **T3 [máy]** Heading đúng cỡ của vai (bảng §3): app `h1` 40 · `h2` 26 · `h3` 20 · `h4` 17; landing `h1` display-1 ·
  `h2` display-2 · `h3` 26 · `h4` 20 · `h5` 17. Cùng vai ⇒ cùng cỡ, độ đậm và màu trên mọi trang.
- **T4 [máy]** Tiêu đề lớn hơn mọi chữ nó dẫn. Cỡ của heading phải lớn hơn cỡ lớn nhất của chữ thường đứng sau nó,
  cho tới heading cùng cấp hoặc cao hơn kế tiếp. Không tính số metric (tabular, 28/56px): số KPI là dữ liệu, nhãn
  dưới nó là chú thích, không phải tiêu đề.
- **T5 [máy]** Tiêu đề là thẻ heading thật: mỗi trang đúng 1 `h1`, không nhảy cấp (`h2` → `h4`). Đây cũng là WCAG
  1.3.1 / 2.4.6: trình đọc màn hình đi theo heading. Tag lệch vai mặc định thì khai `data-ux-role="<vai>"` (VD hộp
  "What to know" ngay dưới `h2` là `h3` mang vai box-title). Giá trị hợp lệ chỉ có 6 vai heading: `display-1`,
  `display-2`, `page-title`, `block-title`, `section`, `box-title`. Không dùng thuộc tính này để che heading sai cấp:
  cha của mỗi heading (heading gần nhất phía trên có tag nông hơn) phải mang vai cha hợp lệ:
  - display-2 dưới display-1;
  - block-title dưới page-title hoặc display-2;
  - section dưới block-title;
  - box-title dưới block-title hoặc section.

  VD `h2` block-title ngay sau `h2` display-2 có cha là `h1` display-1 → vi phạm.
- **T6 [máy·gợi ý]** Card/panel có > 200 ký tự mà không chứa heading → nghi có "tiêu đề giả". **[mắt]** Một dòng chữ
  đậm hoặc màu đứng đầu khối mà không phải heading là tiêu đề giả → **chặn**: đổi thành heading đúng vai.
- **T7 [mắt]** In đậm tối đa 1 cụm mỗi ý. Không in đậm cả câu, không tô màu chữ để nhấn (§3 "Nhấn chữ").

### L — Bố cục và nhịp

- **L1 [máy]** Không cuộn ngang toàn trang ở 375 / 1024 / 1440px.
- **L2 [máy·gợi ý]** Không có thanh cuộn lồng trong khối chỉ vì tràn vài px. Chữ cách mép card ≥ 12px.
- **L3 [mắt]** Khoảng trắng phía trên tiêu đề ≥ 1.5 lần khoảng phía dưới, để tiêu đề "dính" vào phần nó dẫn (luật gần
  nhau). Khoảng cách là bội của 4px (§4).
- **L4 [mắt]** Mỗi tầng một khung lề: app 1280px, landing 1200px. Header và thân thẳng với Nav.
- **L5 [mắt]** Không khoảng trắng lớn vô cớ: khối trải đủ bề rộng, hoặc cột bên kia có nội dung. Không đặt 2 khối
  chữ dày cạnh nhau. Chữ chạy hết bề rộng khung chứa. Chỗ trống dưới hộp Key numbers dính ở cột phụ (K3) là được phép.

### C — Khối và mạch đọc

- **C1 [mắt]** Mọi khối nội dung, kể cả panel của landing, đi theo thứ tự: eyebrow → tiêu đề → câu mục đích → câu
  trả lời → bằng chứng (biểu đồ/bảng) → "Method and limits".
- **C2 [mắt]** Một vai, một component dùng chung. Section, mục, khung câu trả lời, hộp số, Method and limits và chú
  giải lấy từ `AppBlock.tsx`. Không định nghĩa lại cỡ chữ hay kiểu nút tại chỗ cho một vai đã có component; vai mới
  thì thêm vào `AppBlock.tsx` trước, rồi mới dùng. Component có heading nhận prop cấp tiêu đề, để landing render cùng
  vai ở tag sâu hơn 1 cấp (X1) mà không phải viết lại component.
- **C3 [mắt]** Thứ bấm được trông bấm được: viền hoặc nền, chevron, hover, `aria-expanded` cho biết trạng thái. Nút
  "Method and limits" có cùng một kiểu trên mọi trang.
- **C4 [máy]** Vùng chạm ≥ 44×44px cho nút, tab, toggle, slider. Vùng chạm là khung của chính phần tử bấm được (phần
  nhìn thấy có thể nhỏ hơn, như tay cầm timeline §5). Vùng nới bằng `::before` hay padding của phần tử cha không tính.
- **C5 [mắt]** Khối có dữ liệu thì có đủ loading / empty / error (§6, §9).

### N — Số và công thức

Áp cho landing như trang app. Luật chi tiết ở `.claude/rules/dashboard.md`, mục "Trình bày như nhà nghiên cứu NLP".

- **N1 [mắt]** Không số trần: mỗi số trả lời được 3 câu: là gì, tính thế nào, vì sao quan trọng.
- **N2 [mắt]** Mỗi phương pháp được nêu tên phải có công thức kèm nghĩa của từng ký hiệu. Dòng mono chỉ có tham số
  chỉ được là lớp phụ, đặt dưới phần giải thích.
- **N3 [mắt]** Nhãn phân loại (kết quả, trạng thái) có chú giải ngay cạnh, và khác nhau thấy được bằng chữ kèm ký
  hiệu hoặc màu, không cần hover.
- **N4 [mắt]** Số chính là median + IQR + n, không mean (§7).

### K — Hộp số (Key numbers)

Thy chốt 2026-10-31 (ADR-0030), sau khi thấy các hộp số lệch nhau giữa các trang: hộp bị kéo theo chiều cao cột bên
cạnh rồi rải khoảng thừa giữa các dòng, cùng một vai có 2 kiểu hộp và 2 tên, số 15px bằng cỡ nhãn nên không nổi.

- **K1 [máy]** Một vai, một component, một tên. Mọi hộp số (nền ấm, chứa danh sách `dl`) là `KeyNumbers` của
  `AppBlock.tsx`, đánh dấu `data-ux="key-numbers"`, tiêu đề vai box-title đúng chữ "Key numbers". Hộp nói về phạm vi
  hẹp hơn khối chứa nó (VD topic đang chọn) thì ghi phạm vi ở dòng ngay trên tiêu đề: label 12px w600 chữ hoa, VD
  `SELECTED TOPIC · Career & alternance`. `data-ux` gắn lên hộp (khung nền ấm hoặc phần tử bọc nó, khi dòng phạm vi
  nằm ngoài khung). Component phải gắn `data-ux="kn-value"` / `data-ux="kn-label"` cho số và nhãn (PR 2), để máy chọn
  đúng phần tử thay vì đoán theo thứ tự. Máy kiểm component + tiêu đề; dòng phạm vi do reviewer chấm bằng mắt.
- **K2 [máy]** Mỗi dòng: số chính metric 28px tabular w700, đứng riêng một dòng, căn trái → nhãn 15px w600 ngay dưới
  → ghi chú 13px. Tối đa 4 số mỗi hộp; nhiều hơn thì dùng bảng. Máy đo số, nhãn và số dòng; cỡ ghi chú do reviewer
  chấm.
- **K3 [máy]** Hộp cao theo nội dung. Không kéo giãn, không rải khoảng thừa: danh sách không dùng `justify-content`
  kiểu `space-*` hay dòng `flex-grow`; khoảng giữa các dòng bằng nhau (lệch ≤ 4px); đáy hộp cách chữ cuối không quá
  padding + 8px. Hộp ở cột phụ (ô hẹp hơn ô rộng nhất cùng hàng của lưới ≥ 2 cột gần nhất — từ 1024px với
  `AnswerRow`) dính theo khi cuộn, khi hàng có thứ cao hơn hộp (hộp cao nhất hàng thì không cần): `position: sticky` +
  `top` ở khung hoặc phần tử bọc nó, phần tử đó còn chỗ trống bên dưới trong khối chứa nó (khối chứa của ô lưới là cả
  lưới — ô bị kéo giãn ở hàng cuối, hay khung sticky sát đáy phần tử bọc, đều không trượt được; dùng `self-start`), và
  không tổ tiên nào có `overflow` khác `visible`/`clip`. Ô dính trượt trong cả lưới, không chỉ trong hàng của nó: lưới
  chỉ chứa hàng của hộp — khối trải bên dưới (`below` của `AnswerRow`) đặt ngoài lưới, không thì hộp trượt đè lên nó.
  Chỗ trống dưới hộp khi đó là chỗ trống tự nhiên (L5); xếp chồng 1 cột thì không cần dính. Máy chỉ xét lưới CSS; cột
  phụ dựng bằng flex do reviewer chấm. Sửa phép đo K thì chạy `node scripts/ux-shots-fixtures.mjs` (trang mẫu đúng/sai).
- **K4 [mắt]** Số là một phần của số đứng trước (VD 169 bài → 163 có chữ → 110 vào topic) có thanh tỉ lệ 4px kèm chữ
  "N% of <số cha>" dưới nhãn. % tính bằng số nguyên trước khi chia (`Math.floor(a * 100 / b)`). Thanh chỉ để nhìn
  (`aria-hidden`); chữ % mang thông tin, nên màu không là tín hiệu duy nhất (A2).
- **K5 [mắt]** Một kết quả thống kê là một dòng: số chính là median, ghi chú là IQR + n (VD "Middle half 1.77–3.08%
  (IQR), n = 16"); n = 0 thì hiện "—" (N4). Không tách median, IQR, n thành 3 dòng.
- **K6 [mắt]** Căn phải chỉ dành cho cột số cùng đơn vị trong bảng (tabular-nums, để hàng đơn vị thẳng hàng khi so).
  Hộp số luôn căn trái: các số trong hộp khác đơn vị, không ai so chúng theo cột, và ghi chú + thanh tỉ lệ bám cùng
  mép trái với số.

### B — Người đọc và ngôn ngữ

- **B1 [mắt]** Ba người đọc: Thy, người không chuyên (thường không đọc tiếng Việt), người chuyên môn DS/MLE. Đọc lại
  trang 3 lượt, mỗi lượt một vai.
- **B2 [mắt]** Chữ gốc tiếng Việt hoặc tiếng Pháp luôn có ngữ cảnh tiếng Anh trên cùng dòng.
- **B3 [mắt]** Thuật ngữ được định nghĩa trước khi dùng. Không để mã nội bộ trần (`topic_N`, `RQ-01`).

### A — Tiếp cận (WCAG 2.2 AA)

- **A1 [máy]** axe-core (bộ kiểm tra tiếp cận tự động, chuẩn ngành) báo 0 lỗi mức `serious`/`critical` trong các luật
  WCAG 2.x A/AA: tương phản 4.5:1 cho chữ và 3:1 cho chữ lớn, tên của nút, ARIA, kích thước vùng chạm tối thiểu
  24px. Thứ tự heading là luật `best-practice` của axe, không nằm trong A1 — T5 kiểm thay.
- **A2 [mắt]** Focus ring 2px `--amber-600` thấy được. Màu không bao giờ là tín hiệu duy nhất.
  Tôn trọng `prefers-reduced-motion` (§8).

### X — Khác biệt được phép của landing (danh sách trắng)

Landing chỉ được khác trang app ở các điểm dưới đây. Điểm nào không có trong danh sách thì dùng luật chung.

- **X1** display-1 cho H1 hero, display-2 cho tiêu đề section. Tag lệch 1 cấp: `h3` landing = vai "tiêu đề khối" 26px.
- **X2** 2 dải tối (§2.6).
- **X3** Panel bo 20px, bento card (§7).
- **X4** Khoảng cách giữa các section rộng hơn tầng A (vẫn là bội của 4px).
- **X5** "Method and limits" có thể thu gọn mặc định, vì landing là trang giới thiệu. Nút vẫn theo C3, và bên trong
  vẫn theo N1–N2.
- **X6** Khung nội dung 1200px; Nav riêng (`LandingNav`).

---

## 4. Hình khối

| Element | Radius |
|---|---|
| Nút, badge, tab, chấm tay cầm | `999px` |
| Card tầng A | `12px` + hairline |
| Dải hero gradient, khối Author | `20px` |
| Input | `10px` |

Phân tầng bằng đổi nền, không đổ bóng. Ngoại lệ: bóng nhẹ trên chấm tay cầm timeline (`0 1px 4px rgba(17,24,39,0.20)`) để nó tách khỏi đường ray.

Spacing 4px: `4/8/12/16/20/24/32/40/48`. Section cách nhau 40px.

---

## 5. Timeline brush — thành phần chữ ký

Đây là interaction riêng của sản phẩm, không phải date-picker.

**Hình thức:** một đường 2px `--rule` chạy hết chiều ngang. Đoạn đang chọn là vệt `--amber-600` trên chính đường đó. Hai đầu là chấm 13px trắng viền amber 2px. 13 vạch mốc mảnh bên dưới, vạch trong cửa sổ chuyển amber nhạt.

Không dùng khối bar biểu đồ thu nhỏ, không dùng khung chữ nhật có nền.

**Hành vi:**
- Kéo hai chấm để co giãn; kéo vệt giữa để trượt.
- Preset 30d / 60d / 90d / Peak week; pill sáng lên khi cửa sổ khớp preset.
- Cửa sổ tối thiểu 5 ngày.
- Tab tới từng chấm, phím mũi tên dịch 1 ngày. `role="slider"` + `aria-valuetext` là ngày thật.

**Đồng bộ dữ liệu:** mọi KPI, dải hero, danh sách top posts và số content unit đều tính lại từ cửa sổ. Không có số cứng nào trên trang.

**Chuyển động:** số **không** count-up khi đang kéo — phải bám tay theo thời gian thực. Count-up chỉ dùng lần load đầu.

**Vùng chạm:** rail cao 44px, mỗi tay cầm rộng 44px, dải kéo cao 44px — dù phần nhìn thấy chỉ 13px và 2px.

---

## 6. Component

- **KPI strip** — hàng ngang phẳng, không bọc card. Nhãn 12px + chấm màu nếu có series trên chart, số 28px tabular, **dòng công thức mono bên dưới** thay cho delta khi cần lộ phương pháp.
- **Metric card** — 6 index trong lưới 3 cột. Tên 15px, badge trạng thái, công thức mono, một dòng giải thích. Card deferred dùng `--bg-sunken` và tên màu muted.
- **Content unit row** — số thứ tự 2 chữ số, tiêu đề 15px (body) hiển thị đầy đủ (không cắt bằng ba chấm), dòng metadata, bar 220px, số bên phải 15px.
- **Bảng** — header 12px w600 (vai label · th, §3), không uppercase, không zebra striping, hover đổi nền.
- **Trạng thái chart** — bắt buộc có loading (skeleton, không spinner), empty (nói rõ lệnh cần chạy), error (message + retry).
- **Icon** — Phosphor regular 18–20px. Không emoji.

---

## 7. Layout — hai tầng, không trộn

**Tầng A · App shell** (ưu tiên — `src/dashboard/`, sản phẩm thật): `max-width 1280`, padding 24. Thứ tự dọc: topbar (logo + tagline + account pill + avatar) → tab pill → **dải hero gradient** → chart + timeline brush → KPI strip → metric architecture → top content units. Top nav tab pill, không sidebar.

Mỗi trang app trả lời đúng 1 câu hỏi chính (ADR-0023): `/overview` — kênh đang thế nào trong cửa sổ đã chọn? ·
`/analytics` — bài nào, giờ nào hiệu quả? · `/topics` — kênh viết về gì, và chủ đề có liên quan tới engagement không?
Mỗi khối nội dung tầng A đi theo thứ tự đọc của landing: **câu hỏi → câu trả lời 1 dòng → bằng chứng (chart/bảng) →
"Method and limits"** (công thức, phương pháp, n, giới hạn) — nhưng **giữ hình khối tầng A**: card 12px có viền
hairline trên nền sáng, không dải tối, không dùng display-1/2 của landing. Câu trả lời chỉ khẳng định khi phép so có ý nghĩa
sau hiệu chỉnh Holm **và** qua luật bền qua các cách chia cụm (ADR-0024 — chưa có luật nên hiện chưa có câu khẳng định);
tới lúc đó phép so hiện dạng khám phá (giới hạn trong "cách chia hiện tại", δ + CI unadjusted + p Holm, câu giới
hạn); không đạt thì mô tả ("not distinguishable"). Số chính là median + IQR + n, không hiện mean.

**Tầng B · Landing** — chốt 2026-10-01, mockup `src/dashboard/mockups/landing.dc.html`, spec port ở `docs/design/landing-handoff.md`. Trang giới thiệu tool cho portfolio; pricing, FAQ, Login/Register **ngoài scope** (không phải SaaS); landing thương hiệu thydilammuon là việc của roadmap Phase F, cần ADR riêng.

Thứ tự: navbar pill sticky → **Hero** (H1 tagline + panel bằng chứng: beeswarm 144 bài, bài hero amber, toggle Channel/Topic) → **Problem** (3 câu hỏi của người làm kênh, mỗi câu "Threads shows / Missing") → **How it solves** (3 tầng Measure · Group · Search nối bằng mũi tên, theo 1 bài thật) → **Product proof** (2 panel dashboard: chủ đề so với kênh; kết quả NLP) → **How it works** (sơ đồ trên dải tối §2.6, bấm node xem stack) → **About the channel** → **CTA** (dải tối) → footer có câu miễn trừ Meta.

Mỗi panel bằng chứng theo thứ tự đọc chung C1 (§3b): eyebrow → tiêu đề panel (`h3`, vai h2 block title 26px) → câu mục đích 15px →
câu trả lời 1 dòng (answer 18px, khung nhấn) → biểu đồ → nút "Method and limits" mở công thức + giới hạn (X5). Tiêu
đề section landing: display-2 `h2`; eyebrow mono 12.5px amber dạng `01 · Problem`. Cỡ chữ theo thang chung §3 —
landing không có thang riêng (Thy 2026-10-30).

<details><summary>Thứ tự section đo từ reference PNG (lịch sử, không còn dùng)</summary>


1. Floating navbar — pill căn giữa, cách mép trên 16px: logo tròn · menu · Login · nút Register
2. Hero — badge pill nhỏ ("NEW · …") → H1 2 dòng → sub 2 dòng → 2 nút pill (primary + secondary)
3. Logo strip — 6 logo grayscale, opacity ~50%
4. Tab pills + ảnh app trên nền gradient hero, ảnh bo 16px + shadow nổi
5. 3 value props — icon chip tròn + câu dạng `**Bold lead.** phần giải thích`
6. Eyebrow pill ("Features") → H2 → sub → bento grid card
7. Hai card rộng: Privacy / Integrations
8. "Get started in minutes" — 3 card ngang
9. Bảng so sánh — cột của mình được highlight bằng khung nổi
10. Pricing — slider + card
11. FAQ accordion
12. CTA cuối (lặp lại hero)
13. Footer 4 cột + hình tròn gradient trang trí

</details>

**Bento card** — pattern quan trọng nhất của tầng B:
```
┌────────────────────────────────┐
│ (◯ icon chip trắng)            │
│                                │
│ Nhãn tính năng      ← accent AA-safe, weight 600
│ Câu mô tả đậm, 2–3 dòng ← --text-primary, weight 700
│                                │
│ ✓ gạch đầu dòng 1   ← icon nhỏ accent + text 15px (vai body, §3)
│ ✓ gạch đầu dòng 2              │
│ ✓ gạch đầu dòng 3              │
│                                │
│ [ Learn more › ]    ← pill trắng
│                                │
│ ┌──── visual dữ liệu thật ───┐ │
│ └────────────────────────────┘ │
└────────────────────────────────┘
```
Nền `--bg-surface`, radius 20px, không border, padding 32px.

Khi yêu cầu chỉ nói "làm UI" → mặc định tầng A.

---

## 8. Motion

- Transition mặc định: **150ms ease-out**. Chỉ animate `transform` và `opacity`.
- Scroll reveal: `Intersection Observer` (không dùng AOS/GSAP). `opacity 0→1` + `translateY 16px→0`, 400ms ease-out, stagger 80ms, **trigger 1 lần**.
- Chart vào viewport: line vẽ trái→phải; bar grow từ dưới. Metric count-up 600ms — **trừ khi đang kéo timeline brush**, số phải bám tay theo thời gian thực (§5).
- Loading: **skeleton shimmer**, không spinner. Chờ < 300ms thì không hiện gì.
- Toast: góc trên phải, 3s, `aria-live="polite"`, không cướp focus.
- Không dùng modal cho action nhỏ — inline expand.
- Logo `lockup-replay` (ADR-0026, §10b): hoạt cảnh SVG tháo nút phát lúc mở trang rồi mỗi 15 giây, đứng yên ở
  logo hoàn chỉnh giữa hai lần; không phát khi tab ẩn.
- `prefers-reduced-motion: reduce` → tắt toàn bộ animation, hiện thẳng trạng thái cuối (logo: bản tĩnh, kể cả khi bật giữa phiên).

---

## 9. Chart rules

| Loại dữ liệu | Chart | Ghi chú |
|---|---|---|
| Engagement theo thời gian | Line + area fill | Series chính `--amber-600`, so sánh `--text-muted` |
| Top posts / topics | Ranked horizontal bar | Không dùng vertical bar — nhãn tiếng Việt dài |
| Giờ/thứ đăng hiệu quả | Heatmap | Thang tuần tự 1 hue (amber), không dùng thang cầu vồng. Mỗi ô ghi n; ô `insufficient_data` gạch chéo, không tô theo giá trị |
| Phân bổ topic | Horizontal bar | **Không dùng pie khi > 5 nhóm** |
| Bản đồ topic (scatter UMAP) | Mỗi topic 1 màu + hình (đa sắc, Thy chốt 2026-10-29) | 8 màu `--cat-1..8` theo thứ tự cố định (bảng chuẩn skill dataviz, validate PASS); topic thứ 9+ dùng lại màu với hình thoi (mã hoá kép); topic đang chọn điểm to hơn, topic khác nhạt hơn; nhiễu vòng rỗng xám. Danh sách topic có ô màu cạnh bản đồ là chú giải bằng chữ — trên scatter > 3 màu không tách được với mọi người mù màu nên màu không bao giờ mang thông tin một mình. Thay quyết định 1 màu nhấn 2026-09-30 |
| Share rate distribution | Histogram | |

Bắt buộc mọi chart:
- Legend luôn hiện, đặt sát chart
- Tooltip trên hover **và** focus bàn phím (không chỉ hover)
- Đường/cột vs nền ≥ 3:1; nhãn số ≥ 4.5:1
- Có **empty state** riêng: "Chưa có dữ liệu" + hướng dẫn, không hiện khung trục rỗng — quan trọng vì dự án có cold-start snapshot
- Có **error state**: thông báo + nút thử lại
- Không phân biệt series **chỉ bằng màu** — thêm dashed/solid, hoặc direct label
- Số dùng định dạng **en** (`18,420`, xem §3)
- `prefers-reduced-motion` → bỏ animation vẽ, hiện chart hoàn chỉnh ngay

---

## 10. Ảnh tác giả

File: `docs/design/photo_author.JPG` (4000×4000).

- **Trong app:** avatar 32px tròn ở topbar. Vì ảnh gốc vuông và rộng, cần `transform: scale(1.75)` với `transform-origin: 50% 34%` thì khuôn mặt mới đủ lớn.
- **Trên landing:** khối Author 200×240, `object-position: 50% 30%`, radius 16px.

Đây là chỗ duy nhất ảnh cá nhân xuất hiện ở cỡ lớn.

### 10b. Logo (ADR-0021, ADR-0026)

File gốc và quy tắc: `docs/design/brand-assets.md` (file trong `src/dashboard/public/brand/`, không sửa tay). Luôn dùng component `BrandLogo` (`src/dashboard/src/components/BrandLogo.tsx`):

- Topbar dashboard: `lockup-replay` 36px + tagline chữ HTML 15px cạnh logo, ngăn bằng vạch dọc (ẩn tagline dưới 640px).
- Navbar landing: `lockup-replay` 28px. Hero landing: `lockup-replay` 64px.
- `lockup-replay` = bản "chạy 1 lần" phát lúc mở trang rồi mỗi 15 giây (ADR-0026); `prefers-reduced-motion` → bản tĩnh (§8).
- Khối CTA landing: `mark` 52px. Footer landing: `lockup` 24px. Favicon: `app/icon.svg` (bản sao của mark).

---

## 11. UI/UX Pro Max — phạm vi sử dụng

Skill `tools/ui-ux-pro-max/` là **công cụ tra cứu**, không phải nguồn design. Gọi qua skill `ui-lookup`; quy tắc bắt buộc ở `.claude/rules/dashboard.md` (tự nạp khi chạm `src/dashboard/`).

**Không nạp SKILL.md vào context** (55KB ≈ 15k token). Chỉ chạy CLI:

```bash
# Windows dùng `python`; Linux/macOS dùng `python3`
python tools/ui-ux-pro-max/scripts/search.py "<query>" --domain <d> -n 3
```

**Nghiêm cấm** `--design-system` và `--persist`: generator này sinh palette + pattern landing-page marketing, mâu thuẫn với file này, và `--persist` ghi ra `design-system/<slug>/MASTER.md` tạo nguồn sự thật thứ hai.

### Query cookbook cho dashboard này

Dataset index theo **triệu chứng quan sát được**, không theo chủ đề. Query 2–5 từ. (`"analytics dashboard" --domain ux` → 0 kết quả; `"empty data state chart" --domain chart` → 3 kết quả.)

| Cần gì | Lệnh |
|---|---|
| Chart cho chuỗi thời gian engagement | `"time series trend forecast" --domain chart` |
| Chart xếp hạng top posts | `"comparison ranking bar" --domain chart` |
| Heatmap giờ đăng | `"heatmap matrix intensity" --domain chart` |
| Empty state khi chưa có snapshot | `"empty data state chart" --domain chart` |
| Chart accessible không phụ thuộc màu | `"pattern texture colorblind" --domain chart` |
| Bảng sắp xếp được | `"sortable table aria-sort" --domain ux` |
| Lỗi form khi submit | `"error summary validation" --domain ux` |
| Focus bị thanh sticky che | `"focus not obscured" --domain ux` |
| Icon chip trong card | `"decorative icon aria hidden" --domain icons` |
| Nút icon-only trên toolbar | `"icon button accessible label" --domain icons` |
| Badge/pill bị tràn chữ | `"badge chip label wraps" --domain ux` |
| Cập nhật số liệu realtime cho screen reader | `"live badge count screen reader" --domain ux` |
| Next.js data fetching | `"streaming suspense data fetching" --stack nextjs` |
| Next.js chia bundle | `"dynamic import bundle splitting" --stack nextjs` |
| React list re-render | `"rerender memo list" --domain react` |
| shadcn theming | `"theme tokens css variables" --stack shadcn` |
| Tailwind cho chip overflow | `"chip badge overflow nowrap" --stack html-tailwind` |
| Timeline brush / range slider kéo được | `"range slider drag handle" --domain ux` |

Kết quả trả về là **khuyến nghị**, không phải lệnh. Nếu mâu thuẫn với file này → file này thắng. Nếu query trả 0 kết quả: thử lại **một lần** với từ hẹp hơn, sau đó nói rõ "không tìm thấy trong dataset" thay vì bịa.

---

## 12. Checklist trước khi merge UI

Checklist này là bản rút gọn; nguồn chấm là sổ luật §3b (mã luật T/L/C/N/K/B/A/X) và `@agent-ux-reviewer`.

**Sổ luật §3b**
- [ ] `node scripts/ux-shots.mjs` (mọi route): `violations` + `crossRoute` = 0 (dòng cuối in `UX gate (máy): PASS`); mỗi `warnings` đã được reviewer xác nhận hoặc bác.
- [ ] Bảng "vai × trang" của reviewer: cùng vai cùng cỡ/độ đậm/màu trên mọi trang (T3).

**Bám nguồn sự thật**
- [ ] Không có hex rời — mọi màu là token ở §2.
- [ ] Mọi cặp chữ/nền đạt ≥4.5:1.
- [ ] Mọi button/badge/tab là pill `999px`.
- [ ] Phân tầng bằng đổi nền, không bằng shadow (trừ ngoại lệ §4).
- [ ] Gradient vẫn chỉ xuất hiện một lần (§2.5).

**Accessibility**
- [ ] Số dùng tabular-nums, định dạng en.
- [ ] Delta có mũi tên; trạng thái có chữ — không chỉ màu.
- [ ] Focus ring hiện rõ 2px `--amber-600`, không `outline:none`.
- [ ] Icon trang trí có `aria-hidden="true"`; nút icon-only có `aria-label`.
- [ ] Vùng chạm ≥ 44×44px.
- [ ] `prefers-reduced-motion` được tôn trọng.

**Chart & bảng**
- [ ] Có đủ loading / empty / error.
- [ ] Không emoji, không zebra striping, không shadow để phân tầng.
- [ ] Grid track dùng `minmax(0,1fr)`, không `1fr` trần.
- [ ] Không cuộn ngang toàn trang — bảng rộng cuộn trong container riêng.

**Responsive**
- [ ] Test 375 / 768 / 1024 / 1440px.
- [ ] Body ≥ 14px trên mobile.

---

## 13. Decision log

### 2026-10-31 — Hộp Key numbers: một component, số 28px, cao theo nội dung

Thy gửi 6 ảnh hộp số có khoảng trống lệch nhau. Nguyên nhân trong code: luật 2026-10-29 bắt hộp số theo chiều cao của cột
bên cạnh, được làm bằng `justify-evenly`, nên cột trái càng dài thì khoảng giữa các số càng to; trang Topics tự viết hộp
thứ 2 (nhãn trái, số phải, tên riêng); số 15px bằng cỡ nhãn. Thy chốt (ADR-0030): số 28px căn trái
xếp dọc (căn phải chỉ cho cột số trong bảng), hộp cao theo nội dung + dính khi cuộn, luôn tên "Key numbers" + dòng phạm
vi, thanh tỉ lệ cho số lồng nhau, một kết quả thống kê một dòng. Luật K1–K6 (§3b); sửa component là PR 2.

### 2026-10-30 — Một thang chữ + một sổ luật cho mọi trang

Landing và /topics do 2 phiên khác nhau dựng nên ra 2 "giọng": thang chặt của §3 chỉ ghi cho tầng A, landing chỉ có
1 dòng ở §7 (câu hỏi panel 13px), nên tiêu đề khối landing 13px, nhỏ hơn câu trả lời 24px nó dẫn, chỉ là `<span>`. Đo toàn dashboard có
khoảng 21 cỡ chữ khác nhau (10 → 76px); tiêu đề khối Overview 20px (một khối 15px) so với Topics 26px. Thy chốt:
một thang chung (§3, landing chỉ thêm display-1/2), sổ luật có mã (§3b), cưỡng chế 2 lớp — `@agent-ux-reviewer` +
máy đo trong `ux-shots.mjs` (axe-core cho WCAG), chưa chặn commit. Sửa các trang cho đạt là PR riêng, sau PR luật.

### 2026-10-29 — Trang app: tiêu đề lớn hơn nội dung; bản đồ topic đa sắc

Thy bác 2 lần bản /topics: tiêu đề khối 13px nhỏ hơn câu trả lời 20px và thân bài 15px làm mất mạch đọc nhanh. Thang
mới (§3, nay là thang chung cho mọi trang — ADR-0029): h1 40 > h2 26 > h3 20 > answer 18 > h4 17 > body 15; mỗi khối có số thứ tự, câu
mục đích, kẻ đậm; câu trả lời trong khung nhấn. Bản đồ topic chuyển sang đa sắc (§9) và nằm bên trái danh sách topic.

### 2026-10-01 — Giữ amber; landing tầng B chốt; thêm dải tối

- So 4 palette dựng thật trên cùng mảnh landing (Claude Design): **Amber · instrument** (giữ), Highlighter chartreuse + mực, Oxblood trên giấy kem, Petrol trên đá. Thy chốt amber. Lý do giữ: khớp sợi amber đã có trong logo Unknot (đổi palette = xuất lại logo + animation); Oxblood đụng màu âm `#C42A2F`; Petrol gần hướng cyan đã loại; Highlighter làm yếu nút tương tác (nút thành đen). File so sánh đã xoá sau khi chốt.
- Thêm §2.6 dải tối cho landing (sơ đồ + CTA) — trả lời phản hồi "trung tính nhạt nhoà" mà không thêm màu nhấn thứ hai.
- Sửa số tương phản `--amber-600`: 4.9:1 (không phải 5.9:1).
- §7 tầng B thay danh sách section đo từ PNG bằng cấu trúc landing đã chốt.
- Xoá mockup lỗi thời: `threads-dashboard.dc.html` + `.html` (violet, tab Generate Content trái ADR-0001, số cũ 135 unit), `landing-hero-concepts.dc.html` (đã chọn 1c), `design-system-v3.1-amber.md` (đã merge từ 09-03). <!-- consistency: allow ADR0001-generation -->

### 2026-09-30 — Bản đồ topic 1 màu nhấn; heatmap giờ đăng có n

- Topic Explorer bỏ bảng 8 màu v2 (3 tông tím trùng nhau, hex rời): mọi điểm dùng `--text-muted`, topic đang chọn dùng `--amber-600`. Lý do: 9 cluster trên scatter vượt giới hạn phân biệt màu (skill dataviz: tối đa 3 slot an toàn khi mọi cặp màu cùng hiện). Danh sách topic dạng horizontal bar (§9) thành khối chính.
- Heatmap giờ/thứ (§9) thay 4 bar chart dọc: màu = `color-mix` giữa `--amber-soft` và `--amber-700`, trần 65% để `--text-primary` vẫn đạt ≥ 4.5:1 trên ô đậm nhất. Ô thiếu dữ liệu gạch chéo 45°.
- Xoá alias token v2 (`--accent-purple`, `--bg-border`…) khỏi `globals.css` — không còn file nào dùng.

### 2026-09-03 — v3.1: bỏ violet, dùng amber

| Quyết định | Lý do |
|---|---|
| Bỏ violet, dùng amber | Violet/indigo là màu AI-generic. Chọn sau khi dựng và so sánh hai bản thật (`overview-cyan.dc.html` vs `overview-amber.dc.html`). |
| Accent tương tác `#B45309`, không `#F59E0B` | Cam rực fail AA khi làm nền cho chữ. |
| Cho gradient vào tầng A, đúng một lần | Giữ cảm giác sang trọng mà không làm loãng. |
| IBM Plex Mono cho công thức | Phơi phương pháp luận ra mặt tiền là bản sắc sản phẩm. |
| Timeline brush là component chữ ký | Thay cho date-picker rời rạc; mọi chỉ số đồng bộ với cửa sổ. |
| Tagline chốt: "The algorithm, read back to you." | |
| PNG reference hạ xuống ưu tiên 2, chỉ dùng cho cấu trúc | Màu giờ do file này quyết định hoàn toàn (§0). |

Nguồn đầy đủ (research, ảnh style guide, mockup tương tác): `src/dashboard/mockups/` — README của thư mục đó liệt kê từng file.

**Sync 2026-09-03**: `docs/claude/design-system.md` (file này) cập nhật theo v3.1 từ bản `design-system-v3.1-amber.md` trong mockups (đã xoá sau khi sync) để không còn 2 nguồn song song. `globals.css` + `AnalyticsOverview.tsx` refactor sang token v3.1 (bỏ zebra striping, bỏ gradient bar ngoài hero, bỏ hex hardcode trong Recharts). **Chưa làm**: `Nav.tsx`, `TopicExplorer.tsx`, `topics/page.tsx` vẫn dùng token cũ (alias sang giá trị amber trong `globals.css` để không vỡ layout, nhưng chưa refactor cấu trúc/component theo §5–§6). (Cập nhật: `Nav.tsx` đã xong ở `c31d756`, landing Tầng B bản scoped đã dựng ở `7534faa`; `TopicExplorer.tsx` + `topics/page.tsx` chuyển sang token v3.1 ngày 2026-09-30 — xem mục đầu của decision log.)

### 2026-09-02 — v3 thay v2: dark → light

**Bối cảnh**: v2 quy định app dark mode (`--bg-primary: #0d0d0d`, accent `#7c3aed`) và đồng thời trích dẫn `dashboard-reference.png` làm reference. Hai điều này mâu thuẫn nhau: đo pixel toàn ảnh cho thấy **78% diện tích là trắng hoặc xám rất nhạt** (`#FFFFFF` 53%, `#F7F7F7` 19%, `#FAFAFA` 6%). Reference là light mode.

**Hệ quả đã xảy ra**: artifact `f23eb6c8-ee92-44f6-bbb9-ce81dc28eb5f` (2026-09-01) ra kết quả không giống mong đợi. Đọc lại source của artifact cho thấy nó dùng `--bg: #f9f9f7` (kem), `--accent: #4a3aa7` (indigo đậm), font `Instrument Serif` + `IBM Plex Sans` — **không khớp v2, cũng không khớp PNG**. Đó là default palette chung, nghĩa là artifact được sinh mà **không đọc cả design-system.md lẫn PNG**. Ba hướng design cùng tồn tại trong một dự án.

**Quyết định**:
1. Reference PNG là chuẩn → chuyển sang light mode.
2. Bỏ dark mode khỏi scope hiện tại.
3. Bỏ sidebar 220px + emoji icon → top nav tab pill + Phosphor icon.
4. Tách rõ tầng A (app) / tầng B (landing) để không lẫn pattern marketing vào dashboard.
5. Bổ sung §9 Chart rules (v2 thiếu).
6. Thêm quy tắc routing vào `CLAUDE.md` để mọi phiên sau bắt buộc đọc file này trước khi sinh UI (nay nằm ở `.claude/rules/dashboard.md` — ADR-0003).
7. UI hướng ra ngoài (dashboard, LLM label, RAG) chuyển toàn bộ sang tiếng Anh — nội dung post giữ tiếng Việt. Số dùng định dạng en (`18,420`) thay cho `toLocaleString('vi-VN')`.

**Giữ lại từ v2**: breakpoints, scroll animation spec, danh sách trang. (Phím tắt A/S và thẻ gợi ý nội dung của v2 đã bỏ cùng tính năng generation — ADR-0001.)

**Rủi ro còn mở (v3, đã giải quyết ở v3.1)**: hex đo từ ảnh PNG có sai số ±3%/kênh — v3.1 không còn dùng PNG cho màu nên rủi ro này không còn áp dụng. Font vẫn dùng Inter như quyết định độc lập (hỗ trợ tiếng Việt tốt), không phải kết quả nhận dạng từ reference.
