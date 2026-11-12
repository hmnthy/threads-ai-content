# ADR-0041: Luật xếp hạng cho mọi bước của demo RAG

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-09 (quyết định cuối về expand 2026-11-10)
- **Người quyết**: Thy — chốt qua 5 lượt câu hỏi 2026-11-09 (luật hoà; thứ tự bước, top-N, nhãn Haiku, hạng trung bình
  vào RRF; rồi sau mỗi vòng code-reviewer chỉ ra chỗ đặc tả còn hở, Thy chọn chốt hết ngay thay vì để PR engine: MMR,
  hằng số, lọc gần trùng, metadata, lọc Haiku, BM25 khi lọc, phần của thread, câu hỏi nhiều câu con, giá trị mặc định,
  phần còn chờ, cosine dùng cho lọc gần trùng / MMR, có thêm câu gốc vào tập câu con không, cách 4 biến đổi một câu
  vào bước tìm, cách đưa expand vào bước tìm sau khi số đo cho thấy câu mở rộng không giữ câu gốc, A/B cho câu không
  có đáp án, mũi tên đổi hạng; rồi chọn review tới khi sạch hẳn).
  Các luật biên (danh sách rỗng, khoảng hạng sau lọc, gộp hạng đáp án) là hệ quả kỹ thuật, Claude ghi, Thy duyệt cùng
  commit.

> **Quan hệ với ADR-0038.** Bổ sung ADR-0038 D4 (hoà ở các bước trộn và rerank để ngỏ) và **thay một phần D8**: "không
> chunk trúng nào có điểm trên 0 thì hiện *not found*" chỉ còn áp cho BM25 (và rerank khi đáp án vắng trong danh sách vào); "khoảng hạng của D4 áp cho chunk quyết định
> số đó" thành khoảng theo mọi cách xếp lại trong nhóm hoà (mục "Hạng của đáp án"); "chế độ A/B so số chính" thành so cả
> khoảng hạng. Dòng trạng thái của ADR-0038 ghi chú điều này.
>
> **Quan hệ với ADR-0037.** Làm rõ D11 ("LLM tắt" cho câu tự gõ): không có output LLM nào theo câu hỏi; câu ngữ cảnh
> tính sẵn theo chunk vẫn dùng được (Luật chung 9). Dòng trạng thái của ADR-0037 ghi chú điều này.

## Bối cảnh

- ADR-0038 D4 chốt luật hoà cho BM25 (bằng nhau sau khi làm tròn 6 chữ số thập phân → xếp theo mã chunk, đáp án đúng
  hiện khoảng hạng). Trang `/rag-pipeline` bản đầu (Thy chốt 2026-11-09: đủ phạm vi ADR-0037) có mọi bước, nên engine
  TypeScript cần một đặc tả mà hai người viết độc lập ra cùng thứ hạng.
- Đo trên file demo 2026-11-08 / 09 (câu hỏi gốc, 19 bài):
  - Hoà trong cùng một cách chia (hoà tuyệt đối lẫn do làm tròn 6 chữ số, `src/rag_demo/demo_file.py:71#SCORE_DECIMALS`):
    **0 ở dense, 0 ở cross-encoder**. Hoà do làm tròn trên mọi cách chia gộp lại: dense 7, cross-encoder 0.
  - Haiku chấm số nguyên 0–3: 3.647 / 403 / 185 / 45 trên 4.280 cặp — hoà là chuyện thường. Bật lọc Haiku (bỏ < 2):
    câu 10 còn 0 đoạn ở cả 7 cách chia, câu 5 còn 1 đoạn ở 6 / 7 cách chia.
  - Cross-encoder là logit thô: 4.220 / 4.280 ≤ 0; ở 24 / 77 bộ (câu hỏi, cách chia, bài đáp án) chunk đáp án tốt nhất
    ≤ 0. Dense có 10 cosine < 0. Luật "điểm trên 0" của BM25 không dùng được cho bước khác.
  - Cosine chunk × chunk: cao nhất 0,804, không cặp nào ≥ 0,85 ở cả 7 cách chia (cặp bài gần trùng duy nhất đã bỏ theo
    ADR-0040).
  - 105 / 458 chunk chạm cả post mở đầu lẫn ít nhất một post viết tiếp (212 / 458 nếu đếm chunk chạm từ 2 post bất
    kỳ, kể cả 2 post viết tiếp với nhau — bộ lọc "phần của thread" chỉ phân biệt mở đầu / viết tiếp, nên 105 là số
    liên quan); chỉ cách chia theo post tách sạch.
  - Điểm RRF chỉ phụ thuộc các hạng (nguyên, hoặc lẻ nửa khi là hạng trung bình của nhóm hoà) nên hoà có tính cấu
    trúc (đoạn hạng (3, 7) và (7, 3) bằng nhau tuyệt đối);
    làm tròn 6 chữ số còn có thể gộp những giá trị RRF khác nhau thật.
  - Câu mở rộng (expand) do Haiku viết **không giữ câu gốc**: 0 / 10 câu chứa nguyên câu gốc, câu nào cũng thiếu ít
    nhất một từ của câu gốc. Câu 1 chuyển hẳn sang chủ đề tiền cọc (mất "bật sưởi"); câu 6 (hỏi bằng tiếng Pháp, prompt
    bắt viết tiếng Việt) chỉ giữ 2 từ nội dung "filière", "université" (đo 2026-11-09).
  - Prompt (`src/rag_demo/llm_jobs.py:121#TRANSFORM_SYSTEM`) có đòi "the question plus synonyms": đây là lỗi tuân thủ
    chỉ dẫn của LLM; không sửa prompt vì kết quả đã trả tiền.
  - Nối câu gốc với câu mở rộng thành một chuỗi hỏng câu 1: BM25 chọn chế độ có dấu / bỏ dấu cho cả chuỗi (ADR-0038
    D3), câu mở rộng có dấu kéo cả chuỗi sang chế độ có dấu, 7 / 10 từ không dấu của câu gốc không còn khớp.
  - Đo bằng chính `src/dashboard/src/lib/ragDemo/bm25.ts` (từ commit engine đầu tiên, 2026-11-10: `bm25.ts` +
    `rank.ts`; ảnh chụp hồi quy chạy lại ra đúng các số dưới đây), thước = **số chính của trang** (ADR-0038 D8: câu 3 và 7 lấy
    hạng của bài tìm thấy sau cùng; một vị trí sau phá hoà theo mã chunk), 9 câu có đáp án × 7 cách chia, chuỗi ghép → 2
    danh sách gộp RRF (whole / post / fixed 300 / fixed 500 / fixed 800 / recursive 500 / semantic):
    - Câu 1: 9→3, 12→2, 13→2, 12→4, 10→3, 11→2, 6→1 (RRF tốt hơn ở cả 7 cách chia).
    - Câu 7: 2→4, 5→6, 8→11, 3→4, 2→5, 4→5, 6→11 (RRF **kém** 1–5 hạng ở cả 7 cách chia: danh sách của câu gốc yếu).
    - Câu 6: kém 1 hạng ở post và fixed 800; câu 3: kém 1 hạng ở fixed 300; câu 8: tốt hơn 1 hạng ở semantic; câu 2,
      4, 5, 9: như nhau.
    - Tổng hạng 63 ô (cộng từ chính các ô; thấp hơn là tốt hơn): chuỗi ghép 167, RRF **129**; phương án thứ ba (chuỗi
      ghép, bỏ dấu cả chuỗi khi câu gốc không dấu) 131 — câu 1 thành 8 / 7 / 4 / 4 / 11 / 2 / 1, các câu khác như chuỗi
      ghép. Script đo nằm ngoài repo (như ADR-0038): `data/rag_demo/measure/*.mjs`, trong `data/rag_demo/` (gitignored,
      cạnh file demo chứa chữ bài; sao về thư mục chính cùng `data/rag_demo/` trước khi dọn worktree), chạy từ gốc repo bằng `node --experimental-strip-types --no-warnings <file> "$(pwd)"`
      (`bm25.ts` + `demo.json`, số chính theo ADR-0038 D8).
    - Đây là **số mô tả, không phải đánh giá** (như ADR-0038): 9 câu có đáp án, 63 ô không độc lập (7 cách chia của
      cùng một câu), không có khoảng tin cậy; các tổng hạng không đủ để kết luận phương án nào tốt hơn trên câu hỏi
      khác.
    - Có chunk đáp án nằm trong nhóm hoà (VD câu 3, fixed 800, phương án RRF: 2 chunk trúng của cùng một bài hoà ở [3, 4]), nhưng ở
      cả 126 ô (63 ô × 2 phương án) số chính không đổi theo cách xếp lại trong nhóm hoà — nên một vị trí ở bảng trên
      trùng với khoảng hạng của mục "Hạng của đáp án". Kiểm bằng **khoảng chính xác** (vét cạn mọi cách đặt chunk
      đáp án vào các vị trí của nhóm hoà chứa nó, `exact_ranges.mjs`, đo 2026-11-10): 0 / 126 ô là khoảng thật; ở
      mốc không biến đổi bên dưới 4 / 63 ô (cả 4 ở câu 6). Cách tắt "xếp mọi chunk đáp án lên đầu / xuống cuối nhóm"
      ra cùng kết quả ở cả 189 ô này nhưng **không** đúng định nghĩa nói chung (phản ví dụ ở mục "Hạng của đáp án").
      Hạng của bài phụ (bài không quyết định số chính) vẫn có thể là khoảng. Nhận xét này chỉ cho 2 phương án expand;
      với BM25 trên câu gốc, số chính có thể là khoảng thật (VD câu 6: post [10, 11], fixed 300 [10, 12]).
    - Mốc **không biến đổi** (BM25 trên câu gốc) → expand 2 danh sách + RRF, cùng thước, riêng ô có hoà ghi khoảng hạng
      chính xác theo mục "Hạng của đáp án" (`exact_ranges.mjs`): câu 1: 1→3, 2→2, 1→2, 1→4,
      1→3, 1→2, 1→1 (expand **làm câu 1 kém đi** 0–3 hạng: câu gốc vốn đã đứng đầu ở 6 / 7 cách chia, post hạng 2; "RRF tránh câu 1 mất chủ đề"
      chỉ đúng khi so với chuỗi ghép); câu 6: 8→1, [10, 11]→2, [10, 12]→1, [10, 11]→1, 11→2, [6, 7]→1, 12→1 (giúp rõ);
      câu 7: 6→4, 9→6, 11→11, 7→4, 7→5, 4→5, 16→11 (giúp ở 5 / 7 cách chia, như nhau ở fixed 300, **kém 1 hạng ở
      recursive 500 — cách chia mặc định khi mở trang**); câu 3: như nhau; câu 8: kém 1 hạng ở fixed 300; câu 2, 4, 5,
      9: như nhau. Thy giữ quyết định expand sau khi xem mốc này (2026-11-10). Trang phải hiện đúng điều này ở chế độ A/B khi đặt cả hai bên BM25 (ở mặc định hybrid, bên expand là
      "hybrid rơi về BM25" → "no clear winner", Luật chung 8), không quảng cáo expand là luôn tốt hơn.
  - Dense của câu hỏi biến đổi và của chunk kèm câu ngữ cảnh (mục 2 của 3e) chưa có nên chưa đo. Lúc quyết (định dạng 1)
    file demo chưa có ngày đăng hay topic của bài; định dạng 2 (2026-11-10) đã có — mục "Dữ liệu thêm vào file demo".
