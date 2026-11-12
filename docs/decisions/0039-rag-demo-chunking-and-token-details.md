# ADR-0039: Chốt cách chia đoạn, vị trí đáp án và chi tiết token của demo RAG

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-06
- **Người quyết**: Thy — chọn từng mục qua trao đổi 2026-11-06; phương án và số đo do Claude đề xuất.

> **Quan hệ với ADR-0037 và ADR-0038.** ADR này bổ sung, không thay thế. ADR-0038 ghi "còn phải chốt trước khi code" danh
> sách cách chia đoạn và 2 vị trí đáp án; hai mục đó chốt ở đây. Quy tắc token dưới đây chi tiết hoá D3 của ADR-0038 và
> thêm một luật mới (gộp 2 cách đặt dấu). Ước lượng "~500 chunk", "≤ 10.000 cặp" và ngân sách 4 MB của ADR-0037 giữ nguyên.

## Bối cảnh

Đo 2026-11-06 trên 20 content unit đóng băng của ADR-0037 theo đúng luật ADR-0038. Chỉ đo BM25, chưa có dense và rerank;
20 bài, 10 câu, không có khoảng tin cậy, nên bảng chỉ minh hoạ, không kết luận cách nào tốt nhất. Câu 1, 2, 3, 4, 5, 8, 9
gần như không đổi giữa các cách. Script đo nằm ngoài repo. Semantic đo bằng bge-m3 thay thế, bản thật dùng embedding của
ADR-0037 D6 nên số đoạn sẽ khác.

| Cách chia | Số đoạn | Hạng câu 6 | Hạng câu 7 | Câu 10 khớp nhầm |
|---|---|---|---|---|
| Không chia | 20 | 8 | 6 | 16 |
| Theo từng post | 69 | 11–12 | 9 | 29 |
| Cố định 300 ký tự | 113 | 11–13 | 11 | 35 |
| Cố định 500 ký tự | 70 | 11–12 | 6 | 32 |
| Cố định 800 ký tự | 47 | 12 | 7 | 27 |
| Recursive 500 | 72 | 6–7 | 4 | 33 |
| Semantic | 108 | 13 | 6 | 34 |
| Từng câu | 357 | 14 | 9 | 38 |

- **Ranh giới post.** `posts.text` ghép bằng dấu cách dựng lại đúng `full_text` ở 20 / 20 bài, nên vị trí từng post là chính
  xác. Repo mẫu của ADR-0037 không có kiểu chia này. `format_aware` của repo mẫu không dùng được vì bài không có định dạng;
  `token_based` chỉ khác `recursive` ở đơn vị đếm.
- **Từng câu.** 79 / 357 đoạn dưới 40 ký tự, quá ngắn để chấm (40 ký tự chỉ là mốc mô tả, không phải hằng số của code).
- **Chi phí (ước lượng, chưa đo thật).** 7 cách: 499 đoạn, 4.990 cặp, ~$0,6 với Claude Haiku 5.5, file ~1,9 MB, dưới ngân sách
  4 MB và ước lượng 10.000 cặp của ADR-0037. Đủ 8 cách: ~860 đoạn, ~$1, ~2,8 MB.
- **Vị trí đáp án.** Python đếm theo điểm mã, JavaScript theo UTF-16 (ADR-0038 D7). Hai vị trí dưới ghi theo Python.
- **Đặt dấu.** 20 bài chỉ dùng dấu trên nguyên âm đầu (`khỏe`, `tùy`, `tỏa`, 5 lần), 0 lần dấu trên nguyên âm sau; 10 câu cố
  định không có từ nào thuộc diện này, nên luật chỉ tác động ô tự gõ. `src/processing/text.py:31#_TONE_MARK_UNIFICATION` đã
  gộp cùng chiều cho oa, uy.
- **Emoji.** Trong 20 bài: U+FE0F 5 lần, khung số U+20E3 0 lần. **Chữ ghép:** `œ`, `æ`, `ß` 0 lần.

## Quyết định

