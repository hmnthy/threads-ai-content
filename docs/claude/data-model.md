# Data Model — Threads AI Content

> Đọc khi: làm việc trong `src/api/`, `src/analysis/`, hoặc cần biết field/metrics/response shape thật của Threads API, công thức Virality Index, hay mapping chủ đề↔template.
> Xem thêm: [`architecture.md`](architecture.md) cho tech stack/cấu trúc thư mục, [`CLAUDE.md`](../../CLAUDE.md) cho mission/status.

---

## Threads API Integration

**Docs**: https://developers.facebook.com/docs/threads/

### Endpoints cần thiết

```
GET /{user_id}/threads                   # Danh sách posts của kênh
GET /{user_id}/replies                   # Danh sách reply tác giả đã đăng
GET /{thread-id}/insights                # Metrics của 1 post
GET /{user_id}/threads_insights          # Metrics tổng kênh
POST /me/threads                         # Publish post mới (nếu tích hợp auto-post)
```

### Pagination

`GET /{user_id}/threads` và `GET /{user_id}/replies` đều trả kết quả theo **cursor pagination** chuẩn Graph API: response có thêm object `paging: { cursors: { before, after }, next: "<url trang tiếp theo>" }`. Không truyền `limit` → API tự dùng page size mặc định (phát hiện thực tế: 25/page).

`get_posts()` và `get_replies()` (`src/api/endpoints.py`) đều dùng chung helper `_paginate()` — gọi `ThreadsClient.get_url()` với URL tuyệt đối từ `paging.next` (URL này đã có sẵn `access_token`, không inject lại) cho tới khi response không còn `paging.next`. Đảm bảo lấy đủ toàn bộ lịch sử kênh, không chỉ page đầu.

`get_replies()` mới thêm (2026-08-29), dùng scope `threads_manage_replies` đã có sẵn ở Phase 1, tái dùng `POST_FIELDS` + model `ThreadsPost` với `/threads`.

**Verify live (2026-08-29)**: đã fetch thật cả 2 endpoint với pagination fix — `/replies` trả đúng shape như giả định (25/25 item validate sạch qua `ThreadsPost`, không có field lạ ngoài `POST_FIELDS`, các field optional như `thumbnail_url`/`quoted_post`/`reposted_post` chỉ đơn giản là không có mặt ở item nào chứ không sai kiểu). Số liệu thật của kênh `thydilammuon`: **140 posts**, **1,285 replies** (con số "25 posts" ghi ở lần verify trước chỉ là page 1 do bug pagination lúc đó — đã lỗi thời).

### Fields có thể lấy từ mỗi post

`id`, `text`, `timestamp`, `media_type`, `permalink`, `shortcode`, `username`,
`media_url`, `thumbnail_url`, `is_quote_post`, `quoted_post`, `reposted_post`, `children`

`media_type` values: `TEXT_POST`, `IMAGE`, `VIDEO`, `CAROUSEL_ALBUM`, `AUDIO`, `REPOST_FACADE`

### Metrics lấy từ API

**Post-level**: `views`, `likes`, `replies`, `reposts`, `quotes` — response shape: `period: "lifetime"`, `values: [{"value": N}]` (1 phần tử)
**Account-level**: `views`, `likes`, `replies`, `reposts`, `quotes`, `clicks`, `followers_count` (qua `get_account_insights`) + `follower_demographics` riêng (qua `get_follower_demographics`, bắt buộc `breakdown`)

> `reach` và `impressions` **không tồn tại** trong Threads API (khác Instagram)

**Response shape KHÔNG đồng nhất giữa các metric account-level (verify live 2026-08-28)**:
| Metric | Shape thật | Cách `_flatten_insights` xử lý |
|---|---|---|
| `views` | `period: "day"`, `values: [{"value": N}, ...]` — nhiều entry theo ngày | Cộng dồn (sum) toàn bộ `values` |
| `likes`, `replies`, `reposts`, `quotes`, `followers_count` | `total_value: {"value": N}` | Lấy `total_value["value"]` |
| `clicks` | `link_total_values: [{"value": N, "link_url": ...}, ...]` — theo từng link | Cộng dồn toàn bộ `value` |
| `follower_demographics` | **Bắt buộc** param `breakdown` (`country`/`city`/`age`/`gender`), nếu thiếu → lỗi `error_subcode 4279040`. Khi có, trả `total_value` dạng breakdown (không có key `"value"`) | Giữ nguyên dict breakdown |

