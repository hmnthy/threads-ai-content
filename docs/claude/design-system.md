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

```
hero metric   56px  w700  -0.03em   tabular
h2 section    20px  w700  -0.02em
card title    15px  w600
body          15px  w400  lh 1.6
metric KPI    28px  w700  -0.02em   tabular
formula       12.5px mono lh 1.7
label         12px  w500
```

Mọi con số dùng `font-variant-numeric: tabular-nums`, định dạng **en** (`18,420`) — thay cho `toLocaleString('vi-VN')` từng dùng ở v3 (xem §13, quyết định 2026-09-02: UI hướng ra ngoài dùng tiếng Anh, nội dung post giữ tiếng Việt). Không uppercase tiếng Việt.

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
- **Content unit row** — số thứ tự 2 chữ số, tiêu đề 14px hiển thị đầy đủ (không cắt bằng ba chấm), dòng metadata, bar 220px, số bên phải 15px.
- **Bảng** — header 11px w600, không uppercase, không zebra striping, hover đổi nền.
- **Trạng thái chart** — bắt buộc có loading (skeleton, không spinner), empty (nói rõ lệnh cần chạy), error (message + retry).
- **Icon** — Phosphor regular 18–20px. Không emoji.

---

## 7. Layout — hai tầng, không trộn

**Tầng A · App shell** (ưu tiên — `src/dashboard/`, sản phẩm thật): `max-width 1280`, padding 24. Thứ tự dọc: topbar (logo + tagline + account pill + avatar) → tab pill → **dải hero gradient** → chart + timeline brush → KPI strip → metric architecture → top content units. Top nav tab pill, không sidebar.

**Tầng B · Landing** — chốt 2026-10-01, mockup `src/dashboard/mockups/landing.dc.html`, spec port ở `docs/design/landing-handoff.md`. Trang giới thiệu tool cho portfolio; pricing, FAQ, Login/Register **ngoài scope** (không phải SaaS); landing thương hiệu thydilammuon là việc của roadmap Phase F, cần ADR riêng.

Thứ tự: navbar pill sticky → **Hero** (H1 tagline + panel bằng chứng: beeswarm 144 bài, bài hero amber, toggle Channel/Topic) → **Problem** (3 câu hỏi của người làm kênh, mỗi câu "Threads shows / Missing") → **How it solves** (3 tầng Measure · Group · Search nối bằng mũi tên, theo 1 bài thật) → **Product proof** (2 panel dashboard: chủ đề so với kênh; kết quả NLP) → **How it works** (sơ đồ trên dải tối §2.6, bấm node xem stack) → **About the channel** → **CTA** (dải tối) → footer có câu miễn trừ Meta.

Mỗi panel bằng chứng theo thứ tự: câu hỏi (13px w600 amber) → câu trả lời 1 dòng (24px w700) → biểu đồ → nút "Method and limits" mở công thức + giới hạn. Tiêu đề section landing: 46px w800 −0.035em; eyebrow mono 13px amber dạng `01 · Problem`.

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
│ ✓ gạch đầu dòng 1   ← icon nhỏ accent + text 13px
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
- `prefers-reduced-motion: reduce` → tắt toàn bộ animation, hiện thẳng trạng thái cuối.

---

## 9. Chart rules

| Loại dữ liệu | Chart | Ghi chú |
|---|---|---|
| Engagement theo thời gian | Line + area fill | Series chính `--amber-600`, so sánh `--text-muted` |
| Top posts / topics | Ranked horizontal bar | Không dùng vertical bar — nhãn tiếng Việt dài |
| Giờ/thứ đăng hiệu quả | Heatmap | Thang tuần tự 1 hue (amber), không dùng thang cầu vồng. Mỗi ô ghi n; ô `insufficient_data` gạch chéo, không tô theo giá trị |
| Phân bổ topic | Horizontal bar | **Không dùng pie khi > 5 nhóm** |
| Bản đồ topic (scatter UMAP) | Scatter xám + 1 topic tô `--amber-600` | Không tô mỗi cluster 1 màu: trên scatter không bảng màu nào giữ > 3 màu phân biệt được với người mù màu. Chọn topic từ danh sách horizontal bar để làm nổi |
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
