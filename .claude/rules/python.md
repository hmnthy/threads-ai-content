---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "scripts/**/*.py"
---

# Python — quy ước

- Python 3.12, quản lý bằng `uv` (`uv add`, `uv run`) — không `pip install` vào venv.
- ruff (lint + format, line-length 100) chạy tự động sau mỗi Edit/Write qua hook; mypy **strict** trên `src/` + `tests/` + `scripts/` — không thêm `# type: ignore` nếu chưa thử sửa đúng kiểu.
- Model dữ liệu: pydantic v2 cho payload API/response; `@dataclass(frozen=True)` cho domain model (`src/models/`).
- Mọi rate phải guard `views == 0`. Mọi hằng số heuristic: đặt tên HOA + docstring ghi "hypothesis, chưa calibrate" hoặc nguồn bằng chứng.
- Comment/docstring tiếng Việt; tên biến/hàm tiếng Anh.

## Test

- Mỗi module mới có test đi kèm trong `tests/<cùng cấu trúc>/`. HTTP mock bằng `respx`, async bằng `pytest-asyncio` (auto mode).
- **Không bao giờ** đọc/ghi `data/threads.db` thật trong test — dùng `tmp_path` / SQLite `:memory:`.
- Test cần tải model transformer hoặc gọi API thật: đánh dấu `@pytest.mark.slow` / `@pytest.mark.live` (CI bỏ qua).
- Chạy đúng phạm vi đang sửa trước (`uv run pytest tests/analysis -q`). Pre-commit chạy bộ nhanh (`-m "not slow and not live"`, ~20s); `/checkpoint` luôn chạy cả suite (~1 phút).