- Nguồn hằng số đã kiểm 2026-11-09: RRF k = 60 là giá trị của bài gốc (Cormack, Clarke & Büttcher, SIGIR 2009) và mặc
  định `rank_constant` của Elasticsearch; Qdrant mặc định k = 2 (qdrant.tech, "Hybrid queries"). DBSF theo mô tả của
  Qdrant (cùng trang): (s − (μ − 3σ)) / 6σ, σ là độ lệch chuẩn mẫu, không kẹp vào [0, 1], mọi điểm bằng nhau hoặc một
  điểm → 0,5. Kiểm lại trên mã nguồn Qdrant 2026-11-10 (`lib/segment/src/common/score_fusion.rs` của repo
  qdrant/qdrant, nhánh master): đúng cả 4 điểm, σ chia n − 1, điểm chuẩn hoá của các danh sách cộng lại, đoạn vắng ở
  một danh sách không góp gì; khác duy nhất là cách tính — Qdrant 1 lượt (Welford) bằng số 32 bit, repo 2 lượt bằng số
  64 bit theo Luật chung 5.

## Quyết định

### Luật chung

1. **Thứ tự bước** — mọi "bước trước" dưới đây theo thứ tự này: lọc metadata → tìm (BM25 / dense, mỗi câu con một lần) →
   gộp câu con → trộn BM25 + dense → rerank (top-N) → lọc Haiku → lọc gần trùng → MMR → cắt top-K để hiển thị. Các bước
   lọc (metadata, Haiku, gần trùng) và MMR là công tắc, mặc định tắt; tìm, trộn, rerank là lựa chọn.
2. **Hoà ở điểm liên tục** (BM25, dense, gộp câu con, trộn, cross-encoder): hoà = bằng nhau sau khi làm tròn 6 chữ số; xếp
   theo **mã chunk gốc** của cách chia (không phải vị trí trong danh sách đã lọc); mỗi đoạn mang khoảng hạng `[đầu, cuối]`
   của nhóm hoà. Chỉ BM25 bỏ đoạn điểm 0 — điểm **sau làm tròn** 6 chữ số
   bằng 0 (`src/dashboard/src/lib/ragDemo/rank.ts:50#rankBm25`; trước commit engine đầu tiên (2026-11-10) đây là `rankScores` của `bm25.ts`, hàm
   vừa bỏ điểm 0 vừa xếp hạng; đoạn không khớp từ nào luôn thuộc nhóm này); các bước khác xếp hạng mọi đoạn, kể cả
   điểm ≤ 0 (`src/dashboard/src/lib/ragDemo/rank.ts:27#rankRange`).