`children` (field của post, dùng cho carousel album) cũng là dạng edge: `{"data": [{"id": ...}, ...]}`, không phải `list[str]` phẳng — `ThreadsPost` đã có validator tự flatten (`src/api/models.py`).

### Auth

- OAuth 2.0, token lưu trong `.env` (không commit)
- Scope Phase 1 (đang dùng): `threads_basic`, `threads_manage_insights`, `threads_content_publish`, `threads_manage_replies`
- Scope đã request sẵn cho Phase 2 (Standard Access, chưa dùng được đầy đủ — xem Phase 2 trong `CLAUDE.md`): `threads_trending_topics`, `threads_keyword_search`, `threads_read_replies`, `threads_profile_discovery`
- Long-lived token: 60 ngày — dùng `refresh_long_lived_token()` trong `src/api/auth.py` trước khi hết hạn; `should_warn_expiry()` cảnh báo khi còn ≤ 7 ngày (chỉ hoạt động sau lần refresh đầu tiên, vì Threads không cho tra hạn còn lại của 1 token bất kỳ)
- Rate limit chính tài khoản: `4,800 × số impressions` / 24h (rất cao, khó chạm)
- Token hiện tại lấy trực tiếp qua công cụ **"Tạo mã truy cập"** trong Meta Dashboard (App → Trường hợp sử dụng → Truy cập API Threads → Cài đặt → Công cụ tạo mã người dùng) — công cụ này trả ngay long-lived token cho tester đã approve, không cần tự dựng OAuth redirect flow

### Trạng thái setup Meta Developer

1. [x] Tìm hiểu API docs
2. [x] Tạo Meta Developer App (`threads-thydilammuon`)
3. [x] Thêm Threads API use case
4. [x] Lấy App ID + App Secret (dùng cặp **Threads-specific**, không dùng App ID/Secret tổng)
5. [x] Add `thydilammuon` làm Threads Tester — đã accept lời mời (Threads app → Settings → Account → Website permissions → Invites)
6. [x] Generate long-lived Access Token trực tiếp qua "Tạo mã truy cập" (bỏ qua bước exchange short-lived thủ công)
7. [x] Lấy User ID qua `GET https://graph.threads.net/v1.0/me?fields=id,username&access_token=<TOKEN>`
8. [x] Điền đủ 4 giá trị vào `.env`

Setup Meta Developer đã **hoàn tất**.

---

## Virality Index

Công thức tính index 0–100 (implement trong `src/analysis/virality.py`):

```python
def virality_index(post):
    engagement = (likes + replies * 2 + reposts * 3 + quotes * 2) / views
    recency_boost = decay_factor(post_age_hours)  # posts mới được boost
    topic_trend_score = trend_score(post.topic)  # topic đang trending
    length_penalty = optimal_length_score(char_count)  # 150-300 ký tự = optimal

    raw = (
        (engagement * 0.5)
        + (recency_boost * 0.2)
        + (topic_trend_score * 0.2)
        + (length_penalty * 0.1)
    )
    return min(round(raw * 100, 1), 100)
```

Hiển thị kèm label: `Thấp (<30)` / `Trung bình (30–60)` / `Cao (60–80)` / `Viral potential (>80)`

Engagement rate cơ bản (dùng cho `PostInsights.engagement_rate`, `src/api/models.py`): `(likes + replies + reposts) / views * 100`

---

## Chủ đề content hiện có (từ carousel templates)

| Chủ đề | Template | Posts điển hình |
|--------|----------|-----------------|
| Alternance | Alternance/ (7 slides) | Kinh nghiệm alternance, tìm chỗ thực tập |
| CV | CV/ (9 slides) | Cách viết CV Pháp, tips hồ sơ |
| Entretien | Entretien/ (11 slides) | Tips phỏng vấn, câu hỏi thường gặp |
| Lifestyle / Đi đâu chơi gì | Photos/ | Địa điểm, trải nghiệm tại Pháp |
| Data / Insights | Scripts | Posts dạng data, số liệu |
| Divers | Scripts | Các chủ đề tổng hợp khác |
