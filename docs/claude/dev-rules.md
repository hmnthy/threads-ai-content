# Dev Rules — Threads AI Content

> Đọc khi: setup môi trường, chạy lệnh dev, hoặc phối hợp giữa Claude Code / Claude Design / Claude Cowork.
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

# 4. Bật các cổng chặn commit (1 lần): ruff, mypy, sổ luật nhất quán, pytest nhanh, dashboard eslint+tsc, commit-msg
uv run pre-commit install

# 5. Chạy test suite (~1 phút; pre-commit chạy bộ nhanh ~20s)
uv run pytest -q

# 6. Lint + format + type-check (cũng chạy tự động qua pre-commit khi commit)
uv run ruff check .
uv run ruff format .
uv run mypy

# 7. Chạy FastAPI backend
uv run uvicorn src.main:app --reload --port 8000

# 8. Kiểm tra API đang chạy
# Mở trình duyệt: http://localhost:8000/docs
```

**Lưu ý IDE**: chọn Python interpreter là `.venv/Scripts/python.exe` (VSCode: Ctrl+Shift+P → "Python: Select Interpreter") để hết cảnh báo "package not installed".

**Troubleshooting — `uv` báo "not recognized" trong PowerShell** (xảy ra 2026-08-31): `uv` cài qua `pip install --user uv` (bước 1 ở trên) nằm ở `C:\Users\<user>\AppData\Roaming\Python\PythonXXX\Scripts\uv.exe` — thư mục này **không tự động nằm trong PATH** trên Windows. Đóng/mở terminal mới không đủ để fix (đây không phải PATH chưa refresh, mà PATH thật sự thiếu entry này). Fix 1 lần:
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Users\<user>\AppData\Roaming\Python\Python312\Scripts", "User")
```
Rồi **đóng hẳn cửa sổ VS Code** (không chỉ tab terminal) và mở lại — VS Code cache biến môi trường lúc khởi động. Verify bằng `uv --version`.

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

## Multi-Tool Workflow: Claude Code / Claude Design / Claude Cowork

> Đọc khi: có thay đổi liên quan tới `src/dashboard/` hoặc `docs/claude/design-system.md`, hoặc nghi ngờ 2 tool đang "dẫm chân" lên cùng 1 file.

Dự án dùng song song 3 bề mặt Claude khác nhau trên cùng 1 repo: **Claude Code** (VSCode, terminal — implementation), **Claude Cowork** (ghi trực tiếp vào git working tree, giống 1 phiên terminal khác — dùng cho doc/spec/quyết định), và **Claude Design** (canvas riêng trên claude.ai, **KHÔNG kết nối git trực tiếp**).

**Sự thật kỹ thuật cần nhớ** (verify 2026-09-30 qua schema tool `DesignSync`): skill `/design-sync` **đẩy** component library từ máy lên 1 project design-system trên claude.ai/design — incremental, từng component, không bao giờ thay toàn bộ. Chiều ngược lại chỉ **đọc từng file** (`get_file`); không có thao tác kéo cả trang về repo. Vì vậy mọi thứ chỉnh trong canvas **chưa tồn tại trong `src/dashboard/`** cho tới khi Claude Code port lại thành code (từ file đọc qua `get_file` hoặc mockup `.dc.html` Thy xuất ra). Claude Design không đọc GitHub — không cần push để dùng nó.

**Pipeline chuẩn (tuyến tính, không chạy song song trên cùng file)**:
1. Thăm dò ý tưởng visual trong canvas Claude Design (sandbox riêng, không rủi ro cho repo).
2. Khi 1 hướng đã **chốt** → văn bản hoá thành token cụ thể (hex, type scale, spacing) vào `docs/claude/design-system.md` — nguồn sự thật duy nhất về design (routing bắt buộc: `.claude/rules/dashboard.md`).
3. Claude Code port từng component về `src/dashboard/` (đọc file qua `DesignSync get_file` hoặc mockup `.dc.html`), nối data thật; `/design-sync` chỉ dùng khi muốn đẩy component library hiện tại lên Claude Design làm nền cho vòng thiết kế tiếp.
4. Claude Code verify: code đã port có khớp token trong `design-system.md` không → wire data thật → chạy test/build → commit.
5. Quay lại bước 1 chỉ cho hướng visual MỚI — không sửa tay trong canvas rồi port đè lên code đã được sửa sau đó (tạo lại 2 nguồn sự thật).

**3 nguyên tắc chặn xung đột**:
- Trước khi chạm `src/dashboard/` (hoặc bất kỳ file nào) ở tool nào — `git status` trước. Có uncommitted work từ tool khác → không ghi đè, hỏi lại user.
- `design-system.md` là trọng tài khi có mâu thuẫn — sửa spec trước, sync/code sau, không làm ngược.
- Commit nhỏ, thường xuyên, message rõ nghĩa — git log là kênh giao tiếp DUY NHẤT giữa các tool (không chia sẻ bộ nhớ).

