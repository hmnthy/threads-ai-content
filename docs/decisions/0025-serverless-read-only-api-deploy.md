# ADR-0025: Deploy FastAPI chỉ đọc lên Vercel, đọc bản sao DB từ Blob riêng tư

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-20
- **Người quyết**: Thy — chọn phương án D (API serverless chỉ đọc) và giữ job snapshot trên laptop, sau khi đọc bảng so
  sánh có số đo (2026-10-20). Claude Code đo và đề xuất.

## Bối cảnh

### Câu hỏi

Dashboard (Next.js, `src/dashboard/`) chưa deploy cố định — chỉ từng deploy tạm (Vercel `--temporary` ~15 phút + tunnel
về laptop). Trở ngại không nằm ở frontend mà ở **số liệu**: FastAPI (`src/main.py`) đọc `data/threads.db` trên laptop, do
2 cron job ghi (ADR-0013, ADR-0017). Vercel không có máy chủ thường trực và không giữ file lâu dài. Cần chọn cách phục vụ
số liệu cho bản công khai.

### Bằng chứng (đo 2026-10-20)

1. **Giới hạn của Vercel:** hàm Python tối đa **500 MB** sau giải nén (Large Functions beta: 5 GB) — tài liệu Vercel
   "Functions limitations" / "Python runtime" (tra qua context7). Vercel tự nhận điểm vào `src/main.py` có biến `app`
   (danh sách entrypoint chuẩn gồm `main.py` trong `src/`) — không cần đổi cấu trúc thư mục.
2. **Dung lượng thư viện API đang import:** đo wheel Linux (manylinux x86_64, CPython 3.12) đúng phiên bản trong
   `uv.lock` của mọi gói mà `import src.main` nạp: **474,8 MB** — sát giới hạn. Riêng `lingua-language-detector` 292,0 MB;
   scipy 106,8; numpy 54,5; phần còn lại ≈ 21,5. `lingua` và `anthropic` bị kéo vào chỉ vì `src/main.py:88` import
   `src.nlp.topic_identity`, và `src/nlp/__init__.py` import sẵn `src.nlp.language` (lingua) + `src.nlp.topics`
   (anthropic). API không dùng 2 thư viện này. Mô phỏng bản sửa (nạp `src.main` khi gói `src.nlp` không chạy
   `__init__.py`) → còn **177,6 MB** (không còn `lingua`, `anthropic`, `jiter`, `docstring_parser`, `httpx2`; chưa tính
   `setuptools` — vẫn bị nạp, chưa đo). Con số này vẫn gồm `httpx`, `python-dotenv` và mã client Threads, vì
   `src/main.py:64` import `src.api.models` → chạy `src/api/__init__.py` (auth, client, cache, endpoints) —
   chấp nhận (nhỏ, không chứa token); PR triển khai cân nhắc tách. Số của gói thật đo lại ở lần deploy thử.
3. **Danh sách thư viện của dự án:** `pyproject.toml` khai báo chung cả bộ ML (`sentence-transformers` → torch,
   `umap-learn`, `hdbscan`, `underthesea`, `scikit-learn`). Tài liệu Vercel không nêu thứ tự ưu tiên giữa
   `pyproject.toml` / `requirements.txt` → cài nguyên `pyproject.toml` hiện tại chắc chắn vượt 500 MB. Gói API phải có
   danh sách thư viện riêng.
4. **DB:** `data/threads.db` 8,5 MB, `journal_mode = delete` (mở chỉ-đọc được, không cần file `-wal`/`-shm`). Không
   chứa token (token lưu riêng, gitignored). `connect()` hiện mở đọc-ghi và tạo thư mục cha
   (`src/db/schema.py:233-241`) — trên Vercel chỉ ghi được thư mục tạm.
5. **Phép tính theo khoảng ngày tuỳ chọn:** `GET /analytics/window?start&end` (`src/main.py`, `get_analytics_window`)
   tính lại cho khoảng bất kỳ do thanh thời gian chọn; `account_daily_views` có 775 ngày (2024-09-02 → 2026-10-18) →
   ~300.000 cặp ngày, không tính sẵn được.
