# Roadmap — Unthreaded

> Nguồn "làm gì, theo thứ tự nào". Trạng thái hiện tại xem `docs/status.md`; lý do của từng quyết định xem `docs/decisions/`.
> Scope đã chốt tại ADR-0001: **NLP sâu → knowledge base → (sau cổng F) chatbot + landing thương hiệu.** Không generation giọng văn, không carousel.
> Plan gốc có giải thích đầy đủ: phiên 2026-09-30 (plan "LESS IS MORE"). Kế hoạch cũ hơn: lưu trữ riêng, không public (ADR-0028).

Thứ tự: `0 → A1 → B → A2–A6 → G → H → C → D0 → (D ∥ E) → F` (H trước C: Thy ưu tiên deploy, 2026-10-20). Mỗi phase kết thúc bằng checkpoint commit + cập nhật `docs/status.md`.

## Đã xong

- **0** Dọn worktree cũ, `.gitattributes`, `.gitignore`, `.worktreeinclude`
- **A1** `.claude/settings.json` + hooks (status, chặn trailer, ruff-on-edit, pop-up Windows)
- **B** Gỡ generation/carousel (ADR-0001)
- **A2–A6** Tài liệu gọn (CLAUDE.md, status, roadmap, ADR), `.claude/rules/`, subagents, skills, `.mcp.json`
- **Cảnh sát nhất quán** (ADR-0008): sổ luật `invariants.toml`, `check.py`, `/decision-sweep`, pre-commit chặn vi phạm + test nhanh + dashboard, `npm run screenshots`

## C — Chuyển toàn bộ Python sang WSL2 (ADR-0002)

- Clone mới vào ext4 `~/code/threads-ai-content`, mở bằng VS Code Remote-WSL; copy `.env`, `data/threads.db`, `content/`, `~/.claude` (memory dự án).
- `pyproject.toml`: index torch CPU. Bỏ venv `~/threads-clustering-env`.
- `src/config.py::db_path()` — `$THREADS_DB_PATH` hoặc DB của checkout chính (qua `git --git-common-dir`) → mọi worktree dùng chung 1 DB. Thay `DEFAULT_DB_PATH` (`src/db/schema.py`).
- `connect()`: WAL + retry khi "database is locked". Chờ khoá đã làm (`LOCK_WAIT_S` = 120 s, 2026-10-17 — lý do ở `src/db/schema.py`; đừng hạ mà không xem lại khoá ghi dài nhất).
- `scripts/jobs/run_job.sh {snapshot|nlp|kb}` bọc `flock`; job NLP gộp thành `src/pipeline/recluster.py` (gồm cả bước `compare_topics` — ADR-0023; thiếu thì `topic_comparisons` ngừng cập nhật và landing thành `stale`). Xoá cầu nối `clustering_export.py`/`cluster_wsl.py`/`clustering_import.py` + `nlp_cluster_job.py` (launcher Windows của ADR-0013). Giữ nguyên hành vi danh tính cụm của ADR-0018 (ghép thành viên + ngữ nghĩa, bản neo, `retired`) — test `tests/pipeline/test_clustering_import.py` chuyển theo.
- `scripts/jobs/wsl_job.ps1` cho Task Scheduler: retry khi WSL khởi động chậm (`HCS_E_CONNECTION_TIMEOUT`), pop-up khi thất bại hẳn. Mang theo lịch NLP 12:30 + cờ chạy khi dùng pin (ADR-0017, `scripts/configure_jobs.ps1`).
- 5 entry local của pre-commit (mypy, consistency, review-gate, pytest-fast, dashboard) → đường dẫn Linux (`.venv/bin/python`).
- Mang theo bước publish bản sao DB lên Vercel Blob sau mỗi job (ADR-0025) vào `run_job.sh`; `db_path()` không áp cho API trên Vercel (DB tải từ Blob về thư mục tạm, chỉ đọc).
- **Xong khi**: test xanh trong WSL; 2 job chạy chồng thì job sau chờ; 3 ngày log xanh liên tục; publish chạy sau cả 2 job và lỗi publish không làm hỏng job.

## H — Deploy công khai (ADR-0025)

