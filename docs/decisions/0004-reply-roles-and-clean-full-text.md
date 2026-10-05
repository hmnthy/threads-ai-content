# ADR-0004: Phân vai reply, `full_text` sạch, lưu embedding và hồ sơ cụm

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-01
- **Người quyết**: Thy (phạm vi "D0 lõi + gom cụm lại", quy tắc phân vai, tham số gom cụm mới), Claude (thiết kế, đo đạc)

## Bối cảnh

`/me/replies` chỉ trả reply của chính chủ tài khoản, nhưng `thread_reconstruction.py` gộp **mọi** reply của tác giả dưới 1 bài vào `full_text` — kể cả câu trả lời cho bình luận follower. Ví dụ thật (bài "rau muống", 2026-08-18): 2 đoạn viết tiếp + 6 câu trả lời follower bị dán chung.

Hệ quả đo được:
- Trung bình 6,84 "continuation"/bài (thật: 2,35).
- Cụm topic học cả chuyện trò với follower — mô tả cụm do LLM viết lộ ra "Posts and comment replies…".
- CMI tính trên văn bản lẫn.
- Embedding tính xong rồi bỏ; số cụm/nhiễu/DBCV chỉ in ra log.

## Quyết định

1. **Vai reply** (`posts.reply_role`): reply của tác giả là `self_continuation` khi đi ngược `replied_to` qua các reply `self_continuation` (cùng root) tới được root — tức `replied_to ∈ {root} ∪ {các continuation}`.
   - Mọi reply khác dưới bài của tác giả là `author_answer`: reply vào bình luận follower, vào câu trả lời follower của chính tác giả, hoặc có `replied_to` rỗng (bình luận gốc đã xoá/ẩn).
   - Reply trên bài người khác là `outbound`.
   - Quan hệ chỉ suy từ đồ thị `replied_to`, **không** từ timestamp: composer nhiều phần cho timestamp trùng giây, thậm chí con sớm hơn cha (đo: 57 reply trùng giờ cha, 12 reply sớm hơn cha).
   - Số đo 2026-10-01: **353 / 674 / 342**. Quy tắc lỏng "reply vào bất kỳ bài nào của tác giả" cho 362/664 (đo 2026-09-30 trên 1.368 reply; lần đo chặt có thêm 1 reply mới, tổng 1.369) — khác 9 reply viết tiếp dưới câu trả lời follower; Thy chọn quy tắc chặt.
2. **`full_text`** = root + `self_continuation` (theo thứ tự đọc của cây thread) + `text_attachment`.
3. **Lưu embedding** vào bảng `embeddings` (`object_type`, `object_id`, `model_id`, `content_hash`, `dim`, `vector`) trong cùng SQLite (ADR-0010). Chỉ embed lại khi `content_hash` đổi.
4. **Mỗi lần gom cụm ghi 1 dòng `cluster_runs`**:
   - tham số, số cụm, tỉ lệ nhiễu;
   - **2 thước đo DBCV ghi rõ tên hàm**: `validity_index` (DBCV đầy đủ) và `relative_validity_` (xấp xỉ, thước đo lúc calibrate 2026-09-03) — khác thang, không so chéo;
   - **ARI 2 cách**: có tính nhiễu, và chỉ trên bài có cụm ở cả 2 lần;
   - bảng chuyển cụm ↔ nhiễu;
   - nhãn từng bài.
5. **Hồ sơ cụm**:
   - từ khoá **c-TF-IDF**: âm tiết + bigram; nhiễu là lớp nền của IDF; loại từ có mặt ở ≥ 80% số cụm;
   - **3 bài gần tâm cụm nhất** (cosine trên embedding);
   - cosine tới tâm cụm lưu ở `post_topic_labels.confidence`, API trả với tên `centroid_similarity`;
   - Claude đặt tên dựa trên bài gần tâm nhất. Đặt tên xong hết mới ghi, trong 1 transaction.
