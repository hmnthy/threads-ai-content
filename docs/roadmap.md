# Roadmap — threads-ai-content

> Nguồn "làm gì, theo thứ tự nào". Trạng thái hiện tại xem `docs/status.md`; lý do của từng quyết định xem `docs/decisions/`.
> Scope đã chốt tại ADR-0001: **NLP sâu → knowledge base → (sau cổng F) chatbot + landing thương hiệu.** Không generation giọng văn, không carousel.
> Plan gốc có giải thích đầy đủ: phiên 2026-09-30 (plan "LESS IS MORE"). Sprint plan cũ: `docs/archive/sprint-plan-v3-2026-09-02.md`.

Thứ tự: `0 → A1 → B → A2–A6 → C → G → D0 → (D ∥ E) → F`. Mỗi phase kết thúc bằng checkpoint commit + cập nhật `docs/status.md`.

## Đã xong (nhánh `chore/restructure`)

- **0** Dọn worktree cũ, `.gitattributes`, `.gitignore`, `.worktreeinclude`
- **A1** `.claude/settings.json` + hooks (status, chặn trailer, ruff-on-edit, pop-up Windows)
- **B** Gỡ generation/carousel (ADR-0001)
- **A2–A6** Tài liệu gọn (CLAUDE.md, status, roadmap, ADR), `.claude/rules/`, subagents, skills, `.mcp.json`

## C — Chuyển toàn bộ Python sang WSL2 (ADR-0002)

- Clone mới vào ext4 `~/code/threads-ai-content`, mở bằng VS Code Remote-WSL; copy `.env`, `data/threads.db`, `content/`, `~/.claude` (memory dự án).
- `pyproject.toml`: index torch CPU. Bỏ venv `~/threads-clustering-env`.
- `src/config.py::db_path()` — `$THREADS_DB_PATH` hoặc DB của checkout chính (qua `git --git-common-dir`) → mọi worktree dùng chung 1 DB. Thay `DEFAULT_DB_PATH` (`src/db/schema.py`).
- `connect()`: WAL + `busy_timeout=30000` + retry khi "database is locked".
- `scripts/jobs/run_job.sh {snapshot|nlp|kb}` bọc `flock`; job NLP gộp thành `src/pipeline/recluster.py`. Xoá cầu nối `clustering_export.py`/`cluster_wsl.py`/`clustering_import.py` + 2 file `.bat`.
- `scripts/jobs/wsl_job.ps1` cho Task Scheduler: retry khi WSL khởi động chậm (`HCS_E_CONNECTION_TIMEOUT`), pop-up khi thất bại hẳn.
- pre-commit mypy entry → đường dẫn Linux.
- **Xong khi**: test xanh trong WSL; 2 job chạy chồng thì job sau chờ; 3 ngày log xanh liên tục.

## G — CI (GitHub Actions)

- Job `py`: `setup-uv` → `uv sync --frozen` → ruff → mypy → `pytest -m "not live and not slow"`. Job `web`: `npm ci` → lint → `tsc --noEmit` → build. Không data thật, không secrets.

## D0 — Sửa tính đúng của dữ liệu (chặn D và E) — ADR-0004

1. `posts.reply_role ∈ {root, self_continuation, author_answer, outbound}` — continuation khi `replied_to ∈ {root} ∪ {continuation trước đó}`. Đối chiếu số thật 362/664/342.
2. `full_text` = root + self_continuation + `text_attachment`. Câu trả lời cho follower lưu riêng.
3. **Verify live** `GET /{root_id}/conversation`: Standard Access có trả text bình luận follower không. Có → bảng `audience_replies` (username pseudonymize bằng hash có salt — GDPR), ADR-0007. Không → gold set dùng câu hỏi tự soạn.
4. Bảng `qa_pairs` (bình luận follower ↔ câu trả lời tác giả).
5. Bảng `embeddings(object_type, object_id, model_id, content_hash, vector)` — chỉ embed lại khi hash đổi; điền `topics.centroid_embedding_json`.
6. Chạy lại clustering; RQ-00 đo tác động (ARI cũ vs mới).

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
- API `GET /kb/search?q&k&mode&rerank`, `/kb/stats`, `/research/runs`. Dashboard `/kb`, `/research` — không hiển thị nguyên văn bình luận follower.

## F — Cổng mở chatbot + landing thương hiệu (cần 1 ADR để mở)

1. D0 xong; 100% root + cặp qa hợp lệ đã index; đã rà soát privacy.
2. ≥13/14 job hằng ngày xanh; độ trễ index < 26h.
3. Hybrid+rerank: recall@10 ≥ 0.80, nDCG@10 ≥ 0.60 (tạm, chốt sau baseline đầu); cận dưới CI > BM25-only; không regression 2 tuần.
4. Top-10 nhóm câu hỏi RQ-07 đều có tài liệu, hoặc ghi rõ là lỗ hổng.
5. KB explorer chạy thật; có data card + model card; RQ-01/03/09 đã viết.
6. Có bản nháp plan đánh giá answer faithfulness (câu trả lời chatbot trung thực với nguồn).

## Trước khi public repo

Không copy history. `git filter-repo` trên bản clone mới: loại `docs/research/`, `src/carousel/`, trailer ở `31adcbc`/`3eceabe`. Kiểm tra license skill vendored (`tools/`) và mọi asset.
