# Threads AI Content — CLAUDE.md

> Cập nhật lần cuối: 2026-08-29
> Trạng thái: **Phase 1 — `src/api/` đã viết xong và verify end-to-end với data thật, sẵn sàng viết `src/analysis/`**

---

## Mục tiêu tổng thể

Dự án có **2 tầng mục tiêu**, khác nhau về mức độ ưu tiên, ràng buộc kỹ thuật, và mức độ cam kết triển khai.

### Phase 1 — Công cụ phân tích & content cho kênh cá nhân (đang triển khai)

AI solution phân tích và generate content cho kênh Threads **"Thy đi làm muộn"** — kênh của một người Việt tại Pháp, chia sẻ về cuộc sống đi làm, alternance, xin việc, và lifestyle tại Pháp.

Mục tiêu: kéo data từ Threads API → phân tích hiệu suất → gợi ý content mới → generate carousel theo template có sẵn, **luôn giữ đúng giọng văn gốc của tác giả**.

**Đây là internal tool dùng riêng cho tác giả** — không phải SaaS công khai. Không cần auth nhiều user, không cần scale lớn. Dùng Threads API ở mức **Standard Access** (chỉ thao tác trên chính tài khoản `thydilammuon` thông qua vai trò Threads Tester).

### Phase 2 — Nghiên cứu hệ sinh thái Threads & KOL Strategy Engine (định hướng, chưa triển khai)

Tham vọng dài hạn: mở rộng từ phân tích 1 kênh sang **nghiên cứu algo/hệ sinh thái Threads trên diện rộng**, ứng dụng NLP để rút ra insight về:
- Pattern nội dung & thời điểm đăng tương quan với hiệu suất cao, tổng hợp từ nhiều tài khoản công khai (không chỉ kênh của tác giả)
- Trending topics theo thời gian thực trên nền tảng Threads
- Chiến lược reply/tương tác chéo giúp tăng visibility, dựa trên hành vi reply chủ động hiện có của tác giả

Đích đến: xây dựng một **"KOL Strategy Engine" dựa trên NLP** — theo đánh giá hiện tại, đây là hướng sản phẩm/phương pháp luận **chưa có trên thị trường**, có tiềm năng vượt ra ngoài phạm vi "internal tool" nếu chứng minh được giá trị thực tế.

**Ràng buộc kỹ thuật cần lưu ý (chốt ngày 2026-08-28)**:
- Bắt buộc cần **Advanced Access** qua Meta App Review (Business Verification, Privacy Policy URL, mô tả use case, video demo) — Standard Access hiện tại **không đủ** để đọc content/profile của tài khoản khác ở quy mô có ý nghĩa; Meta thiết kế Standard Access chỉ để test trên chính tài khoản tester.
- `threads_keyword_search` giới hạn **500 query / 7 ngày** ngay cả khi được duyệt Advanced Access — không đủ cho phân tích hệ thống liên tục, cần chiến lược lấy mẫu (sampling) hợp lý.
- Các quyền liên quan đã được thêm sẵn ở mức Standard Access (chưa dùng được đầy đủ cho tới khi có Advanced Access): `threads_trending_topics`, `threads_keyword_search`, `threads_read_replies`, `threads_profile_discovery`.
- **Chưa cam kết timeline hay engineering effort** cho Phase 2 — đây là hướng nghiên cứu/roadmap, sẽ được lên kế hoạch cụ thể (module phân tích, kiến trúc NLP, nguồn dữ liệu, chi phí App Review) sau khi Phase 1 (data pipeline + dashboard cơ bản) hoàn thiện và ổn định.

> **Nguyên tắc ưu tiên**: mọi quyết định kỹ thuật ở Giai đoạn 1 — Data Foundation hiện tại phục vụ Phase 1. Phase 2 không được phép làm chậm tiến độ hoặc làm phức tạp hoá kiến trúc của Phase 1.

---

## Trạng thái hiện tại (2026-08-29)