1. **D1 — 7 cách chia**, mỗi cách tính sẵn, người xem chọn trong danh sách cố định: không chia; theo từng post; cỡ cố định
   300 / 500 / 800 ký tự, chồng lấn 40 / 60 / 100 ký tự (~12%), ngắt ở dấu cách; recursive 500 (đoạn văn, rồi câu, gộp lên
   tới 500 ký tự); semantic (ngắt ở 1/4 thấp nhất của độ giống câu liền kề, tối đa 800 ký tự). Không làm chia từng câu và
   small-to-big.
   Nguồn từng hằng số: chồng lấn ~12% nằm trong khoảng 10–15% mà README repo mẫu gợi ý
   (https://github.com/vietnh1009/RAG-pipeline-visualizer); 500 ≈ trung vị độ dài post (473 ký tự), 300 và 800 là một cỡ dưới
   và một cỡ trên post, trần 800 của semantic lấy theo cỡ lớn nhất; ngưỡng 1/4 thấp nhất và trần 800 là **lựa chọn thiết kế**
   để minh hoạ, không có bằng chứng tối ưu.
2. **D2 — Câu ngữ cảnh** (ADR-0037 D7) là công tắc cho mọi cách trừ không chia, vì chunk khi đó đã là cả bài. Cross-encoder và LLM rerank chấm trên chữ gốc
   của chunk, không kèm câu ngữ cảnh, để số cặp không nhân đôi.
3. **D3 — Vị trí đáp án** đã Thy duyệt, nửa mở, tính trên `full_text` theo điểm mã Unicode của Python: câu 5 bài
   18156311638533948 ký tự [979, 1219); câu 8 bài 18042552590841773 ký tự [1141, 1363).
4. **D4 — Token**, bổ sung ADR-0038 D3 (`src/dashboard/src/lib/ragDemo/bm25.ts:42#tokenize`):
   - dấu thanh trên nguyên âm sau ở cụm oa, oe, uy gộp về nguyên âm đầu (`tuỳ` = `tùy`), chỉ ở cuối token và không sau `q`;
   - bỏ ký tự đi kèm emoji, khung số đổi thành khoảng trắng để từ dính sau nó không gộp vào số;
   - số thập phân chỉ áp cho token toàn số, token mở đầu bằng chữ hoặc số;
   - `œ`, `æ` không đổi.
5. **D5 — CI**: job Python cài Node để test đối chiếu chạy thật; thiếu Node thì test hỏng, không bỏ qua.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Đủ 8 cách (thêm từng câu; công tắc small-to-big dùng lại đoạn câu nên không tính thêm đoạn) | Kỹ sư hay hỏi tới small-to-big | Nhiều đoạn quá ngắn, nhiều lượt LLM phí, thêm phần giải thích | Thy chọn 7 cách |
| 5 cách (một cỡ cố định) | Gọn hơn, ~$0,4 | Mất so sánh cỡ đoạn, nút chỉnh quen thuộc nhất của chunking | Như trên |
| 4 cách (không có semantic) | Gọn nhất, không cần bước semantic | Thiếu kỹ thuật người đọc kỹ thuật thường mong đợi | Như trên |
| Giữ 2 cách đặt dấu, ghi giới hạn | Không thêm code | Gõ `tuỳ` kết quả kém hơn gõ không dấu mà không hiểu vì sao | Thy chọn gộp |
| Xử lý `œ`, `æ` | Phòng khi có bài tiếng Pháp | 0 lần trong 20 bài, không đổi kết quả nào | Thy giữ nguyên |

## Hệ quả

- **Code (chặng 2, PR code ADR-0037):** `src/rag_demo/` có 7 cách chia, mỗi chunk giữ vị trí trong `full_text`; hằng số cỡ, chồng
  lấn, ngưỡng semantic có nhãn nguồn; file câu hỏi có 2 vị trí của D3. Chunk lấy từ `full_text`, không từ `normalized_text`.
- **Semantic phụ thuộc embedding:** phần ngắt viết ở chặng 2, số đoạn thật chỉ có khi chạy với embedding của chặng 3. Mảnh
  ngắn (17 / 108 dưới 40 ký tự trên bản đo thay thế) chưa quyết cách xử lý, hỏi Thy khi có số đoạn thật.
- **Nợ ngoài phạm vi:** `src/processing/text.py:82#_unify_tone_marks` thay ở mọi vị trí nên đổi cả `hoàng`, `quý` trong
  `normalized_text`; cột này chỉ được lưu, không ảnh hưởng demo.
- **Luật (`invariants.toml`): không có luật mới.** ADR không đổi tên hay đường dẫn; `planned_paths` của ADR-0037 đã phủ
  `src/rag_demo/**`. Luật chữ cho trang viết ở PR giao diện.
- **Docs:** `docs/decisions/README.md`, `docs/claude/data-model.md`, `docs/claude/architecture.md`, `docs/design/ui-contract.md`,
  `docs/status.md`.
- **Rủi ro chấp nhận:** bảng số chỉ đo BM25 trên đoạn tạm; số đoạn semantic thật có thể khác nhiều.
- **Xem lại khi:**
  1. Có số đoạn semantic thật → đo lại file và chi phí. Vượt 4 MB thì chia file theo ADR-0037 D3; vẫn vượt, hoặc chi phí quá
     ước lượng, thì hỏi Thy có bỏ bớt cỡ cố định không.
  2. Làm mới 20 bài → kiểm lại D3 (ADR-0037, điều kiện xem lại 5) và luật đặt dấu, chữ ghép.
  3. Có đủ dense + rerank → xem lại cách nào không còn cho thấy khác biệt thì bỏ.

### Hệ quả UI

- Sửa `UI-0037-free-query-bm25-only`: câu tự gõ có thêm luật gộp 2 cách đặt dấu của D4.
- Thêm `UI-0039-chunking-options` (7 cách chia cố định, công tắc câu ngữ cảnh). Nâng mốc "Cập nhật tới" lên ADR-0039.
