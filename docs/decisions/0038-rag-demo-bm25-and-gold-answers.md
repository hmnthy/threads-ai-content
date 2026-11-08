# ADR-0038: Chốt BM25 và cách chấm đáp án đúng của demo RAG

- **Trạng thái**: Accepted — luật câu 4 của D7 (một trong 2 bài → một bài) thay bởi ADR-0040
- **Ngày**: 2026-11-06
- **Người quyết**: Thy — chọn từng mục qua trao đổi 2026-11-06; phương án và số đo do Claude đề xuất.

> **Quan hệ với ADR-0037.** ADR này bổ sung ADR-0037, không thay thế. ADR-0037 giao cho PR code chốt biến thể IDF, k1 / b,
> cách tách token và cách phân hạng khi điểm bằng nhau; các mục đó chốt ở đây. Bốn điểm khác nguyên văn ADR-0037, ADR này
> thắng: (1) bỏ bước tách từ trong WSL2 (mục Hệ quả của ADR-0037); (2) đáp án đúng của câu 5 và 8 có thêm vị trí ký tự
> (D10 ghi "gắn theo id bài"); (3) test đối chiếu so điểm trong sai số thay vì đòi cùng thứ hạng tuyệt đối (D5 dưới);
> (4) "âm tiết + bản bỏ dấu" của D11 nghĩa là mỗi câu chỉ so khớp một trong hai chỉ mục, không chạy cả hai (D3 dưới).

## Bối cảnh

Đo 2026-11-06 trên 20 content unit đóng băng của ADR-0037 (27.744 ký tự, 5.994 token, 10 câu hỏi). Cách chia đoạn thật
chưa chốt nên đoạn là **đại diện tạm**: cửa sổ cố định 60 / 120 / 250 token (110 / 60 / 36 đoạn). Các số dưới chỉ minh
hoạ, không phải đánh giá: 20 bài, 10 câu, không có khoảng tin cậy. Script đo nằm ngoài repo.