3. **Hoà ở bước giữ thứ tự** (rerank Haiku, MMR): cùng điểm thì giữ thứ tự bước trước (sắp xếp ổn định).
4. **Một lựa chọn mỗi loại**: một lựa chọn rerank (không / cross-encoder / Haiku), một lựa chọn trộn BM25 + dense; chỉ
   chọn một bộ tìm thì bỏ qua trộn. Gộp câu con (multi-query, decompose, expand, step-back) luôn bằng RRF và là bước riêng, không tính là
   "trộn lần hai". Với multi-query và decompose: tập câu con = đúng các câu Haiku viết (3 câu multi-query / các câu
   decompose), **không thêm câu gốc**
   (Thy chọn; như mặc định `include_original=False` của LangChain `MultiQueryRetriever`). Danh sách BM25 sau khi gộp câu
   con vẫn là danh sách BM25: đoạn không khớp câu con nào (tổng 0) không có hạng (không vào RRF; ở weighted / DBSF nó
   vẫn nằm trong tập chuẩn hoá với điểm 0 — xem bảng), đáp án như vậy là "not found". Decompose chỉ ra 1 câu con vẫn
   qua bước gộp (điểm RRF), để thang điểm không đổi theo số câu con. Rewrite và HyDE (một câu, thay câu gốc) **không**
   qua bước gộp.
   **Mỗi lần chọn một cách biến đổi** (7 lựa chọn của ADR-0037 D7, kể cả "không biến đổi").
   **Biến đổi một câu** (Thy chọn): rewrite (Ma et al. 2023) và HyDE (Gao et al. 2022) **thay câu gốc** ở bước tìm. HyDE
   dùng cho BM25 là biến thể, bài gốc chỉ dùng cho dense — trang ghi rõ. **Expand**: tìm **2 lần** — câu gốc và câu mở
   rộng, mỗi câu tự chọn chế độ dấu theo ADR-0038 D3 — rồi qua bước gộp câu con (RRF), như step-back. Thy chọn sau khi
   xem bảng đủ 63 ô ở Bối cảnh (đo bằng số chính của trang): RRF tránh được câu 1 mất chủ đề ở mọi cách chia (so với chuỗi ghép; so với
   không biến đổi thì câu 1 vẫn kém 0–3 hạng — mốc ở Bối cảnh), đổi lại
   câu 7 kém 1–5 hạng ở mọi cách chia, câu 6 và câu 3 kém 1 hạng ở vài cách chia; tổng hạng 129, thấp hơn phương án
   "chuỗi ghép bỏ dấu" 2 hạng (131; số mô tả, không phải đánh giá — xem Bối cảnh), nhất quán với step-back. Ý của Query2doc (Wang et al. 2023: giữ câu gốc trong truy vấn, nối bằng code) được giữ,
   nhưng ở dạng 2 danh sách thay vì 1 chuỗi. **Step-back** (Zheng et al. 2023) tìm bằng **cả câu
   gốc lẫn câu tổng quát**: bài gốc và mẫu LangChain đưa cả hai bộ kết quả cho LLM; trang này không có LLM viết câu trả
   lời nên gộp 2 danh sách bằng bước gộp câu con (RRF) — phần gộp là lựa chọn của repo, theo luật gộp câu con ở trên.
5. **Điểm truyền đi đã làm tròn**: mỗi bước xuất điểm làm tròn 6 chữ số; bước sau dùng đúng điểm đó. Giá trị trung
   gian trong một bước (m của weighted, điểm chuẩn hoá DBSF, rel của MMR) giữ số thực 64 bit; giá trị MMR ở mỗi lượt
   tính bằng số thực rồi làm tròn 6 chữ số **chỉ để so hoà** (lượt chọn đoạn có giá trị đã làm tròn lớn nhất, bằng
   nhau → đoạn đứng trước ở bước trước); điểm xuất của mỗi bước làm tròn, bằng đúng một hàm của engine
   (`src/dashboard/src/lib/ragDemo/rank.ts:11#roundScore`, `Number(x.toFixed(6)) + 0`: giá trị đúng nửa ô làm tròn ra xa
   số 0, `+ 0` đổi −0 thành 0 như `_score` của Python). Giá trị mong đợi viết bằng Python trong test (đo
   2026-11-10, Python 3.12.4 trên Windows, node):
   - Khớp từng bit với engine chỉ được bảo đảm cho `+ − × ÷` và căn bậc hai (IEEE 754 bắt các phép này làm tròn
     đúng). Bình phương viết `d * d` ở cả hai ngôn ngữ (Python `x ** 2` khác `x * x` ở 84 / 200.000 số `random.seed(0)` + `random.uniform`,
     đều trong [−10, 10]). Phép có `log` (IDF của BM25) không khớp bit: `Math.log` của node và `math.log` của Python
     khác bit cuối ở 1.519 / 20.100 đầu vào IDF (N 1–200, số đoạn chứa từ 1–N; số 0 không bao giờ tới IDF vì từ không
     có trong đoạn nào không được cộng; đo lại 2026-11-10, node 24.15 — bản đầu ghi 1.526 / 20.300 vì tính cả số 0) —
     điểm BM25 thô không đóng cứng từ
     Python: so sau khi làm tròn 6 chữ số cho lệch ≤ 1e-6 (lệch bit cuối sát mép ô làm tròn đổi được chữ số cuối),
     hoặc so trong sai số với bài giải mẫu độc lập `bm25s` như ADR-0038 D5;
     không lấy giá trị mong đợi từ chính engine (tham chiếu chung code thì mang chung lỗi).
   - Làm tròn bằng `Decimal(x).quantize(Decimal("1e-6"), ROUND_HALF_UP)` với x là **số thực** (giá trị nhị phân
     chính xác) — không `round` (làm tròn nửa về số chẵn: `round(1 / 128, 6)` = 0,007812, `toFixed` và cách này cho
     0,007813; 1 / 128 = 1 / (60 + 68) là một số hạng RRF có thật), không `Decimal(str(x))` (5e-7 → 0,000001, còn
     `toFixed` cho 0,000000 vì giá trị nhị phân thật nhỏ hơn 5e-7).
   - Cộng bằng vòng lặp trái → phải (`acc = acc + x`), không `sum` (từ Python 3.12 cộng có bù sai số:
     `sum([0.1] * 10)` = 1.0, vòng lặp và JS = 0.9999999999999999), không `math.fsum`, `statistics` hay numpy.
   - Mọi số làm tròn trong file demo (dense, cross-encoder, cosine chunk × chunk) cũng theo luật này: `assemble`
     (`src/rag_demo/demo_file.py:213#_score`) dùng ROUND_HALF_UP (giữ `+ 0.0` để −0 thành 0) từ định dạng 2
     (2026-11-10; định dạng 1 dùng `round`). Đo 2026-11-10: 2 / 4.280 logit thô rơi đúng nửa ô, 1 trong đó cho kết
     quả khác — −11,0390625, câu 9, đoạn 403: định dạng 1 ghi −11,039062, luật này cho −11,039063; thứ hạng không
     đổi. Dựng lại sang định dạng 2: đúng ô đó đổi, `rounding_ties` không đổi (dense 7, cross-encoder 0).

   Giá trị thanh kéo (α, λ, ngưỡng gần trùng, k1, b) = số nguyên i / 100 trước khi dùng, và
   1 − α, 1 − λ, 1 − b tính là (100 − i) / 100, để bước 0,1 không thành 0,30000000000000004. Trước commit engine đầu tiên
   (2026-11-10) `scoreDocs` nhận b rồi tự tính `1 - b`; từ commit đó nó nhận cả 1 − b tính sẵn từ vị
   trí thanh kéo (`src/dashboard/src/lib/ragDemo/bm25.ts:89#bm25Params`; α qua `rank.ts:69#slider`) (đo 2026-11-09 trên lưới thanh kéo b 0–1 bước 0,05 × k1 0–3 bước 0,05 × 10 câu gốc
   × 7 cách chia × mọi chunk: 6 / 21 giá trị b cho `1 - i/100` khác `(100 - i)/100`; 149.406 / 5.866.980 điểm thô
   khác (2,5 %), 0 điểm khác sau làm tròn 6 chữ số — không đổi thứ hạng nào, nhưng engine và test đối chiếu cần một
   luật duy nhất). Khoảng và bước của thanh kéo (lựa
   chọn thiết kế; không đổi thứ hạng của một cấu hình cho trước): α, λ, b 0–1 bước 0,05; k1 0–3 bước 0,05; ngưỡng gần
   trùng 0,50–1,00 bước 0,01; N 5–50 bước 5; K 1–20 bước 1. Phép cộng nhiều số hạng theo thứ tự cố định: câu con theo thứ tự trong file (expand /
   step-back: câu gốc trước), BM25 trước dense; μ, σ của DBSF tính 2 lượt theo thứ tự mã chunk, chia sau khi cộng:
   `acc = acc + x` rồi `mu = acc / n`; `d = x - mu`, `acc2 = acc2 + d * d` rồi `sigma = Math.sqrt(acc2 / (n - 1))`.
