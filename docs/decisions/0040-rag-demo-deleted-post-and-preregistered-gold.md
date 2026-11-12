# ADR-0040: Bỏ bài đã xoá khỏi demo RAG, giữ đáp án chốt trước, ghi chú bản dịch máy

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-08
- **Người quyết**: Thy — chọn 3 mục qua câu hỏi 2026-11-08 sau khi đọc số đo; phương án và số đo do Claude đề xuất.

> **Quan hệ với ADR-0037, ADR-0038.** ADR này thay một phần: số bài của ADR-0037 D2 (20 → 19) và luật câu 4 của
> ADR-0038 D7 ("một trong 2 bài" → một bài). Mọi mục khác giữ nguyên, kể cả 10 câu hỏi, 2 vị trí đáp án (ADR-0039 D3) và
> thứ tự bài dùng phân hạng khi điểm bằng nhau (ADR-0038 D4).

## Bối cảnh

Kiểm dữ liệu chặng 3e trên bài thật, 2026-11-08 (`scripts/rag_demo_build.py`, lệnh `check` và `live-check`):

- **Một bài đáp án đã bị xoá trên Threads.** Bài `18117744790996401` (đăng 2026-10-12), một trong 2 bài đáp án của câu 4,
  không có trong danh sách 1.734 post + reply đang sống. Gọi thẳng `GET /{id}` cũng trả lỗi 400, mã 100, "does not
  exist". 5 post viết tiếp của bài vẫn còn. Bài đáp án còn lại của câu 4, `17923191900443021` (đăng 2026-10-26), còn sống;
  phần mở đầu giống 85 % (`difflib`, 600 ký tự đầu). Đây chính là lý do ADR-0038 cho câu 4 "một trong 2 bài". DB vẫn còn
  bài cũ vì ingest chỉ ghi thêm (`src/rag_demo/corpus.py:165#load_units`).
- **Bỏ bài này không đổi chữ chunk nào của 19 bài còn lại**, ở cả 7 cách chia (ADR-0039 D1). Ngưỡng semantic tính chung
  trên cả tập, nhưng không có chỗ ngắt nào đổi bên. Vì vậy không phải gọi lại OpenAI hay Haiku. Riêng file cặp
  cross-encoder phải ghi và chấm lại, việc chấm chạy trong WSL2 nên miễn phí.
- **Haiku chấm "trả lời một phần" cho đoạn ngoài đáp án.** Có 43 đoạn (đếm theo chữ chunk khác nhau) không thuộc đáp án
  mà vẫn được 2 / 3 điểm: câu 1 có 7, câu 2 có 7, câu 4 có 4, câu 7 có 16, câu 8 có 9. Không đoạn ngoài đáp án nào được
  3 điểm. Câu 10 (không có đáp án) có 0 đoạn được giữ. Trong số đó có đoạn trả lời một phần thật: câu 4, bài khuyên chú ý
  "growth mindset" khi chọn coach; câu 7, thực đơn 33 € đồ Việt nấu tại nhà; câu 2, chợ bán đồ hiệu déstockage. Cũng có
  đoạn nhầm rõ: câu 1 giữ một đoạn của bài đổi ngành; câu 7 giữ dòng "mua trên Amazon" của bài về bút.
- **Bản dịch tiếng Anh còn chữ tiếng Việt.** Có 27 dòng (`chunk_en`, `context_en`) chứa một cụm ≥ 3 từ có chữ cái chỉ tiếng
  Việt mới có. 22 dòng là tên món, nhãn hàng (bánh lọc, bơ Tường An, bút Thiên Long), giữ nguyên là đúng. 5 dòng sót
  thật, cả 5 ở đầu một chunk bắt đầu giữa câu.

## Quyết định

1. **D1 — 19 bài.** Bỏ bài `18117744790996401` khỏi danh sách đóng băng, không lấy bài khác thay. 19 bài còn lại giữ
   nguyên thứ tự. Trang ghi rõ: đóng băng 20 bài, 1 bài bị tác giả xoá trên Threads sau mốc đóng băng nên demo còn 19.
2. **D2 — Câu 4 một bài đáp án**: `17923191900443021`, theo luật một bài như câu 1, 2, 6, 9.
3. **D3 — Kiểm bài còn sống trước khi publish.** Bước dựng chạy `live-check` trước mỗi lần publish file demo. Bài nào mất
   hay đổi chữ trên Threads thì dừng, Thy quyết; code không tự bỏ bài.