6. **Cách lấy dữ liệu của dashboard:** landing là server component, fetch `no-store` phía server
   (`src/dashboard/src/app/page.tsx`); Overview / Analytics / Topics fetch trong trình duyệt (client component) — mọi
   lời gọi qua `NEXT_PUBLIC_API_BASE_URL` (`src/dashboard/src/lib/api.ts`).
7. **Vercel Blob riêng tư:** store private bắt buộc xác thực cho mọi lần đọc/ghi, không có URL công khai; code chạy trên
   Vercel đọc bằng OIDC, code ngoài Vercel (laptop) ghi bằng `BLOB_READ_WRITE_TOKEN`; SDK Python `vercel` ≥ 0.5.0 — tài
   liệu Vercel "Private storage". `data/` gitignored nên Git integration không mang DB theo được.

## Quyết định

1. **API công khai = chính FastAPI hiện có, chạy như Vercel Python Function chỉ đọc.** Hàm đọc một **bản sao DB** lấy từ
   **Vercel Blob riêng tư** về thư mục tạm khi khởi động, mở ở chế độ chỉ đọc; logic tính số giữ một bản duy nhất
   (Python). Gói hàm chỉ chứa thư viện API cần (không bộ ML, không `lingua`/`anthropic`).
2. **Code deploy qua Vercel Git integration** (2 project: dashboard `src/dashboard/`, API ở gốc repo) mỗi khi `main` có
   commit mới; **số liệu đi đường riêng**: sau mỗi lần job chạy trên laptop, một bước publish tạo bản sao DB nhất quán và
   tải lên Blob. Cập nhật thường kỳ không cần Vercel CLI (CLI trên Windows lỗi symlink; chỉ chạy được từ
   WSL2 — giữ cho việc deploy tay nếu cần).
3. **Job snapshot và job NLP vẫn chạy trên laptop** (ADR-0013, ADR-0017); trang công khai mới bằng lần publish gần nhất.
   Chuyển job lên cloud là quyết định riêng (mục "Xem lại khi").
4. **Lần deploy thử là cổng:** gói vượt 500 MB, hàm không mở được DB, hoặc trang không tải được vì cold start → chuyển
   sang phương án A (snapshot tĩnh) bằng ADR mới.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| A. Snapshot tĩnh: laptop xuất JSON qua chính API (TestClient), trang đọc file | Đơn giản, an toàn nhất, không có API công khai | Phép tính khoảng ngày (bằng chứng 5) phải viết lại bằng TypeScript + test đối chiếu, hoặc chỉ cho chọn khoảng cố định (cần mockup); phải đổi cả 2 kiểu lấy dữ liệu (bằng chứng 6); không có API sống; Phase E/F vẫn phải dựng API | Hai bản logic cho cùng 1 số; giữ làm phương án dự phòng (quyết định 4) |
| B. Thuê VM / PaaS chạy FastAPI + SQLite + cron 24/7 | Bịt khoảng hở ban đêm của snapshot | Tốn phí hằng tháng; token Threads lên cloud; tự vá bảo mật máy chủ | Chi phí và bề mặt tấn công không tương xứng với API chỉ đọc ~150 bài |
| Supabase (Postgres + REST tự sinh) | Có pgvector cho Phase E | Không chạy Python → vẫn phải thuê chỗ chạy FastAPI hoặc viết lại thống kê bằng SQL/TS; đổi CSDL, đụng ADR-0010 | Không giải quyết chỗ chạy logic; xem lại khi chọn lưu trữ KB (ADR-0006 dự kiến) |
| Vercel CLI `--prebuilt` từ WSL2, đóng DB vào gói | Không cần Blob | Mỗi lần cập nhật số = 1 lần build + deploy từ laptop; CLI trên Windows lỗi symlink, phải chạy WSL2 (Phase C chưa xong) | Git integration + Blob tách code khỏi số liệu, ít bước hơn |
| Chuyển job snapshot lên GitHub Actions ngay | Bịt khoảng hở ~16 h/đêm (ADR-0017), velocity dày hơn | Token Threads lên GitHub Secrets; DB phải sống trên cloud; đổi cả 2 cron | Thy chọn deploy trước, xem lại sau |

## Hệ quả