6. **Sau mỗi bước lọc**: hạng đánh lại theo vị trí; nhóm hoà = các thành viên còn lại, khoảng tính lại theo vị trí mới;
   còn 1 thành viên thì hết hoà. Nhóm hoà là tập thành viên mang theo từ bước sinh ra nó, không tính lại bằng cách so
   điểm trên danh sách ghép (VD khối đã rerank + đuôi "not reranked"). Danh sách rỗng sau bất kỳ bước nào (kể cả BM25
   khi câu tự gõ không khớp từ nào) → các bước sau bỏ qua, trang ghi "no passages left after: <bước>". Ngoại lệ ở hybrid:
   một bộ tìm rỗng thì khối của nó ghi "no passages", trộn vẫn chạy với bộ kia (RRF góp 0, weighted m = 0, DBSF 0,5);
   chỉ dừng khi cả hai rỗng. Tương tự ở bước gộp câu con: một câu con rỗng góp 0, chỉ dừng khi mọi câu con rỗng (trang
   ghi "no passages left after: sub-query merge").
7. **Rerank, lọc Haiku luôn chấm theo câu hỏi gốc** (file chỉ có điểm đó), kể cả khi bước tìm dùng câu hỏi biến đổi;
   trang nói rõ.
8. **Phần còn chờ** (`provenance.pending`, mục 2 của 3e): dense của câu hỏi biến đổi và dense của chunk kèm câu ngữ cảnh.
   Câu ngữ cảnh tính theo **công tắc có hiệu lực**: ở cách "không chia" công tắc coi là tắt (chunk đã là cả bài, ADR-0039
   D2). Hai tên dùng thống nhất trong ADR và hợp đồng UI. Cả hai được xác định **theo cấu hình, trước khi chạy** (Thy
   chọn): bước 3 của A/B xét theo cấu hình của bên kia, không theo việc dense có thực sự ra danh sách. Riêng "dense
   trần cần phần còn chờ" có trạng thái "in progress", và trạng thái này thắng mọi trạng thái của bước đứng trước (VD
   lọc metadata đã loại đáp án vẫn hiện "in progress"; khối lọc vẫn hiện số đoạn còn lại, trạng thái chung là "in
   progress"); "hybrid rơi về BM25" vẫn có hạng (gạch dưới).
   - **"hybrid rơi về BM25"** = hybrid + biến đổi câu hỏi, hoặc hybrid + câu ngữ cảnh có hiệu lực → **chỉ chạy BM25**,
     khối trộn ghi rõ "dense … in progress — showing BM25 only" (Thy chọn); không lấy dense của câu gốc / chữ gốc thế vào;
     rerank, lọc, MMR, top-K vẫn chạy trên danh sách BM25 đó. Hạng của đáp án tính trên danh sách cuối như mọi cấu hình;
     nhãn "BM25 only" chỉ báo bước tìm không có dense. BM25 rỗng thì "no passages left after: BM25" (không có bộ kia để
     trộn); nếu biến đổi đi qua bước gộp câu con và mọi câu con rỗng thì nhãn theo Luật chung 6 ("no passages left
     after: sub-query merge").
   - **"dense trần cần phần còn chờ"** = chọn dense không trộn, kèm biến đổi câu hỏi hoặc câu ngữ cảnh có hiệu lực →
     khối dense ghi "in progress", không có danh sách; các bước sau bỏ qua; đáp án mang trạng thái "in progress".

   Chung cho cả hai: lọc gần trùng và MMR **luôn dùng cosine chunk × chunk của chữ gốc** (Thy chọn, lựa chọn thiết kế:
   đo độ trùng / đa dạng trên nội dung người đọc thấy, câu ngữ cảnh chỉ hỗ trợ tìm), nên không phụ thuộc phần còn chờ.
   File định dạng 1 ghi 3 mục còn chờ; mục thứ ba (cosine chunk × chunk kèm câu ngữ cảnh) vì vậy không dùng, đã bỏ
   khỏi `PENDING_PARTS` ở định dạng 2 (2026-11-10) và trang không hiện nó. A/B với hai cấu hình này: mục "Hạng của đáp án".
9. **Câu tự gõ** (ADR-0037 D11): chỉ BM25. Vẫn dùng được: lọc metadata, lọc gần trùng, MMR (rel = điểm BM25), cắt
   top-K, chọn cách chia, thanh kéo k1 / b, công tắc câu ngữ cảnh (câu ngữ cảnh tính sẵn theo chunk, không theo câu
   hỏi). Tắt: dense, trộn, biến đổi câu hỏi, rerank, lọc Haiku (không có điểm tính sẵn cho câu tự gõ); trang ghi lý do.
   "LLM tắt" của ADR-0037 D11 hiểu là không có output LLM nào theo câu hỏi; câu ngữ cảnh là output LLM tính sẵn theo
   chunk nên vẫn dùng được.
10. **A/B** so 2 cấu hình trên **cùng một câu hỏi**.

### Từng bước

| Bước | Danh sách vào | Điểm, thang | Chuẩn hoá / hằng số | Hoà | Đoạn vắng mặt / bị loại |
|---|---|---|---|---|---|
| Lọc metadata | Mọi chunk của cách chia | — | Topic (tên tiếng Anh), tháng đăng của post mở đầu (giờ Paris, ADR-0034; tập 19 bài chỉ có 2 tháng — trang nói thật), phần của thread: chunk **chạm** phần nào (giao khác rỗng giữa hai khoảng nửa mở `[start, end)`, khoảng của post lấy từ `units[].posts[].start/end`) thì khớp phần đó (chunk vắt qua khớp cả hai; trang ghi số chunk vắt qua ở cách chia đang chọn). Mỗi trường chọn nhiều giá trị: **OR trong một trường, AND giữa các trường**, trường không chọn = không lọc, "Unclustered" là một giá trị topic (lựa chọn thiết kế, quy ước của tìm kiếm theo mặt — faceted search) | — | Đáp án bị loại → "filtered out at: metadata filter" |
| BM25 | Chunk còn lại; bật câu ngữ cảnh thì câu ngữ cảnh (`passages[].context`, chữ gốc — không phải `context_en`) đặt **trước** chunk, ngăn bằng một dấu xuống dòng (như Anthropic "Contextual Retrieval", 2024); chunk là cả bài thì không có câu ngữ cảnh (ADR-0039 D2): `context` = null → giữ chunk trần | Lucene ≥ 0 (ADR-0038) | **Thống kê của cả kho** (IDF, độ dài trung bình trên mọi chunk của cách chia đang chọn, kèm câu ngữ cảnh khi công tắc có hiệu lực) — lọc chỉ loại đoạn, không đổi điểm (như Elasticsearch / Lucene) | Luật chung 2 | Điểm 0 không được xếp hạng; mọi chunk trúng điểm 0 → "not found" |
| Dense | Chunk còn lại | Cosine, [−1, 1] | Câu hỏi biến đổi hoặc bật câu ngữ cảnh: Luật chung 8 | Luật chung 2 | Mọi đoạn có hạng |
| Gộp câu con | Một danh sách mỗi câu con, mỗi bộ tìm | Σ 1 / (60 + r) | RRF như hàng dưới (RAG-Fusion); multi-query / decompose: không thêm câu gốc; expand / step-back: câu gốc + câu biến đổi (Luật chung 4) | Luật chung 2 | BM25: tổng 0 → không có hạng (Luật chung 4) |
| Trộn RRF | Hai danh sách đầy đủ | Σ 1 / (k + r) | **k = 60** (Bối cảnh: bài gốc + Elasticsearch). r của nhóm hoà = **hạng trung bình** của khoảng (fractional ranking, như `scipy.stats.rankdata(method="average")`) | Luật chung 2 | Đoạn BM25 điểm 0 góp 0 vào tổng |
| Trộn weighted | Hai danh sách đầy đủ | α·m(dense) + (1 − α)·m(BM25) | m = min-max `(x - min) / (max - min)` trên danh sách vào, **tính cả điểm BM25 = 0**; max = min thì m = 0 (lựa chọn thiết kế: danh sách không phân biệt gì thì không góp vào điểm trộn). Thanh kéo α, **mặc định 0,5** — lựa chọn thiết kế: trọng số bằng nhau, không ưu tiên bên nào | Luật chung 2 | — |
| Trộn DBSF | Hai danh sách đầy đủ | Tổng 2 điểm đã chuẩn hoá | Mỗi danh sách: `(x - (mu - 3*sigma)) / (6*sigma)`, đúng biểu thức này (không viết lại thành `(x - low) / (high - low)`, lệch ở bit cuối); σ mẫu; không kẹp; mọi điểm vào bằng nhau (so trên điểm đã làm tròn, không so σ = 0 vì sai số số thực) hoặc 1 phần tử → 0,5 — công thức theo Qdrant (Bối cảnh). Tập tính μ, σ = **mọi chunk còn lại, kể cả điểm BM25 = 0** (lựa chọn thiết kế; Qdrant tính trên kết quả trả về của từng truy vấn con) | Luật chung 2 | — |
| Rerank cross-encoder | **Top-N** của bước trước (thanh kéo N, mặc định 20 — lựa chọn thiết kế); N ≥ độ dài danh sách → cả danh sách | Logit thô | — | Luật chung 2, trong khối đã rerank | Nhóm hoà vắt mốc N vào cả nhóm. Đoạn ngoài N giữ thứ tự cũ, nối sau khối đã rerank, hạng đánh tiếp, nhãn "not reranked"; đuôi giữ nguyên điểm, nhóm hoà và khoảng hạng của bước trước (vị trí không đổi vì khối đầu đã lấy trọn nhóm vắt mốc N), dòng đuôi hiện điểm của bước trước. Đáp án không có trong danh sách vào (VD BM25 điểm 0) giữ trạng thái của bước tìm ("not found") |
| Rerank Haiku | Như trên | Nguyên 0–3 | — | Luật chung 3. Khoảng hạng chỉ khi hai đoạn cùng điểm Haiku **và** bước trước báo chúng hoà: khoảng = các vị trí mới mà nhóm {cùng điểm Haiku, cùng nhóm hoà trước} chiếm (luôn liền nhau, vì sắp xếp ổn định). VD bước trước hoà ở 3–4, cả hai được 2 điểm, sau rerank ở 1–2 → "1–2" | Như trên. Haiku xếp **mọi** ứng viên trong khối rerank (top-N), kể cả điểm dưới mức giữ; "keep / drop" (giữ khi ≥ 2, `src/rag_demo/llm_jobs.py:46#RERANK_KEEP_MIN_SCORE`) là nhãn |
| Lọc Haiku | Cả danh sách, kể cả "not reranked" | Điểm Haiku đã chấm sẵn | Bỏ đoạn < 2. **Bước độc lập**: bật được với mọi lựa chọn rerank | Luật chung 6 | Đáp án bị bỏ → "filtered out at: Haiku relevance filter" |
| Lọc gần trùng | Cả danh sách | Cosine chunk × chunk | Đi theo thứ tự, bỏ đoạn có cosine ≥ ngưỡng với một đoạn **đã giữ** đứng trước. Thanh kéo ngưỡng, **mặc định 0,95** — lựa chọn thiết kế, giả thuyết "gần như sao chép", chưa hiệu chuẩn; trang nói thật: trên 19 bài cosine cao nhất 0,804, không cặp nào ≥ 0,85, nên mặc định không bỏ gì; hiện số đoạn bị bỏ | Luật chung 6 | Đáp án bị bỏ → "filtered out at: near-duplicate filter" |
| MMR | Cả danh sách; khi có rerank: **chỉ khối đã rerank**, đuôi "not reranked" giữ nguyên phía sau | λ·rel − (1 − λ)·max cos(đoạn, đoạn đã chọn); lượt đầu phần phạt = 0 | rel = điểm của **bước chấm điểm gần nhất** (tìm / gộp / trộn / rerank — bỏ qua các bước lọc), min-max `(x - min) / (max - min)` về [0, 1] trên danh sách vào MMR (lựa chọn thiết kế: đưa các thang điểm khác nhau về cùng thang với cosine); max = min thì rel = 0 (lựa chọn thiết kế, như weighted). Phần phạt dùng cosine chunk × chunk của chữ gốc (Luật chung 8). Công thức: Carbonell & Goldstein 1998; **λ mặc định 0,5** theo `lambda_mult` của LangChain, thanh kéo. Chọn tham lam tới **hết danh sách** rồi mới cắt top-K | Bằng giá trị (6 chữ số) ở một lượt → chọn đoạn đứng trước ở bước trước; dòng MMR hiện giá trị MMR lúc được chọn (làm tròn 6 chữ số; lựa chọn thiết kế); đoạn được chọn mang **một hạng + nhãn "tied at this pick"** kèm số đoạn khác cùng giá trị, không tính chính nó (VD "tied with 2 others") (không khoảng hạng: giá trị MMR đổi sau mỗi lượt nên nhóm hoà không chắc liền nhau) | Danh sách 0 hoặc 1 đoạn → giữ nguyên |
| Cắt top-K | Danh sách cuối | — | Thanh kéo K, **mặc định 10** — lựa chọn thiết kế. Nhóm hoà vắt qua mốc K được hiện **cả nhóm** (như mốc N), các dòng sau K mang nhãn "tied across the cut" | — | Hạng của đáp án tính trên **cả danh sách trước khi cắt**; ngoài K hiện "rank 30 (outside top 10)"; khoảng hạng vắt qua K → tính là trong top-K khi đầu khoảng ≤ K |

### Hạng của đáp án (thay một phần ADR-0038 D8)

- Mọi khoảng hạng của đáp án là **[nhỏ nhất, lớn nhất] của giá trị đó trên mọi cách xếp lại các đoạn bên trong các nhóm
  hoà của danh sách cuối** (thứ tự giữa các nhóm giữ nguyên; các bước trước dùng thứ tự theo mã chunk như Luật chung 2).
  Ngoại lệ: chunk được chọn ở một lượt MMR có hoà mang một hạng + nhãn "tied at this pick" (bảng, hàng MMR), so A/B coi
  là một số. Từ đó:
  - Hạng một bài = chunk trúng tốt nhất. VD 2 chunk trúng của cùng một bài cùng ở nhóm hoà [3, 4] → hạng bài là 3 (không
    phải [3, 4]).
  - Câu 3 và 7 (cần 2 bài; số chính = hạng của bài tìm thấy sau cùng): VD X và Y cùng nằm trong nhóm hoà [5, 6] → số chính
    là 6.
  - Nhiều chunk của nhiều bài trong cùng nhóm: VD nhóm hoà [5, 7] = {X1, X2, Y1} → số chính **[6, 7]** (X lên đầu thì Y
    đứng 6; Y xuống cuối thì 7). Không tính bằng cách xếp mọi chunk đáp án lên đầu / xuống cuối nhóm (cả hai lượt ra 7).
  - Công thức đóng (hệ quả của định nghĩa; khớp vét cạn ở ví dụ trên và 189 ô có thật, đo 2026-11-10 — nhưng ở 189 ô
    đó chunk đáp án nằm trong nhóm hoà ở 16 ô, mỗi ô tối đa 4 cách đặt, và không nhóm hoà nào chứa chunk đáp án của 2
    bài: phần công thức cho nhiều bài trong một nhóm chỉ được kiểm bằng ví dụ dựng tay). Ở đây "nhóm"
    gồm cả **nhóm 1 phần tử** (vị trí không hoà) — khác chữ "nhóm hoà" ở Luật chung 6. Mỗi bài u lấy
    nhóm sớm nhất chứa chunk trúng của nó, vị trí [a_u, b_u], c_u = số chunk trúng của u trong nhóm đó → hạng bài u
    = [a_u, b_u − c_u + 1]. Số chính câu 3 / 7: đầu khoảng = max của (a_g + k_g − 1) qua **chỉ các nhóm g là nhóm sớm
    nhất của ít nhất một bài**, k_g = số bài có nhóm sớm nhất là g (nhóm không phải nhóm sớm nhất của bài nào không
    tính); cuối khoảng = max qua u của (b_u − c_u + 1).
- "Not found" chỉ có ở BM25 (và ở rerank khi đáp án vắng trong danh sách vào rerank, VD BM25 điểm 0 — giữ trạng thái của bước tìm). Bước khác đáp
  án luôn có hạng, trừ khi một bước lọc loại nó — trang ghi bước đã loại chunk trúng cuối cùng của bài (BM25 bỏ đoạn
  điểm 0 cũng tính là một bước loại: "not found" — khi danh sách chỉ do BM25 tìm, kể cả "hybrid rơi về BM25"; ở hybrid
  thật đoạn BM25 điểm 0 góp 0 vào điểm trộn nhưng vẫn có hạng nhờ dense) — hoặc ở cấu hình "dense trần cần phần còn chờ" ("in progress",
  Luật chung 8; thắng mọi trạng thái của bước lọc đứng trước). Ở "hybrid rơi về BM25" đáp án có hạng trên danh sách cuối như mọi cấu hình, kèm nhãn "BM25 only".
- Câu 3 và 7 thiếu một bài (không có hạng) → số chính = trạng thái của bài thiếu ("not found" / "filtered out at: …"),
  hạng của bài kia vẫn hiện bên dưới. Thiếu cả hai bài với 2 trạng thái khác nhau → số chính = trạng thái của bước đứng
  sau trong thứ tự bước; trạng thái từng bài vẫn hiện bên dưới.
- So A/B (cùng một câu hỏi), xét **theo thứ tự**, dừng ở bước đầu tiên áp được:
  1. Câu không có đáp án (câu 10, câu tự gõ): **không phán quyết** (Thy chọn); mỗi bên hiện số đoạn còn lại (đếm
     **trước** khi cắt top-K; danh sách rỗng ghi "0 passages"; bên "in progress" ghi "in progress") và đoạn đứng đầu
     (vị trí 1 của danh sách cuối, kèm nhãn "tied" theo nhóm hoà của danh sách đó hoặc "tied at this pick" ở MMR;
     danh sách rỗng thì không có) — đúng mục đích câu 10:
     bộ lọc làm rỗng danh sách là đúng khi không bài nào trả lời.
  2. Một bên "in progress" → **"no clear winner"**.
  3. Một bên là **"hybrid rơi về BM25"** và bên kia có dense thật chạy (hybrid thật hoặc dense trần) → **"no clear
     winner"**, kèm nhãn "<bên đó> used BM25 only" và gợi ý đặt cả hai bên BM25 để thấy tác dụng riêng của biến đổi (Thy
     chọn: không gán nhầm nguyên nhân). Một bên rơi về BM25 mà bên kia là BM25 thật, hoặc cả hai bên cùng rơi về
     BM25 → so bình thường, giữ nhãn "BM25 only" ở bên rơi về. Khác bộ tìm do người xem tự chọn (VD BM25 so với hybrid thật, BM25 so với dense) → sang bước 4–5 như
     thường.
  4. Một bên có hạng, bên kia "not found" / "filtered out" → bên có hạng thắng; cả hai không có hạng → "no clear
     winner".
  5. So cả khoảng: hai khoảng chồng nhau (tính cả hai hạng bằng nhau và hai khoảng chung một đầu mút, VD [3, 4] với
     [4, 5]) → "no clear winner"; không chồng nhau → bên hạng nhỏ hơn thắng.

