# Next Steps — Threads AI Content
> Cập nhật: 2026-09-03
> **Đang chạy theo `docs/sprint-plan.md`** — kế hoạch ngày-theo-ngày (Giai đoạn 1-3, Carousel hoãn lại). File này giữ lịch sử các mốc đã qua; sprint-plan.md là nguồn "hôm nay làm gì".
> **Việc cần làm ngay khi quay lại phiên tiếp theo**: xem mục 12-13 — toàn bộ 6 commit đã **push lên `origin/main`** (`dd7bf37..7534faa`). User đã tự test Timeline Brush thật trong browser (log backend xác nhận có drag/nudge liên tục theo ngày) — không còn là điểm mù. Việc còn lại: user tự duyệt lại bio tác giả (`LandingAuthor.tsx`) và sub-headline diễn giải tagline (`LandingHero.tsx`) — cả 2 do tôi draft, chưa phải bản cuối user xác nhận. TopicExplorer.tsx/topics/page.tsx vẫn còn ở token v2 cũ, ngoài phạm vi cả 2 đợt.

---

## Hành động ưu tiên ngay khi quay lại

### 1. Meta Developer setup — ĐÃ HOÀN TẤT

App `threads-thydilammuon`, use case Threads API, 8 permissions (Standard Access), Tester `thydilammuon` đã accept, `.env` đủ 4/5 giá trị. Không còn việc gì ở mục này.

### 2. `src/api/` — ĐÃ HOÀN TẤT

6 file (`models.py`, `cache.py`, `auth.py`, `client.py`, `endpoints.py`, `__init__.py`) + test đầy đủ tại `tests/api/` (27 test). Tooling: `uv` + `pyproject.toml`, ruff + mypy strict + pytest + pre-commit, git repo đã init.

```bash
uv run pytest -q          # 27 passed
uv run ruff check .       # All checks passed!
uv run mypy               # Success: no issues found
```

### 3. Test end-to-end với data thật — ĐÃ HOÀN TẤT (2026-08-28)

Đã fetch thật 25 posts + account insights của `thydilammuon`. Phát hiện và sửa 2 vấn đề thật trong `endpoints.py`/`models.py` mà giả định ban đầu sai:
- `children` (field post) là edge `{"data": [{"id": ...}]}`, không phải `list[str]` phẳng → đã thêm `field_validator` trong `ThreadsPost`.
- `follower_demographics` bắt buộc param `breakdown`, không gộp được với các metric khác → tách thành hàm riêng `get_follower_demographics()`. Response shape account-level cũng không đồng nhất giữa các metric (`views` là time-series theo ngày cần cộng dồn, `likes/replies/...` là `total_value`, `clicks` là `link_total_values` theo từng link) — chi tiết đầy đủ tại `docs/claude/data-model.md` phần "Metrics lấy từ API".

Test suite hiện có 25 test, tất cả pass, cùng ruff/mypy sạch.

### 4. Pagination cho `get_posts()` + thêm `get_replies()` — ĐÃ HOÀN TẤT (2026-08-29)

`get_posts()` trước đây chỉ lấy 1 page (25 posts, default page size của Graph API) — không follow `paging.cursors.after`/`paging.next` nên bỏ sót phần còn lại của lịch sử kênh nếu kênh có > 25 bài. Đã sửa:
- Thêm `ThreadsClient.get_url()` — fetch thẳng URL tuyệt đối (`paging.next` đã có sẵn `access_token`, không inject lại)
- Thêm helper `_paginate()` trong `endpoints.py`, dùng chung cho `get_posts()` và `get_replies()` mới — loop theo `paging.next` tới khi hết
- Thêm `get_replies()` (dùng scope `threads_manage_replies` đã có sẵn ở Phase 1) — lấy toàn bộ reply tác giả đã đăng, cache riêng key `replies_{user_id}`

