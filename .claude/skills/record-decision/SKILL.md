---
name: record-decision
description: Record an architecture or methodology decision as a new numbered ADR in docs/decisions/.
argument-hint: "<short decision title>"
disable-model-invocation: true
---

# /record-decision — ghi 1 quyết định thành ADR

Tiêu đề: **$ARGUMENTS**

## ADR hiện có

!`ls docs/decisions`

## Các bước

1. Số mới = số lớn nhất trong `docs/decisions/` + 1 (kể cả số đang "giữ chỗ" trong `docs/decisions/README.md` — nếu quyết định này đúng là 1 số giữ chỗ thì dùng số đó). Tên file `NNNN-ten-ngan-khong-dau.md`.
2. Copy cấu trúc `docs/decisions/0000-template.md`. Viết **tiếng Việt**, ngắn:
   - **Bối cảnh**: bằng chứng thật (số liệu, `file:line`, link) — không viết chung chung.
   - **Quyết định**: 1-3 câu khẳng định.
   - **Phương án đã cân nhắc**: chỉ những phương án thật sự đã được bàn.
   - **Hệ quả**: việc phải làm theo + điều kiện cụ thể để xem lại.
   - **Người quyết**: ghi đúng — nếu Thy chưa duyệt thì trạng thái `Proposed`, không phải `Accepted`.
3. Nếu thay thế ADR cũ: đổi trạng thái ADR cũ thành `Superseded by ADR-NNNN` (chỉ sửa dòng trạng thái).
4. Thêm 1 dòng vào bảng trong `docs/decisions/README.md`; bỏ số khỏi danh sách "Dự kiến" nếu có. Quyết định đổi công thức/methodology → cập nhật section tương ứng của `docs/claude/data-model.md` (trỏ tới ADR). Đề xuất từ `docs/research/` → ghi rõ đã được Thy duyệt.
5. **Bắt buộc — luật nhất quán**: thêm vào `docs/decisions/invariants.toml` những gì ADR này làm lỗi thời (`[[forbid]]` cho tên/khái niệm/đường dẫn/số liệu cũ, `[[stale_asset]]` cho ảnh cần làm lại, `planned_paths` cho file sẽ tạo). ADR không làm gì lỗi thời → ghi rõ "không có luật" trong mục Hệ quả, kèm lý do.
6. Nếu thay thế ADR cũ: luật cũ của ADR đó có còn đúng không — sửa/xoá trong `invariants.toml` cho khớp.
7. **Không dừng ở đây** (commit ADR cần dấu consistency-auditor, `invariants.toml` cần dấu code-reviewer — git hook pre-commit chặn, ADR-0015): chạy tiếp `/decision-sweep NNNN` để lan quyết định ra toàn repo (kiểm kê → sửa → kiểm tra cuối). Chỉ sau khi sweep báo 0 vi phạm mới `/checkpoint`.
