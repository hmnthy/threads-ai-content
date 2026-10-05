# ADR-0018: Danh tính cụm bền — ghép theo thành viên + ngữ nghĩa, đặt lại tên khi trôi, prompt v2

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-04
- **Người quyết**: Thy — chọn phương án B (ghép cụm, giữ tên khi cụm không đổi); sau thí nghiệm 10 seed + kiểm chứng tài liệu chốt: bỏ nhiễu khỏi mẫu số, lõi giữ tên khi tách, thêm bước ghép ngữ nghĩa (trừ cụm nhập), đặt lại tên theo độ trôi; duyệt toàn văn prompt v2; chưa cần khoá tên tay. Claude đề xuất, đo, code-reviewer + researcher kiểm.

## Bối cảnh

Trước ADR này, mỗi lần job NLP chạy: xoá sạch topic, ghi lại với `topic_id = cluster_N` theo vị trí nhãn HDBSCAN (thuật toán đánh số lại mỗi lần) và gọi Claude đặt tên **mọi** cụm. Hệ quả đo được:

- **Tên trôi dù nội dung không đổi**: gọi lại prompt cũ trên cùng 9 cụm (2026-10-04, 1 lần gọi/cụm) → 4/9 tên đổi ("Vietnamese Food in France" → "Food Life in France").
- **Không có danh tính qua thời gian**: `cluster_3` hôm nay ≠ hôm sau → RQ-06 (chủ đề dịch chuyển), RQ-01 (độ ổn định) không có khoá nối các lần chạy.
- **Gọi Claude thừa** (~9 lời gọi mỗi lần, phần lớn cho cụm không đổi — phương án ADR-0016 để sau).
- Prompt cũ cho tên viết hoa không thống nhất, quá chung, mất góc nhìn người Việt.

### Tài liệu (researcher kiểm bản gốc 2026-10-04)

| Nguồn | Ghép bằng | Ngưỡng + cách chọn | Khi tách |
|---|---|---|---|
| MONIC — Spiliopoulou, Ntoutsi, Theodoridis, Schult (KDD 2006; đọc bản "The MONIC Framework for Cluster Transition Detection", HDMS, Def. 3–4, Bảng 1, §5) | Tỉ lệ thành viên chung **1 chiều** (phần cụm cũ X nằm trong Y, có trọng số tuổi) | τ_match ∈ [0,5; 1] "để cụm khớp chứa ít nhất nửa thành viên"; thí nghiệm τ_match = 0,5, τ_split = 0,1. Nhiễu: ngoài phạm vi (giả định đã loại trước) | Có 1 cụm khớp ≥ τ → **sống tiếp**; còn lại mới là tách |
| Greene, Doyle & Cunningham (ASONAM 2010, §III-B, §IV-C) | Jaccard với "front" (cụm khớp gần nhất) | θ = 0,3 **chọn thực nghiệm** trên dữ liệu mô phỏng; nhiều–nhiều | Danh tính gốc sống tiếp, nhánh thành danh tính mới |
| Palla, Barabási, Vicsek (Nature 446, 2007) | Thành viên chung, ghép tham lam theo overlap giảm dần | — | Phần lớn nhất sống tiếp; cộng đồng lớn giữ danh tính dù thay gần hết thành viên |
| BERTopic `merge_models` (docs) | **Cosine embedding topic** | `min_similarity` 0,7 — mặc định thư viện, không giải thích | Khớp → giữ tên + id của mô hình gốc |
| BERTilda (Oliveira & Figueira, arXiv:2608.18101, ECML PKDD 2026 — mới đọc tóm tắt) | Kết hợp tương đồng ngữ nghĩa + dòng tài liệu | — | Phân loại tiếp tục/tách/nhập/biến mất |
| hdbscan docs (how_hdbscan_works, soft_clustering) | — | — | Nhiễu = "không thuộc cụm được chọn **lần này**"; điểm nhiễu vẫn có độ thuộc mềm vào các cụm |

