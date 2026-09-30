---
paths:
  - "docs/**"
  - "CLAUDE.md"
  - "README*.md"
---

# Tài liệu

- `CLAUDE.md` ≤ 80 dòng — chỉ thứ cần mọi phiên. Thứ chỉ cần cho 1 mảng code → `.claude/rules/<mảng>.md` có `paths:`.
- `docs/status.md` ≤ 60 dòng, chỉ trạng thái hiện tại; cập nhật ở mỗi `/checkpoint`. Không thêm mục "lịch sử" — lịch sử là git log.
- Quyết định mới → ADR mới (`/record-decision`), cập nhật bảng trong `docs/decisions/README.md`, thêm luật vào `docs/decisions/invariants.toml`, rồi `/decision-sweep` (ADR-0008). Không sửa ADR `Accepted` để đổi ý; không thêm dòng vào `legacy-log.md`.
- Không ghi số liệu dễ trôi (số test, số post, số cluster) rải rác trong văn xuôi — chỉ ở `docs/status.md` và badge README, nơi `count_fact` kiểm được.
- `docs/archive/` là lưu trữ nguyên văn — không sửa.
- `docs/research/` private (gitignored) — không trích nguyên văn vào README/docs công khai; chỉ cite kết luận đã chốt.
- README có 3 bản (EN/VI/FR) — sửa 1 bản thì sửa cả 3 trong cùng commit. Chỉ ghi trạng thái THẬT của code (không hứa tính năng chưa có).
