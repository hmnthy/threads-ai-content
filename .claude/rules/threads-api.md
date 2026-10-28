---
paths:
  - "src/api/**"
  - "tests/api/**"
---

# Threads API

- Standard Access, chỉ tài khoản `thydilammuon` (Threads Tester). Không đọc được content/profile tài khoản khác ở quy mô có ý nghĩa.
- Post-level insights chỉ có `views, likes, replies, reposts, quotes` — **không** có `shares`, `reach`, `impressions`.
- `/me/replies` chỉ trả reply **của chính tác giả** (vai ở `posts.reply_role`, ADR-0004). `/{id}/conversation` đã verify live 2026-10-01: trả cả bình luận follower có text + username — **chưa lưu**, cần ADR-0007 (privacy, pseudonymize).
- Response shape không đồng nhất (edge `{"data": [...]}`, `total_value`, time-series theo ngày) — chi tiết + các lần "giả định sai rồi sửa" ở `docs/claude/data-model.md` §Threads API Integration.
- **Verify live trước khi tin**: field/endpoint mới phải gọi thật 1 lần, ghi kết quả vào `data-model.md`; test dùng fixture lấy từ response thật (đã ẩn danh).
- Pagination: follow `paging.next` tới hết (`_paginate()` trong `endpoints.py`) bằng cursor `after`; Meta trả HTTP 500 code 1 ở trang nặng → thu nhỏ `limit` và thử lại cùng cursor, không thử lại 4xx (`data-model.md`, verify 2026-10-17). Cache JSON TTL 6h ở `data/cache/`.
- Vòng phân trang/thử lại phải có guard tiến triển (cursor mới mỗi vòng, id không trùng); test cho nhánh thử lại/fallback phải chạy ở trang giữa (cursor ≠ None), không chỉ trang đầu (bài học review 2026-10-17: fallback mất cursor vẫn pass test trang đầu). Guard mới có `raise` trong code cron: trường hợp đó trước đây có vô hại không? Nếu có (VD bài trùng — upsert ghi đè) thì chỉ cảnh báo, trừ khi đã verify live.
- Token long-lived: job snapshot tự đổi mỗi 7 ngày (`src/pipeline/token_refresh.py`, ghi đè `.env` của thư mục chính) + `job_health` báo hạn. Không in token ra log/output — token nằm trong query string, nên logger `httpx` ghim ở WARNING (`client.py`); không hạ mức đó, và không dùng `raise_for_status()` cho request mang token (thông báo `HTTPStatusError` chứa URL đầy đủ) — dựng `ThreadsAPIError` từ body. Test không bao giờ gọi Meta thật hay sửa `.env`: `tests/conftest.py` chặn.
