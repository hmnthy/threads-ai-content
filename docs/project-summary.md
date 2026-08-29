# Project Summary — Threads AI Content
> Cập nhật: 2026-08-28

---

## Tóm tắt chức năng chính

Công cụ AI nội bộ dành riêng cho tác giả kênh Threads **"Thy đi làm muộn"** — một người Việt tại Pháp. Công cụ thực hiện toàn bộ vòng lặp content:

```
Kéo data từ Threads API
        ↓
Phân tích hiệu suất từng bài + toàn kênh
        ↓
Gợi ý content mới dựa trên gap phân tích
        ↓
Generate text đúng giọng văn tác giả (3 phiên bản dài/ngắn)
        ↓
Tác giả review → approve
        ↓
(Tùy chọn) Generate carousel PNG từ template có sẵn
        ↓
Tác giả đăng thủ công lên Threads
```

---

## Các tính năng dự kiến xây dựng

### Module 1 — Data Pipeline (`src/api/` + `src/analysis/`)
- Fetch toàn bộ posts + metrics từ Threads API
- Cache local 6 giờ tránh rate limit
- Tính engagement rate: `(likes + replies + reposts) / views × 100`
- Tính Virality Index (0–100) theo weighted formula
- Phân loại post theo topic: Alternance / CV / Entretien / Lifestyle / Data / Divers

### Module 2 — Dashboard (`src/dashboard/`)
- Trang Dashboard: followers growth, avg engagement, top posts
- Trang Analytics: charts theo thời gian, heatmap giờ đăng tốt nhất
- Trang Topic Explorer: scatter plot chủ đề × engagement, gap analysis
- Trang Generate Content: AI workflow review + approve
- Trang Carousel Builder: hiển thị sau khi approve text
- Trang Content Library: lịch sử đã approve
- Trang Settings: API config, tone preferences
- Mobile responsive + scroll animations (Intersection Observer)

### Module 3 — AI Content Generation (`src/generation/`)
- Đọc scripts gốc (`Content/Scripts/`) để học giọng văn tác giả
- Propose 3–5 content ideas dựa trên gap analysis
- Mỗi idea: generate 3 phiên bản (Short ≤150 / Medium 150–400 / Long 400–500 ký tự)
- Gán Virality Index dự đoán cho mỗi version
- Workflow: Propose → Review → Edit → Approve

### Module 4 — Carousel Generation (`src/carousel/`)
- Map approved content → đúng template folder (Alternance/CV/Entretien)
- Pillow overlay text lên PNG template
- Font: Google Sans (Việt hóa) — đã có tại `src/carousel/fonts/Google_Sans/`
- Export PNG sequence ra `output/carousel_YYYY-MM-DD_topic/`
- Không sửa template gốc trong `Content/Content - Photo carousel/`

---

## Những phần đã làm

| Hạng mục | Chi tiết |
|----------|---------|
| CLAUDE.md + docs/claude/ | Mission, trạng thái, quy tắc tuyệt đối ở CLAUDE.md; design system/tech stack/data model/dev rules tách riêng tại docs/claude/*.md |
| Carousel templates | 7 slides Alternance, 9 slides CV, 11 slides Entretien |
| Ảnh/video gốc | Tại `Content/Content - Photo carousel/Photos/` |
| Scripts gốc | 5 file docx/xlsx tại `Content/Scripts/` — nguồn học giọng văn |
| Font Google Sans | Đã tải về, hỗ trợ tiếng Việt, tại `src/carousel/fonts/Google_Sans/` |
| Design reference | `docs/design/dashboard-reference.png` |
| .env.example / .gitignore | Đã cấu hình |
| Meta Developer App | **Hoàn tất** — app, use case Threads API, 8 permissions, Tester `thydilammuon` đã accept |
| Credentials (.env) | Đủ 4/5 giá trị (thiếu `ANTHROPIC_API_KEY`, chưa cần gấp) |
| Tooling | `uv` + `pyproject.toml`, ruff + mypy strict + pytest + pre-commit — đã setup, git repo đã init |
| `src/api/` | **Hoàn tất & verify với data thật** — 6 file + test đầy đủ (25 test pass, ruff/mypy sạch). Fetch thật 25 posts + account insights của `thydilammuon` |
| Documentation | `docs/project-summary.md`, `docs/next-steps.md` |

---

## Những phần còn phải làm

### Ưu tiên cao — Cần làm ngay
- [ ] Viết `src/analysis/` — virality scoring, engagement calc, topic classification
- [ ] Viết `src/main.py` — FastAPI entry point

### Ưu tiên thấp hơn — Làm sau khi data pipeline hoạt động
- [ ] Viết `src/generation/` — Claude API integration
- [ ] Viết `src/carousel/` — Pillow composition
- [ ] Build `src/dashboard/` — Next.js frontend

### Phase 2 (định hướng, chưa cam kết — xem CLAUDE.md, mục "Mục tiêu tổng thể")
- [ ] Đánh giá Meta App Review / Business Verification cho Advanced Access nếu muốn theo đuổi KOL Strategy Engine

---

## Điểm còn mở, rủi ro và câu hỏi cần xử lý

### Rủi ro kỹ thuật
| Rủi ro | Mức độ | Giải pháp dự kiến |
|--------|--------|-------------------|
| Threads API thay đổi (Meta thay đổi thường xuyên) | Trung bình | Tách `endpoints.py` riêng, dễ update |
| Long-lived token hết hạn sau 60 ngày | Thấp | `auth.py` cảnh báo khi còn < 7 ngày |
| Template PNG thay font/layout | Thấp | Tọa độ text cần định nghĩa thủ công mỗi template |

### Câu hỏi còn mở
- Giọng văn tác giả cần đọc scripts gốc để xác nhận chi tiết trước khi viết prompts cho `generation/`
- Template carousel: tọa độ text box của từng slide chưa được đo — cần làm khi implement `src/carousel/`
- Dashboard: chọn Next.js hay Streamlit? Streamlit nhanh hơn cho prototype, Next.js chuẩn hơn cho production
- Có cần tích hợp auto-post lên Threads không? Hiện tại thiết kế là manual post