- FastAPI chỉ đọc chạy như Vercel Python Function, đọc bản sao `threads.db` từ Vercel Blob riêng tư; dashboard và API deploy tự động từ GitHub (2 project Vercel); job vẫn chạy trên laptop.
- Các bước và điều kiện: mục "Hệ quả" của ADR-0025 (gói API tối giản → chế độ chỉ đọc → publish sau mỗi job → deploy thử preview → việc trước khi public → docs).
- **Xong khi**: bản công khai chạy trên dữ liệu publish từ laptop; Thy duyệt bản preview; `job_health` cảnh báo khi bản publish cũ. Deploy thử thất bại (gói > 500 MB, không mở được DB, cold start làm trang không tải được) → ADR mới, chuyển sang snapshot tĩnh.
- **Trạng thái (2026-10-28): live** — https://unthreaded-analytics.vercel.app, API https://unthreaded-api.vercel.app (PR #19, #20; cấu hình + 2 chỗ lệch so với ADR: `docs/claude/architecture.md` mục "Deploy"). Thy chọn công khai ngay thay cho bước duyệt preview. Còn: việc trước khi chia sẻ link rộng (bio, link CTA, giới hạn tần suất gọi API, theo dõi Usage).
- Ngay sau H: RQ-01 (ADR-0024). Repo public chính thức, giữ mọi quyền, harness `.claude/` riêng tư (ADR-0027) — mục "Repo public" bên dưới.

## G — CI (GitHub Actions) — ADR-0014

- ✅ (2026-10-05) Chạy lần đầu trên GitHub qua PR #1 (CI chỉ chạy khi mở/cập nhật PR, push vào `main` hoặc chạy tay, ADR-0019): job `web` đỏ — `LayoutProps` là kiểu Next sinh vào `.next/` (gitignored), máy sạch chưa có → sửa `67c3bf8` (`npm run typecheck` = `next typegen && tsc --noEmit`) → xanh, merge `e8d645e`.
- Job `py`: `setup-uv` → `uv sync --frozen` (bỏ torch + gói CUDA, danh sách sinh từ `uv.lock`) → ruff + `ruff format --check` → mypy → `python -m scripts.consistency.check --all` (kể cả đếm số test, quét cả file chưa track) → `pytest -m "not live and not slow"`. Job `web`: `npm ci` → lint → `npm run typecheck` (`next typegen` + `tsc --noEmit`) → build. Không data thật, không secrets.

## D0 — Sửa tính đúng của dữ liệu (chặn D và E) — ADR-0004

1. ✅ (2026-10-01) `posts.reply_role ∈ {self_continuation, author_answer, outbound}` — continuation khi `replied_to ∈ {root} ∪ {continuation trước đó}`. Số thật: 353 / 674 / 342 (suy từ đồ thị `replied_to`, không từ timestamp).
2. ✅ (2026-10-01) `full_text` = root + self_continuation + `text_attachment`. Câu trả lời cho follower giữ trong `posts` với vai `author_answer`.
   - ✅ Cùng migration: bỏ `'fixed'` khỏi CHECK `method` của `topics`/`post_topic_labels` (Thy chốt 2026-09-30) — bộ phân loại 6 nhãn không còn là thành phần sản phẩm (ADR-0001); nhãn tay + kết quả RQ-08 lưu ở `experiments/`, không vào DB sản phẩm. SQLite không sửa CHECK tại chỗ → tạo lại 2 bảng (topic sinh lại được).
3. ✅ **Verify live** `GET /{root_id}/conversation` (2026-10-01): **có** trả text + username bình luận follower → bảng `audience_replies` (username pseudonymize bằng hash có salt — GDPR) cần ADR-0007 trước; gold set dùng được câu hỏi thật.
4. Bảng `qa_pairs` (bình luận follower ↔ câu trả lời tác giả) — sau ADR-0007.
5. ✅ (2026-10-01) Bảng `embeddings(object_type, object_id, model_id, content_hash, dim, vector)` — chỉ embed lại khi hash đổi; điền `topics.centroid_embedding_json` + từ khoá c-TF-IDF + bài đại diện.
6. ✅ (2026-10-01) Chạy lại clustering, calibrate lại n_neighbors 8: 9 cụm, nhiễu 36,1%, `validity_index` 0,317; ARI so với cụm cũ: gộp 0,22, riêng phần dữ liệu 0,13, riêng phần tham số 0,38 (có tính nhiễu) — ADR-0004. RQ-00 phân tích sâu tác động.

## D — Câu hỏi nghiên cứu (`docs/rq/RQ-xx.md`, tracking JSON + git — ADR-0005)