6. **Tham số gom cụm calibrate lại** trên `full_text` sạch: `n_neighbors` 10 → **8** (giữ leaf, `min_cluster_size` 4). Thy chọn sau sweep 24 tổ hợp × 3 seed.
7. Bỏ `'fixed'` khỏi CHECK `method` của `topics`/`post_topic_labels` (Thy chốt 2026-09-30). Migration chạy trong 1 transaction tường minh và tự phục hồi DB bị dừng giữa chừng.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Quy tắc lỏng (362/664) | Đơn giản | 9 đoạn trả lời follower vẫn dán vào bài | Thy chọn quy tắc chặt |
| Duyệt theo timestamp | Dễ viết | Sai 67 reply do timestamp trùng/ngược (bản cài đặt đầu tiên, code-reviewer phát hiện trước commit) | Thay bằng duyệt đồ thị |
| Giữ tham số cũ (n_neighbors 10) | So được với lần trước | Nhiễu 45–50% trên dữ liệu sạch | Sweep lại |
| Ứng viên mcs 5 / nn 8 (7 cụm) | Chỉ số cao nhất (`relative_validity_` 0,291, `validity_index` 0,398, nhiễu 32%) | 1 cụm tạp 31 bài gộp học/việc/tiếng Pháp | Thy chọn 9 cụm rõ nghĩa hơn |
| Ứng viên mcs 3 / nn 5 (13 cụm) | Chi tiết nhất | Nhiễu 40%, có cụm 3 bài | Quá nhỏ để so sánh thống kê |

## Hệ quả

- **Kết quả gom cụm 2026-10-01** (n = 144 bài có chữ; 1 lần chạy seed 42 — biến thiên giữa seed thuộc RQ-01):
  - **9 cụm** (sweep: 8–9 qua 3 seed);
  - nhiễu **36,1%**;
  - `validity_index` **0,317**;
  - `relative_validity_` 0,008 — thước đo này dao động mạnh giữa seed (median 0,046 khi sweep), không dùng làm ngưỡng.
- **So với cụm trước ADR-0004** (bản sao lưu DB), tách 2 thay đổi bằng 1 lần chạy chỉ đổi 1 yếu tố (cùng embedding, seed 42, n = 144):

  | So sánh | ARI có tính nhiễu | ARI chỉ trên bài có cụm ở cả 2 lần | Chuyển chính |
  |---|---|---|---|
  | Chỉ đổi dữ liệu (văn bản cũ → sạch, nn 10) | 0,13 | 0,73 | 49 bài cụm → nhiễu |
  | Chỉ đổi tham số (nn 10 → 8, văn bản sạch) | 0,38 | 0,91 | 29 bài nhiễu → cụm |
  | Gộp (đang dùng) | 0,22 | 0,78 | 34 cụm → nhiễu, 15 nhiễu → cụm |

  Đọc: làm sạch dữ liệu thay đổi cấu trúc thật (nhiều bài vốn chỉ "dính" vào cụm nhờ câu trả lời follower); đổi tham số chủ yếu kéo bài nhiễu về cụm, giữ gần nguyên phần lõi. ARI chỉ-trên-bài-có-cụm là số đo có điều kiện (phần lõi sống sót qua cả 2 lần) nên thiên cao — không đọc như độ ổn định chung. 1 seed; biến thiên giữa seed thuộc RQ-01.
- **Verify live `/{root_id}/conversation`** (2026-10-01, chỉ đọc, 1 bài): trả **cả bình luận follower có `text` và `username`** (8/8). Knowledge base có thể dùng câu hỏi thật làm gold set — nhưng lưu dữ liệu follower cần ADR-0007 (privacy, pseudonymize). Chưa lưu gì.
- `is_author_reply_event` có nghĩa trở lại (= vai `author_answer`). `unique_repliers` / `early_reply_velocity` vẫn = 0 tới ADR-0007.
- **Job cron** chạy code trong thư mục này: `create_schema()` tự migrate (idempotent); job ingest ghi vai reply mỗi lần chạy; job NLP hằng ngày dùng tham số mới và ghi `cluster_runs`.
- **Luật** (`invariants.toml`, mục ADR-0004):
  - cấm số cũ (6,84 continuation; 362/664; 286/740/741 của bản cài đặt sai);
  - cấm "comment replies";
  - cấm `method='fixed'` như lựa chọn schema;
  - cấm `/conversation` "chưa verify";
  - cấm "ARI chưa có";
  - cấm số DBCV không kèm tên hàm (`validity_index` / `relative_validity_`);
  - cấm `n_neighbors=10` như tham số hiện hành;
  - `[[stale_asset]]` cho ảnh `topics.png`.
- **Xem lại khi**:
  - nhiễu vượt 50% (mức tham số cũ đã chạm), hoặc số cụm ra ngoài khoảng 8–9 của sweep;
  - Threads đổi shape `replied_to`/`root_post`;
  - ADR-0007 cho phép lưu bình luận follower (khi đó `author_answer` ghép cặp thành `qa_pairs`).