**Verify live (2026-08-29)**: fetch thật cả 2 endpoint — `/replies` trả đúng shape như giả định ban đầu (khác với `children`/account insights trước đây, lần này giả định đúng ngay, không cần sửa code). Số liệu thật của kênh: **140 posts** (số "25 posts" ghi ở mục 3 chỉ là page 1 do bug pagination cũ, đã lỗi thời), **1,285 replies**.

Test suite hiện có 27 test (thêm 2: pagination `get_posts()` qua nhiều trang + `get_replies()`), tất cả pass, ruff/mypy sạch.

### 5. `src/analysis/engagement.py` — ĐÃ HOÀN TẤT (2026-08-29)

Build trên `PostInsights.engagement_rate` có sẵn:
- `average_engagement_rate(insights)` — trung bình engagement rate trên tập post
- `top_posts_by_engagement(posts, insights, limit)` — ghép post với insights theo `id`/`post_id`, sort giảm dần, bỏ qua post không có insights khớp
- `engagement_by_hour(posts, insights)` / `engagement_by_weekday(posts, insights)` — gom nhóm theo giờ/thứ trong tuần, phục vụ heatmap "giờ đăng tốt nhất" ở dashboard

**Cập nhật (2026-08-29)**: audience kênh trải cả Pháp và Việt Nam (2 múi giờ chênh 5-6h tùy DST) — Threads API không cho biết engagement tới từ đâu, nên không tách được thật sự theo audience. Giải pháp: `engagement_by_hour`/`engagement_by_weekday` nhận thêm param `timezone: ZoneInfo | None` — gọi 2 lần với `ZoneInfo("Europe/Paris")` và `ZoneInfo("Asia/Ho_Chi_Minh")` để so sánh 2 góc nhìn trên cùng dữ liệu (mặc định `None` giữ nguyên UTC thô, tương thích ngược). Cần thêm `tzdata` vào dependencies vì Windows không có sẵn IANA timezone database. Chi tiết lý do tại `docs/claude/architecture.md` phần "Quyết định quan trọng đã chốt".

Test suite hiện có 35 test (33 trước đó + 2 test timezone conversion), tất cả pass, ruff/mypy sạch.

### 6. [SUPERSEDED 2026-08-30] `src/analysis/virality.py`, `src/analysis/topics.py`, rồi `src/main.py`

> Mục này đã lỗi thời — `topics.py` (keyword matching + Claude classification) bị thay hoàn toàn bằng pipeline NLP thật (embedding + SVM-RBF/LogReg + UMAP/HDBSCAN + RAG). Xem `docs/sprint-plan.md` (Ngày 1-13) cho kế hoạch hiện hành, `docs/claude/data-model.md` phần "NLP Pipeline" cho thiết kế chi tiết.

### 7. Batch qua đêm — Bước 1/2/4/9 + snapshot job + draft NLP + dashboard tối giản — ĐÃ HOÀN TẤT (2026-08-31/09-01)

Chạy trên worktree `agent-ae623e2a159ec48c4` (chưa merge vào `main`, chưa commit). Tóm tắt:
- `src/models/`, `src/db/schema.py`, `src/processing/`, `src/analysis/{popularity,virality,conversation,freshness}.py` — xong, test/ruff/mypy sạch, verify trên 140-141 post thật.
- Verify live phát hiện `text_attachment` **thực ra có được tác giả dùng** (ngược ghi chú cũ "0/100 item có data") — đã sửa field validator + doc.
- Dashboard Next.js (Overview + Topic Explorer skeleton) — build/lint sạch, chưa deploy, chưa push GitHub.
- `src/nlp/{language,embeddings,topics}.py` viết xong nhưng embedding/clustering CHƯA verify chạy thật lúc đó (Application Control Policy chặn — xem mục 9).

### 8. Bắt post mới + `velocity.py` + cron snapshot 4h + Virality Potential Tracker — ĐÃ HOÀN TẤT (2026-09-01)

