# Audit dữ liệu Topics (Việc 2 của brief Topics)

> Người đọc: Claude Design và Claude Code. Viết bởi Claude Code, 2026-10-09, trên bản sao DB của thư mục chính
> (lần gom cụm `cluster_runs.id = 9`, `run_at` 2026-10-09T10:30:47Z; snapshot mới nhất 2026-10-09T15:18:57Z).
> Theo brief (`docs/design/topics-brief-for-claude-code.md` Việc 2): mỗi mục gồm câu SQL, **kết luận cấu trúc** (điều
> code bảo đảm hoặc không bảo đảm) và số đếm **chỉ để minh hoạ** — số đổi theo cron, cấu trúc thì không. Chỉ query,
> không sửa code.

## 1. Chuỗi mẫu số

```sql
SELECT COUNT(*) FROM posts WHERE is_reply = 0;                               -- bài gốc
SELECT COUNT(*) FROM content_units;                                          -- content unit
SELECT COUNT(*) FROM content_units WHERE trim(coalesce(full_text,'')) <> ''; -- unit có chữ
-- unit trong lần gom cụm: khoá của cluster_runs.labels_json (lần mới nhất)
-- đo được: snapshot mới nhất của bài có views > 0 (split_measurable, ADR-0011)
```

| Bước | Điều kiện | Code | Số minh hoạ |
|---|---|---|---|
| Bài gốc | `posts.is_reply = 0` | `list_root_posts` (`src/db/schema.py:387`) | 152 |
| Content unit | 1 unit / 1 bài gốc (id unit = id bài gốc) | `rebuild_content_units` (`src/pipeline/ingest.py:90`) | 152 |
| Unit có chữ | `full_text` khác rỗng sau `strip()` | `src/pipeline/clustering_export.py:71` | 146 |
| Unit trong lần gom cụm (có embedding, có toạ độ UMAP) | = unit có chữ tại lúc export | khoá `labels_json`; `embeddings` cùng `model_id`; `umap_x` | 146 |
| Unit đo được | snapshot mới nhất `views > 0` | `split_measurable` (`src/analysis/stats.py`) | 146 trong lần gom cụm; 146 bài gốc |

**Kết luận cấu trúc:**
- Bài gốc ↔ content unit là 1:1.
- Bước "có chữ" loại bài theo **văn bản**; bước "đo được" loại theo **snapshot**. Hai bước độc lập trong code.
- Tập unit trong lần gom cụm cố định tại thời điểm export (12:30 Paris). Bài đăng sau đó chỉ vào lần gom cụm hôm sau.
  Còn tập "đo được" đổi theo mỗi snapshot 4 giờ.
- **Hệ quả cho Việc 3:** phép so topic (ADR-0023) có mẫu số là *unit trong lần gom cụm và đo được*. Bảng top và
  Overview có mẫu số là *bài gốc đo được*. Hai tập này **không được code bảo đảm trùng nhau** (xem mục 2). Vì vậy
  dòng "kênh" của bảng so sánh topic được định nghĩa là "mọi unit trong lần gom cụm", không phải số của
  `/analytics/overview`.

## 2. Hai tập loại có trùng nhau không

```sql
SELECT p.media_type, COUNT(*) FROM content_units u JOIN posts p ON p.id = u.id
WHERE trim(coalesce(u.full_text,'')) = '' GROUP BY 1;
```

Hôm nay hai tập **trùng từng id**: 6 unit không có chữ chính là 6 bài có views = 0. Cả 6 có `media_type =
REPOST_FACADE`: bài đăng lại của người khác, không có chữ của tác giả, và Threads không trả views cho bài đó.

**Kết luận cấu trúc:** sự trùng này có lý do (repost không có chữ, cũng không có views), nhưng code **không bảo
đảm** nó. Một bài có chữ vẫn có thể có views = 0, ví dụ bài vừa đăng trước lần snapshot đầu. Một bài chỉ có ảnh
không caption vẫn có views. Quy tắc hiện có vẫn đúng: UI giữ hai dòng loại riêng và chỉ gộp khi kiểm từng id
(`UI-0011-two-exclusions`).

> Ghi chú cho ADR-0023, mục Dữ liệu: câu "hai số đếm trùng nhau là ngẫu nhiên" nói đúng một nửa. Hôm nay hai **tập**
> trùng nhau vì cùng 6 bài repost; code không bảo đảm điều này. ADR đã `Accepted` nên không sửa. Ghi chú này là bản
> chính xác hoá.

## 3. Trường của topic

```sql
SELECT COUNT(*) FROM topics WHERE <cột> IS NULL OR <cột> = '' OR <cột> = '[]';
```

