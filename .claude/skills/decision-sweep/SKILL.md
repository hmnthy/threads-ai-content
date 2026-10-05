---
name: decision-sweep
description: Propagate one decision (ADR) through the whole threads-ai-content repo — inventory everything the decision made obsolete (rule-book checker + independent consistency-auditor subagent), fix it systematically, then run a full final verification. Use right after an ADR is recorded or changed, and whenever the session status reports consistency violations.
argument-hint: "<ADR number, e.g. 0004>"
---

# /decision-sweep — Quyết định → Kiểm kê → Sửa → Kiểm tra cuối

ADR: **$ARGUMENTS**

!`uv run --no-sync python -m scripts.consistency.check --all --no-pytest --count`

(số trên = vi phạm hiện có theo sổ luật, trước khi bắt đầu)

## Bước 1 — Quyết định thành luật

1. Đọc `docs/decisions/$ARGUMENTS-*.md`. Chưa có ADR → dừng, dùng `/record-decision` trước.
2. Mở `docs/decisions/invariants.toml`: ADR này đã có luật chưa? Chưa có → soạn luật **trước khi sửa bất cứ gì**:
   - `[[forbid]]` cho mỗi khái niệm/tên/đường dẫn/số liệu bị làm lỗi thời (mẫu hẹp; `allow` cho `docs/decisions/**` và nơi được phép nhắc lịch sử; `multiline = true` nếu câu hay vắt dòng).
   - `[[stale_asset]]` cho ảnh/file nhị phân mà quyết định làm sai (VD screenshot).
   - `planned_paths` cho file ADR yêu cầu tạo nhưng chưa tồn tại.
3. Mỗi luật mới → thêm 1 ví dụ vào test `tests/scripts/test_consistency.py` (khớp + không khớp).

## Bước 2 — Kiểm kê (2 tầng song song, độc lập)

- Tầng 1: `uv run --no-sync python -m scripts.consistency.check --all`
- Tầng 2: gọi `@agent-consistency-auditor` với ADR-$ARGUMENTS (chạy nền trong lúc xem tầng 1) — prompt phải nêu rõ `ADR-NNNN` (VD `ADR-0015`), không chỉ số trần — không thì lượt chạy không được ghi dấu (ADR-0015).
- Gộp thành **1 danh sách khử trùng**, mỗi mục phân loại đúng 1 nhóm:
  - **Sửa** — thông tin sai/lỗi thời hiện tại.
  - **Ngoại lệ có chủ đích** — câu lịch sử hoặc câu nói rõ "đã bỏ" → gắn `consistency: allow <rule-id>` (markdown: `<!-- … -->` trên dòng trước; code: comment cùng dòng). Không lạm dụng: mỗi ngoại lệ phải tự giải thích được.
  - **Luật mới** — phát hiện của auditor tổng quát hoá được → thêm vào `invariants.toml` + test **trước** khi sửa, để thấy luật bật lên rồi tắt đi.
- Trình danh sách cho Thy nếu có mục cần quyết (VD đổi copy sản phẩm, xoá tính năng). Mục hiển nhiên thì làm luôn.

## Bước 3 — Sửa có hệ thống

- Theo từng file, 1 lượt / file. Không sửa `docs/archive/**`, `legacy-log.md`, ADR `Accepted` khác.
- README: sửa cả 3 bản (EN/VI/FR) cùng lúc, giữ cùng cấu trúc.
- Ảnh cũ (`stale_asset`): cần backend + `npm run dev` đang chạy → `npm run screenshots` trong `src/dashboard`.
- Code: chỉ sửa comment/docstring/copy trừ khi ADR yêu cầu đổi hành vi — khi đó kèm test.

## Bước 4 — Kiểm tra cuối (tất cả phải xanh mới được báo xong)

1. `uv run --no-sync python -m scripts.consistency.check --all` → **0 vi phạm** (có cả kiểm tra số test).
2. `uv run ruff check .` · `uv run mypy` · `uv run pytest -q` (**bộ đầy đủ**, không chỉ test nhanh).
3. Có chạm `src/dashboard/**` → trong `src/dashboard`: `npm run lint` · `npm run typecheck` · `npm run build`.
4. Gọi lại `@agent-consistency-auditor` lần 2 → phải là "0 phát hiện ngoài tầng 1". Còn phát hiện → quay lại Bước 2. Lượt này là **lượt ghi dấu** cho git hook pre-commit chặn commit (ADR-0015): chạy SAU lần sửa cuối của ADR, không sửa ADR trong lúc nó chạy; sửa ADR sau đó → chạy lại.
5. Báo cáo ngắn: số vi phạm trước → sau, luật mới đã thêm, ngoại lệ đã gắn (và vì sao), kết quả từng lệnh kiểm tra.
6. Diff có `invariants.toml` hoặc file logic → cần `@agent-code-reviewer` (ADR-0015) — `/checkpoint` bước 2b làm.
7. → `/checkpoint` (chờ Thy đồng ý commit).