| RQ | Câu hỏi | Ghi chú |
|---|---|---|
| RQ-01 | Cluster có ổn định không? | 10 seed, ARI/AMI cặp, bootstrap subsample, DBCV vào code. **Làm ngay sau deploy (ADR-0024):** đầu ra chọn luật bền cho câu khẳng định về topic — tỉ lệ seed mà mỗi kết luận đạt p Holm + ARI cặp seed |
| RQ-02 | HDBSCAN có hơn baseline không? | KMeans (silhouette), agglomerative, c-TF-IDF, NPMI coherence |
| RQ-03 | Model embedding nào tốt nhất cho VI/FR/EN trộn? | bge-m3 vs multilingual-e5-large vs mpnet đa ngôn ngữ; trên cluster + RQ-09 |
| RQ-04 | Mức trộn ngôn ngữ (CMI) có liên quan engagement? | `compare_groups()` (`src/analysis/significance.py`) + hiệu chỉnh Holm |
| RQ-05 | Chủ đề nào hiệu suất cao hơn? | CI, nói rõ giới hạn n≈150 |
| RQ-06 | Chủ đề dịch chuyển theo thời gian? | tỉ trọng theo tháng, drift centroid |
| RQ-07 | Follower hỏi những gì? | cluster câu hỏi follower → lỗ hổng KB (cần D0 bước 3) |
| RQ-08 | 6 nhãn cố định có học được từ embedding? | tác giả gán nhãn 150 bài + gán lại 30 bài sau 2 tuần (Cohen's κ); bậc thang 5 baseline; nested CV; bootstrap CI macro-F1; model card |
| RQ-09 | Thành phần truy xuất nào thật sự có ích? | ablation BM25/dense/RRF/rerank/chunking — Phase E |
| RQ-10 | Lọc từ khoá theo từ loại có tốt hơn danh sách stopword tay? | `underthesea.pos_tag` (giữ danh từ/động từ/tính từ) vs `src/nlp/stopwords.py` trên cùng lần gom cụm; đo từ chức năng/mảnh âm tiết/từ chung chung trong top-8 (ADR-0022) |

## E — Knowledge base (`src/kb/`) — ADR-0006

- Tài liệu: `post` (root + continuation + attachment), `qa` (câu hỏi follower diễn đạt lại + câu trả lời tác giả).
- Chunking so sánh trong RQ-09: 1 chunk/unit · chunk con theo segment trả về cha (mặc định) · cửa sổ 256 token.
- Lưu trong SQLite hiện có: `kb_documents`, `kb_chunks`, FTS5 `unicode61` giữ dấu tiếng Việt; dense = numpy cosine brute-force sau interface `VectorIndex` (sqlite-vec khi dữ liệu lớn).
- Truy xuất: BM25 top50 + dense top50 → RRF → rerank `bge-reranker-v2-m3` → top-k kèm nguồn.
- Cập nhật tăng dần: `run_job.sh kb` sau ingest, embed lại theo hash, dọn chunk mồ côi, ghi `kb_builds`.
- Eval: gold set câu hỏi follower thật (loại chính cặp qa đó khỏi index lúc eval) + 30–50 câu tự soạn; recall@5/10, MRR@10, nDCG@10, bootstrap CI.
- Skill `/kb-eval` (chạy eval truy xuất, so với run trước trong registry) — tạo cùng phase này, không tạo trước khi KB tồn tại.
- API `GET /kb/search?q&k&mode&rerank`, `/kb/stats`, `/research/runs`. Dashboard `/kb`, `/research` — không hiển thị nguyên văn bình luận follower.

## F — Cổng mở chatbot + landing thương hiệu (cần 1 ADR để mở)

1. D0 xong; 100% root + cặp qa hợp lệ đã index; đã rà soát privacy.
2. ≥13/14 job hằng ngày xanh; độ trễ index < 26h.
3. Hybrid+rerank: recall@10 ≥ 0.80, nDCG@10 ≥ 0.60 (tạm, chốt sau baseline đầu); cận dưới CI > BM25-only; không regression 2 tuần.
4. Top-10 nhóm câu hỏi RQ-07 đều có tài liệu, hoặc ghi rõ là lỗ hổng.
5. KB explorer chạy thật; có data card + model card; RQ-01/03/09 đã viết.
6. Có bản nháp plan đánh giá answer faithfulness (câu trả lời chatbot trung thực với nguồn).

## Repo public (ADR-0027, ADR-0028)

Thy public repo hiện tại thay cho kế hoạch curate sang repo mới (2026-10-30). Đã làm: `LICENSE` giữ mọi quyền,
`tools/ui-ux-pro-max/LICENSE` (MIT gốc), `.claude/` gitignored + kho riêng; soát nội dung nhạy cảm, bỏ `docs/archive/`,
quy tắc làm việc riêng sang `CLAUDE.local.md`; viết lại lịch sử (bỏ `.claude/`, `docs/research/`, `docs/archive/`
khỏi mọi commit, force push 2026-10-30) + ticket GitHub Support xoá ref PR cũ. Còn: cập nhật mã commit trong docs theo
bảng đổi mã (ADR-0028); kiểm license asset khác khi thêm mới.
