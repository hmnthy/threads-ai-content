# Next Steps — Threads AI Content
> Cập nhật: 2026-08-29
> **Đang chạy theo `docs/sprint-plan.md`** — kế hoạch ngày-theo-ngày (Giai đoạn 1-3, Carousel hoãn lại). File này giữ lịch sử các mốc đã qua; sprint-plan.md là nguồn "hôm nay làm gì".

---

## Hành động ưu tiên ngay khi quay lại

### 1. Meta Developer setup — ĐÃ HOÀN TẤT

App `threads-thydilammuon`, use case Threads API, 8 permissions (Standard Access), Tester `thydilammuon` đã accept, `.env` đủ 4/5 giá trị. Không còn việc gì ở mục này.

### 2. `src/api/` — ĐÃ HOÀN TẤT

6 file (`models.py`, `cache.py`, `auth.py`, `client.py`, `endpoints.py`, `__init__.py`) + test đầy đủ tại `tests/api/` (27 test). Tooling: `uv` + `pyproject.toml`, ruff + mypy strict + pytest + pre-commit, git repo đã init.

```bash
uv run pytest -q          # 27 passed
uv run ruff check .       # All checks passed!
uv run mypy               # Success: no issues found
```

### 3. Test end-to-end với data thật — ĐÃ HOÀN TẤT (2026-08-28)

Đã fetch thật 25 posts + account insights của `thydilammuon`. Phát hiện và sửa 2 vấn đề thật trong `endpoints.py`/`models.py` mà giả định ban đầu sai:
- `children` (field post) là edge `{"data": [{"id": ...}]}`, không phải `list[str]` phẳng → đã thêm `field_validator` trong `ThreadsPost`.
- `follower_demographics` bắt buộc param `breakdown`, không gộp được với các metric khác → tách thành hàm riêng `get_follower_demographics()`. Response shape account-level cũng không đồng nhất giữa các metric (`views` là time-series theo ngày cần cộng dồn, `likes/replies/...` là `total_value`, `clicks` là `link_total_values` theo từng link) — chi tiết đầy đủ tại `docs/claude/data-model.md` phần "Metrics lấy từ API".

Test suite hiện có 25 test, tất cả pass, cùng ruff/mypy sạch.

### 4. Pagination cho `get_posts()` + thêm `get_replies()` — ĐÃ HOÀN TẤT (2026-08-29)

`get_posts()` trước đây chỉ lấy 1 page (25 posts, default page size của Graph API) — không follow `paging.cursors.after`/`paging.next` nên bỏ sót phần còn lại của lịch sử kênh nếu kênh có > 25 bài. Đã sửa:
- Thêm `ThreadsClient.get_url()` — fetch thẳng URL tuyệt đối (`paging.next` đã có sẵn `access_token`, không inject lại)
- Thêm helper `_paginate()` trong `endpoints.py`, dùng chung cho `get_posts()` và `get_replies()` mới — loop theo `paging.next` tới khi hết
- Thêm `get_replies()` (dùng scope `threads_manage_replies` đã có sẵn ở Phase 1) — lấy toàn bộ reply tác giả đã đăng, cache riêng key `replies_{user_id}`

**Verify live (2026-08-29)**: fetch thật cả 2 endpoint — `/replies` trả đúng shape như giả định ban đầu (khác với `children`/account insights trước đây, lần này giả định đúng ngay, không cần sửa code). Số liệu thật của kênh: **140 posts** (số "25 posts" ghi ở mục 3 chỉ là page 1 do bug pagination cũ, đã lỗi thời), **1,285 replies**.

Test suite hiện có 27 test (thêm 2: pagination `get_posts()` qua nhiều trang + `get_replies()`), tất cả pass, ruff/mypy sạch.

### 5. `src/analysis/engagement.py` — ĐÃ HOÀN TẤT (2026-08-29)

Build trên `PostInsights.engagement_rate` có sẵn:
- `average_engagement_rate(insights)` — trung bình engagement rate trên tập post
- `top_posts_by_engagement(posts, insights, limit)` — ghép post với insights theo `id`/`post_id`, sort giảm dần, bỏ qua post không có insights khớp
- `engagement_by_hour(posts, insights)` / `engagement_by_weekday(posts, insights)` — gom nhóm theo giờ/thứ trong tuần, phục vụ heatmap "giờ đăng tốt nhất" ở dashboard

**Cập nhật (2026-08-29)**: audience kênh trải cả Pháp và Việt Nam (2 múi giờ chênh 5-6h tùy DST) — Threads API không cho biết engagement tới từ đâu, nên không tách được thật sự theo audience. Giải pháp: `engagement_by_hour`/`engagement_by_weekday` nhận thêm param `timezone: ZoneInfo | None` — gọi 2 lần với `ZoneInfo("Europe/Paris")` và `ZoneInfo("Asia/Ho_Chi_Minh")` để so sánh 2 góc nhìn trên cùng dữ liệu (mặc định `None` giữ nguyên UTC thô, tương thích ngược). Cần thêm `tzdata` vào dependencies vì Windows không có sẵn IANA timezone database. Chi tiết lý do tại `docs/claude/architecture.md` phần "Quyết định quan trọng đã chốt".

Test suite hiện có 35 test (33 trước đó + 2 test timezone conversion), tất cả pass, ruff/mypy sạch.

### 6. [SUPERSEDED 2026-08-30] `src/analysis/virality.py`, `src/analysis/topics.py`, rồi `src/main.py`

> Mục này đã lỗi thời — `topics.py` (keyword matching + Claude classification) bị thay hoàn toàn bằng pipeline NLP thật (embedding + SVM-RBF/LogReg + UMAP/HDBSCAN + RAG). Xem `docs/sprint-plan.md` (Ngày 1-13) cho kế hoạch hiện hành, `docs/claude/data-model.md` phần "NLP Pipeline" cho thiết kế chi tiết.

---

## Kế hoạch theo giai đoạn

**[SUPERSEDED 2026-08-30]** — kế hoạch chi tiết theo ngày (13 ngày, Giai đoạn 1-3 mở rộng NLP/RAG, Giai đoạn 4 hoãn) nay nằm ở `docs/sprint-plan.md`, không lặp lại ở đây nữa để tránh 2 nguồn lệch nhau theo thời gian.

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