- `velocity.py` (view_velocity, amplification_velocity) — xong, verify thật: post mới đăng lúc 12:10:19Z đạt **65,31 views/h** giữa 2 snapshot cách nhau ~22 phút.
- Cron 4h qua Windows Task Scheduler (`ThreadsAI_SnapshotJob_4h`) — gặp `STATUS_CONTROL_C_EXIT` do lỗi quoting `cmd.exe /c "..."` inline, sửa bằng launcher `run_snapshot_job.bat` riêng, verify chạy ổn định qua chính Task Scheduler (không chỉ chạy tay). **Lưu ý: task đang trỏ vào path worktree tạm — cần trỏ lại sau khi merge vào `main`.**
- Publish artifact CV tạm thời (link riêng, không phải repo) — data thật đầy đủ 141 post, top-10 mỗi metric + tab "All posts", Virality Potential Tracker cho post mới nhất, demographics thật (VN 71,5%/FR 19,3%).
- Dọn side-effect: `uv sync` lại `.venv` repo chính (gỡ 36 package cài nhầm lúc debug), xoá bản copy `.env` trong worktree (verify `load_dotenv()` tự tìm ngược lên `.env` gốc của repo chính, không cần copy riêng).

### 9. Chẩn đoán Smart App Control + dựng pipeline clustering qua WSL2 — ĐÃ HOÀN TẤT (2026-09-02)

Chi tiết đầy đủ + lý do tại `docs/claude/architecture.md` (decision log 2026-09-02) và `docs/claude/data-model.md` ("Methodology log: clustering space cho HDBSCAN"). Tóm tắt: xác định đúng là Smart App Control (không phải WDAC), quyết định không tắt, chuyển toàn bộ embedding+UMAP+HDBSCAN sang WSL2 (đã cài sẵn), dựng cầu nối 3 script (`clustering_export.py`/`cluster_wsl.py`/`clustering_import.py`), verify chạy thật thành công.

### 10. Thực nghiệm methodology: raw embedding space vs UMAP space cho HDBSCAN — ĐÃ CÓ KẾT LUẬN, CHỜ XÁC NHẬN (2026-09-02)

Phát hiện raw-embedding-space suy biến (1 cluster 82% dữ liệu), chẩn đoán curse of dimensionality. Phát hiện phụ: 6/141 post `REPOST_FACADE` (full_text rỗng) làm nhiễu so sánh — đã loại khỏi export (135 post sạch). Kết quả cuối: **UMAP-space thắng rõ rệt** (noise 3% vs 59% khi raw-embedding-space mất đi 6 điểm neo). Số liệu đầy đủ tại `docs/claude/data-model.md`.

**Việc còn lại — làm khi quay lại phiên sau (hoặc trong phiên này nếu được xác nhận)**:
1. Sửa `cluster_embeddings()` (`src/nlp/topics.py`) — đổi input HDBSCAN sang UMAP coords, cập nhật docstring theo bằng chứng thực nghiệm (không phải lý thuyết cũ).
2. Chạy lại `clustering_import.py` — ghi toạ độ UMAP + chạy LLM labeling (đặt tên cluster tiếng Anh) vào SQLite thật.
3. Wire data thật vào Topic Explorer (`src/dashboard/`), verify hiển thị đúng.
4. Cân nhắc thử `min_cluster_size` khác 5 nếu 2 cluster (50/81) vẫn quá thô so với 6 category cố định — chưa làm, chỉ là ý tưởng dự phòng.
5. Trỏ lại cron `ThreadsAI_SnapshotJob_4h` sang path `main` sau khi merge worktree.

### 11. LLM cluster labeling + commit/push toàn bộ pipeline lên `main` — ĐÃ HOÀN TẤT (2026-09-02)

- `ANTHROPIC_API_KEY` đã có (user tự tạo tại console.anthropic.com, $5 credit). Chạy `clustering_import.py` thật: 2 cluster được đặt tên có ý nghĩa — **"Food and Shopping in France"** (50 post) và **"Studying in France Guidance"** (81 post). Verify UTF-8 sạch trong DB.
- Test suite cuối: **107 passed, 0 failed, 0 skipped**; ruff + mypy sạch toàn bộ 62 file.
- **Commit + push lên GitHub thành công** (`869aa41..8af3f30` trên `main`), 2 commit:
  1. `59a303a` — NLP pipeline, dashboard, cron 4h (81 file — toàn bộ việc mục 7-10)
  2. `8af3f30` — Design Claude Skills + research docs từ Claude Cowork/Design (179 file, xem mục dưới)
