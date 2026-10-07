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
- Mọi rate phải guard `views == 0`. Bài `views == 0` là insight thiếu, không phải 0%: mọi phân phối rate (median/IQR/bucket/xếp hạng) đi qua `split_measurable()` (`src/analysis/stats.py`) và trả số bị loại ra ngoài (ADR-0011). Mọi hằng số heuristic: đặt tên HOA + docstring ghi "hypothesis, chưa calibrate" hoặc nguồn bằng chứng.
- Tuổi bài đi kèm 1 số đo từ snapshot → tính tại thời điểm **snapshot đó** (`fetched_at`), không tới `now`: cron có thể ngắt nhiều ngày (ADR-0017).
- Script CLI in chữ Việt / ký tự ngoài ASCII → `sys.stdout.reconfigure(encoding="utf-8")` đầu `main()`, trước argparse (`--help` in `__doc__`) (console Windows cp1252 làm lỗi; `capsys` trong test là UTF-8 nên test không bắt được).
- Comment/docstring tiếng Việt; tên biến/hàm tiếng Anh.

## Test

- Mỗi module mới có test đi kèm trong `tests/<cùng cấu trúc>/`. HTTP mock bằng `respx`, async bằng `pytest-asyncio` (auto mode). Không truyền `pytest.approx(...)` vào constructor có kiểu (mypy fail) — so từng trường.
- **Không bao giờ** đọc/ghi `data/threads.db` thật trong test — dùng `tmp_path` / SQLite `:memory:`.
- Test chạy `git` trong repo tạm: `tests/conftest.py` đã xoá biến `GIT_*` (git hook xuất `GIT_INDEX_FILE` tuyệt đối của repo thật — thừa hưởng là ghi đè index thật). Không truyền lại `GIT_*` vào subprocess.
- Test cần tải model transformer hoặc gọi API thật: đánh dấu `@pytest.mark.slow` / `@pytest.mark.live` (CI bỏ qua).
- Chạy đúng phạm vi đang sửa trước (`uv run pytest tests/analysis -q`). Pre-commit chạy bộ nhanh (`-m "not slow and not live"`, ~20s); `/checkpoint` luôn chạy cả suite (~1 phút).