4. **D4 — Giữ đáp án chốt trước** (ADR-0038 D7), không thêm đoạn theo điểm Haiku, cùng tinh thần luật chốt trước của
   ADR-0036. Trang công bố số đoạn ngoài đáp án mà Haiku chấm 2 điểm, kèm vài ví dụ trả lời một phần thật và vài ví dụ
   nhầm.
5. **D5 — Bản dịch máy giữ nguyên.** Không dịch lại 5 dòng sót. Trang ghi chú: bản dịch do máy làm, tên món và nhãn hàng
   giữ tiếng Việt, đoạn bắt đầu giữa câu đôi khi còn sót tiếng Việt.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ đủ 20 bài | Không phải làm lại gì | Trang công khai chữ của bài tác giả đã xoá; link tới bài không mở được | Thy chọn bỏ |
| Thay bằng bài mới nhất kế tiếp | Giữ con số 20 | Tốn lượt Haiku + chờ lô ≤ 24 giờ; phải kiểm lại đáp án cả 10 câu (ADR-0037, điều kiện xem lại 5) | Như trên |
| Thy chấm thêm mức "đáp án phụ" + chỉ số có mức độ (nDCG) | Đo công bằng hơn với đoạn trả lời một phần | Đổi phương pháp đo sau khi đã thấy kết quả; thêm việc cho chặng 4 | Thy giữ đáp án chốt trước |
| Lấy đoạn Haiku chấm 2 làm đáp án | Không tốn công đọc | Đo vòng tròn: Haiku chọn đáp án rồi chấm chính Haiku; chọn sau khi thấy kết quả | Như trên |
| Dịch lại 5 dòng sót (prompt mới) | Bản dịch sạch | Vài cent + chờ lô; phải tăng phiên bản prompt | Thy giữ + ghi chú |

## Hệ quả

- **Code:** `src/rag_demo/corpus.py:31#FROZEN_UNITS` còn 19 bài; `src/rag_demo/questions.py:69#Question` (câu 4) dùng luật
  một bài, bỏ luật `ANY_OF_TWO` vì không câu nào còn dùng; test theo đó. Bước dựng: ghi lại file cặp (`ce-export`), chấm
  lại trong WSL2, `ce-check`, rồi `check` và `live-check` phải ra 0 lỗi.
- **Dữ liệu đã trả tiền giữ nguyên.** Không xoá dòng nào khỏi `data/rag_demo/llm/results.jsonl` hay cache vector. Bước
  đóng file demo chỉ lấy dòng của chunk thuộc 19 bài.
- **Số đo cũ.** Số đo đã ghi trong code và docs trên 20 bài (chunking, chi phí, số cặp, số dòng kết quả) giữ nguyên làm
  số của lần đo đó, ghi rõ "trên 20 bài"; số mô tả tập hiện tại đổi sang 19 bài. Methodology log thêm số của tập 19 bài.
- **Luật (`invariants.toml`):** `ADR0040-deleted-unit-in-code` (mã bài đã xoá dạng chuỗi trong code),
  `ADR0040-twenty-frozen-units` (câu "20 bài / content unit đóng băng" mô tả tập hiện tại),
  `ADR0040-q4-any-of-two` (luật câu 4 cũ).
- **Docs:** `docs/decisions/README.md`, trạng thái ADR-0037 và ADR-0038, `docs/claude/data-model.md`,
  `docs/claude/architecture.md`, `docs/design/ui-contract.md`, `docs/roadmap.md`, `docs/status.md`.
- **Rủi ro chấp nhận:** câu 4 mất một cách trúng nên hạng của câu 4 có thể kém đi so với số đo cũ; 43 đoạn trả lời một
  phần vẫn bị tính là trượt.
- **Xem lại khi:**
  1. `live-check` báo thêm một bài mất hoặc đổi chữ → hỏi Thy, không tự bỏ.
  2. Làm mới tập bài (ADR-0037, điều kiện xem lại 5) → chấm lại đáp án từ đầu, khi đó mới được thêm đáp án phụ.
  3. Có đáp án phụ do Thy chấm → thêm chỉ số có mức độ, ADR mới.

### Hệ quả UI

- Sửa `UI-0037-rag-pipeline-page`: dữ liệu là 19 content unit đóng băng; trang ghi 1 bài bị xoá sau mốc đóng băng.
- Sửa `UI-0037-explain-every-step`: n = 19 bài, 10 câu hỏi.
- Sửa `UI-0038-gold-definition`: câu 4 một bài.
- Thêm `UI-0040-honest-data-notes`: số đoạn ngoài đáp án Haiku chấm 2 + ví dụ đúng và nhầm; ghi chú bản dịch máy.
- Nâng mốc "Cập nhật tới" lên ADR-0040.
