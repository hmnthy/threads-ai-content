# ADR-0028: Viết lại lịch sử repo public; dọn tài liệu trước người đọc ngoài

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-30
- **Người quyết**: Thy — chọn "viết lại lịch sử" và "dọn hết" sau khi đọc báo cáo soát nội dung nhạy cảm (2026-10-30);
  Claude Code soát (2 lượt độc lập) và đề xuất

## Bối cảnh

- Soát 2026-10-30 trên mọi tài liệu public (27 ADR, `legacy-log.md`, `docs/claude/`, `docs/design/`, `docs/archive/`,
  CLAUDE.md, status, roadmap): **không có secret thật** (token, key, mật khẩu, ID tài khoản), không có dữ liệu follower,
  bảng giá hay tên khách hàng.
- Rủi ro cao nhất nằm trong **lịch sử commit**: bản harness `.claude/` đầy đủ (agent, skill, hook — 39 commit có chạm)
  và 2 báo cáo nghiên cứu riêng `docs/research/` vẫn lấy lại được bằng một lệnh, trong khi harness có thể được cấp phép
  riêng (ADR-0027). ADR-0027 chọn không viết lại lịch sử khi chưa thấy rõ hệ quả này.
- GitHub API công khai 2026-10-30: repo **0 fork, 0 sao** → viết lại lịch sử gỡ được bản cũ trên GitHub (trừ ref của các
  PR đã merge, cần GitHub Support xoá). Bản clone đã tải về (nếu có) không kiểm soát được.
- `docs/archive/` (kế hoạch cũ, lưu trữ nguyên văn): phạm vi đã bỏ (ADR-0001), giọng ghi chép nội bộ, câu chọn công cụ
  theo tín hiệu tuyển dụng — không phản ánh dự án hiện tại.
- Tài liệu public còn: quy tắc làm việc riêng giữa Thy và Claude trong CLAUDE.md (giải thích thuật ngữ, trailer), câu tự
  hạ thấp và chi tiết cá nhân trong vài ADR (số dư tài khoản, giờ mở máy, "người mới với git"), mã commit chỉ đường tới
  bản cũ, ghi chú vận hành deploy (token, lối vượt cổng review), đường dẫn lộ tên user Windows; ảnh tác giả còn EXIF
  (số serial máy ảnh, không có GPS) ở 3 bản, gồm bản đang chạy trên trang live.

## Quyết định

1. **Viết lại toàn bộ lịch sử** bằng `git filter-repo` trên một bản `clone --mirror` mới, trong cùng một lượt:
   - xoá khỏi mọi commit `.claude/`, `docs/research/`, `docs/archive/`;
   - thay trong mọi phiên bản file các chi tiết riêng tư mà PR này đã sửa ở bản hiện tại (đường dẫn lộ tên user, số dư
     tài khoản, giờ mở máy, câu tự hạ thấp) — danh sách chuỗi thay thế giữ ngoài repo;
   - gỡ segment metadata (EXIF/XMP/C2PA) ở mọi phiên bản cũ của ảnh JPEG, không nén lại;
   - gỡ dòng trailer `Co-Authored-By` còn trong thông điệp commit cũ.

   Sao lưu mirror đầy đủ trước; Thy chạy force push `main`; Thy gửi GitHub Support yêu cầu xoá ref PR + cache view. Thay
   phần "không viết lại lịch sử" của ADR-0027. Câu cũ trong CLAUDE.md của các commit cũ (quy tắc làm việc) không thay —
   chấp nhận. Phần mô tả thiết kế cổng review trong ADR-0015 (cổng "cố gắng hết mức", có liệt kê điểm ngoài tầm) là tài
   liệu thiết kế, giữ nguyên.

   **Điều kiện an toàn (cổng chặn trước force push):** mọi phép biến đổi phải để nguyên cây của commit đầu `main`:
   - mỗi chuỗi trong danh sách thay thế có **0 kết quả** `git grep -F` trên cây `main` trước khi chạy;
   - bước gỡ metadata ảnh chỉ bỏ segment APP1/APP11/APP13, không ghi lại gì khác — chạy trên ảnh đã sạch phải ra đúng
     từng byte (thử trên cây hiện tại trước);
   - sau khi chạy: cây `main` mới giống hệt cây `main` cũ (`git diff` rỗng giữa 2 cây). Không đạt → dừng, không push.