Không tìm thấy: tài liệu xử lý nhiễu HDBSCAN khi theo dõi cụm; quy tắc khi nào đặt lại tên do LLM sinh; ngưỡng suy từ data theo từng lần chạy. Lập luận "> 1/2 cả hai chiều → ghép 1–1" **không có trong tài liệu** (MONIC chỉ lập luận 1 chiều) — là suy luận của mình, đúng vì các cụm không giao nhau.

### Thí nghiệm (`scripts/topic_identity_eval.py`, gọi đúng `match_topics` production — mọi số dưới đây tái lập bằng `evaluate`)

Cùng dữ liệu (146 bài, embedding đã lưu), gom cụm lại với 10 seed UMAP, tham số production → 8–11 cụm, nhiễu 30–40%. 90 cặp seed có thứ tự (lần trước → lần sau), 828 cụm. Seed 42 ở thí nghiệm ra 10 cụm, lần chạy thật cùng seed ra 9 — khác thứ tự bài đầu vào: UMAP nhạy cả với thứ tự, nên xáo trộn kiểu này xảy ra thật mỗi khi có bài mới.

Hai loại lỗi:
1. **Đổi tên thừa** — data y nguyên → mọi lần đổi tên = tên trên dashboard đổi khi nội dung không đổi. Kiểm ngữ nghĩa: cosine tâm (bge-m3) giữa cụm bị đổi tên và topic cũ gần nhất so với mốc của **chính cặp đó** (cosine lớn nhất giữa 2 topic khác nhau của lần trước; trên 10 seed: cosine 2 topic khác nhau cùng lần n = 381, median 0,746, max 0,886).
2. **Giữ id sai** — với mỗi cụm được giữ, xoá hẳn cụm đó + mọi bài của topic cũ khỏi lần sau rồi ghép lại: topic đã biến mất mà id vẫn được trao là lỗi.

Tỉ lệ = **trung bình theo cặp seed** (mỗi cặp 1 tỉ lệ; tỉ lệ gộp = số đổi tên / 828 cụm hơi khác, VD mốc 31,4%, chốt 15,7%, thăm dò 10,5% — số 10,5% báo trước đó là tỉ lệ gộp). CI95: bootstrap **hai chiều** theo seed (mỗi cặp phụ thuộc cả seed lần trước lẫn lần sau — lấy mẫu lại tập seed, trung bình mọi cặp seed khác nhau trong mẫu; 5000 lần); chênh lệch là bootstrap ghép cặp trên cùng mẫu.

| Biến thể | Đổi tên thừa [CI95] | Giảm so với cũ [CI95] | Giữ (thành viên/ngữ nghĩa) · mới · tách · nhập | Bị đổi tên nhưng gần topic cũ hơn mốc | Giữ id sai |
|---|---|---|---|---|---|
| tính nhiễu · tách đổi hết · không ngữ nghĩa (**trước ADR**) | 30,6% [21,0; 40,3] | — | 568/– · 131 · 86 · 43 | 231/260 | 0/568 |
| tính nhiễu · lõi giữ | 30,3% [20,8; 39,7] | 0,3 [0,0; 1,1] | 571/– · 134 · 80 · 43 | 228/257 | 0/571 |
| bỏ nhiễu · tách đổi hết | 27,2% [19,5; 35,3] | 3,5 [0,6; 6,1] | 598/– · 81 · 86 · 63 | 201/230 | 0/598 |
| bỏ nhiễu · lõi giữ | 22,7% [15,8; 29,7] | 7,9 [4,5; 11,5] | 636/– · 119 · 10 · 63 | 163/192 | 0/636 |
| … + ngữ nghĩa cả cho cụm nhập (thăm dò) | 9,9% [6,6; 13,3] | 20,8 [13,9; 27,9] | 636/105 · 83 · 4 · 0 | 58/87 | 4/741 |
| … + ngữ nghĩa trừ cụm nhập (bản Thy duyệt, trước khi sửa phép thử nhập) | 17,7% [12,7; 22,8] | 12,9 [7,2; 18,4] | 636/42 · 83 · 4 · 63 | 121/150 | 4/678 |
| **chốt: như trên + phép thử nhập tính cả nhiễu** | **15,2% [10,7; 19,9]** | **15,5 [9,3; 21,2]** | 645/53 · 83 · 4 · 43 | 101/130 | **4/698 (0,6%)** |

