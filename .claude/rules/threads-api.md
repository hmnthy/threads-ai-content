---
paths:
  - "src/api/**"
  - "tests/api/**"
---

# Threads API

- Standard Access, chỉ tài khoản `thydilammuon` (Threads Tester). Không đọc được content/profile tài khoản khác ở quy mô có ý nghĩa.
- Post-level insights chỉ có `views, likes, replies, reposts, quotes` — **không** có `shares`, `reach`, `impressions`.
- `/me/replies` chỉ trả reply **của chính tác giả**; bình luận của follower chưa được ingest (Phase D0 sẽ verify `/{id}/conversation`).
- Response shape không đồng nhất (edge `{"data": [...]}`, `total_value`, time-series theo ngày) — chi tiết + các lần "giả định sai rồi sửa" ở `docs/claude/data-model.md` §Threads API Integration.
- **Verify live trước khi tin**: field/endpoint mới phải gọi thật 1 lần, ghi kết quả vào `data-model.md`; test dùng fixture lấy từ response thật (đã ẩn danh).
- Pagination: follow `paging.next` tới hết (`_paginate()` trong `endpoints.py`). Cache JSON TTL 6h ở `data/cache/`.
- Token long-lived: `auth.py` refresh + cảnh báo hết hạn. Không in token ra log/output.