### Mũi tên đổi hạng giữa hai bước (Thy chọn)

- Mũi tên **chỉ ở 2 bước thật sự xếp lại danh sách: rerank và MMR** (Thy chọn). Mũi tên = chênh vị trí của đoạn giữa
  danh sách bước đó nhận vào và danh sách nó xuất ra; độ lớn = vị trí vào − vị trí ra (vị trí sau phá hoà theo mã
  chunk / sắp xếp ổn định), khoảng hạng chỉ dùng để quyết có vẽ hay không. Hai khoảng hạng chồng nhau (cùng định nghĩa "chồng nhau" ở mục A/B)
  → không vẽ (chưa chắc đã đổi). Ở MMR vị trí ra luôn là một số, kể cả đoạn "tied at this pick" (bảng, hàng MMR):
  chỉ khoảng của danh sách vào được xét chồng nhau. Đuôi "not reranked" → không mũi tên.
- Không mũi tên ở: bước tìm (không có danh sách trước để so), bước lọc và cắt top-K (chỉ bỏ bớt đoạn — trang hiện số
  đoạn bị bỏ), gộp câu con và trộn (nhận nhiều danh sách — trang hiện hạng ở từng danh sách vào ngay cạnh hạng sau khi
  gộp / trộn).

### Dữ liệu thêm vào file demo