- **Phát hiện quan trọng lúc commit**: `main` có sẵn thay đổi cục bộ chưa commit từ **Claude Cowork và Claude Design** (2 công cụ khác của Anthropic, user chủ động dùng song song, không phải rác) — `CLAUDE.md`, `docs/claude/design-system.md`, `docs/sprint-plan.md`, `uv.lock`, `.claude/skills/*` (7 skill thiết kế: banner-design/brand/design/design-system/slides/ui-styling/ui-ux-pro-max), `docs/research/*.html`. Đã `git stash` → merge nhánh worktree (fast-forward sạch) → `stash pop` → **`uv.lock` xung đột thật đúng như dự đoán** → xử lý bằng regenerate (`uv lock`) từ `pyproject.toml` đã merge sạch, không hand-merge lockfile.
- 2 bug hạ tầng phát hiện + sửa trong lúc commit (chi tiết đầy đủ tại `docs/claude/architecture.md` decision log 2026-09-02):
  - `.pre-commit-config.yaml` mypy hook: `entry: .venv/Scripts/python.exe` thiếu tiền tố `./` → Windows `CreateProcess` không resolve được (khác Bash) → `WinError 2`. Sửa thành `./.venv/Scripts/python.exe`.
  - `.claude/skills/` (vendored, không phải code dự án) bị ruff lint theo chuẩn dự án này → thêm `.claude` vào `extend-exclude` trong `pyproject.toml`.
- **Quy tắc mới**: mọi commit message của repo này **luôn viết tiếng Anh** (đã lưu memory `feedback_commit_language.md`) — mục tiêu để người ngoài (portfolio audience) đọc được lịch sử commit.

**Việc còn lại**:
1. Cron `ThreadsAI_SnapshotJob_4h` vẫn trỏ vào path worktree (`​.claude/worktrees/agent-ae623e2a159ec48c4`) — cần trỏ lại sang `main` (worktree giờ chỉ còn giữ lại vì cron cần, không xoá được cho tới khi trỏ lại xong).
2. Wire data cluster thật (đã có trong SQLite) vào Topic Explorer (`src/dashboard/`), verify hiển thị đúng.
3. Dashboard vẫn chưa deploy public (Vercel) — xem lại thảo luận "static export + Vercel Deploy Hook" đã bàn trước đó nếu muốn làm tiếp.

### 12. Overview page thật: windowed analytics endpoint + Timeline Brush + Analytics tab thật — ĐÃ HOÀN TẤT (2026-09-03)

Việc build thật sau khi v3.1 Amber design sync (mục trước) bị chỉ ra là "quá sơ sài, không liên quan gì đến design đã làm ở Claude Design" — xem `feedback_mockup_is_spec` trong memory. Kế hoạch đầy đủ + 3 quyết định đã hỏi user trực tiếp (không tự quyết âm thầm) nằm trong plan file phiên này; tóm tắt:

