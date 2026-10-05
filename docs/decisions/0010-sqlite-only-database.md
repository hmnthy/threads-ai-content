# ADR-0010: SQLite là cơ sở dữ liệu duy nhất — bỏ lời hứa PostgreSQL

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy (chọn "bỏ chữ planned"), Claude (đề xuất)

## Bối cảnh

3 README (dòng Database của bảng tech stack) và thẻ Database trên landing (`LandingTechStack.tsx`) ghi "SQLite (dev) → PostgreSQL (planned before any multi-user use)". Câu này có từ trước ADR-0001, khi sản phẩm còn hướng tới nhiều người dùng.

- `docs/roadmap.md` không có bước nào chuyển sang PostgreSQL. Phase E đặt knowledge base **trong chính file SQLite** (FTS5 + bảng embeddings) — sổ luật đã có `KB-no-separate-vectorstore`.
- Quy tắc docs: README chỉ ghi trạng thái thật, không hứa tính năng chưa có trong kế hoạch.
- Lỗi `database is locked` của job NLP (2026-09-30) do 2 job chạy chồng — Phase C sửa bằng cách cho job sau chờ, không cần đổi CSDL.

## Quyết định

SQLite (1 file, 1 tiến trình ghi tại một thời điểm) là cơ sở dữ liệu duy nhất của dự án, gồm cả knowledge base ở Phase E. Không ghi "PostgreSQL planned" ở bất kỳ đâu. Chỉ khi sau cổng F chatbot public cần nhiều tiến trình ghi đồng thời mới xét lại — bằng ADR mới.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ "PostgreSQL planned" | Không phải sửa | Hứa điều không có trong roadmap | Trái quy tắc "chỉ ghi trạng thái thật" |
| Đưa PostgreSQL vào roadmap | Nhất quán với lời hứa | Thêm hạ tầng không có nhu cầu thật (1 người ghi) | Không có bằng chứng cần |
| Ghi dạng điều kiện ("only if multi-user writes…") | Không phải lời hứa | Vẫn nhắc công nghệ không dùng | Thy chọn bỏ hẳn |

## Hệ quả

- Sửa dòng Database (README ×3), thẻ Database trên landing; bỏ mục này khỏi "Blocked" trong `docs/status.md`.
- Luật (`invariants.toml`, mục ADR-0010): `[[forbid]] ADR0010-postgres` cấm nhắc PostgreSQL ngoài `docs/decisions/**`; `[[stale_asset]] ADR0010-landing-screenshot` (thẻ Database hiện trên ảnh landing).
- Xem lại khi: chatbot public sau cổng F cần nhiều tiến trình ghi đồng thời, hoặc SQLite thành nút thắt đo được (latency/lock) sau khi Phase C đã tuần tự hoá job.
