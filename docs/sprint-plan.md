# Sprint Plan — Giai đoạn 1-3 (Redesign v2: 6-index metrics + ContentUnit, Carousel hoãn lại)

> Cập nhật: 2026-08-30 — redesign lần 2 sau khi user chỉ ra vấn đề phương pháp luận trong `virality_index` v1 (hằng số không evidence, trộn intrinsic/explanatory variables). Chi tiết đầy đủ + lý do từng quyết định tại `docs/claude/data-model.md` ("Metric Architecture", "NLP Pipeline") và `docs/claude/architecture.md` (decisions log 2026-08-30).
> Phạm vi: Data + NLP Foundation (6 index tách biệt, ContentUnit, velocity/longevity từ snapshot, code-switching-tolerant NLP) + Dashboard + AI Content Generation (RAG). **Giai đoạn 4 (Carousel) vẫn hoãn.**
> Nhịp độ giả định: 6-8h/ngày.
> Tổng ước tính: **~16-20 ngày** (tăng từ 13 sau redesign v2 — scope thật lớn hơn: ContentUnit reconstruction, 6 index thay vì 1 formula, snapshot-driven velocity/longevity)

## Cách dùng file này

Đánh dấu `[x]` khi xong. Có phụ thuộc thật (bước sau cần bước trước) — không nhảy bước. Hằng số heuristic (`grace_hours=12`, `half_life_hours=48`...) đã ghi rõ là **hypothesis ban đầu, chưa calibrate** — không sửa thành "đúng" khi chưa có data thật để kiểm chứng.

## Đã hoãn

- **Giai đoạn 4 — Carousel Generation** (đo tọa độ 28 slide, thứ tự slide chưa rõ)
- **`MomentumIndex`, maturation curve/`Projected72h`** — cần data tích luỹ hàng tháng (~2 post/ngày), không scope vào sprint này
- **Multimodal (vision/ASR ảnh/video)** — V2

---

## Bước 0 — Verify API fields live ✅ ĐÃ XONG (2026-08-30)

`root_post`, `replied_to`, `is_reply`, `is_reply_owned_by_me` **xác nhận thật** (test `limit=20` trên `/replies`, 9-10/20 item có data). `text_attachment`, `is_ghost_post`, `poll_attachment`, `gif_attachment`, `location_id`, `enable_reply_approvals` — không lỗi nhưng 0/100 item có data (nhiều khả năng tác giả chưa dùng, không kết luận field sai). Metric "shares" không tồn tại (verify từ trước). Chi tiết đầy đủ tại `docs/claude/data-model.md` bảng "Fields cho thread reconstruction".

---

## Bước 1 — `src/models/` + `src/db/` schema

- [ ] `src/models/content_unit.py` — `ContentUnit` dataclass (root, continuations, text_attachment, full_text, media)
- [ ] `src/models/insight_snapshot.py` — `InsightSnapshot` dataclass (post_id, fetched_at, views, likes, replies, reposts, quotes)
- [ ] `src/db/schema.py` — SQLite: `posts`, `content_units`, `insights_snapshots`, `topics`, `post_topic_labels`
- [ ] `data/raw/` — thư mục archive JSON vĩnh viễn (khác `data/cache/` TTL 6h)

**Xong khi**: schema tạo được, test insert/query cơ bản pass.

## Bước 2 — `src/processing/`

- [ ] `thread_reconstruction.py` — build `ContentUnit` từ `ThreadsPost` (root) + `get_replies()` (continuations, lọc `is_reply_owned_by_me=True`, nối theo `replied_to`/`root_post`)
- [ ] `text.py` — `raw_text` (bất biến) + `normalize_text()` (CHỈ whitespace + URL, KHÔNG strip emoji/hashtag)

**Xong khi**: chạy trên data thật, tạo được vài `ContentUnit` có `continuations` không rỗng (post nào tác giả từng tự reply tiếp).

## Bước 3 — `src/nlp/language.py` + `embeddings.py`