Đọc bảng:
- Bỏ nhiễu và lõi giữ tên **cộng hưởng**: riêng bỏ nhiễu giảm 3,5 điểm [0,6; 6,1], riêng lõi giữ 0,3, cùng nhau 7,9 (bỏ nhiễu làm số ca "con" tăng nên phải có lõi giữ thì ca tách mới giảm 86 → 10).
- Ở mọi biến thể chỉ dùng thành viên, 85–89% cụm bị đổi tên có tâm gần topic cũ hơn mốc của cặp đó → HDBSCAN xáo thành viên mạnh hơn nội dung đổi; bước ngữ nghĩa nhắm đúng phần này.
- **Sửa phép thử nhập** (code-reviewer, sau khi Thy chốt): bỏ nhiễu ở mẫu số làm phần sót của 1 topic đã tan vào nhiễu (VD 1/10 bài) thành "cha" → nhập giả (20/63 ca nhập). Phép thử *giữ* vẫn bỏ nhiễu (câu 1); phép thử *nhập* tính cả nhiễu — cùng lý do của câu 1: bài ở nhiễu chưa "đi" đâu, nên 1 bài sót không phải là cả topic nhập vào. Số ca nhập về lại 43.
- Bước ngữ nghĩa có giá: **4/698 (0,6%)** lần giữ id cho topic đã bị xoá hẳn. Quy tắc chỉ thành viên ra 0 **theo cấu tạo phép thử** (topic bị xoá không còn bài nào để làm cha) — phép thử chỉ đo được lỗi của bước ngữ nghĩa.
- Trong 130 lần đổi tên còn lại của quy tắc chốt: 83 mới, 43 nhập (luôn tên mới theo lựa chọn — cụm nuốt thêm chủ đề khác), 4 tách.

Lần chuyển **thật** (`cluster_runs` 2→3 cùng data, 3→4 +2 bài): mọi biến thể giữ 9/9. Biên (số bài phải đổi chỗ để mất đa số, quy tắc chốt): 2→3 `[2, 4, 5, 5, 5, 6, 7, 7, 7]`; 3→4 `[1, 2, 2, 2, 3, 3, 5, 5, 6]` — biên mỏng (cụm nhỏ nhất lật nếu 1 bài đổi chỗ), bước ngữ nghĩa là lưới đỡ. Chỉ n = 1 lần chuyển có data đổi.

## Quyết định

1. **Id bền** `topic_N`, không bao giờ tái dùng: topic biến mất ghi dòng `retired` vào `topic_label_history`; `next_topic_number` đọc cả lịch sử.
2. **Ghép theo thành viên — đa số hai chiều** ("đa số" = > 1/2, theo định nghĩa; MONIC dùng 0,5 làm cận dưới cùng lý do): *con* của P = cụm mới có > 1/2 thành viên từ P; P *gửi đa số* vào C = > 1/2 thành viên (còn có mặt) của P nằm trong C.
   - Phép thử **giữ** bỏ bài rơi vào nhiễu khỏi mẫu số phía topic cũ (Thy chốt câu 1): nhiễu = "không thuộc cụm được chọn lần này", không phải đổi chủ đề. Bài sang cụm KHÁC vẫn tính là rời đi.
   - Phép thử **nhập** (C có ≥ 2 topic cũ gửi đa số vào) tính cả nhiễu ở mẫu số — 1 bài sót của topic đã tan không làm cụm lõi thành "nhập" → id + tên mới chỉ khi nhập thật.
   - **Lõi giữ tên** (câu 2, khớp mặc định MONIC/Greene/Palla): cụm nhận > 1/2 của P giữ danh tính; mảnh còn lại là cụm mới (ghi nguồn P). Chỉ khi không con nào nhận > 1/2 của P mới là **tách** → tên mới hết.
