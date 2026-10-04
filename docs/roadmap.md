# Roadmap — Unthreaded

> Nguồn "làm gì, theo thứ tự nào". Trạng thái hiện tại xem `docs/status.md`; lý do của từng quyết định xem `docs/decisions/`.
> Scope đã chốt tại ADR-0001: **NLP sâu → knowledge base → (sau cổng F) chatbot + landing thương hiệu.** Không generation giọng văn, không carousel.
> Plan gốc có giải thích đầy đủ: phiên 2026-09-30 (plan "LESS IS MORE"). Sprint plan cũ: `docs/archive/sprint-plan-v3-2026-09-02.md`.

Thứ tự: `0 → A1 → B → A2–A6 → C → G → D0 → (D ∥ E) → F`. Mỗi phase kết thúc bằng checkpoint commit + cập nhật `docs/status.md`.

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
- `connect()`: WAL + `busy_timeout=30000` + retry khi "database is locked".
- `scripts/jobs/run_job.sh {snapshot|nlp|kb}` bọc `flock`; job NLP gộp thành `src/pipeline/recluster.py`. Xoá cầu nối `clustering_export.py`/`cluster_wsl.py`/`clustering_import.py` + `nlp_cluster_job.py` (launcher Windows của ADR-0013). Giữ nguyên hành vi danh tính cụm của ADR-0018 (ghép thành viên + ngữ nghĩa, bản neo, `retired`) — test `tests/pipeline/test_clustering_import.py` chuyển theo.
- `scripts/jobs/wsl_job.ps1` cho Task Scheduler: retry khi WSL khởi động chậm (`HCS_E_CONNECTION_TIMEOUT`), pop-up khi thất bại hẳn. Mang theo lịch NLP 12:30 + cờ chạy khi dùng pin (ADR-0017, `scripts/configure_jobs.ps1`).
- 5 entry local của pre-commit (mypy, consistency, review-gate, pytest-fast, dashboard) → đường dẫn Linux (`.venv/bin/python`).
- **Xong khi**: test xanh trong WSL; 2 job chạy chồng thì job sau chờ; 3 ngày log xanh liên tục.

## G — CI (GitHub Actions) — ADR-0014

- ✅ (2026-10-01) `.github/workflows/ci.yml` viết xong; mô phỏng job `py` trong WSL2. **Xong khi**: lần chạy đầu trên GitHub (sau push) xanh.
- Job `py`: `setup-uv` → `uv sync --frozen` (bỏ torch + gói CUDA, danh sách sinh từ `uv.lock`) → ruff + `ruff format --check` → mypy → `python -m scripts.consistency.check --all` (kể cả đếm số test, quét cả file chưa track) → `pytest -m "not live and not slow"`. Job `web`: `npm ci` → lint → `tsc --noEmit` → build. Không data thật, không secrets.

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
| RQ-01 | Cluster có ổn định không? | 10 seed, ARI/AMI cặp, bootstrap subsample, DBCV vào code |
| RQ-02 | HDBSCAN có hơn baseline không? | KMeans (silhouette), agglomerative, c-TF-IDF, NPMI coherence |
| RQ-03 | Model embedding nào tốt nhất cho VI/FR/EN trộn? | bge-m3 vs multilingual-e5-large vs mpnet đa ngôn ngữ; trên cluster + RQ-09 |
| RQ-04 | Mức trộn ngôn ngữ (CMI) có liên quan engagement? | `compare_groups()` (`src/analysis/significance.py`) + hiệu chỉnh Holm |
| RQ-05 | Chủ đề nào hiệu suất cao hơn? | CI, nói rõ giới hạn n≈150 |
| RQ-06 | Chủ đề dịch chuyển theo thời gian? | tỉ trọng theo tháng, drift centroid |
| RQ-07 | Follower hỏi những gì? | cluster câu hỏi follower → lỗ hổng KB (cần D0 bước 3) |
| RQ-08 | 6 nhãn cố định có học được từ embedding? | tác giả gán nhãn 150 bài + gán lại 30 bài sau 2 tuần (Cohen's κ); bậc thang 5 baseline; nested CV; bootstrap CI macro-F1; model card |
| RQ-09 | Thành phần truy xuất nào thật sự có ích? | ablation BM25/dense/RRF/rerank/chunking — Phase E |

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

## Trước khi public repo

Không copy history. `git filter-repo` trên bản clone mới: loại `docs/research/`, `src/carousel/` <!-- consistency: allow dead-path -->, trailer ở `31adcbc`/`3eceabe`. Kiểm tra license skill vendored (`tools/`) và mọi asset.