| Hạng mục | Trạng thái |
|----------|-----------|
| CLAUDE.md & tài liệu kiến trúc | Hoàn tất — xem mục "Kiến trúc tài liệu" bên dưới |
| Font Google Sans (Việt hóa) | Đã tải về tại `src/carousel/fonts/Google_Sans/` |
| Carousel templates | Có sẵn tại `Content/Content - Photo carousel/` |
| Meta Developer App | **Hoàn tất** — app `threads-thydilammuon`, use case Threads API |
| Threads permissions | `threads_basic`, `threads_manage_insights`, `threads_content_publish`, `threads_manage_replies`, `threads_trending_topics`, `threads_keyword_search`, `threads_read_replies`, `threads_profile_discovery` — tất cả Standard Access |
| Threads Tester | `thydilammuon` đã accept lời mời |
| Credentials (.env) | **Đủ 4/5 giá trị** — thiếu `ANTHROPIC_API_KEY` (chưa cần tới Giai đoạn 3) |
| Tooling | `uv` + `pyproject.toml`, ruff (lint+format) + mypy strict + pytest + pre-commit — tất cả đã setup và pass |
| Git | Repo đã init (`git init`), pre-commit hook đã cài, **chưa có commit nào** |
| `src/api/` code | **Hoàn tất & verify với data thật** — `models.py`, `cache.py`, `auth.py`, `client.py`, `endpoints.py`, `__init__.py` + test đầy đủ (25 test pass). Đã fetch thật 25 posts + account insights của `thydilammuon` |
| `src/analysis/` | Chưa viết |
| `src/generation/` | Chưa viết |
| `src/carousel/` | Chưa viết |
| Dashboard (Next.js) | Chưa viết |

**Bước tiếp theo ngay**: Viết `src/analysis/` (virality index, engagement calc, topic classifier) dựa trên `src/api/` đã verify, rồi `src/main.py` (FastAPI entry point).

---

## Kiến trúc tài liệu

CLAUDE.md gốc chỉ giữ phần **luôn cần thiết mỗi phiên** (mission, trạng thái, quy tắc tuyệt đối). Chi tiết kỹ thuật theo từng mảng được tách sang `docs/claude/` — **đọc theo nhu cầu khi task chạm tới đúng mảng đó**, không cần đọc hết mỗi phiên:

| File | Đọc khi... |
|---|---|
| [`docs/claude/architecture.md`](docs/claude/architecture.md) | Cần cấu trúc thư mục, tech stack, decisions log, workflow diagram, roadmap tính năng |
| [`docs/claude/data-model.md`](docs/claude/data-model.md) | Làm việc với `src/api/`/`src/analysis/`, cần field/metrics/response shape của Threads API, công thức Virality Index, mapping topic↔template |
| [`docs/claude/design-system.md`](docs/claude/design-system.md) | Làm việc với `src/dashboard/` — color palette, typography, component patterns, layout, motion |
| [`docs/claude/dev-rules.md`](docs/claude/dev-rules.md) | Setup môi trường, chạy lệnh dev, implement `src/generation/`/`src/carousel/` |

---

## Quy tắc tuyệt đối

- **Không tự đăng lên Threads** khi chưa được tác giả review và approve
- **Không sửa template gốc** trong `Content/Content - Photo carousel/`
- **Không generate carousel** khi chưa có approved text content
- **Không commit** `.env`, API tokens, hoặc personal data
- **Luôn đọc scripts gốc** trong `Content/Scripts/` trước khi generate text content mới
- Giọng văn phải phản ánh đúng tác giả — không dùng giọng generic AI

---

## Khi bắt đầu phiên mới

1. Đọc `docs/next-steps.md` để biết đang ở đâu và làm gì tiếp
2. Kiểm tra `.env` đã có đủ credentials chưa (`THREADS_APP_ID`, `THREADS_APP_SECRET`, `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`; `ANTHROPIC_API_KEY` cần từ Giai đoạn 3)
3. Chạy `uv run pytest -q` để xác nhận môi trường vẫn ổn định trước khi code tiếp
4. Đọc `Content/Scripts/*.docx` trước khi generate bất kỳ nội dung nào
5. Đọc file liên quan trong `docs/claude/` đúng với mảng đang làm (xem bảng "Kiến trúc tài liệu" ở trên) — không cần đọc hết
