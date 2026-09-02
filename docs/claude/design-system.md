# Design System — Threads AI Content

> **Đọc khi**: làm việc trong `src/dashboard/`, hoặc bất kỳ UI/frontend/mockup/artifact nào của dự án.
> **Đây là nguồn sự thật DUY NHẤT về design.** Xem thêm: [`architecture.md`](architecture.md) (tech stack), [`CLAUDE.md`](../../CLAUDE.md) (mission).
>
> **Reference bắt buộc**: [`../design/dashboard-reference.png`](../design/dashboard-reference.png)
> **Phiên bản**: v3 — 2026-09-02. v3 thay thế v2 (dark mode) sau khi đối chiếu lại với reference. Lý do đầy đủ ở [§11 Decision log](#11-decision-log).

---

## 0. Nguyên tắc bất biến

1. **Reference PNG là chuẩn.** Khi file này mâu thuẫn với PNG → PNG thắng, và phải sửa file này. Khi file này mâu thuẫn với bất kỳ nguồn nào khác (skill, generator, default palette của model, "best practice" chung) → **file này thắng**.
2. **Light mode là mặc định và là chế độ duy nhất được thiết kế.** Dark mode chưa nằm trong scope. Không tự thêm block `@media (prefers-color-scheme: dark)` khi chưa có yêu cầu.
3. **Không hex rời.** Mọi màu trong code phải là CSS variable khai báo ở §2. Thấy hex lạ trong PR → reject.
4. **Text và interactive dùng tier AA-safe**, không dùng hex đo trực tiếp từ PNG (§2.3 giải thích tại sao).
5. Nguyên tắc cảm quan giữ nguyên từ v2: **Tinh gọn — Hiện đại — Chuyên nghiệp — Hiệu quả**.

---

## 1. Reference PNG chứa hai tầng — đừng trộn lẫn

Ảnh là một trang landing page SaaS hoàn chỉnh, bên trong có ảnh chụp app. Hai thứ khác nhau:

| Tầng | Là gì trong PNG | Dùng cho | Ưu tiên |
|---|---|---|---|
| **A — App shell** | Ảnh chụp dashboard trắng nằm trong hero (§5) | `src/dashboard/` — sản phẩm thật | **Cao.** Build trước. |
| **B — Landing** | Toàn bộ phần còn lại: navbar pill, hero, bento features, pricing, FAQ, footer (§6) | Trang public giới thiệu tool cho portfolio | Thấp. Làm sau khi dashboard chạy. |

Khi có yêu cầu "làm UI" mà không nói rõ tầng nào → mặc định là **tầng A**.

---

## 2. Color tokens

> **Provenance**: các hex có ghi *(đo)* được trích bằng pixel sampling trực tiếp từ `dashboard-reference.png` (2026-09-02). Ảnh chỉ rộng **313px** nên có anti-aliasing — sai số ước tính ±3% mỗi kênh. Các hex ghi *(dẫn xuất)* là do tôi tính ra để đạt ngưỡng contrast, không có trong ảnh. Các hex ghi *(giả định)* là bổ sung cho nhu cầu của dự án mà PNG không có.

### 2.1 Neutral

```css
--bg-page:        #FFFFFF;              /* (đo) 53% diện tích pixel toàn ảnh */
--bg-surface:     #F7F7F7;              /* (đo) 19% — card, secondary button, input, table header */
--bg-inverse:     #14141F;              /* (đo) navbar pill, floating toolbar, tooltip, badge tối */
--border-hairline: rgba(20,20,31,0.08); /* (dẫn xuất) chỉ dùng trong tầng A */

--text-primary:   #14141F;   /* 18.3:1 trên trắng — PASS AAA */
--text-secondary: #52525B;   /* (giả định) 7.9:1 */
--text-muted:     #8A8A94;   /* (giả định) 3.4:1 — CHỈ dùng cho label ≥18px hoặc UI phi văn bản */
```

**Quy tắc nền**: `#F7F7F7` là surface **trên** nền `#FFFFFF`. Không đảo ngược. Không có tầng nền thứ ba.

### 2.2 Brand violet

```css
--violet-50:   #F1F0FE;   /* (dẫn xuất) nền icon chip, badge nhạt, row hover */
--violet-200:  #C7C4FA;   /* (dẫn xuất) border nhạt, gradient stop */
--violet-400:  #918DF6;   /* (đo) nút CTA trong PNG — DECORATIVE ONLY */
--violet-500:  #9580FF;   /* (đo) nút Register trên navbar tối */
--violet-600:  #6A5AE8;   /* (dẫn xuất) INTERACTIVE — nút primary, link, focus ring */
```

**Cảnh báo bắt buộc đọc**: `--violet-400` (#918DF6) là màu nút CTA đo được từ PNG. Chữ trắng trên nền này cho contrast **2.86:1 — FAIL WCAG AA** (cần 4.5:1). Reference đẹp nhưng không đạt chuẩn a11y.

→ Giải pháp: giữ nguyên *hue* để không lệch nhận diện, hạ *value*.
- Nút primary + chữ trắng → dùng `--violet-600` (#6A5AE8), **4.95:1 PASS AA**.
- `--violet-400` chỉ dùng cho: fill trang trí, chart series, gradient stop, icon trên nền sáng — **không bao giờ làm nền cho text**.

### 2.3 Feature accents

PNG dùng 4 màu code theo nhóm tính năng (thấy rõ ở các bento card: Revenue=xanh lá, Realtime=xanh dương, Visitor profiles=hồng, Performance=cam). Mỗi màu có 2 biến thể:

| Vai trò | Ref hex *(đo)* | Contrast /`#F7F7F7` | AA-safe hex *(dẫn xuất)* | Contrast |
|---|---|---|---|---|
| Green | `#34C757` | 1.94:1 ❌ | `--green-700: #2C7F44` | 4.64:1 ✅ |
| Blue | `#4486FC` | 3.23:1 ❌ | `--blue-700: #386DCE` | 4.62:1 ✅ |
| Pink | `#D747A3` | 3.68:1 ❌ | `--pink-700: #BD3E8F` | 4.61:1 ✅ |
| Orange | `#FFAA0C` | 1.78:1 ❌ | `--orange-800: #996607` | 4.60:1 ✅ |
| Violet | `#918DF6` | 2.86:1 ❌ | `--violet-600: #6A5AE8` | 4.64:1 ✅ |

**Ref hex** → fill, chart mark, chấm chỉ báo, viền, nền chip. **AA-safe hex** → mọi chữ, mọi icon mang nghĩa, mọi border của control.

**Ánh xạ vào domain của dự án** (đây là quyết định của dự án, không có trong PNG):

| Token | Nghĩa trong dashboard |
|---|---|
| violet | Brand, engagement tổng hợp, Virality Index |
| green | Delta dương, virality cao (≥80), trạng thái đã approve |
| blue | Reach / views / impressions |
| pink | Replies, interactions, hành vi reply chủ động |
| orange | Cảnh báo, hiệu suất dưới trung vị |
| `--red-600: #C42A2F` *(giả định — PNG không có)* | Delta âm, destructive action. 5.1:1 trên `#F7F7F7` |

Bắt buộc: màu **không được là tín hiệu duy nhất**. Delta âm phải có mũi tên ↓ hoặc dấu `−`, không chỉ đổi màu đỏ.

### 2.4 Hero gradient (chỉ tầng B)

Đo dọc mép trái vùng backdrop sau hero:

```css
--gradient-hero: linear-gradient(180deg, #B1A0E9 0%, #7863E9 45%, #2D5AF9 100%);
```

Xuất hiện **đúng một lần** trên toàn trang, làm nền cho ảnh chụp app. Không dùng gradient trong card, button, hay bất kỳ đâu trong tầng A.

---

## 3. Typography

> **Assumption cần nói rõ**: không thể xác định chính xác font của reference từ ảnh 313px. Chữ trong PNG là một geometric/neo-grotesque sans, không phải serif.

**Quyết định**: giữ **Inter** (đã có trong repo, hỗ trợ tiếng Việt đầy đủ — quan trọng vì content là tiếng Việt có dấu). Fallback: `Inter → system-ui → sans-serif`.

Các đặc điểm **đo được** từ PNG, phải tái tạo:

| Thuộc tính | Giá trị |
|---|---|
| H1 landing | rất lớn, weight **700**, tracking **-0.03em**, line-height **1.05**, căn giữa |
| H2 section | weight 700, tracking -0.02em, line-height 1.1, căn giữa |
| Body | weight 400, line-height 1.6, màu `--text-secondary` |
| Eyebrow (nhãn nhóm tính năng) | weight 600, cùng size với H3, **màu accent AA-safe** |
| Số metric | weight 700, `font-variant-numeric: tabular-nums` |

Scale:

```
h1   48 / 64px    (mobile 32px)
h2   32 / 40px    (mobile 24px)
h3   18 / 20px
body 15px         (mobile 14px — không xuống dưới 14px)
label 12px, weight 500
metric 28 / 36px, tabular-nums
```

Cấm: chữ body < 14px; `letter-spacing` dương trên body; xám-trên-xám (`--text-muted` trên `--bg-surface`).

---

## 4. Shape & elevation

Đây là phần tạo ra "cảm giác" của reference. Sai chỗ này thì dù màu đúng vẫn nhìn khác hẳn.

| Element | Radius | Ghi chú |
|---|---|---|
| **Mọi button, badge, tab, chip** | `999px` (pill hoàn toàn) | Đặc trưng số 1 của reference. Không có button bo góc vuông. |
| Card tầng B (bento) | `20px` | Nền `--bg-surface`, **không border** |
| Card tầng A (trong app) | `12px` | Nền `--bg-page`, hairline border |
| Icon chip | `999px` | Vòng tròn trắng, icon accent ở giữa |
| Navbar / floating toolbar | `999px` | Nền `--bg-inverse` |
| Input | `10px` | |

**Elevation**: reference gần như không dùng shadow. Phân tầng bằng **đổi nền** (`#F7F7F7` trên `#FFFFFF`), không bằng đổ bóng.

Ngoại lệ duy nhất — ảnh chụp app nổi trên gradient và floating toolbar:
```css
--shadow-float: 0 8px 32px -8px rgba(20,20,31,0.18);
```

Spacing: hệ 4px. Thang dùng: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96`.

---

## 5. Tầng A — App shell

Bám sát ảnh chụp dashboard trong hero của PNG.

### 5.1 Layout tổng

```
┌────────────────────────────────────────────────────────────┐
│ [logo] [◉ account ⌄]                            [avatar]   │  topbar, nền trắng
│ [Today ⌄]                                            [⤓]   │  filter pill trái, action phải
├────────────────────────────────────────────────────────────┤
│  People●  Revenue●  Views   CR    Bounced   Duration       │  KPI strip — label 12px muted
│  3,349    $2,916    9,102   100%  30.8%     6m40s          │  value 28px bold tabular
│  ↑18%     ↑16%      ↑4%     0%    ↓76%      ↑29%           │  delta 12px + mũi tên
├────────────────────────────────────────────────────────────┤
│                                                             │
│         ╭──╮      chart chính, cao ~280px                  │
│    ╭────╯  ╰──────╮      2 series + annotation markers     │
│  ──╯               ╰───────────────────────                │
│  ·····························●·········█······            │  event dots + bar
│  00:00      06:00      12:00      18:00      24:00         │
├──────────────────────────┬─────────────────────────────────┤
│ 28 people in last 30m    │ Experience Score                │  card grid 2×2
│ ▁▃▁▂▅▂█▃▅▂▃              │    ◯ 100   Perfect              │
├──────────────────────────┼─────────────────────────────────┤
│ Revenue        +104%     │ Sales                    +154%  │
│ A$750  ────────          │ 3× industry average             │
└──────────────────────────┴─────────────────────────────────┘
              [ ◍ ◍ ◍ ◍ ◍ ◍ ]   ← floating pill toolbar, nền #14141F
```

Container: `max-width 1280px`, padding ngang 24px (mobile 16px).

### 5.2 KPI strip

Không phải card. Là một hàng ngang phẳng trên nền trắng, phân cách bằng khoảng trắng.

- Label: 12px, `--text-muted`, kèm chấm màu 6px nếu metric đó có series trên chart
- Value: 28px, weight 700, `tabular-nums`, `--text-primary`
- Delta: 12px, weight 500, `--green-700` / `--red-600`, **luôn kèm ↑ ↓** 
- Mobile: cuộn ngang trong `overflow-x:auto`, **không** wrap xuống hàng

### 5.3 Chart chính

- 2 series: series chính `--violet-400` (line 2px + area fill 12% opacity), series so sánh `--text-muted` 1px không fill
- Không gridline dọc. Gridline ngang: 1px `rgba(20,20,31,0.06)`, tối đa 4 đường
- Trục X: nhãn giờ/ngày 11px `--text-muted`, tick nhỏ
- **Annotation markers**: đường dọc mảnh từ đỉnh xuống, đầu có ô vuông nhỏ — dùng đánh dấu thời điểm đăng bài
- **Event dots** dưới đáy: chấm `#34C757` size theo engagement, hover hiện tooltip
- Tooltip: nền `--bg-inverse`, chữ trắng, radius 10px, không viền

### 5.4 Card nhỏ trong app

```
┌─────────────────────────────────┐
│ Tiêu đề card        [badge/pill]│  14px weight 600 | 11px pill
│                                 │
│ [nội dung: sparkline / ring /   │
│  số lớn / bar mini]             │
└─────────────────────────────────┘
```
Nền `--bg-page`, hairline border, radius 12px, padding 16px.

### 5.5 Component patterns

**Virality Score Ring** — theo mẫu "Experience Score" trong PNG: donut stroke 6px, số ở giữa 24px bold, nhãn text bên phải (không phải bên dưới). Ngưỡng màu: `0–30 --red-600` / `30–60 --orange-800` / `60–80 --violet-600` / `80–100 --green-700`. Bắt buộc kèm nhãn chữ ("Thấp/Trung bình/Cao"), không chỉ màu.

**Ranked bar list** — theo mẫu bảng quốc gia trong PNG: mỗi hàng là `[icon] [nhãn] [thanh nền nhạt fill theo tỉ lệ] [số phải]`. Thanh nền dùng ref hex ở 15% opacity, không dùng gradient. Dùng cho: top posts, top topics, giờ đăng hiệu quả.

**Topic badge** — pill 999px, 11px weight 500, **không uppercase** (tiếng Việt có dấu, uppercase làm hỏng dấu). Nền `--violet-50` chữ `--violet-600`; đổi cặp màu theo topic dùng bảng §2.3.

**Data table** — header 11px weight 600 `--text-muted` không uppercase; row hover `--bg-surface`; **không zebra striping**; cột Virality dùng ranked bar ở trên.

**Content Idea Card** — giữ cấu trúc từ v2 (tabs SHORT/MEDIUM/LONG, nút Edit/Approve/Skip) nhưng: nút dạng pill, bỏ emoji 💡 thay bằng icon Phosphor `Lightbulb`, badge Score dùng ring §5.5.

### 5.6 Navigation — thay đổi so với v2

v2 quy định sidebar 220px với **emoji làm icon** (📊 📈 🧭 ✍️). Bỏ toàn bộ:
- Emoji vi phạm quy tắc `no-emoji-icons`: render khác nhau giữa Windows/macOS, không nhận màu từ token, không scale theo font-size.
- Reference không có sidebar. Reference dùng **floating pill navbar** ở giữa phía trên.

Thay bằng:

| Mục | Icon (Phosphor `@phosphor-icons/react`, weight `regular`, 20px) |
|---|---|
| Dashboard | `ChartPieSlice` |
| Analytics | `ChartLineUp` |
| Topic Explorer | `Compass` |
| Generate Content | `PencilSimple` |
| Carousel Builder | `ImagesSquare` |
| Content Library | `FolderOpen` |
| Settings | `GearSix` |

Dạng: **top nav dạng tab pill** (giống hàng `Dashboard / Profiles / Funnels / Performance / Realtime` trong PNG) — tab active có nền `--bg-surface` + chữ `--text-primary`, tab thường chữ `--text-muted`. Mobile: cuộn ngang.

Toàn bộ icon dùng **một bộ Phosphor duy nhất, một weight duy nhất**. Không trộn Lucide/Heroicons.

---

## 6. Tầng B — Landing page

Thứ tự section đo trực tiếp từ PNG, giữ nguyên khi dựng:

1. **Floating navbar** — pill `--bg-inverse` căn giữa, cách mép trên 16px: logo tròn · menu · Login · nút Register (`--violet-500`)
2. **Hero** — badge pill nhỏ ("NEW · …" nền `--violet-50`) → H1 2 dòng → sub 2 dòng → 2 nút pill (primary `--violet-600` + secondary `--bg-surface`)
3. **Logo strip** — 6 logo grayscale, opacity ~50%
4. **Tab pills** + **ảnh app** trên nền `--gradient-hero`, ảnh bo 16px + `--shadow-float`
5. **3 value props** — icon chip tròn + câu dạng `**Bold lead.** phần giải thích`
6. **Eyebrow pill** ("Features") → H2 → sub → **bento grid** card
7. Hai card rộng: Privacy / Integrations
8. "Get started in minutes" — 3 card ngang
9. Bảng so sánh — cột của mình được highlight bằng khung nổi
10. Pricing — slider + card
11. FAQ accordion
12. CTA cuối (lặp lại hero)
13. Footer 4 cột + hình tròn gradient trang trí

**Bento card** (§6.6) — pattern quan trọng nhất:
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

---

## 7. Motion

- Transition mặc định: **150ms ease-out**. Chỉ animate `transform` và `opacity`.
- Scroll reveal: `Intersection Observer` (không dùng AOS/GSAP). `opacity 0→1` + `translateY 16px→0`, 400ms ease-out, stagger 80ms, **trigger 1 lần**.
- Chart vào viewport: line vẽ trái→phải; bar grow từ dưới. Metric count-up 600ms.
- Loading: **skeleton shimmer**, không spinner. Chờ < 300ms thì không hiện gì.
- Toast: góc trên phải, 3s, nền `--bg-inverse`, `aria-live="polite"`, không cướp focus.
- Keyboard: `A` approve / `S` skip khi review content.
- Không dùng modal cho action nhỏ — inline expand.
- `prefers-reduced-motion: reduce` → tắt toàn bộ animation, hiện thẳng trạng thái cuối.

---

## 8. Chart rules

(v2 thiếu mục này — bổ sung. Dashboard analytics mà không có quy ước chart là lỗ hổng.)

| Loại dữ liệu | Chart | Ghi chú |
|---|---|---|
| Engagement theo thời gian | Line + area fill | Series chính `--violet-400`, so sánh `--text-muted` |
| Top posts / topics | Ranked horizontal bar | Không dùng vertical bar — nhãn tiếng Việt dài |
| Giờ/thứ đăng hiệu quả | Heatmap | Thang tuần tự 1 hue (violet), không dùng thang cầu vồng |
| Phân bổ topic | Horizontal bar | **Không dùng pie khi > 5 nhóm** |
| Virality distribution | Histogram | |

Bắt buộc mọi chart:
- Legend luôn hiện, đặt sát chart
- Tooltip trên hover **và** focus bàn phím (không chỉ hover)
- Đường/cột vs nền ≥ 3:1; nhãn số ≥ 4.5:1
- Có **empty state** riêng: "Chưa có dữ liệu" + hướng dẫn, không hiện khung trục rỗng — quan trọng vì dự án có cold-start snapshot
- Có **error state**: thông báo + nút thử lại
- Không phân biệt series **chỉ bằng màu** — thêm dashed/solid, hoặc direct label
- Số dùng `toLocaleString('vi-VN')`
- `prefers-reduced-motion` → bỏ animation vẽ, hiện chart hoàn chỉnh ngay

---

## 9. UI/UX Pro Max — phạm vi sử dụng

Skill `.claude/skills/ui-ux-pro-max/` là **công cụ tra cứu**, không phải nguồn design. Xem quy tắc bắt buộc ở `CLAUDE.md` §Quy tắc tuyệt đối.

**Không nạp SKILL.md vào context** (55KB ≈ 15k token). Chỉ chạy CLI:

```bash
# Windows dùng `python`; Linux/macOS dùng `python3`
python .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain <d> -n 3
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

Kết quả trả về là **khuyến nghị**, không phải lệnh. Nếu mâu thuẫn với file này → file này thắng. Nếu query trả 0 kết quả: thử lại **một lần** với từ hẹp hơn, sau đó nói rõ "không tìm thấy trong dataset" thay vì bịa.

---

## 10. Checklist trước khi merge UI

**Bám reference**
- [ ] Light mode. Nền trang `#FFFFFF`, surface `#F7F7F7`. Không có nền tối ngoài `--bg-inverse`
- [ ] Mọi button/badge/tab là pill `999px`
- [ ] Phân tầng bằng đổi nền, không bằng shadow (trừ 2 ngoại lệ §4)
- [ ] Không hex rời — mọi màu là CSS variable của §2

**Accessibility**
- [ ] Text dùng tier AA-safe, không dùng ref hex. Body ≥ 4.5:1
- [ ] Không dùng màu làm tín hiệu duy nhất (delta có mũi tên, ring có nhãn chữ)
- [ ] Focus ring hiện rõ 2px `--violet-600`, không `outline:none`
- [ ] Icon trang trí có `aria-hidden="true"`; nút icon-only có `aria-label`
- [ ] Tap target ≥ 44×44px
- [ ] `prefers-reduced-motion` được tôn trọng

**Chart**
- [ ] Có empty state và error state
- [ ] Tooltip truy cập được bằng bàn phím
- [ ] Legend hiện, số format `vi-VN`

**Responsive**
- [ ] Test 375 / 768 / 1024 / 1440px
- [ ] Không cuộn ngang toàn trang (KPI strip cuộn trong container riêng)
- [ ] Body ≥ 14px trên mobile

**Icon**
- [ ] Không emoji làm icon ở bất kỳ đâu
- [ ] Chỉ một bộ Phosphor, một weight

---

## 11. Decision log

### 2026-09-02 — v3 thay v2: dark → light

**Bối cảnh**: v2 quy định app dark mode (`--bg-primary: #0d0d0d`, accent `#7c3aed`) và đồng thời trích dẫn `dashboard-reference.png` làm reference. Hai điều này mâu thuẫn nhau: đo pixel toàn ảnh cho thấy **78% diện tích là trắng hoặc xám rất nhạt** (`#FFFFFF` 53%, `#F7F7F7` 19%, `#FAFAFA` 6%). Reference là light mode.

**Hệ quả đã xảy ra**: artifact `f23eb6c8-ee92-44f6-bbb9-ce81dc28eb5f` (2026-09-01) ra kết quả không giống mong đợi. Đọc lại source của artifact cho thấy nó dùng `--bg: #f9f9f7` (kem), `--accent: #4a3aa7` (indigo đậm), font `Instrument Serif` + `IBM Plex Sans` — **không khớp v2, cũng không khớp PNG**. Đó là default palette chung, nghĩa là artifact được sinh mà **không đọc cả design-system.md lẫn PNG**. Ba hướng design cùng tồn tại trong một dự án.

**Quyết định**:
1. Reference PNG là chuẩn → chuyển sang light mode.
2. Bỏ dark mode khỏi scope hiện tại.
3. Bỏ sidebar 220px + emoji icon → top nav tab pill + Phosphor icon.
4. Tách rõ tầng A (app) / tầng B (landing) để không lẫn pattern marketing vào dashboard.
5. Bổ sung §8 Chart rules (v2 thiếu).
6. Thêm quy tắc routing vào `CLAUDE.md` để mọi phiên sau bắt buộc đọc file này trước khi sinh UI.

**Giữ lại từ v2**: nguyên tắc "Tinh gọn — Hiện đại — Chuyên nghiệp — Hiệu quả", breakpoints, scroll animation spec, keyboard shortcut A/S, cấu trúc Content Idea Card, danh sách trang.

**Rủi ro còn mở**:
- Hex đo từ ảnh 313px có sai số ±3%/kênh. Nếu sau này có bản reference độ phân giải cao hơn, phải đo lại §2 và cập nhật file này.
- Font của reference **chưa xác định được**. Đang dùng Inter như một quyết định độc lập (lý do: đã có sẵn, hỗ trợ tiếng Việt tốt), không phải kết quả nhận dạng.
- Palette gốc của reference **fail WCAG AA** ở 5/5 màu accent. File này cố ý lệch khỏi reference ở tier text để đạt chuẩn — đây là lệch có chủ đích, không phải sai sót. Nếu ưu tiên giống-hệt-reference hơn a11y thì phải sửa quyết định này một cách tường minh.