2. **`docs/archive/` thôi được theo dõi** (gitignored, bản sao lưu ngoài repo).
3. **Quy tắc làm việc riêng** (giải thích thuật ngữ cho Thy, trailer, kho harness, ghi chú deploy) chuyển sang
   `CLAUDE.local.md` — gitignored, Claude Code tự nạp, worktree nhận bản sao qua `.worktreeinclude`.
4. **Ngoại lệ có chủ đích** cho quy tắc "không sửa ADR Accepted / `legacy-log.md`": được sửa **câu chữ** (bỏ chi tiết cá
   nhân, câu tự hạ thấp, mã commit chỉ đường, dòng "Người quyết" ghi "Claude (thiết kế)" → "Claude Code (đề xuất thiết
   kế)") — không đổi nội dung quyết định.
5. Ảnh: gỡ segment EXIF/XMP/C2PA mà không nén lại (Orientation = 1 nên không đổi hướng hiển thị).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ lịch sử, chỉ bỏ câu chỉ đường (ADR-0027) | Không thao tác phá huỷ | Harness và báo cáo nghiên cứu vẫn lấy được | Thy muốn giữ giá trị cấp phép của harness |
| Repo public mới sạch, repo cũ chuyển private | Sạch tuyệt đối | Mất 104 commit / 25 PR trên trang public; đồng bộ 2 repo | Lịch sử quyết định là phần giá trị chính |
| Viết lại lịch sử bằng `git filter-repo` | Gỡ đúng 3 thư mục, giữ mọi commit khác | Mọi mã commit đổi; không hoàn tác được sau force push; ref PR cần GitHub Support | **Chọn** |

## Hệ quả

- **Mọi mã commit đổi** (gồm các mã docs/memory đang trích, VD merge PR). Sau khi viết lại: cập nhật mã trong tài liệu
  theo bảng đổi mã `filter-repo/commit-map` ở một PR riêng. Thông điệp commit được `filter-repo` tự đổi mã.
- Thứ tự: merge PR này → sao lưu `clone --mirror` ra ngoài → `filter-repo` trên bản clone mới → kiểm (không còn 3 thư
  mục ở bất kỳ commit nào; cây `main` giống hệt trước khi viết lại) → Thy force push → GitHub Support → thư mục chính
  `git fetch` + `git reset --hard origin/main` (file gitignored — `.env`, `data/`, `.claude/`, `CLAUDE.local.md` — không bị
  đụng) → tạo lại worktree nếu cần. Không mở nhánh mới trong lúc viết lại.
- Kho harness riêng (ADR-0027) không bị ảnh hưởng. Vercel deploy lại từ `main` mới.
- File đổi trong PR này: ADR này, CLAUDE.md, `.gitignore`, `.worktreeinclude`, `docs/archive/` (bỏ theo dõi), ADR
  0003, 0004, 0008, 0015, 0016, 0017, 0019, 0022, 0025, 0027 + `legacy-log.md` (câu chữ), `docs/decisions/README.md`,
  `docs/decisions/invariants.toml`, `docs/design/ui-contract.md`, `docs/claude/architecture.md`, `dev-rules.md`,
  `git-workflow.md`, `data-model.md`, `docs/status.md`, `docs/roadmap.md`, README 3 bản (số test), 3 ảnh tác giả,
  `tests/pipeline/test_job_runners.py` (đường dẫn ví dụ), `tests/scripts/test_consistency.py` (ca luật mới — ví dụ tổng
  hợp, không chép nguyên văn chi tiết thật: file test bị loại khỏi quét).
- `CLAUDE.local.md` và bản sao lưu `docs/archive/` nằm ở thư mục chính / ngoài repo trước khi thư mục chính `git pull`
  (pull commit bỏ theo dõi sẽ xoá file khỏi đĩa).
- Việc của Thy ngoài repo: bật giới hạn tần suất gọi API trên Vercel trước khi chia sẻ link rộng (ghi ở
  `CLAUDE.local.md`; tài liệu public chỉ nói chung).
- Luật mới: `ADR0028-private-detail-in-public` (đường dẫn lộ tên user Windows, đường dẫn file nghiên cứu riêng, số dư tài
  khoản, "người mới với git", quy tắc giải thích thuật ngữ trong tài liệu public). `known_untracked` thêm `docs/archive`.
- Xem lại khi: phát hiện bản clone cũ bị phát tán (khi đó dựa vào `LICENSE`), hoặc cần thêm thư mục vào danh sách xoá.

### Hệ quả UI

- Dòng `docs/design/ui-contract.md` thêm: `UI-0028-no-ui-impact` (không có hệ quả UI — ảnh tác giả chỉ đổi metadata,
  điểm ảnh giữ nguyên).
