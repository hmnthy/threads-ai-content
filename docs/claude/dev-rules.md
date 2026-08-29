# Dev Rules — Threads AI Content

> Đọc khi: setup môi trường, chạy lệnh dev, hoặc implement `src/generation/`/`src/carousel/` (cần biết đúng workflow và ràng buộc).
> Xem thêm: [`architecture.md`](architecture.md) cho tech stack, [`data-model.md`](data-model.md) cho API/virality, [`CLAUDE.md`](../../CLAUDE.md) cho quy tắc tuyệt đối và mission.

---

## Setup & Run Commands

```bash
# 1. Cài uv (1 lần duy nhất trên máy)
python -m pip install --user uv

# 2. Tạo venv + cài toàn bộ dependencies (đọc từ pyproject.toml + uv.lock)
uv sync

# 3. Copy env template và điền credentials (đã điền sẵn trên máy hiện tại)
copy .env.example .env

# 4. Chạy test suite
uv run pytest -q

# 5. Lint + format + type-check (cũng chạy tự động qua pre-commit khi commit)
uv run ruff check .
uv run ruff format .
uv run mypy

# 6. Chạy FastAPI backend (sau khi có src/main.py)
uv run uvicorn src.main:app --reload --port 8000

# 7. Kiểm tra API đang chạy
# Mở trình duyệt: http://localhost:8000/docs
```

**Lưu ý IDE**: chọn Python interpreter là `.venv/Scripts/python.exe` (VSCode: Ctrl+Shift+P → "Python: Select Interpreter") để hết cảnh báo "package not installed".

---

## Environment Variables (.env)

```env
THREADS_APP_ID=
THREADS_APP_SECRET=
THREADS_ACCESS_TOKEN=
THREADS_USER_ID=
ANTHROPIC_API_KEY=
```

---

## Content Generation (TEXT)

**Nguyên tắc quan trọng nhất**: Học giọng văn từ `Content/Scripts/` trước khi generate.

Đặc điểm giọng văn tác giả (cần xác nhận sau khi đọc scripts):
- Tiếng Việt thân thiện, gần gũi, đôi khi xen tiếng Pháp tự nhiên
- Kể chuyện theo góc nhìn cá nhân ("mình", "tớ")
- Kết hợp thông tin thực tế + cảm xúc cá nhân
- Hook mạnh ở câu đầu tiên

**Workflow generate text**:
1. Đọc scripts gốc để extract giọng văn (few-shot examples cho Claude)
2. Phân tích gap: chủ đề nào chưa có / chưa đủ sâu
3. Propose 3–5 content ideas với title + brief
4. Với mỗi idea: generate 3 phiên bản độ dài khác nhau:
   - **Short** (≤150 ký tự): hook only, phù hợp standalone Threads
   - **Medium** (150–400 ký tự): hook + body + CTA nhẹ
   - **Long** (400–500 ký tự, max Threads): full story arc
5. Gán Virality Index dự đoán cho mỗi version (công thức tại [`data-model.md`](data-model.md#virality-index))
6. Tác giả chọn → có thể edit → approve

**Không tự đăng bài khi chưa có explicit approval từ tác giả.**

---

## Carousel Generation (IMAGE)

**Chỉ generate khi tác giả đã approve content text và yêu cầu.**

Template hiện có theo chủ đề:
- `Alternance/` → 7 slides (dùng khi content về alternance, thực tập, đi làm)
- `CV/` → 9 slides (dùng khi content về viết CV, hồ sơ xin việc)
- `Entretien/` → 11 slides (dùng khi content về phỏng vấn xin việc)

Quy trình:
1. Map content topic → đúng template folder (bảng mapping đầy đủ tại [`data-model.md`](data-model.md#chủ-đề-content-hiện-có-từ-carousel-templates))
2. Dùng Pillow để overlay text lên từng slide PNG
3. Giữ nguyên font, màu sắc, layout từ template — chỉ thay text
4. Export ra `output/carousel_YYYY-MM-DD_topic/` dưới dạng PNG sequence
5. Không tự modify template gốc trong `Content/Content - Photo carousel/`
