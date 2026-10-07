---
paths:
  - "src/nlp/**"
  - "src/kb/**"
  - "src/analysis/**"
  - "experiments/**"
  - "docs/rq/**"
---

# NLP, phân tích, nghiên cứu

- ML thật (embedding, UMAP, HDBSCAN, reranker) **chỉ chạy trong WSL2** — Smart App Control chặn DLL trên Windows, kể cả khi thỉnh thoảng có vẻ chạy được.
- Embedding: `BAAI/bge-m3` trên `ContentUnit.full_text`, không tách từ, không xoá emoji/hashtag/stop word trước embedding.
- Claude **chỉ** đặt tên cluster (`label_cluster_with_claude`). Không classify, không embed, không tham gia NLP core.
- Mỗi thí nghiệm: seed cố định, ghi config + metric (sau ADR-0005: 1 dòng vào `experiments/registry.jsonl`). Không báo kết quả của 1 lần chạy đơn lẻ khi có thể chạy nhiều seed.
- Kết quả thống kê luôn đủ tầng: n → median/IQR → effect size (Cliff's δ) → CI (bootstrap) → mới được diễn giải. So sánh nhiều nhóm → hiệu chỉnh (Holm). Dùng lại `compare_groups()` (`src/analysis/significance.py`), không viết engine mới.
- So 2 lần gom cụm (ARI) khác nhau ở > 1 yếu tố (dữ liệu, tham số, seed) → ghi rõ là hiệu ứng gộp, hoặc chạy thêm 1 lần chỉ đổi 1 yếu tố để tách. Luôn ghi tên hàm cạnh số DBCV (`validity_index` hay `relative_validity_` — khác thang).
- n≈150 root post: ghi rõ giới hạn sức mạnh thống kê trong mọi RQ. Không cherry-pick: nếu CI trùng nhau thì kết luận "chưa phân biệt được".
- Số liệu trong ADR/doc ghi "sinh lại bằng script X" → script X in ra **từng** con số đó (kể cả khoảng ngày / giai đoạn được trích); so sánh nhóm nêu trong ADR kèm δ + CI qua `compare_groups()`, không chỉ median; ≥ 2 phép so trên cùng dữ liệu → ghi p Holm; câu giải thích cơ chế của 1 tương quan ghi rõ "giả thuyết" — cảnh giác tương quan giả khi 2 đại lượng chung mẫu số `views` (bài học ADR-0012).
- Eval truy xuất / classifier: tách tập trước khi làm bất cứ gì phụ thuộc nhãn; loại chính cặp qa đang hỏi khỏi index khi eval (chống leakage).
- Text bình luận của follower là dữ liệu cá nhân: pseudonymize username, không đưa nguyên văn lên dashboard/README/RQ public.
- Methodology log chi tiết + các thực nghiệm đã chốt: `docs/claude/data-model.md`. Nguồn/paper: `docs/research/README.md` (private).