**Backend** (`22380ca`):
- Verify live 2026-09-03: `threads_insights?metric=views&period=day&since=...&until=...` trả breakdown thật theo ngày, cap lookback **2 năm** (Meta trả lỗi rõ ràng "Metrics data is available for the last 2 years" khi vượt), `end_time` luôn `07:00:00+0000` (ranh giới ngày Pacific time, đã quy đổi đúng — verify khớp chính xác điểm cuối cùng thật khi so với data đã ingest).
- Bảng mới `account_daily_views` (date, views, fetched_at) + `src/pipeline/daily_views.py` (backfill full 729 ngày lần đầu, chỉ refetch 7 ngày gần nhất các lần sau) — đã gộp vào `run_ingest()` nên chạy tự động cùng cron 4h có sẵn. Đã backfill thật: **730 điểm** (2024-09-02 → 2026-09-01).
- `src/analysis/stats.py` mới — generalize `EngagementBucketStats` (Layer 2 cũ) thành `DistributionStats`/`distribution_stats()`/`window_stats()` dùng chung cho Engagement/Virality/Conversation trong 1 cửa sổ thời gian (trước đây chỉ Engagement có median/mean).
- 2 endpoint mới: `GET /analytics/daily-views` (toàn bộ series đã ingest, gọi 1 lần) và `GET /analytics/window?start=...&end=...` (hero/KPI/top-content tính lại thật theo [start,end]).
- **Quyết định methodology quan trọng** (user chốt, không phải tôi tự chọn): số Engagement/Virality/Conversation trong window là **median+mean của từng post** (đúng Layer 2 cũ), KHÔNG dùng pooled ratio Σinteractions/Σviews mà file mockup `.dc.html` tự tính cho đẹp — "MOCKUPS tuyệt đối chỉ dùng cho DESIGN, không được phép can thiệp vào quyết định mọi kĩ thuật đã thống nhất trước đó" (nguyên văn user).
- 183 test pass (20 mới), ruff/mypy sạch.

**Frontend** (`c31d756`, `f887b9b`, `040096b`):
- `Nav.tsx` rebuild: topbar (logo/tagline/account pill/avatar) + 3-tab pill thật (Overview/Analytics/Topic Explorer — Analytics giờ là route thật, không phải placeholder, theo yêu cầu user "Xây luôn tab Analytics thật đợt này").
- `AnalyticsOverview.tsx` → đổi tên `AnalyticsBreakdown.tsx`, chuyển sang route `/analytics` (bảng top-post 3 metric + biểu đồ giờ/thứ theo timezone) — đồng thời sửa bug type-drift có sẵn (`HourBucket`/`WeekdayBucket` phía frontend đọc field `average_engagement_rate` không còn tồn tại từ khi backend đổi sang `DistributionStats`).
- Overview (`/`) rebuild hoàn toàn: `HeroBand`, `TimelineBrush` (component tương tác chính — port pointer-capture drag 2 tay cầm + pan + keyboard nudge + 4 preset từ `overview-amber.dc.html`, nhưng số liệu KPI refetch thật từ backend, debounce 300ms, không tính tại client như mockup), `KpiStrip`, `MetricArchitectureGrid`, `TopContentList`.
- Thêm dependency `@phosphor-icons/react` (design-system.md §6 yêu cầu Phosphor icon).
- `npm run build` + `npm run lint` sạch. Verify **API thật** qua curl (daily-views trả 728 điểm khớp data backfill, `/analytics/window?start=2026-08-01&end=2026-09-01` trả 16 content unit/991,841 views/median engagement 2.30% — số hợp lý). `npm run dev` + `uvicorn` chạy thật, cả 3 route (`/`, `/analytics`, `/topics`) trả 200, không lỗi server.

**Chưa verify được** (không có tool browser trong môi trường này): tương tác kéo/pan/phím mũi tên/preset thật trong trình duyệt — cần user tự mở `npm run dev` + `uvicorn src.main:app --reload` và thử tay trước khi coi là "done" theo đúng house rule "test trong browser trước khi báo done".

**Việc còn lại (mục 12) — ĐÃ XONG, xem mục 13**: user đã tự test Timeline Brush thật (xác nhận qua log backend), đã push.

### 13. Landing/story page (Tầng B scoped) + di chuyển tool sang `/overview` — ĐÃ HOÀN TẤT, ĐÃ PUSH (2026-09-03)

User tự mở link deploy tạm ở mục 12, test thật thấy Timeline Brush chạy tốt nhưng chỉ ra đúng 1 vấn đề: ai bấm link cũng rơi thẳng vào raw analytics, không có gì giải thích sản phẩm là gì/giải quyết vấn đề gì/tác giả là ai. Cũng hỏi "tại sao views trống trước tháng 3" — trả lời trực tiếp bằng data thật (không sửa code gì): bài đăng đầu tiên của kênh là 2025-04-14, nên 7 tháng đầu trong cửa sổ 2 năm Meta cho phép (từ 2024-09) đúng là 0 thật (kênh chưa tồn tại), không phải lỗi.

