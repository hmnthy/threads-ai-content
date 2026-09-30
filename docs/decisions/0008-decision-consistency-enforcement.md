# ADR-0008: Cưỡng chế nhất quán giữa quyết định và nội dung repo

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy (yêu cầu + duyệt plan), Claude (thiết kế)

## Bối cảnh

Sau đợt tái cấu trúc ADR-0001/0003, kiểm tra tay vẫn tìm ra 7 nhóm thông tin lỗi thời rải rác: badge README "Phase 1", ảnh `landing.png` cũ, `schema.py` còn nói "Chroma/FAISS — Bước 10", comment trỏ "decisions log trong architecture.md", `/design-sync` mô tả sai hướng, "audience replies" (thực ra là reply của tác giả), nhãn "coming soon". Các chốt chặn có sẵn (ruff, mypy, commit-msg) chỉ kiểm code, không kiểm **quyết định ↔ nội dung**. Lần chạy đầu của bộ kiểm tra mới trên repo thật: 50 vi phạm, phủ đủ 7 nhóm.

## Quyết định

Mỗi quyết định phải được biến thành **luật máy kiểm được** và lan ra toàn repo theo 1 quy trình cố định:

1. **Sổ luật** `docs/decisions/invariants.toml` — mỗi ADR khai báo mẫu lỗi thời (`forbid`), file phải làm lại (`stale_asset`), đường dẫn sắp tạo (`planned_paths`), giới hạn docs, số liệu phải khớp thực tế.
2. **Tầng 1 — `scripts/consistency/check.py`** (thư viện chuẩn): chạy ở pre-commit (`--staged`, **chặn commit**), đầu mỗi phiên (đếm vi phạm), `/decision-sweep` và CI (`--all`).
3. **Tầng 2 — subagent `consistency-auditor`** (chỉ đọc, context riêng): tìm cách diễn đạt khác mà regex không bắt; phát hiện tổng quát hoá được → thành luật mới ở tầng 1.
4. **Quy trình `/decision-sweep <ADR>`**: luật trước → kiểm kê 2 tầng → sửa có hệ thống → kiểm tra cuối (check = 0, ruff, mypy, pytest đầy đủ, dashboard lint/tsc/build, auditor lần 2 = 0). `/record-decision` bắt buộc chuyển tiếp sang bước này.
5. **Ngoại lệ phải có dấu vết**: `consistency: allow <rule-id>` tại chỗ — không có ngoại lệ ngầm.
6. Pre-commit thêm test nhanh (`-m "not slow and not live"`) và kiểm dashboard (eslint + tsc) khi chạm `src/dashboard/`. Ảnh README làm lại bằng `npm run screenshots` (Playwright + Edge có sẵn).

## Phương án đã cân nhắc

| Phương án | Vì sao không chọn |
|---|---|
| Chỉ dựa vào subagent LLM rà soát | Không xác định, không chạy được ở pre-commit, có thể bỏ sót khác nhau mỗi lần |
| Chỉ dựa vào regex | Không bắt được cách diễn đạt khác; không tự học thêm luật |
| Cảnh báo thay vì chặn commit | Thy chọn chặn — cảnh báo đã từng bị bỏ qua, lỗi vặt lọt vào |
| Chụp ảnh README thủ công | Không lặp lại được cùng khung nhìn; Claude không tự thấy UI |

## Hệ quả

- Mọi ADR mới phải có mục luật trong `invariants.toml` (hoặc ghi rõ "không có luật" + lý do).
- Luật của chính ADR này (`invariants.toml`, mục ADR-0008): `ADR0008-pytest-slow`, `ADR0008-mypy-scope`, `ADR0008-precommit-scope`, cùng `count_fact` cho badge số test README.
- Lượt `/decision-sweep` đầu tiên (ADR-0001/0003/0008): tầng 1 sửa 58 vi phạm; 2 auditor tầng 2 tìm thêm ~35 chỗ diễn đạt khác → thành 16 luật mới, mỗi luật có test hồi quy.
- Luật quá rộng sẽ bắt nhầm → thu hẹp bằng `paths`/`allow` và thêm test hồi quy (VD luật "Bước N" đã phải giới hạn về code + docs tham chiếu vì skill dùng "Bước 1..4" hợp lệ).
- Pre-commit chậm hơn (dashboard ~12 giây khi chạm `src/dashboard/`; test nhanh), bù lại commit hỏng bị chặn sớm.
- Xem lại khi: số ngoại lệ `consistency: allow` tăng nhanh (luật sai hướng), hoặc pre-commit vượt ~60 giây.