- Mỗi bài ghi **tháng đăng** của post mở đầu (giờ Paris) và **topic** (mã + tên tiếng Anh; bài chưa vào cụm ghi
  "Unclustered" — gồm bài nhiễu và bài không có trong nhãn của lần gom cụm đó), đọc từ `data/threads.db` của thư mục chính (`--db`, mở chỉ đọc — cùng cách các lệnh dựng đang dùng).
  Topic lấy từ **lần gom cụm mới nhất** trong DB lúc `assemble` (cùng lần trang `/topics` hiện tại thời điểm đó) — ảnh
  chụp lúc dựng file: `provenance` ghi mã lần gom cụm đã dùng. Tăng `DEMO_FILE_FORMAT` lên 2, nên `publish`
  từ chối file cũ thiếu 2 trường này (chốt định dạng sẵn có). Không gọi API, không tốn tiền.

### Mặc định khi mở trang (lựa chọn thiết kế)

- Câu hỏi 1, không biến đổi câu hỏi, câu ngữ cảnh tắt, cách chia recursive 500, tìm BM25 + dense trộn RRF, chưa
  rerank, mọi bước lọc và MMR tắt, K = 10, N = 20
  (dùng khi bật rerank), α = 0,5, λ = 0,5, ngưỡng gần trùng 0,95. Người xem bắt đầu từ "hybrid search" phổ biến rồi tự
  bật thêm từng bước.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Dense / cross-encoder: theo thứ tự đoạn, không ghi hoà | Mỗi đoạn một hạng | Thứ tự là quy ước, không do điểm | Thy chọn khoảng hạng |