3. **Ghép theo ngữ nghĩa** (câu 4) cho cụm `new`/`split`, **không cho cụm nhập**: giữ id của topic cũ chưa ai giữ có tâm gần nhất khi cosine > `semantic_reference` = cosine **lớn nhất giữa 2 topic khác nhau của lần trước** (suy từ data mỗi lần, như sàn views P25 — không hằng số). Topic đã nhập vào cụm khác không trao id qua bước này. Tiền lệ: BERTopic `merge_models`, BERTilda.
4. **Đặt lại tên theo độ trôi** (câu 3), không theo lịch: lưu **bản neo** (thành viên lúc đặt tên, `topics.label_anchor_json`); mỗi lần chạy so cụm với bản neo bằng chính phép thử giữ (thành viên bỏ nhiễu, hoặc tâm gần hơn mốc). Không còn khớp → đặt lại tên (`drift`), bản neo mới. Bắt trôi **tích luỹ** mà ghép từng lần không thấy; không đổi tên vô cớ (lịch hằng tháng sẽ đổi ~4/9 tên mỗi tháng do model dao động). Đặt lại cả khi tên được đặt bằng model/`LABEL_PROMPT_VERSION` khác (`config_change`) hoặc chưa có mốc (DB trước ADR này).
5. **Prompt v2** (`LABEL_PROMPT_VERSION = 2`, Thy duyệt toàn văn; test khoá toàn văn bằng SHA-256): giữ nguyên prompt cũ, thêm quy tắc cho `label` — Title Case, ≤ 5 chữ, chủ đề cụ thể; chỉ nhắc "Vietnamese" khi phần lớn bài nói rõ về trải nghiệm người Việt ở Pháp; không dùng khung chung "Abroad"/"Expat Life". So trên 9 cụm thật, **1 lần gọi/cụm, định tính**: Title Case 9/9, "Vietnamese" ở 2 cụm đúng nghĩa; 2 tên 6 chữ (chấp nhận).
6. **Ghi vết**: `topic_label_history` (lý do `new|split|merged|drift|config_change|retired`, topic nguồn, model, phiên bản prompt); `topics.labeled_at/label_model/label_prompt_version/label_anchor_json`; `cluster_runs.topic_events_json` (`kept|kept_semantic|relabeled|new|split|merged|retired`). Gán bài → topic vẫn tính lại toàn bộ mỗi lần; chỉ id + tên là bền.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| A. Đặt tên lại mọi cụm mỗi lần | Không code | Tên trôi (4/9 đổi khi gọi lại); không có danh tính | Thy chọn B |
| Hỏi Claude "tên cũ còn đúng?" mỗi cụm | Không cần quy tắc ghép | Vẫn ~9 lời gọi; không có danh tính | Không giải quyết danh tính |
| Ngưỡng Jaccard/cosine chỉnh tay (Greene 0,3; BERTopic 0,7) | Có tiền lệ | Hằng số chưa căn cứ trên data này (quy tắc tuyệt đối của repo) | "Đa số" + mốc suy từ data mỗi lần |
| Tính nhiễu là rời đi; tách → tên mới hết | Chặt, đơn giản | 30,6% cụm đổi tên khi data không đổi; mảnh 4 bài làm cả lõi mất tên | Số đo + tài liệu |
| Ngữ nghĩa cả cho cụm nhập | 9,9% đổi tên | Cụm nuốt thêm chủ đề khác vẫn giữ tên cũ | Thy chọn trừ cụm nhập |
| Đặt lại hằng tháng | Dự đoán được | ~4/9 tên đổi mỗi tháng do model dao động, 9 cụm đổi cùng ngày | Theo độ trôi |
| Khoá tên tay | Thy kiểm soát tên | Thêm cờ + công cụ; tên khoá lệch khi cụm trôi | Chưa cần — lịch sử tên sẵn sàng |

