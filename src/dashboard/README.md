# Dashboard (Next.js 16)

Giao diện của threads-ai-content: landing `/` + tool `/overview`, `/analytics`, `/topics`.
Tài liệu chính ở README gốc của repo; design system: `docs/claude/design-system.md`.

```bash
npm install
npm run dev            # http://localhost:3000 — cần backend: uv run uvicorn src.main:app --port 8000
npm run lint           # eslint (cũng chạy ở pre-commit, kèm tsc --noEmit)
npm run build
npm run screenshots    # chụp lại docs/screenshots/*.png (Playwright + Edge có sẵn)
```

`.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (trả về localhost sau mỗi lần deploy tạm qua tunnel).
Next.js 16 có breaking changes — xem `AGENTS.md` cùng thư mục.
