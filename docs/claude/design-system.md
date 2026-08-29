# Design System — Threads AI Content

> Đọc khi: làm việc trong `src/dashboard/` hoặc bất kỳ UI/frontend nào của dashboard.
> Xem thêm: [`architecture.md`](architecture.md) cho tech stack, [`CLAUDE.md`](../../CLAUDE.md) cho mission/status.

> Reference: [../design/dashboard-reference.png](../design/dashboard-reference.png)
> Nguyên tắc: **Tinh gọn — Hiện đại — Chuyên nghiệp — Hiệu quả**

## Color Palette

```css
/* Backgrounds */
--bg-primary:    #0d0d0d;   /* app background */
--bg-surface:    #141414;   /* card, sidebar */
--bg-elevated:   #1c1c1c;   /* hover states, table rows */
--bg-border:     #2a2a2a;   /* dividers, card borders */

/* Accent */
--accent-purple: #7c3aed;   /* primary CTA, active states, badges */
--accent-purple-soft: #a78bfa; /* secondary labels, icons */

/* Status colors */
--color-positive: #22c55e;  /* growth up, high virality */
--color-negative: #ef4444;  /* drop, low performance */
--color-neutral:  #a3a3a3;  /* muted text, secondary info */

/* Text */
--text-primary:   #f5f5f5;
--text-secondary: #a3a3a3;
--text-muted:     #525252;
```

## Typography

```
Headline (h1):   32–48px, font-weight 700, tracking tight
Section (h2):    20–24px, font-weight 600
Card title (h3): 14–16px, font-weight 500, uppercase letter-spacing
Body:            14px, font-weight 400, line-height 1.6
Label / badge:   11–12px, font-weight 500
Number metric:   28–40px, font-weight 700, tabular-nums
```

Font stack: `Inter` → `system-ui` → `sans-serif`

## Layout

- **Sidebar** cố định bên trái, width 220px, dark `--bg-surface`
- **Main content** padding 24px, max-width 1280px centered
- **Grid system**: 12 cột, gap 16px
- **Cards**: border-radius 10px, border `1px solid --bg-border`, padding 20px
- Không dùng shadow nặng — dùng border thay thế

### Mobile Responsive (bắt buộc)

- **Breakpoints**: mobile < 768px / tablet 768–1024px / desktop > 1024px
- Sidebar collapse thành bottom navigation bar trên mobile
- Grid tự co từ 12 cột → 2 cột (tablet) → 1 cột (mobile)
- Cards stack dọc trên mobile, metric cards hiển thị 2×2 grid
- Charts responsive — tự resize theo container width, không cắt trục
- Touch-friendly: tap target tối thiểu 44×44px cho mọi button/link
- Font scale nhỏ hơn trên mobile: headline 24px, body 13px

## Component Patterns

**Metric Card**
```
┌─────────────────────────────┐
│  LABEL TEXT        [badge]  │
│                             │
│  1,284             ↑ 12%    │  ← số lớn + trend arrow (green/red)
│  vs last 7 days             │
└─────────────────────────────┘
```

**Line / Area Chart**
- Background: `--bg-surface`
- Line: `--accent-purple` với gradient fill phía dưới (opacity 20%)
- Axis labels: `--text-muted`, không có gridlines rối — chỉ horizontal dashed nhẹ
- Tooltip: dark card với border `--bg-border`

**Data Table**
- Header: uppercase, 11px, `--text-muted`
- Row hover: `--bg-elevated`
- Zebra striping nhẹ (opacity 3%)
- Search/filter bar phía trên, full-width
- Cột Virality Index: progress bar màu gradient purple → green

**Topic Badge / Tag**
```
[Alternance]  [CV]  [Entretien]  [Lifestyle]  [Data]
```
- Pill shape, border-radius 999px
- Màu riêng theo topic (purple, blue, amber, green, pink)
- Font 11px, uppercase

**Virality Score Ring**
- Donut chart tròn, stroke-width 6px
- 0–30: red, 30–60: amber, 60–80: purple, 80–100: green
- Số ở giữa, 24px bold
- Label bên dưới: "Viral potential"

**Content Idea Card** (panel generate)
```
┌──────────────────────────────────────────────────┐
│  💡 [Topic badge]                  Score: 87/100  │
│                                                   │
│  Title: "3 lỗi CV mình từng mắc khi apply..."    │
│                                                   │
│  SHORT  │  MEDIUM  │  LONG   ← tabs               │
│  ─────────────────────────                        │
│  [Content preview text...]                        │
│                                                   │
│  [Edit]  [Approve]  [Skip]                        │
└──────────────────────────────────────────────────┘
```

## Trang & Navigation

```
Sidebar:
  📊 Dashboard          ← overview metrics
  📈 Analytics          ← charts chi tiết, heatmap giờ đăng
  🧭 Topic Explorer     ← gap analysis, topic map
  ✍️  Generate Content   ← AI content workflow
  🖼️  Carousel Builder   ← image generation (chỉ hiện sau approve text)
  📁 Content Library    ← lịch sử đã approve
  ⚙️  Settings           ← API config, tone preferences
```

## Interaction & Motion

- Transitions: 150ms ease-out (không dùng animation rườm rà)
- Loading state: skeleton shimmer (không dùng spinner quay)
- Toast notifications: góc trên phải, 3 giây, dark background
- Approve/Skip actions: keyboard shortcut `A` / `S` khi đang review content
- Không dùng modal cho các action nhỏ — dùng inline expand

### Scroll Animations (bắt buộc cho mọi section)

- Dùng `Intersection Observer API` — không dùng thư viện nặng (AOS, GSAP)
- Mỗi section/card fade-in + slide-up khi scroll vào viewport: `opacity 0→1`, `translateY 20px→0`
- Duration: 400ms ease-out, delay stagger 80ms giữa các card liên tiếp
- Chỉ trigger 1 lần (không replay khi scroll ngược lại)
- Charts animate khi vào viewport: line chart vẽ từ trái sang phải, bar chart grow từ dưới lên
- Metric numbers count-up animation khi lần đầu hiển thị (0 → giá trị thực, 600ms)
- `prefers-reduced-motion`: tắt toàn bộ animation nếu user bật accessibility setting này