| Haiku: khoảng hạng cho cả nhóm cùng điểm | Trung thực với điểm Haiku | Khoảng rộng hàng chục hạng, khó đọc, khó so A/B | Thy chọn giữ thứ tự bước trước |
| Haiku: phá hoà bằng điểm cross-encoder | Mỗi đoạn một hạng | Trộn 2 bộ chấm, người đọc không biết hạng do bộ nào | Không đưa ra |
| RRF: hạng đầu khoảng / vị trí theo mã chunk khi hoà | Đơn giản | Ưu ái nhóm hoà / để mã chunk lọt vào điểm trộn | Thy chọn hạng trung bình |
| Rerank toàn bộ, không top-N | Không có mốc cắt | Không giống pipeline thật, mất bài học "đáp án ngoài N thì rerank không cứu được" | Thy chọn thanh kéo N |
| Haiku rerank luôn bỏ đoạn "drop" / lọc Haiku chỉ khi rerank Haiku | Gọn | 4.050 / 4.280 cặp điểm 0–1: danh sách còn rất ít đoạn; trộn 2 vai vào một lựa chọn | Thy chọn nhãn + bước lọc độc lập |
| MMR trước rerank | Đa dạng hoá sớm | Rerank có thể xếp các đoạn gần giống lại cạnh nhau | Thy chọn MMR sau rerank |
| MMR cổ điển: rel = cosine câu hỏi × đoạn | Đúng công thức gốc, cùng không gian embedding | Xoá tác dụng của rerank đứng trước | Thy chọn điểm bước trước |
| MMR hoà: khoảng gần đúng t … t + n − 1 | Nhìn giống bước khác | Có thể sai so với vị trí thật | Thy chọn một hạng + nhãn "tied" |
| Lọc gần trùng mặc định theo dữ liệu (0,75) | Thấy tác dụng ngay | Cặp 0,75 không phải bản trùng thật, dễ hiểu nhầm | Thy chọn 0,95 + nói thật |
| Metadata chỉ post mở đầu / viết tiếp | Không sửa `assemble` | Chỉ một trường, nghèo | Thy chọn thêm tháng + topic |
| Phần của thread theo chữ đầu chunk | Mỗi chunk một phần | Lọc "post viết tiếp" ở cách "không chia" ra 0 chunk dù bài có post viết tiếp | Thy chọn "chạm là khớp" |
| BM25 tính lại trên kho đã lọc | Như index riêng mỗi topic | Điểm đổi theo bộ lọc, khó tách tác dụng của lọc | Thy chọn giữ thống kê cả kho |
| Expand: nối câu gốc + câu mở rộng một lần thành một chuỗi (ý của Query2doc, không đúng hệt dạng của bài gốc) | Một lần tìm | Chế độ dấu chọn cho cả chuỗi làm câu 1 mất chủ đề; tổng hạng 63 ô 167 | Thy chọn 2 danh sách + RRF (129), sau khi xem hạng trên chính 9 câu |
| Expand: chuỗi ghép, bỏ dấu cả chuỗi khi câu gốc không dấu | Câu 1 khá hơn chuỗi ghép thường | Thêm một luật dấu riêng cho một biến đổi; tổng hạng 131 | Như trên |
| Câu con: lấy điểm cao nhất | Không trộn 2 lần | Điểm BM25 của câu khác độ dài không so trực tiếp được | Thy chọn RRF qua câu con |
| Mặc định BM25 trần | Dễ hiểu từng bước | Lần đầu nhìn thấy kết quả kém hơn | Thy chọn hybrid RRF |

## Hệ quả

- **Code (PR 1, cùng nhánh):** engine `src/dashboard/src/lib/ragDemo/` theo đúng đặc tả trên. Đã làm ở commit engine
  đầu tiên (2026-11-10): tách phần lọc điểm ≤ 0 khỏi hàm khoảng hạng `rankScores` cũ của `bm25.ts` (đúng cho BM25, sai
  cho bước khác) thành `rankRange` (mọi bước, phá hoà theo mã chunk gốc) + `rankBm25`; đổi chữ ký `scoreDocs` /
  `searchBm25` để nhận 1 − b tính theo Luật chung 5 và sửa test đối chiếu `bm25s` (`tests/rag_demo/test_bm25_engine.py`)
  theo; bộ đọc file, bước tìm, gộp câu con, trộn. Commit engine thứ hai (2026-11-10): rerank top-N, ba bước lọc, MMR, cắt
  top-K, hạng của đáp án (công thức đóng, `src/dashboard/src/lib/ragDemo/answer.ts:64#goldAnswer`), so A/B, mũi tên. `assemble` ghi tháng đăng + topic của mỗi bài, dựng lại file. Hai loại test:
  test luật dùng **dữ liệu tổng hợp** với giá trị mong đợi viết tay, chạy được trên CI; test trên file demo thật
  (`data/rag_demo/demo.json`, gitignored vì chứa chữ bài) chỉ chạy ở máy có file (bỏ qua khi thiếu file) và là
  **ảnh chụp hồi quy** của số đo ở Bối cảnh — các số đó sinh từ chính engine (`bm25.ts`, nay cùng `rank.ts`), không phải bài giải độc lập. Ảnh chụp
  hồi quy chạy đúng cấu hình đã đo — BM25 cả hai bên, không rerank, mọi bước lọc và MMR tắt, k1 = 1,2, b = 0,75 — và
  so số chính theo mục "Hạng của đáp án" (khoảng hạng khi hoà): expand 2 danh sách + RRF ở 63 ô và mốc không biến đổi
  ở 63 ô (bảng ở Bối cảnh); cột chuỗi ghép không chụp (phương án đã bỏ, engine không có đường chạy này). Mọi mục khác
  dưới đây là test luật. Test đóng cứng giá
  trị mong đợi (không đọc nhánh từ code đang test) cho: hoà ở mỗi bước, điểm âm, hạng trung bình vào RRF, gộp câu con,
  min-max có điểm 0 và max = min, DBSF σ = 0 và 1 phần tử, nhóm hoà vắt mốc N, đáp án ngoài danh sách rerank, khoảng hạng
  sau lọc, danh sách rỗng (câu không có đáp án + lọc Haiku, như câu 10), MMR hoà ở một lượt, chunk vắt qua 2 phần của thread, đáp án bị từng bộ
  lọc loại, 3 ví dụ gộp hạng ở mục "Hạng của đáp án" (kể cả {X1, X2, Y1} ở [5, 7] → [6, 7]), câu 3 / 7 thiếu một hoặc cả hai bài, khoảng vắt qua K, A/B khoảng
  chồng nhau, step-back (câu gốc + câu tổng quát), decompose 1 câu con, lọc metadata nhiều trường, dense trần + phần
  còn chờ, câu tự gõ + câu ngữ cảnh, giá trị đúng nửa ô làm tròn (1 / (60 + 68) → 0,007813; ở Python: −11,0390625 →
  −11,039063, Luật chung 5), lọc gần trùng giữ đoạn đứng trước, rel của MMR lấy từ bước chấm điểm gần nhất, rewrite /
  HyDE thay câu gốc, expand = 2 danh sách (câu gốc + câu mở rộng, mỗi câu tự chọn chế độ dấu), đuôi
  "not reranked" có nhóm hoà,
  DBSF mọi điểm bằng nhau, A/B câu không có đáp án, mũi tên chỉ ở rerank / MMR và không vẽ khi khoảng chồng nhau,
  hybrid một bộ tìm rỗng, hybrid rơi về BM25 + A/B (bên kia hybrid thật / BM25 thật / cũng rơi về BM25; BM25 so với
  hybrid thật do người xem chọn), công tắc câu
  ngữ cảnh ở cách "không chia", thanh kéo 0,1 / 0,3, dense trần cần phần còn chờ + lọc metadata loại đáp án → "in progress". Mục 2 của 3e (sau PR 1, chưa làm): embed chunk kèm câu ngữ cảnh theo đúng chuỗi BM25 dùng (câu ngữ cảnh, xuống dòng, chunk; `context =
  null` → chunk trần), và embed `transforms.expand` riêng (không
  embed chuỗi ghép), vì expand đi theo 2 danh sách. Phần định dạng file thì đã làm, ở commit dựng file định dạng 2 (2026-11-10): nâng
  `DEMO_FILE_FORMAT` lên 2, bỏ mục thứ ba khỏi `PENDING_PARTS` (Luật chung 8) và đổi `_score` sang ROUND_HALF_UP (Luật chung 5). Hằng 6 chữ số có 2
  bản (`src/rag_demo/demo_file.py:71#SCORE_DECIMALS`, `src/dashboard/src/lib/ragDemo/rank.ts:7#SCORE_DECIMALS`):
  engine từ chối file có `provenance.score_decimals` khác hằng của mình
  (`src/dashboard/src/lib/ragDemo/demoFile.ts:123#parseDemoFile`).