## Hệ quả

- Code: `src/nlp/topic_identity.py` (`match_topics` — các cờ chỉ để thí nghiệm, mặc định = quy tắc chốt; `semantic_reference`, `anchor_holds`, `centroid`), `src/pipeline/clustering_import.py` (`plan_topic_names`, `topic_events`, ghi `retired`), `src/nlp/topics.py` (prompt v2), `src/db/schema.py` (cột + bảng mới, migration `cluster_N` → `topic_N` trong 1 transaction, `replace_cluster_topics`, `next_topic_number`). Thí nghiệm: `scripts/topic_identity_eval.py` (kết quả thô `data/experiments/`, gitignored — chứa id bài thật). Test: `tests/nlp/test_topic_identity.py`, `tests/pipeline/test_clustering_import.py`, `tests/nlp/test_topics.py`, `tests/db/test_schema.py`, `tests/scripts/test_topic_identity_eval.py`.
- Kiểm chứng trên bản sao DB thật (2026-10-04): lần đầu đặt lại tên 9/9 (`config_change`, prompt v2, mốc ngữ nghĩa 0,863), giữ id `topic_0…8`, lưu bản neo; lần hai 9/9 `kept`, 0 lời gọi Claude.
- **DB thật đã migrate một phần** trước khi ADR này được commit: job snapshot 2026-10-04 21:15 chạy code đang sửa trong checkout chính (`create_schema()` ở mọi job) → id đã là `topic_0…8`, đã có 3 cột `labeled_at/label_model/label_prompt_version` (rỗng) + bảng `topic_label_history` (rỗng); chưa có `label_anchor_json`. Lần job NLP kế tiếp (12:30, ADR-0017) thêm cột còn thiếu và đặt lại tên 9 cụm một lần (`config_change`) — tên trên dashboard đổi 1 lần; ảnh `topics` trong README chụp lại cùng đợt UI P1. Bài học: thay đổi schema phải làm trong worktree (`/wt`), không trong checkout chính mà cron chạy.
- API + dashboard coi `topic_id` là chuỗi định danh — không đổi.
- `--dry-run` vẫn chạy migration (`create_schema`) — không phải "không ghi gì".
- Docs: `docs/claude/data-model.md`, `docs/claude/architecture.md`, `.claude/rules/pipeline-db.md`, skill `recluster`, `docs/roadmap.md` (Phase C giữ hành vi này khi gộp sang `recluster.py`). Sổ luật: `ADR0018-full-recompute-topics`.
- Rủi ro chấp nhận: 15,2% cụm vẫn đổi tên dưới xáo trộn kiểu seed (trung bình theo cặp; gộp: 130/828 = 83 mới · 43 nhập · 4 tách); 0,6% giữ id cho topic đã biến mất (bước ngữ nghĩa); biên thành viên mỏng (lần chuyển thật 3→4: 1 bài đủ lật cụm nhỏ nhất); mốc ngữ nghĩa là bằng chứng *tiếp nối*, không phải chứng minh; dòng `retired` ghi `labeled_at` = lúc xoá, và topic từ trước ADR ghi `label_model = 'unknown'`, `label_prompt_version = 0` (RQ-06 xử lý riêng); chuyển working tree sang code trước ADR-0018 lúc cron chạy sẽ ghi lại `cluster_N` rồi bị migration đổi thành `topic_N` trùng số với lịch sử → merge nhánh trước khi đổi nhánh ở checkout chính.
- Xem lại khi: có lần tách/nhập thật đầu tiên (kiểm tên mới hợp lý); RQ-01 (nhiều seed, nhiều ngày) cho tỉ lệ đổi tên thực tế; Thy muốn khoá tên tay; đổi model embedding (mốc ngữ nghĩa phải cùng model).
