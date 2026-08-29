# Next Steps — Threads AI Content
> Cập nhật: 2026-08-28

---

## Hành động ưu tiên ngay khi quay lại

### 1. Meta Developer setup — ĐÃ HOÀN TẤT

App `threads-thydilammuon`, use case Threads API, 8 permissions (Standard Access), Tester `thydilammuon` đã accept, `.env` đủ 4/5 giá trị. Không còn việc gì ở mục này.

### 2. `src/api/` — ĐÃ HOÀN TẤT

6 file (`models.py`, `cache.py`, `auth.py`, `client.py`, `endpoints.py`, `__init__.py`) + test đầy đủ tại `tests/api/` (22 test). Tooling: `uv` + `pyproject.toml`, ruff + mypy strict + pytest + pre-commit, git repo đã init.

```bash
uv run pytest -q          # 22 passed
uv run ruff check .       # All checks passed!
uv run mypy               # Success: no issues found
```

### 3. Test end-to-end với data thật — ĐÃ HOÀN TẤT (2026-08-28)

Đã fetch thật 25 posts + account insights của `thydilammuon`. Phát hiện và sửa 2 vấn đề thật trong `endpoints.py`/`models.py` mà giả định ban đầu sai:
- `children` (field post) là edge `{"data": [{"id": ...}]}`, không phải `list[str]` phẳng → đã thêm `field_validator` trong `ThreadsPost`.
- `follower_demographics` bắt buộc param `breakdown`, không gộp được với các metric khác → tách thành hàm riêng `get_follower_demographics()`. Response shape account-level cũng không đồng nhất giữa các metric (`views` là time-series theo ngày cần cộng dồn, `likes/replies/...` là `total_value`, `clicks` là `link_total_values` theo từng link) — chi tiết đầy đủ tại `docs/claude/data-model.md` phần "Metrics lấy từ API".

Test suite hiện có 25 test, tất cả pass, cùng ruff/mypy sạch.

### 4. Viết `src/analysis/` rồi `src/main.py`

```
1. src/analysis/engagement.py     — engagement rate, đã có sẵn công thức trong PostInsights.engagement_rate
2. src/analysis/virality.py       — virality index theo công thức trong docs/claude/data-model.md
3. src/analysis/topics.py         — phân loại post theo topic (keyword matching + Claude classification)
4. src/main.py                    — FastAPI entry point, expose các endpoint qua /docs
```

---

## Kế hoạch theo giai đoạn

```
GIAI ĐOẠN 1 — Data Foundation
├── [x] Meta Developer setup + credentials
├── [x] src/api/ (6 files + test, tooling uv/ruff/mypy/pytest/pre-commit)
├── [x] Verify field mapping insights với data thật (25 posts + account insights fetch thành công)
├── [ ] src/analysis/ (virality index, engagement calc, topic classifier)
└── [ ] src/main.py (FastAPI entry point)
    → Có thể: fetch data thydilammuon và xem kết quả qua /docs

GIAI ĐOẠN 2 — Dashboard
├── src/dashboard/ (Next.js hoặc Streamlit)
├── Trang Dashboard + Analytics + Topic Explorer
└── Mobile responsive + scroll animations
    → Có thể: xem analytics trực quan trên web

GIAI ĐOẠN 3 — AI Content
├── src/generation/ (Claude API + prompts từ scripts gốc)
├── Trang Generate Content trên dashboard
└── Workflow: propose → review → approve
    → Có thể: generate content mới đúng giọng văn

GIAI ĐOẠN 4 — Carousel
├── src/carousel/ (Pillow + Google Sans)
├── Đo tọa độ text box từng template PNG
├── Trang Carousel Builder trên dashboard
└── Export PNG sequence
    → Hoàn chỉnh toàn bộ workflow
```

---

## Prompt sẵn để resume project

Copy đoạn sau và paste vào Claude khi quay lại:

```
Tôi đang tiếp tục dự án "Threads AI Content" — công cụ AI phân tích và generate content cho kênh Threads "thydilammuon".

Hãy đọc CLAUDE.md và docs/next-steps.md để nắm context (đọc thêm file liên quan trong docs/claude/ nếu task chạm tới đúng mảng đó), sau đó:
1. Tóm tắt ngắn gọn project đang ở đâu (1 đoạn)
2. Xác nhận bước tiếp theo cần làm là gì
3. Hỏi tôi cần làm gì trong phiên này trước khi bắt đầu

Working directory: c:\Users\hmnth\Desktop\Portfolio\project_AI\threads-ai-content
```

---

## Tham khảo nhanh

| Tài nguyên | Đường dẫn / Link |
|-----------|-----------------|
| Threads API docs | https://developers.facebook.com/docs/threads/ |
| Retrieve posts | https://developers.facebook.com/docs/threads/retrieve-and-discover-posts/retrieve-posts |
| Insights API | https://developers.facebook.com/docs/threads/insights |
| Meta Developer Portal | https://developers.facebook.com |
| Design reference | `docs/design/dashboard-reference.png` |
| Carousel templates | `Content/Content - Photo carousel/` |
| Scripts gốc (giọng văn) | `Content/Scripts/` |
| Font Google Sans | `src/carousel/fonts/Google_Sans/static/` |