- **Docs:** `docs/claude/data-model.md` (mục demo RAG), `docs/claude/architecture.md`, `docs/status.md`,
  `docs/design/ui-contract.md`, `docs/decisions/README.md`, dòng
  trạng thái ADR-0038, comment hằng `SCORE_DECIMALS` và hàm `rounding_ties` ở `src/rag_demo/demo_file.py`. Chữ hiển thị
  của các nhãn ("not reranked", "tied at this pick", "tied across the cut", "filtered out at: …", "no passages left
  after: …", tên nút lọc) là bản nháp; Thy duyệt chữ cuối cùng trang.
- **Luật (`invariants.toml`): không có luật mới.** ADR không đổi tên, đường dẫn hay số liệu nào đã ghi ở nơi khác. Các câu
  "luật hoà chưa quyết" còn sót ngoài ADR sửa trong cùng commit; thân ADR-0038 (Accepted) giữ nguyên, dòng trạng thái
  của nó trỏ sang ADR-0041. Một luật cấm cho cụm này chỉ bắt được việc chép lại câu cũ — giá
  trị thấp so với một luật + test phải giữ.
- **Rủi ro chấp nhận:** hạng sau rerank Haiku và MMR phụ thuộc bước trước — đúng bản chất pipeline nhiều tầng, nhưng hai
  cấu hình A/B khác bước trước có thể ra hạng khác dù điểm Haiku y hệt; trang nói điều này. Lọc gần trùng ở mặc định
  không làm gì trên 19 bài. Topic trong file là ảnh chụp, có thể lệch với trang `/topics` sau lần gom cụm sau. Rerank
  chấm theo câu hỏi gốc dù bước tìm dùng câu biến đổi. Lọc gần trùng giữ đoạn đứng trước, nên khi 2 đoạn hoà điểm
  lại gần trùng nhau thì đoạn bị bỏ do mã chunk quyết định (tất định, nhưng khoảng hạng không phản ánh việc thứ tự
  khác sẽ giữ đoạn kia); ở ngưỡng mặc định 0,95 không xảy ra trên 19 bài.
- **Xem lại khi:**
  1. Đổi thang điểm Haiku hoặc số chữ số làm tròn → đo lại số hoà.
  2. Có phần còn chờ (dense của câu hỏi biến đổi, chunk kèm câu ngữ cảnh) → đo lại hoà trong từng cách chia.
  3. Engine xong → đo số lần hoà chạm đáp án ở RRF; thường xuyên thì xem lại cách hiện khoảng hạng. Đo 2026-11-10
     (engine xong, `data/rag_demo/measure/rrf_ties.mjs`, 9 câu có đáp án × 7 cách chia = 63 ô mỗi cấu hình; số ô có
     chunk trúng nằm trong nhóm hoà / hạng một bài là khoảng / số chính là khoảng): trộn RRF mặc định (hybrid, không
     biến đổi) 9 / 3 / 2; gộp câu con trên BM25: expand 12 / 0 / 0, step-back 6 / 3 / 3, multi-query 0 / 0 / 0,
     decompose 6 / 2 / 2. **Thy chọn giữ nguyên cách hiện khoảng hạng (2026-11-10).** Lý do: số chính ra khoảng
     ở 0–3 / 63 ô mỗi cấu hình (mặc định 2 / 63, ≈ 3 %), không phải "thường xuyên"; khi có hoà, khoảng hạng là cách
     hiện trung thực — một hạng đơn sẽ cho thứ tự do mã chunk quyết định trông như do điểm quyết định. Đo lại (cùng
     script) khi làm mới bộ bài (xem lại 4) hoặc có phần còn chờ (xem lại 2), vì cả hai đổi số hoà.
  4. Làm mới bộ bài (ADR-0037 xem lại 5) → đo lại cosine chunk × chunk trước khi giữ ngưỡng gần trùng 0,95.

### Hệ quả UI

- Sửa `UI-0038-tied-rank`: luật hoà chung cho BM25, dense, gộp câu con, trộn, cross-encoder; chỉ BM25 bỏ điểm 0; phá
  hoà theo mã chunk gốc; khoảng tính lại sau lọc.
- Sửa `UI-0038-gold-definition`: "not found" chỉ BM25; đáp án bị lọc ghi bước lọc; hạng ngoài top-K; gộp hạng theo mọi
  cách xếp lại trong nhóm hoà; câu 3 / 7 thiếu một bài; so A/B theo khoảng.
- Thêm `UI-0041-stable-rerank-ties`: top-N rerank, "not reranked", Haiku giữ thứ tự bước trước, nhãn "keep / drop",
  rerank chấm theo câu hỏi gốc.
- Thêm `UI-0041-step-order`: thứ tự bước, hằng số có nguồn hoặc nhãn "lựa chọn thiết kế", lọc Haiku độc lập, lọc gần
  trùng (0,95, nói thật), MMR (λ 0,5, "tied at this pick"), danh sách rỗng, mặc định khi mở trang; biến đổi câu hỏi
  nói thật (A/B không quảng cáo expand là luôn tốt hơn — mốc ở Bối cảnh; cách nối expand chọn sau khi xem hạng trên
  chính 9 câu này, không chốt trước; HyDE cho BM25 ghi là biến thể).
- Sửa `UI-0037-free-query-bm25-only`: câu tự gõ giữ lọc metadata, lọc gần trùng, MMR, cắt top-K (Luật chung 9).
- Sửa `UI-0037-rag-pipeline-page` (cột E: hạng ở từng bước theo `UI-0041-step-order`, luật mũi tên) và
  `UI-0037-static-precomputed` (cột B trỏ `UI-0041-step-order`).
- Thêm `UI-0041-metadata-filter`: lọc theo topic, tháng đăng, phần của thread (chạm là khớp); BM25 giữ thống kê cả kho.
- Nâng mốc "Cập nhật tới" lên ADR-0041.