- **PR triển khai (sau ADR này), theo thứ tự:**
  1. Gói API tối giản: gỡ import sẵn trong `src/nlp/__init__.py` (hoặc chuyển hàm API cần ra khỏi gói `src.nlp`) + test
     "import `src.main` không nạp `lingua`, `anthropic`, `torch`, `sklearn`"; danh sách thư viện riêng cho API — cơ chế
     (nhóm thư viện ML tách khỏi danh sách mặc định, hay thư mục deploy riêng) chốt và kiểm ở lần deploy thử; cron và CI
     phải vẫn cài đủ bộ ML.
  2. Chế độ chỉ đọc cho API: lấy DB từ Blob về thư mục tạm khi khởi động, mở `mode=ro`; chạy local giữ nguyên
     `data/threads.db`. Test cho nhánh chỉ đọc.
  3. Bước publish sau mỗi job (snapshot 4h + NLP 12:30): bản sao nhất quán bằng backup API của SQLite (không copy file
     đang ghi), tải lên Blob riêng tư bằng `BLOB_READ_WRITE_TOKEN` trong `.env` (không commit). Publish lỗi không được làm
     hỏng job chính; `job_health` cảnh báo khi bản đã publish cũ hơn ngưỡng tươi của job snapshot.
  4. Vercel: 2 project, biến môi trường `NEXT_PUBLIC_API_BASE_URL` (dashboard), `CORS_ALLOW_ORIGINS` (API, chỉ domain
     dashboard). **Deploy thử ở môi trường preview trước, Thy duyệt rồi mới public** (đưa dữ liệu lên mạng là hành động
     ra ngoài).
  5. Trước khi public: kiểm theo ADR-0021 "Xem lại khi" (Safari/Firefox, thời gian tải hero ~400 KB); Thy duyệt bio ở
     `LandingAuthor.tsx`; link CTA thật thay `#`; rà privacy — API chỉ trả bài và reply của chính tác giả, chưa có bình
     luận follower (ADR-0007 chưa làm).
  6. Docs: `docs/claude/architecture.md` (luồng dữ liệu + trạng thái deploy), `docs/claude/dev-rules.md` (biến môi trường,
     token Blob), `src/dashboard/README.md`, `docs/status.md`, `docs/roadmap.md`, README ×3 (link sản phẩm thật).
- **Ngay sau deploy:** RQ-01 (ADR-0024).
- **Rủi ro chấp nhận:** laptop ngủ/tắt → trang công khai đứng ở lần publish cuối (khoảng hở đêm như ADR-0017); API
  công khai không xác thực: chỉ đọc, nhưng `GET /analytics/window` tính lại theo mỗi yêu cầu → bị gọi dồn dập có thể tiêu
  hết hạn mức gói Hobby; PR triển khai kiểm cơ chế chặn của Vercel (rate limit / firewall) trước khi public; cold start kéo lại 8,5 MB từ Blob; repo public: xem ADR-0027. ADR-0010 giữ nguyên: Blob chỉ chứa **bản sao** file SQLite, không phải CSDL thứ hai.
- **Luật (`invariants.toml`):** `ADR0025-tunnel-backend` (backend qua ngrok/cloudflared/tunnel không còn là cách phục vụ
  số liệu), `ADR0025-internal-api` (API không còn "internal"). Không cấm "chưa deploy cố định" — đúng tới khi PR triển
  khai xong; PR đó cập nhật `architecture.md`.
- **Xem lại khi:**
  1. Deploy thử thất bại theo quyết định 4 → ADR mới chọn phương án A.
  2. Cần số liệu dày hơn (velocity, RQ cần snapshot ban đêm) hoặc Phase C xong (cron chạy trong WSL2) → quyết định
     riêng về chạy job snapshot trên cloud (GitHub Actions + nơi lưu DB).
  3. Phase E/F cần mô hình lúc truy vấn (embedding câu hỏi, reranker `bge-reranker-v2-m3`) — không vừa 500 MB → xem lại
     nơi chạy API (Large Functions, hoặc máy chủ riêng).
  4. Lượng truy cập vượt hạn mức gói Hobby, hoặc dự án có mục đích thương mại.

### Hệ quả UI

- Thêm `UI-0025-published-snapshot`: trang công khai đọc bản sao DB publish từ laptop → số liệu chỉ mới bằng lần publish
  gần nhất; UI ghi rõ mốc dữ liệu (`PipelineSummaryOut.latest_snapshot_at`), không ngụ ý cập nhật liên tục. Nâng mốc
  "Cập nhật tới: ADR-0025".