- [ ] `language.py` — `lingua-py`, `LanguageInfo` (primary_language, detected_languages, confidence, language_mix_score liên tục)
- [ ] `embeddings.py` — sentence-transformers multilingual (`bge-m3`/`multilingual-e5-large`) trên `ContentUnit.full_text`

**Xong khi**: chạy trên vài `ContentUnit` thật, `language_mix_score` phân biệt được câu thuần Việt (thấp) vs câu code-switch rõ (cao), không false-positive với từ mượn tech.

## Bước 4 — Base indexes (`src/analysis/`)

- [ ] **Sửa** `PostInsights.engagement_rate` (`src/api/models.py`) — thêm `quotes` vào tử số (lỗi cũ thiếu), cập nhật `tests/api/test_models.py`
- [ ] `popularity.py`, `virality.py` (chỉ nhận `insights`), `conversation.py` — theo công thức tại `data-model.md`

**Xong khi**: test pass, verify trên 140 post thật, ruff/mypy sạch.

## Bước 5 — Snapshot job + `velocity.py`

- [ ] `insights_snapshots` fetch job (chạy tay hoặc cron) — bắt đầu tích luỹ từ đây, KHÔNG hồi cứu được cho 140 post cũ
- [ ] `velocity.py` — `view_velocity`, `amplification_velocity` giữa 2 snapshot

**Xong khi**: job chạy 2 lần cách nhau vài giờ, velocity tính được cho ít nhất 1 post thật.

## Bước 6 — `longevity.py` + `freshness.py`

- [ ] `longevity.py` — `late_engagement_share` (cần snapshot phủ 24h+72h, chỉ áp dụng post mới)
- [ ] `freshness.py` — `freshness_weight(age_hours, grace_hours=12, half_life_hours=48)` — docstring ghi rõ "initial hypothesis, chưa calibrate"

**Xong khi**: test pass các edge case (age=0, age=grace_hours, age rất lớn).

## Bước 7 — `src/nlp/topics.py` + `topic_affinity.py`

- [ ] UMAP + HDBSCAN trên embedding (từ Bước 3) + LLM (Claude) labeling cluster — tên/mô tả **tiếng Anh**
- [ ] `topic_affinity_score(topic_id, window_days)` — report_window 7d/14d/30d/90d, ưu tiên 30d/90d

**Xong khi**: có cluster + tên tiếng Anh hợp lý, so sánh ARI với 6 fixed category.

## Bước 8 — `timing.py`

- [ ] `audience_activity_profile()` — group velocity theo publish_hour + hour_since_publish
- [ ] Verify live `get_follower_demographics(breakdown="country")` (đã build, chưa từng gọi thật) — đối chiếu hypothesis timezone VN/Pháp

**Xong khi**: có empirical evidence (không chỉ giả định) cho pattern giờ audience active.

## Bước 9 — `src/main.py` (FastAPI) → **Giai đoạn 1 hoàn tất**

- [ ] Expose endpoint đọc từ SQLite (KHÔNG chạy lại pipeline embedding/clustering mỗi request)

## Bước 10 — RAG (`src/generation/rag.py`)

- [ ] Retrieval (vector store từ Bước 3) + Claude generation, grounded trên content thật

## Bước 11-13 — Dashboard (Next.js)

- [ ] Setup + component library
- [ ] Dashboard/Analytics (trend theo report_window, heatmap timing 2 timezone)
- [ ] Topic Explorer (3D scatter Plotly) + Content Library + Settings — **toàn bộ copy tiếng Anh**

## Bước 14-15 — Content Generation (RAG-assisted)

- [ ] Đọc `Content/Scripts/*.docx`, prompt + RAG context động
- [ ] Trang Generate Content + vòng lặp calibrate giọng văn ⚠️ rủi ro lịch cao nhất

## Bước 16 — Buffer + Polish

- [ ] Mobile responsive, scroll animation, bug fix → **Giai đoạn 1-3 hoàn tất**

---

## Nếu còn thời gian

Giai đoạn 4 — Carousel Generation (~25-40h).
