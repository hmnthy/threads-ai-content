# ADR-0009: Đổi tên hiển thị sản phẩm thành "Unthreaded"

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy (chọn tên + phạm vi), Claude (tra trùng tên, đề xuất)

## Bối cảnh

Tên "Threads AI Content" (title dashboard, logo navbar, title API, H1 của 3 README, tiêu đề docs) gợi ý một công cụ **AI sinh nội dung** — đúng tính năng đã bỏ vĩnh viễn ở ADR-0001. Lượt `/decision-sweep` đầu tiên (2026-09-30) đã nêu tên này là 1 trong 5 quyết định mở trong `docs/status.md`.

Tra web 2026-09-30 các tên ứng viên:
- **ThreadLens**, **Threadwise**: mỗi tên đã có ≥5 sản phẩm đang dùng → dễ nhầm, loại.
- **Threadscope**: trùng tên công cụ profiler của Haskell (khác lĩnh vực nhưng chiếm kết quả tìm kiếm) → loại.
- **Unthreaded**: không thấy công cụ phân tích Threads nào dùng tên này.

Meta khuyến cáo sản phẩm bên thứ ba không được gây hiểu nhầm là do Meta làm hoặc bảo trợ; tên chứa "Threads" đứng đầu càng dễ gây hiểu nhầm đó.

## Quyết định

1. Tên hiển thị sản phẩm là **Unthreaded** ("gỡ từng sợi" — khớp tagline giữ nguyên "The algorithm, read back to you.").
2. **Chỉ đổi tên hiển thị**: giữ slug `threads-ai-content` (thư mục, repo GitHub, `pyproject.toml`, đường dẫn Task Scheduler, tên repo trong mô tả agent/skill). Repo public sẽ được đặt tên khi curate.
3. Landing và 3 README có câu miễn trừ: "Not affiliated with Meta. Threads is a trademark of Meta Platforms, Inc." (bản dịch tương ứng trong README tiếng Việt/Pháp).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ "Threads AI Content" | Không tốn công | Gợi ý generation (trái ADR-0001), dễ bị hiểu là sản phẩm của Meta | Sai thông điệp sản phẩm |
| ThreadLens / Threadwise | Nghĩa rõ ("soi" Threads) | ≥5 sản phẩm trùng tên | Trùng tên |
| Threadscope | Nghĩa rõ | Trùng profiler Haskell | Trùng tên, chiếm kết quả tìm kiếm |
| Đổi cả slug repo | Nhất quán tuyệt đối | Phải sửa đường dẫn Task Scheduler, worktree, memory, remote | Repo private sẽ curate sang repo public mới — đổi slug bây giờ tốn công mà không ai thấy |

## Hệ quả

- Đổi: `src/dashboard/src/app/layout.tsx` (title), `LandingNav.tsx` + `Nav.tsx` (logo), footer landing (câu miễn trừ), `src/main.py` (title API), H1 + câu miễn trừ trong README ×3, tiêu đề `CLAUDE.md`, `docs/claude/*.md`, `docs/status.md`, `docs/roadmap.md`, `src/dashboard/README.md`, thông điệp mặc định `.claude/hooks/toast.ps1`.
- Luật (`invariants.toml`, mục ADR-0009): `[[forbid]] ADR0009-old-name` cấm "Threads AI Content" ngoài `docs/decisions/**`; `ADR0009-old-name-variants` (biến thể "Threads AI", "Threads-AI-Content" — phân biệt hoa/thường để không bắt slug/tên job `ThreadsAI_*`); `ADR0009-slug-as-title` (tiêu đề tài liệu `# … — threads-ai-content`); `[[stale_asset]]` cho 4 ảnh README (`landing`, `overview`, `analytics`, `topics` — navbar có tên).
- Câu miễn trừ được kiểm "phải có" bằng `tests/test_branding.py` (sổ luật chỉ có kiểu cấm) — xoá câu sẽ bị chặn ở pre-commit.
- Không sửa mockup `src/dashboard/mockups/**` và `docs/archive/**` (lưu trữ nguyên văn, đã loại khỏi quét).
- Slug `threads-ai-content` vẫn hợp lệ ở mọi đường dẫn/định danh kỹ thuật — luật chỉ bắt tên cũ viết hoa ("Threads AI", "Threads-AI-Content") và slug đứng làm tiêu đề tài liệu.
- Xem lại khi: curate sang repo public (chọn slug mới, có thể là `unthreaded`), hoặc phát hiện sản phẩm khác cùng tên trong lĩnh vực phân tích mạng xã hội.