**Đã làm**: landing page thật ở `/` (Hero + Problem + Solution 3 tầng statistics/NLP/RAG + Tech stack grid ~15 dòng có badge live/coming soon + khối "AI Content Generation — Coming soon" riêng + About the channel), tool chuyển sang `/overview` qua Next.js route group `(app)/` (Analytics/Topics giữ nguyên route, chỉ đổi vị trí file). `Nav.tsx` sửa: tab Overview trỏ `/overview`, logo/tagline giờ là link về `/`.

**2 chỗ nội dung cần user tự duyệt lại** (draft từ fact có sẵn, không bịa, nhưng chưa phải bản cuối user xác nhận):
- Bio tác giả trong `LandingAuthor.tsx` — chỉ dùng đúng fact đã có trong CLAUDE.md.
- Sub-headline diễn giải tagline "The algorithm, read back to you." trong `LandingHero.tsx` — grep xác nhận tagline này official/locked trong `design-system.md` §13 nhưng KHÔNG có rationale nào được ghi lại; sub-headline là diễn giải của tôi, đã nói rõ với user.

**Đã push**: `origin/main` tại `7534faa` (6 commit tổng cộng từ đầu phiên, `dd7bf37..7534faa`).

**Việc còn lại**:
1. User duyệt/sửa bio tác giả + sub-headline tagline (2 điểm ở trên).
2. `TopicExplorer.tsx`/`topics/page.tsx` vẫn ở token v2 cũ — ngoài phạm vi cả 2 đợt.
3. Tầng B đầy đủ (logo strip, bento feature, pricing, FAQ, footer 4 cột — 13-section spec gốc trong design-system.md §7) — KHÔNG phải cái vừa làm (bản vừa làm là scoped, chỉ đúng phần user yêu cầu). Chưa làm, chưa được yêu cầu ở mức đó.

---

## Kế hoạch theo giai đoạn

**[SUPERSEDED 2026-08-30]** — kế hoạch chi tiết theo ngày (13 ngày, Giai đoạn 1-3 mở rộng NLP/RAG, Giai đoạn 4 hoãn) nay nằm ở `docs/sprint-plan.md`, không lặp lại ở đây nữa để tránh 2 nguồn lệch nhau theo thời gian.

---

## Prompt sẵn để resume project

Copy đoạn sau và paste vào Claude khi quay lại:

```
Tôi đang tiếp tục dự án "Threads AI Content" — công cụ AI phân tích và generate content cho kênh Threads "thydilammuon".

Hãy đọc CLAUDE.md và docs/next-steps.md để nắm context (đọc thêm file liên quan trong docs/claude/ nếu task chạm tới đúng mảng đó), sau đó:
1. Tóm tắt ngắn gọn project đang ở đâu (1 đoạn)
2. Xác nhận bước tiếp theo cần làm là gì
3. Hỏi tôi cần làm gì trong phiên này trước khi bắt đầu

Working directory: c:\Users\hmnth\Desktop\Portfolio\project_AI\threads-ai-content
```

---

## Tham khảo nhanh

| Tài nguyên | Đường dẫn / Link |
|-----------|-----------------|
| Threads API docs | https://developers.facebook.com/docs/threads/ |
| Retrieve posts | https://developers.facebook.com/docs/threads/retrieve-and-discover-posts/retrieve-posts |
| Insights API | https://developers.facebook.com/docs/threads/insights |
| Meta Developer Portal | https://developers.facebook.com |
| Design reference | `docs/design/dashboard-reference.png` |
| Carousel templates | `Content/Content - Photo carousel/` |
| Scripts gốc (giọng văn) | `Content/Scripts/` |
| Font Google Sans | `src/carousel/fonts/Google_Sans/static/` |