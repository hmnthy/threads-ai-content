# Threads AI Content — CLAUDE.md

> Cập nhật lần cuối: 2026-08-30 (redesign v2: 6-index metrics + ContentUnit + code-switching-tolerant NLP)
> Trạng thái: **Phase 1 — `src/api/` hoàn tất & verify; `src/analysis/engagement.py` xong; Bước 0 (verify API field cho ContentUnit) đã xong. Kế hoạch chi tiết + lý do tại `docs/sprint-plan.md` + `docs/claude/data-model.md`**

---

## Mục tiêu tổng thể

Dự án có **2 tầng mục tiêu**, khác nhau về mức độ ưu tiên, ràng buộc kỹ thuật, và mức độ cam kết triển khai.

### Phase 1 — Công cụ phân tích & content cho kênh cá nhân (đang triển khai)

AI solution phân tích và generate content cho kênh Threads **"thydilammuon"** — kênh của một người Việt tại Pháp, chia sẻ về cuộc sống đi làm, alternance, xin việc, và lifestyle tại Pháp.

Mục tiêu: kéo data từ Threads API → phân tích hiệu suất → gợi ý content mới dựa trên giọng văn tác giả và quét data báo chí tại Pháp, những nội dung phù hợp kênh giáo dục và cuộc sống tại Pháp → generate carousel theo template có sẵn éventuellement - tùy tình hình, **luôn giữ đúng giọng văn gốc của tác giả**.

**Đây là internal tool dùng riêng cho tác giả, được đăng lên 1 link website để đáp ứng nhu cầu cho portfolio DS/MLE** — không phải SaaS công khai. Không cần auth nhiều user, không cần scale lớn. Dùng Threads API ở mức **Standard Access** (tập trung thao tác trên chính tài khoản `thydilammuon` thông qua vai trò Threads Tester).

### Phase 2 — Nghiên cứu hệ sinh thái Threads & KOL Strategy Engine (định hướng, chưa triển khai)

Tham vọng kéo dài xuyên suốt: mở rộng từ phân tích 1 kênh sang **nghiên cứu algo/hệ sinh thái Threads trên diện rộng**, ứng dụng NLP để rút ra insight về:
- Pattern nội dung & thời điểm đăng tương quan với hiệu suất cao, tổng hợp từ nhiều tài khoản công khai (không chỉ kênh của tác giả)
- Trending topics theo thời gian thực trên nền tảng Threads
- Chiến lược reply/tương tác chéo giúp tăng visibility, dựa trên hành vi reply chủ động hiện có của tác giả