- **IDF.** Từ có trong quá nửa số đoạn: 2 / 6 / 18 trên 1.376 từ theo 3 cỡ đoạn. Công thức Okapi cho những từ này IDF âm;
  `rank_bm25` thay bằng mức sàn 0,64–0,91, cao hơn IDF của 10–30 từ ít phổ biến hơn, tức từ quá phổ biến nặng hơn từ hiếm
  hơn nó (https://github.com/dorianbrown/rank_bm25). SQLite FTS5 cho những từ này điểm 0,000001 (chạy thử với SQLite
  3.45.3, trang tài liệu không ghi). Lucene cộng 1 trong log nên IDF luôn dương
  (https://lucene.apache.org/core/9_11_0/core/org/apache/lucene/search/similarities/BM25Similarity.html). Giữa 3 công
  thức, hạng đáp án đúng lệch tối đa 2 bậc và không công thức nào thắng rõ; top-5 cùng thứ tự ở 2–5 / 10 câu, trùng tập
  0,88–0,96. Vậy lý do chọn là công thức dễ giải thích, **không** phải số đo tốt hơn.
- **k1 / b.** Đổi k1 từ 1,2 sang 1,5: top-5 giữ nguyên thứ tự ở 8–9 / 10 câu, trùng tập 0,96–0,98. Giá trị 1,2 / 0,75 là
  mặc định của Lucene và cố định trong FTS5 (https://www.sqlite.org/fts5.html); 1,5 / 0,75 là mặc định của `rank_bm25`.
- **Dấu.** Bảng dưới (theo 3 cỡ đoạn): hạng đáp án câu 1 (gõ không dấu), câu 6 (tiếng Pháp), số đoạn khớp nhầm của câu 10
  (câu không có đáp án, ít hơn là tốt hơn).

| Cách | Câu 1 | Câu 6 | Câu 10 |
|---|---|---|---|
| Chỉ có dấu | không tìm thấy | 11–12 | 21–34 |
| Luôn bỏ dấu | 1–2 | 14–22 | 30–84 |
| Đổi theo câu hỏi | 1–2 | 11–12 | 21–34 |
| Trộn theo từng từ | 1–2 | 11–15 | 27–66 |

- **Tách từ ghép** (underthesea, một cỡ đoạn): câu 1 mất đáp án vì câu không dấu bị tách sai, đáp án thứ 2 của câu 7 tụt
  từ hạng 8 xuống 20, câu 6 lên từ 12 thành 10.
- **Điểm bằng nhau.** Đoạn dài đều nhau: đáp án đúng bị hoà ở câu 6 (cùng điểm với 4–8 đoạn khác) và câu 4 (2 bài gần
  trùng). Đoạn theo câu hoặc đoạn văn: không ca nào.
- **Thư viện đối chiếu.** `bm25s` 0.3.16 nhận token có sẵn; `method="lucene", idf_method="lucene"` cho điểm bằng công thức
  D1 dưới, sai khác < 1e-6 do `bm25s` lưu số 32 bit (3 câu × 2 bộ k1 / b, cùng thứ tự). Dạng BM25 cổ điển có thêm (k1 + 1)
  ở tử số thì điểm gấp (k1 + 1) lần, thứ tự như nhau. Bắt buộc chỉ có
  numpy (https://pypi.org/project/bm25s/). `rank_bm25` bản mới nhất 0.2.2 từ 02/2022, không có bản Lucene.
- **Vị trí ký tự.** Cùng một vị trí trong bài có emoji: Python đếm 979 thì UTF-16 của JavaScript đếm 985 (bài câu 5), 1141
  so với 1143 (bài câu 8).

## Quyết định

1. **D1 — Công thức Lucene** cho BM25 của demo:
   `score = Σ IDF(t) · f / (f + k1 · (1 − b + b · |D| / avgdl))`, `IDF(t) = log(1 + (N − n + 0,5) / (n + 0,5))`. Tử số không
   có (k1 + 1), bằng đúng điểm `bm25s` `method="lucene"`.
2. **D2 — k1 = 1,2, b = 0,75** là hằng số mặc định có nhãn nguồn, kèm 2 thanh kéo trên trang. Trang nói rõ tác động thường
   nhỏ.
3. **D3 — Token theo âm tiết**, không tách từ ghép, không danh sách stopword: chuẩn hoá NFC, chữ thường, giữ số như `1,0`,
   dấu gạch và dấu nháy tách token. Hai chỉ mục (có dấu, bỏ dấu; bỏ dấu đổi `đ` thành `d`). **Đổi theo câu hỏi**: câu có
   ít nhất một chữ có dấu (chữ đổi khi bỏ dấu, kể cả tiếng Pháp như é, ç) thì so khớp chỉ mục có dấu; câu không dấu thì so
   khớp chỉ mục bỏ dấu. Áp cho câu cố định, câu tự
   gõ (ADR-0037 D11) và câu do LLM biến đổi.
4. **D4 — Điểm bằng nhau trong BM25** (hoà = bằng nhau sau khi làm tròn tới 6 chữ số thập phân, hằng số có nhãn): xếp
   theo mã chunk, ổn định giữa các lần chạy. Đáp án đúng bị hoà thì hiện khoảng
   hạng thay vì một số. Đoạn điểm 0 (không khớp từ nào) không được xếp hạng. Hoà ở các bước trộn và rerank chưa quyết, chọn
   khi làm các bước đó.
5. **D5 — Bài giải mẫu**: `bm25s` chỉ trong nhóm `dev`. Test so trực tiếp điểm TypeScript với `bm25s` trong một sai số có
   nhãn riêng, khác hằng làm tròn của D4 vì `bm25s` lưu 32 bit còn TypeScript 64 bit, để thư viện trong test không chi phối
   sản phẩm; hai đoạn gần nhau hơn sai số thì test không so thứ tự của chúng.
6. **D6 — 10 câu hỏi + đáp án**: một file bản gốc trong `src/rag_demo/`; bước dựng chép vào file dữ liệu demo (file `common`,
   ADR-0037 D3); trình duyệt đọc từ file dữ liệu. Câu hỏi và mã bài đã công khai trong ADR-0037.
7. **D7 — Đáp án đúng**: tính theo mã bài. Câu 3 và 7 cần cả 2 bài, câu 4 một trong 2 bài, câu 10 không có đáp án. Câu 5 và
   8 thêm vị trí ký tự trong `full_text`: chunk phải chạm đoạn đó mới tính là trúng. Lý do ở câu 8: bài này cũng là đáp án
   câu 2, nên nếu chỉ tính mã bài thì đoạn nói về áo khoác cũng được tính là trúng câu 8. Vị trí ghi bằng số, không chép chữ của bài (repo public); Thy duyệt 2 vị trí
   trước khi vào file. **Bước dựng bằng Python tính sẵn chunk nào trúng** rồi ghi vào file dữ liệu; trình duyệt không tự
   tính vị trí, vì Python và JavaScript đếm khác nhau khi có emoji. Python chỉ đánh dấu, không xếp hạng (ADR-0037).
8. **D8 — Hạng của đáp án đúng**: mỗi bài lấy chunk trúng đứng cao nhất. Câu cần một bài (kể cả câu 4) có một hạng. Câu 3
   và 7 có **số chính** = phải đọc tới hạng mấy mới đủ cả 2 bài (hạng của bài tìm thấy sau cùng), ngay dưới là hạng từng
   bài, VD "8 (2 and 8)"; chế độ A/B so số chính. Khoảng hạng của D4 áp cho chunk quyết định số đó. Không chunk trúng nào có điểm trên 0 thì hiện
   "not found", không hiện hạng.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Okapi + `rank_bm25` | Thư viện đơn giản, đúng ghi chú cũ | Mức sàn làm từ quá phổ biến nặng hơn từ hiếm hơn; thư viện đứng từ 2022 | Thy chọn Lucene + `bm25s` |
| FTS5 của SQLite | Giống knowledge base sau này, không thêm thư viện | k1 / b khoá cứng nên không kiểm được thanh kéo; FTS5 tự tách từ | Như trên |
| 1,2 / 0,75 cố định | Gọn nhất | Mất nút chỉnh mà kỹ sư đọc portfolio hay muốn thử | Thy chọn có thanh kéo |
| 1,5 / 0,75 cố định | Mặc định `rank_bm25` | Lệch giá trị của FTS5 | Như trên |
| Luôn bỏ dấu | Đơn giản nhất | Câu 6 và câu 10 kém hơn (bảng trên) | Thy chọn đổi theo câu hỏi |
| Trộn theo từng từ | Tinh tế | Không hơn, khó giải thích, test phức tạp hơn | Như trên |
| Thêm tách từ ghép bằng underthesea | Minh hoạ từ ghép | Không hơn trên số đo, file nặng thêm, ô tự gõ không dùng được | Như trên |
| Chỉ theo mã chunk, không ghi hoà | Gọn nhất | Hạng trông chính xác nhưng một phần do cách đánh mã | Thy chọn ghi khoảng hạng |
| Bài mới hơn trước khi hoà | Có nghĩa đời thường | Thêm một ưu tiên không liên quan độ khớp | Như trên |
| Câu hỏi viết cứng trong TypeScript | Trang hiện câu hỏi kể cả khi file lỗi | Python cũng cần, thành 2 bản phải giữ khớp | Thy chọn một file bản gốc trong repo |
| Câu hỏi chỉ trong file dữ liệu | Gọn về code | Không review, CI không kiểm được, mất file là mất đáp án | Như trên |
| Chỉ mã bài | Đúng nguyên văn ADR-0037 | Hạng câu 5 và 8 đẹp hơn thực tế | Thy chọn thêm vị trí cho 2 câu |
| Vị trí cho mọi câu | Chính xác nhất | Khoảng 11 vị trí phải duyệt, quá nặng cho trang minh hoạ | Như trên |
| Câu 3, 7 chỉ hiện số "đọc tới đâu" | Gọn, so A/B dễ | Không thấy bài đầu đứng hạng mấy | Thy chọn số chính + hạng từng bài |
| Câu 3, 7 chỉ lấy hạng cao nhất | Đơn giản nhất | Đẹp hơn thực tế, bỏ qua bài thứ hai | Như trên |
| Hoà = bằng tuyệt đối | Không cần hằng số | 2 điểm thật ra bằng nhau, lệch do cách máy cộng, không được ghi là hoà | Thy chọn làm tròn 6 chữ số |
| Hoà = chênh dưới ngưỡng | Không đổi điểm | Không bắc cầu: A hoà B, B hoà C mà A không hoà C, khoảng hạng không xác định | Như trên |

## Hệ quả

- **Code (PR code ADR-0037, cùng nhánh):** engine `src/dashboard/src/lib/ragDemo/` theo D1–D4; hằng số k1, b, ngưỡng hoà có
  nhãn nguồn; `bm25s==0.3.16` vào nhóm `dev` của `pyproject.toml` + `uv.lock` (gói API trên Vercel chạy `--no-dev`, không
  kéo theo). File câu hỏi trong `src/rag_demo/`; test kiểm mọi mã bài có trong 20 bài đóng băng và vị trí nằm trong
  `full_text`. Mỗi chunk giữ vị trí trong `full_text` để tính được D7, kể cả chunk có câu ngữ cảnh (ngữ cảnh không tính
  vào vị trí). `scripts/rag_demo_build.py` bỏ bước tách từ. Cột B các dòng `UI-0038-*` thêm neo `file:dòng#Tên`
  khi code có thật (ADR-0033).
- **Test tách token:** Python tham chiếu và TypeScript phải ra cùng token trên bộ câu mẫu có dấu, tiếng Pháp, số và emoji.
- **Còn phải chốt trước khi code:** danh sách cách chia đoạn; 2 vị trí của câu 5 và 8 (Thy duyệt).
- **Luật (`invariants.toml`): không có luật mới.** ADR không đổi tên hay đường dẫn; `planned_paths` của ADR-0037 đã phủ
  `src/rag_demo/**`. Phát biểu cũ còn lại nằm trong ADR-0037 (không sửa ADR Accepted, xem khung đầu); dòng `UI-0037-free-query-bm25-only` đã sửa tại chỗ. Luật chữ cho trang
  viết ở PR giao diện, khi có chữ thật để kèm test câu đúng không bị bắt.
- **Docs:** `docs/decisions/README.md`, `docs/claude/data-model.md` (đoạn demo), `docs/design/ui-contract.md`, `docs/status.md`.
- **Rủi ro chấp nhận:** số đo trên đoạn đại diện, kết quả có thể đổi khi có cách chia thật; thanh kéo k1 / b thường đổi ít
  nên trang phải nói thật; câu nhiều chữ không dấu lẫn một chữ có dấu sẽ so khớp theo chỉ mục có dấu và có thể sót.
- **Xem lại khi:**
  1. Có cách chia đoạn thật → đo lại D3 và D4; hoà chạm đáp án đúng thường xuyên → xem lại cách hiện khoảng hạng.
  2. Làm mới 20 bài → kiểm lại 2 vị trí (ADR-0037, điều kiện xem lại 5).
  3. Knowledge base thật (FTS5) được dựng → FTS5 khác công thức IDF và không chỉnh được k1 / b; trang phải ghi rõ khác biệt
     nếu đọc từ KB.
  4. `bm25s` đổi công thức bản Lucene → test đối chiếu sẽ báo, ghim lại phiên bản.

### Hệ quả UI

- Sửa `UI-0037-free-query-bm25-only`: câu tự gõ dùng luật đổi theo câu hỏi của D3.
- Thêm `UI-0038-bm25-controls` (2 thanh kéo, mặc định có nhãn nguồn, câu nói tác động thường nhỏ), `UI-0038-tied-rank`
  (khoảng hạng khi hoà, đoạn điểm 0 không xếp hạng), `UI-0038-gold-definition` (định nghĩa đáp án đúng và hạng của nó). Nâng mốc "Cập nhật
  tới" lên ADR-0038.
