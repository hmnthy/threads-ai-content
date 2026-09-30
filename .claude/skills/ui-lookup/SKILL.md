---
name: ui-lookup
description: Look up UX, chart, accessibility or React/Next.js UI guidance for the threads-ai-content dashboard via the local ui-ux-pro-max search CLI. Use when building or fixing UI in src/dashboard and a concrete, observable symptom needs a recommendation (e.g. "empty data state chart", "touch target too small").
argument-hint: "\"<symptom, 2-5 words>\" --domain <chart|ux|icons|react|color|typography>"
paths:
  - "src/dashboard/**"
allowed-tools: Bash(python tools/ui-ux-pro-max/scripts/search.py *)
---

# ui-lookup — tra cứu UI (công cụ tham khảo, không phải nguồn design)

Chạy:

```bash
python tools/ui-ux-pro-max/scripts/search.py $ARGUMENTS -n 3
# hoặc theo stack: python tools/ui-ux-pro-max/scripts/search.py "<query>" --stack <nextjs|react|shadcn|html-tailwind>
```

- Query theo **triệu chứng quan sát được**, 2–5 từ, không theo chủ đề (`"analytics dashboard"` → 0 kết quả; `"empty data state chart"` → có kết quả). Cookbook: `docs/claude/design-system.md` §11.
- **Cấm** `--design-system` và `--persist` (sinh palette marketing mâu thuẫn design system; `--persist` tạo nguồn sự thật thứ hai).
- **Không** đọc `tools/ui-ux-pro-max/SKILL.md` (56KB).
- Kết quả là **khuyến nghị**. Mâu thuẫn với `docs/claude/design-system.md` → design-system thắng. Không dùng màu/font từ kết quả.
