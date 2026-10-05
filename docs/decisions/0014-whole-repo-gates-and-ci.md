# ADR-0014: Pre-commit quét toàn repo (`--commit`) + CI GitHub Actions

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-01
- **Người quyết**: đề xuất bởi Claude (Thy yêu cầu vá lỗ hổng cảnh sát), Thy duyệt 2026-10-01

## Bối cảnh

ADR-0008 đặt tầng 1 (`scripts/consistency/check.py`) ở pre-commit với `--staged` — chỉ quét file đang stage. Ba lỗ hổng lộ ra ngày 2026-10-01:

- **Lỗi nằm ở file khác file đang sửa.** Thêm 21 test (`tests/**`) làm README ×3 + `docs/status.md` ghi sai số test (277 thay vì 298); `count_fact` chỉ chạy ở `--all`, pre-commit không thấy. Tương tự cho đường dẫn chết khi xoá file, ảnh lỗi thời (`stale_asset`). Chỉ `/decision-sweep` bắt được (hook đầu phiên chạy `--count`, bỏ đếm test cho nhanh) — tức là SAU khi commit, nếu có ai chạy sweep.
- **File mới chưa `git add` không bị quét.** `--all` chỉ đọc `git ls-files` → hook đầu phiên báo "0 vi phạm" trong khi 1 file mới (`src/pipeline/nlp_cluster_job.py`) đang vi phạm luật ADR-0013 (code-reviewer bắt được).
- **Cổng chỉ có trên máy đã `pre-commit install`.** Clone mới, commit qua giao diện web, hay phiên Claude Design/Cowork chưa cài hook → không có cổng nào.

Đo: `check.py --all` (kể cả `pytest --collect-only` để đếm test) mất ~6,5 giây; `--staged` ~1,5 giây.

## Quyết định

1. Thêm chế độ `--commit` cho `check.py`: quét **toàn repo** (forbid, đường dẫn chết, đếm số test, ảnh lỗi thời) + giữ luật "3 README sửa cùng nhau" theo file đang stage. Pre-commit dùng `--commit` thay `--staged`. `--all` (hook đầu phiên, sweep, CI) quét thêm file chưa track (`git ls-files --others --exclude-standard`); `--commit` thì không — file chưa track không thuộc commit, nên ở chế độ này: đếm test bỏ file test chưa track (`--ignore`), đường dẫn chết phải có trong git (không chỉ trên đĩa).
2. `stale_asset` so theo tổ tiên commit (`git merge-base --is-ancestor`) thay vì timestamp: squash/rebase merge trên GitHub đặt cùng 1 committer date cho cả chuỗi → so thời gian báo sai vĩnh viễn. ADR và asset trong cùng 1 commit = asset được làm lại cùng ADR → hợp lệ.
3. Thêm CI `.github/workflows/ci.yml` đúng roadmap Phase G: job `py` (ruff, format, mypy, `check.py --all`, pytest nhanh) + job `web` (lint, tsc, build). Không data thật, không secrets. Bỏ cài torch + gói CUDA ở CI (sinh danh sách từ `uv.lock`) — bộ test nhanh không import chúng (đo 2026-10-01: chỉ `anthropic`, `lingua`, `scipy`).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ `--staged` | Nhanh hơn ~5 giây | Lọt lỗi ở file khác (đã xảy ra) | Lỗ hổng thật |
| Pre-commit chạy `--all` | Đơn giản | Mất luật "3 README cùng commit" (cần danh sách stage) | `--commit` = `--all` + luật đó |
| CI cài đủ torch | Giống máy dev | Tải vài GB mỗi lần, chậm | Test cần torch đã đánh dấu `slow`, CI bỏ |

## Hệ quả

- Đổi: `scripts/consistency/check.py`, `.pre-commit-config.yaml`, `tests/scripts/test_consistency.py` (test `--commit` bắt vi phạm ở file không stage), `.github/workflows/ci.yml`, `docs/roadmap.md` (Phase G), `CLAUDE.md`.
- Pre-commit cất (stash) phần chưa stage của file đã track nhưng KHÔNG cất file chưa track → `--commit` tự loại chúng (không quét, không đếm test, không coi là đường dẫn có thật).
- CI chỉ chạy khi push lên GitHub (repo private — tốn phút Actions miễn phí). Kiểm chứng trước bằng mô phỏng job `py` trong WSL2 (bản sao sạch, venv Linux).
- Không có luật mới: ADR không làm lỗi thời nội dung nào ngoài dòng mô tả `--staged` của pre-commit (đã sửa ở `CLAUDE.md`/`.pre-commit-config.yaml`); ADR-0008 giữ nguyên làm lịch sử.
- Xem lại khi: pre-commit vượt ~15 giây, hoặc Phase C đổi đường dẫn `.venv` sang Linux.