Đích đến: xây dựng một **"KOL Strategy Engine" dựa trên NLP** — theo đánh giá hiện tại, đây là hướng sản phẩm/phương pháp luận **chưa có trên thị trường**, có tiềm năng vượt ra ngoài phạm vi "internal tool" nếu chứng minh được giá trị thực tế, có impact, có câu chuyện, có kỹ thuật rõ ràng, đáp ứng tiêu chuẩn project NLP/MLE trong năm 2026. 

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
| Git | Đã đồng bộ GitHub — [`hmnthy/threads-ai-content`](https://github.com/hmnthy/threads-ai-content) (private), branch `main`, commit đầu tiên `31adcbc`. `Content/` không commit (personal media + rate card) |
| `src/api/` code | **Hoàn tất & verify với data thật** — `models.py`, `cache.py`, `auth.py`, `client.py`, `endpoints.py`, `__init__.py` + test đầy đủ (27 test pass). Pagination đầy đủ + `get_replies()` verify live (2026-08-29): **140 posts, 1,285 replies** của `thydilammuon` |
| `src/analysis/` | `engagement.py` xong (average, top posts, by hour/weekday) — `virality.py` + NLP pipeline (`preprocessing.py`/`embeddings.py`/`classification.py`/`clustering.py`/`trends.py`) chưa viết, xem `docs/sprint-plan.md` |
| `src/generation/` | Chưa viết |
| `src/carousel/` | Chưa viết |
| Dashboard (Next.js) | Chưa viết |

**Bước tiếp theo ngay**: Bước 1 trong `docs/sprint-plan.md` — `src/models/` (`ContentUnit`, `InsightSnapshot`) + `src/db/` schema. Bước 0 (verify API field) đã xong.

---

## Kiến trúc tài liệu

CLAUDE.md gốc chỉ giữ phần **luôn cần thiết mỗi phiên** (mission, trạng thái, quy tắc tuyệt đối). Chi tiết kỹ thuật theo từng mảng được tách sang `docs/claude/` — **đọc theo nhu cầu khi task chạm tới đúng mảng đó**, không cần đọc hết mỗi phiên:

| File | Đọc khi... |
|---|---|
| [`docs/claude/architecture.md`](docs/claude/architecture.md) | Cần cấu trúc thư mục, tech stack, decisions log, workflow diagram, roadmap tính năng |
| [`docs/claude/data-model.md`](docs/claude/data-model.md) | Làm việc với `src/api/`/`src/analysis/`, cần field/metrics/response shape của Threads API, công thức Virality Index, mapping topic↔template |
| [`docs/claude/design-system.md`](docs/claude/design-system.md) | **BẮT BUỘC đọc trước MỌI việc chạm tới UI** (`src/dashboard/`, frontend, mockup, artifact, HTML demo) — nguồn sự thật duy nhất về design: tokens, tầng A/B, component patterns, chart rules, checklist merge, query cookbook cho `ui-ux-pro-max` |
| [`docs/claude/dev-rules.md`](docs/claude/dev-rules.md) | Setup môi trường, chạy lệnh dev, implement `src/generation/`/`src/carousel/` |
| [`docs/research/README.md`](docs/research/README.md) | **Nghiên cứu thị trường và methodology (PRIVATE)**: đọc trước khi thay đổi metric, định nghĩa viral hay NLP pipeline, hoặc khi cần cite nguồn/paper cho một quyết định kỹ thuật. README là chỉ mục các kết luận đã chốt và đề xuất chưa duyệt; chi tiết trong các file HTML cùng thư mục |

---

## Quy tắc tuyệt đối

- **Không tự đăng lên Threads** khi chưa được tác giả review và approve
- **Không sửa template gốc** trong `Content/Content - Photo carousel/`
- **Không generate carousel** khi chưa có approved text content
- **Không commit** `.env`, API tokens, hoặc personal data
- **Luôn đọc scripts gốc** trong `Content/Scripts/` trước khi generate text content mới
- Giọng văn phải phản ánh đúng tác giả — không dùng giọng generic AI

### Design — routing bắt buộc (chốt 2026-09-02, cập nhật 2026-09-03)

- **Nguồn sự thật DUY NHẤT về design là [`docs/claude/design-system.md`](docs/claude/design-system.md)** (hiện tại: v3.1 Amber). Phải đọc file này **trước khi viết dòng UI đầu tiên** — kể cả với mockup nhanh, artifact, hay HTML demo dùng một lần.
  - Không tự chọn palette / font / layout. Không dùng default palette của model.
  - Thứ tự thắng khi mâu thuẫn: **design-system.md > [`docs/design/dashboard-reference.png`](docs/design/dashboard-reference.png) (chỉ còn dùng cho cấu trúc/hình khối, không dùng cho màu) > mọi nguồn khác** (skill, generator, "best practice" chung) — xem §0 trong `design-system.md`.
  - Lý do đảo priority PNG↔file (2026-09-03): PNG dùng violet, dự án đã chủ động rời khỏi violet (quá generic cho mọi AI SaaS) sang amber sau khi dựng và so sánh 2 hướng thật — xem §13 Decision log trong `design-system.md`.
  - Lý do gốc file này là nguồn duy nhất: 2026-09-01 artifact `f23eb6c8` được sinh mà không đọc cả design-system.md lẫn PNG, tạo ra hướng design thứ ba (`#f9f9f7` + Instrument Serif).

- **Skill `.claude/skills/ui-ux-pro-max/` là công cụ TRA CỨU, không phải nguồn design.**
  - **KHÔNG nạp `SKILL.md` vào context** (55KB ≈ 15k token mỗi lần trigger). Chỉ chạy CLI:
    ```bash
    # Windows: python | Linux/macOS: python3
    python .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain <chart|ux|icons|react|color|typography> -n 3
    python .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --stack <nextjs|react|shadcn|html-tailwind>
    ```
  - **NGHIÊM CẤM `--design-system` và `--persist`.** Generator sinh palette + pattern landing-page marketing mâu thuẫn với `design-system.md`; `--persist` còn ghi ra `design-system/<slug>/MASTER.md` ở project root, tạo nguồn sự thật thứ hai.
  - Query phải viết theo **triệu chứng quan sát được**, 2-5 từ, không theo chủ đề. Cookbook sẵn có: `design-system.md` §11.
  - Kết quả trả về là khuyến nghị. Mâu thuẫn với `design-system.md` → `design-system.md` thắng.
  - Các skill design khác trong `.claude/skills/` (`design`, `design-system`, `ui-styling`, `slides`, `banner-design`, `brand`) **không dùng cho dashboard** — chúng trùng vai trò và sẽ kéo lệch khỏi reference.
- **Nghiên cứu thị trường và methodology: xem `docs/research/README.md` trước khi thay đổi metric hay NLP pipeline.** Thư mục `docs/research/` là quá trình hình thành methodology (private) — không đưa vào repo public/bản squash; README công khai chỉ mô tả methodology bản cuối. Đề xuất trong đó chỉ được triển khai sau khi Thy duyệt, và khi triển khai phải ghi vào decisions log `docs/claude/architecture.md`.
- **Không thêm trailer `Co-Authored-By: Claude...`** vào git commit message (quyết định 2026-08-30 — repo này sẽ dùng làm nguồn squash sang 1 repo public riêng sau; commit message + decisions log trong `docs/claude/architecture.md` đã đủ thể hiện quá trình tư duy, không cần trailer). Lịch sử commit cũ trước quyết định này (`31adcbc`, `3eceabe`) giữ nguyên, không rewrite.

---

## Khi bắt đầu phiên mới

1. Đọc `docs/next-steps.md` để biết đang ở đâu và làm gì tiếp
2. Kiểm tra `.env` đã có đủ credentials chưa (`THREADS_APP_ID`, `THREADS_APP_SECRET`, `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`; `ANTHROPIC_API_KEY` cần từ Giai đoạn 3)
3. Chạy `uv run pytest -q` để xác nhận môi trường vẫn ổn định trước khi code tiếp
4. Đọc `Content/Scripts/*.docx` trước khi generate bất kỳ nội dung nào
5. Đọc file liên quan trong `docs/claude/` đúng với mảng đang làm (xem bảng "Kiến trúc tài liệu" ở trên) — không cần đọc hết