| Trường | Hôm nay | Khi nào có thể null hoặc rỗng (theo code) |
|---|---|---|
| `keywords_json` | 9/9 có, 8 từ khoá mỗi topic | `[]` khi lần gom cụm chưa ghi hồ sơ (`TopicOut.keywords`, `src/main.py:183`) |
| `representative_ids_json` | 9/9 có, 3 bài | `[]` khi cụm không có embedding. API bỏ id không còn content unit (`_representatives`) |
| `centroid_embedding_json` | 9/9 có | null khi file kết quả không có embedding (`clustering_import.py`, nhánh `embeddings is None`) |
| `labeled_at`, `label_model`, `label_prompt_version` | 9/9 có (đặt tên 2026-10-05, `claude-sonnet-5-5`, prompt v2) | null với topic từ trước ADR-0018 chưa được đặt lại tên (`src/db/schema.py:331`) |
| `label_anchor_json` | 9/9 có | null cùng điều kiện trên |
| `description_en` | 9/9 có | cột cho phép null |

**Kết luận cấu trúc:** UI phải xử lý được `keywords = []`, `representatives = []` và `labeled_at = null`, dù hôm nay
không trường nào rỗng.

## 4. Mẫu số của nhiễu

`cluster_runs.noise_ratio` = số unit nhãn −1 ÷ `n_units` (mọi unit trong lần gom cụm, gồm cả nhiễu).
`clustering_import.py` tính `n_noise / len(ids)`. Kiểm hôm nay: 60 / 146 = 0.411, khớp cột.

**Kết luận cấu trúc:** mẫu số của tỉ lệ nhiễu là unit có chữ trong lần gom cụm, không phải bài gốc và không phải
bài đo được. Số unit nhiễu không lưu thành cột riêng; `/pipeline/summary` đếm lại từ `labels_json` (`n_noise`).

## 5. Các cột của `cluster_runs`

Cột: `id, run_at, model_id, params_json, n_units, n_clusters, noise_ratio, dbcv, dbcv_relative, ari_vs_previous,
ari_clustered_only, transitions_json, labels_json, topic_events_json`.

- `params_json` hôm nay: `cluster_selection_method = leaf`, `hdbscan_min_cluster_size = 4`, `umap_n_components = 3`,
  `umap_n_neighbors = 8`, `umap_random_state = 42`, `keyword_segmenter = underthesea==9.5.0; …` (ADR-0022).
- `dbcv` = `hdbscan.validity.validity_index` (DBCV đầy đủ); `dbcv_relative` = `relative_validity_` (xấp xỉ, khác
  thang). Tên hàm không lưu thành cột: nó cố định trong code (`UI-0004-dbcv-named`).
- `ari_vs_previous` coi nhiễu là một nhóm; `ari_clustered_only` chỉ tính trên bài có cụm ở cả hai lần.
  `transitions_json` đếm cụm→cụm / cụm→nhiễu / nhiễu→cụm / bài mới. Lần chạy 9: ARI = 1.0, 0 bài chuyển.
- `topic_events_json` chỉ có từ ADR-0018: 5/8 lần chạy có. Lần chạy 9: 9/9 topic `kept`.
- `id` có thể nhảy số (hôm nay 2…9, thiếu 1). `id` chỉ dùng để nối dữ liệu, không dùng để đếm số lần chạy.

**Kết luận cấu trúc (khớp mục "Chỗ lệch" của brief):** brief gọi `n_input`, `n_noise`, `validity_fn`. Tên thật là
`n_units`; `n_noise` suy từ `labels_json`; `validity_fn` là hằng trong code, không phải cột.

## 6. `centroid_similarity`

```sql
SELECT COUNT(*), SUM(confidence IS NULL), MIN(confidence), MAX(confidence)
FROM post_topic_labels WHERE method = 'cluster';
```

Cosine (độ tương đồng góc) giữa embedding của bài và tâm cụm, lưu ở `post_topic_labels.confidence`. Hôm nay có cho
86/86 thành viên, miền 0.65–0.89. Tập thành viên đúng bằng tập unit có nhãn ≠ −1 trong `labels_json`.

**Kết luận cấu trúc:** chỉ thành viên của cụm mới có giá trị (bài nhiễu không có dòng `post_topic_labels`). Giá trị
null khi lần gom cụm không có embedding. Đây là độ gần tâm, không phải xác suất thuộc cụm, nên UI không được gọi là
"confidence" hay "probability".

## 7. Ngưỡng mẫu nhỏ

Đã chốt 2026-10-06: một ngưỡng duy nhất `MIN_N_PER_BUCKET = 5` (`UI-L20260903-small-n-flag`). Hôm nay chỉ `topic_2`
(n = 4 đo được) dưới ngưỡng. Theo ADR-0023, topic đó vẫn có p trong họ Holm nhưng không có câu kết luận.

## 8. Cửa sổ Overview

`account_daily_views` từ 2024-09-02 tới 2026-10-07 (764 ngày; dữ liệu theo ngày của Meta trễ khoảng 1–2 ngày).
Cửa sổ mặc định = 30 ngày cuối của chuỗi này, hoặc toàn bộ nếu chuỗi ngắn hơn (`TimelineBrush.tsx:48-52`). Bài
thuộc cửa sổ khi `timestamp[:10]` nằm trong [start, end] (`list_root_posts_in_range`, `src/db/schema.py:394`).

**Kết luận cấu trúc:** cửa sổ cắt theo ngày cuối của **daily views**, không theo ngày hôm nay. Bài đăng sau ngày
cuối đó chưa vào cửa sổ mặc định cho tới khi Meta trả ngày mới.
