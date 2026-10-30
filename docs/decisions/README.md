# Decisions (ADR)

Mỗi quyết định kiến trúc/methodology = 1 file ngắn `NNNN-ten-ngan.md`, theo `0000-template.md`. Tạo bằng skill `/record-decision`.

**Quy tắc**
- Không sửa ADR đã `Accepted` để đổi ý — viết ADR mới và đổi trạng thái ADR cũ thành `Superseded by ADR-XXXX`.
- Đề xuất từ `docs/research/` (private) chỉ thành ADR khi Thy đã duyệt.
- Bảng quyết định trước 2026-09-30: `legacy-log.md` (lưu trữ nguyên văn, không sửa).

| # | Quyết định | Trạng thái | Ngày |
|---|---|---|---|
| [0001](0001-less-is-more-scope.md) | Thu hẹp scope: bỏ generation giọng văn, carousel, KOL engine; tập trung NLP → knowledge base | Accepted | 2026-09-30 |
| [0003](0003-docs-and-harness-structure.md) | Cấu trúc tài liệu + harness Claude Code: CLAUDE.md ngắn, rules theo đường dẫn, ADR, skills, subagents | Accepted | 2026-09-30 |
| [0004](0004-reply-roles-and-clean-full-text.md) | Phân vai reply (self_continuation / author_answer / outbound), `full_text` sạch, lưu embedding + hồ sơ cụm, bỏ `'fixed'` | Accepted | 2026-10-01 |
| [0008](0008-decision-consistency-enforcement.md) | Cưỡng chế nhất quán quyết định ↔ repo: sổ luật + check.py + consistency-auditor + /decision-sweep, pre-commit chặn | Accepted | 2026-09-30 |
| [0009](0009-product-name-unthreaded.md) | Tên hiển thị sản phẩm "Unthreaded" (slug `threads-ai-content` giữ nguyên) + câu miễn trừ Meta | Accepted | 2026-09-30 |
| [0010](0010-sqlite-only-database.md) | SQLite là CSDL duy nhất (gồm cả knowledge base) — bỏ lời hứa PostgreSQL | Accepted | 2026-09-30 |
| [0011](0011-zero-view-posts-are-missing-data.md) | Bài views = 0 là dữ liệu thiếu — loại khỏi mọi phân phối rate, báo số bị loại | Accepted | 2026-09-30 |
| [0012](0012-reach-tiers-and-share-rate.md) | "Bài lan rộng" = tầng reach tương đối ("Top 20% reach" P80 / "Above median reach" P50 của views ÷ median 20 bài trước, bài đã chín); đổi tên `share_rate`; bỏ nhãn P90 tỉ lệ chia sẻ + sàn P25 | Accepted | 2026-10-06 |
| [0013](0013-headless-cron-jobs.md) | Cron job chạy bằng pythonw (không console), job tự ghi log UTF-8, hook đo độ tươi từ DB | Accepted | 2026-10-01 |
| [0014](0014-whole-repo-gates-and-ci.md) | Pre-commit quét toàn repo (`--commit`), `--all` quét cả file chưa track, CI GitHub Actions | Accepted | 2026-10-01 |
| [0015](0015-mandatory-tier2-review.md) | Bắt buộc review tầng 2: dấu review khớp nội dung (hook SubagentStart/Stop) + git hook pre-commit chặn commit do Claude chạy (harness `.claude/` ngoài phạm vi từ ADR-0027) | Accepted | 2026-10-01 |
| [0016](0016-sonnet-cluster-labeling.md) | Đặt tên cụm bằng `claude-sonnet-5-5` thay `claude-opus-5`; bỏ lời hứa prompt caching | Accepted | 2026-10-04 |
| [0017](0017-daytime-nlp-job.md) | Job NLP chạy 12:30 (Modern Standby đóng băng job đêm); cả 2 cron chạy khi dùng pin; cấu hình task bằng `configure_jobs.ps1` | Accepted | 2026-10-04 |
| [0018](0018-stable-topic-identity.md) | Danh tính cụm bền (`topic_N`): ghép theo thành viên (đa số hai chiều, bỏ nhiễu, lõi giữ tên) + ngữ nghĩa; đặt lại tên khi trôi khỏi bản neo; prompt đặt tên v2 | Accepted | 2026-10-04 |
| [0019](0019-git-workflow.md) | Quy trình git: thư mục chính luôn ở `main`, mọi thay đổi trong worktree trên nhánh riêng, PR + CI + merge commit; nhắc tự động ở hook đầu phiên, skill `/git-flow` (harness `.claude/` ngoài phạm vi từ ADR-0027) | Accepted | 2026-10-05 |
| [0020](0020-ui-contract.md) | Hợp đồng UI `docs/design/ui-contract.md` neo thiết kế vào ADR (ADR → hợp đồng → mockup → code); ADR có mục "Hệ quả UI"; mockup bị sổ luật quét ở mức cảnh báo | Accepted | 2026-10-06 |
| [0021](0021-brand-logo-unknot.md) | Logo Unknot: một nguồn file `public/brand/`, component `BrandLogo`, vị trí cố định (cỡ topbar và chỗ chuyển động: xem ADR-0026), favicon `app/icon.svg`, tôn trọng `prefers-reduced-motion` | Accepted | 2026-10-07 |
| [0022](0022-topic-keywords-word-segmentation.md) | Từ khoá topic tách theo từ bằng underthesea 9.5.0 + bigram 2 từ đơn, bỏ stopword có nhãn (`src/nlp/stopwords.py`) — chỉ ở bước c-TF-IDF sau gom cụm | Accepted | 2026-10-08 |
| [0023](0023-page-roles-and-topic-comparison.md) | Vai trò 3 trang app (câu hỏi → câu trả lời → bằng chứng → phương pháp); so topic với phần còn lại của kênh bằng Brunner-Munzel hoán vị + Cliff's δ kèm CI, họ Holm = mọi phép so trên trang Topics (landing dùng chung); UI không hiện mean; sàn views P25 cho bảng top theo tỉ lệ | Accepted | 2026-10-09 |
| [0024](0024-exploratory-topic-comparisons.md) | Kết luận so sánh topic hiển thị dạng khám phá (δ + CI + p Holm, không câu khẳng định) tới khi qua luật bền đo bằng RQ-01 (đa seed); lịch sử "đạt ở k trong m cách chia" đếm theo cách chia khác nhau — thu hẹp quy tắc khẳng định của ADR-0023 | Accepted | 2026-10-18 |
| [0025](0025-serverless-read-only-api-deploy.md) | Deploy: FastAPI chỉ đọc chạy như Vercel Python Function, đọc bản sao DB từ Vercel Blob riêng tư (publish sau mỗi job trên laptop); code deploy tự động từ GitHub; job snapshot giữ trên laptop; deploy thử thất bại → snapshot tĩnh | Accepted | 2026-10-20 |
| [0026](0026-brand-logo-size-and-replay.md) | Logo topbar 36px kèm tagline 15px cạnh logo; topbar, navbar landing và hero landing phát lại hoạt cảnh tháo nút mỗi 15 giây (`lockup-replay`, Blob + object URL mới mỗi chu kỳ, `prefers-reduced-motion` → tĩnh) — thay mục 3 ADR-0021 | Accepted | 2026-10-29 |
| [0027](0027-public-repo-all-rights-reserved-private-harness.md) | Repo public giữ mọi quyền (`LICENSE`; bên thứ ba giữ giấy phép gốc); harness `.claude/` gitignored, lịch sử ở kho bare riêng ngoài thư mục, worktree nhận bản sao chỉ đọc; `check --all` vẫn quét harness trên máy, `--commit` chặn `.claude/` bị track — thu hẹp ADR-0015/0019 cho `.claude/` (phần "không viết lại lịch sử" thay bởi ADR-0028) | Accepted | 2026-10-30 |
| [0028](0028-rewrite-public-history-and-public-readiness.md) | Viết lại lịch sử repo public (`git filter-repo` bỏ `.claude/`, `docs/research/`, `docs/archive/` khỏi mọi commit; Thy force push + GitHub Support); `docs/archive/` gitignored; quy tắc làm việc riêng sang `CLAUDE.local.md`; ngoại lệ sửa câu chữ ADR (không đổi quyết định); ảnh tác giả bỏ EXIF | Accepted | 2026-10-30 |
| [0029](0029-product-wide-ui-rule-book.md) | Một thang chữ cho landing + mọi trang app (landing chỉ thêm display-1/2), sổ luật UI/UX có mã T/L/C/N/B/A/X + danh sách trắng của landing (`design-system.md` §3, §3b); cưỡng chế 2 lớp — `@agent-ux-reviewer` chấm mọi trang + máy đo `ux-shots.mjs` (axe-core), không chặn commit; sửa trang ở PR riêng | Accepted | 2026-10-30 |

Dự kiến (đánh số giữ chỗ theo `docs/roadmap.md` và plan P1 dashboard): 0002 runtime WSL2 · 0005 experiment tracking JSON + git · 0006 lưu trữ + truy xuất KB · 0007 dữ liệu bình luận follower & privacy.
