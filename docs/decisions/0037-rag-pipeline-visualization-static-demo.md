# ADR-0037: Trang "RAG pipeline visualization" — demo truy xuất tĩnh trên 20 thread gần nhất

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-05
- **Người quyết**: Thy — chọn qua trao đổi 2026-11-05: D1–D12 dưới đây, rồi nơi đặt file dữ liệu (Vercel Blob riêng tư)
  và route `/rag-pipeline` + tab "RAG pipeline". Thiết kế do Claude đề xuất sau khi đọc repo mẫu.

> **Quan hệ với ADR-0001 và roadmap Phase E/F.** Không mở cổng F: trang không có câu trả lời do LLM viết. ADR này chỉ
> (1) ghi cách hiểu cổng F của Thy — mọi vai LLM trung gian (biến đổi câu hỏi, HyDE, rerank, lọc, nén, câu ngữ cảnh
> cho chunk) **không** phải "sinh câu trả lời", vì không cái nào là đáp án cuối; (2) thu hẹp 2 dòng `UI-0001-kb-next` và
> `UI-0001-dropped-scope` để trang demo có ô câu hỏi; (3) thu hẹp ranh giới "LLM / Claude chỉ đặt tên cluster" (chốt
> 2026-09-03, `docs/claude/architecture.md` + `docs/claude/data-model.md`) thành "trong job NLP". Knowledge base thật (roadmap E, số giữ chỗ ADR-0006) vẫn chưa làm; lớp 03 "Search" của
> landing giữ trạng thái `next`.

## Bối cảnh

- Mục tiêu của Thy (2026-11-05): một trang trực quan hoá pipeline RAG đầy đủ, đổi liên tục được lựa chọn ở từng bước
  (loading, chunking, kỹ thuật truy xuất, có / không bước trước và sau truy xuất) và thấy kết quả đổi cụ thể ra sao —
  để thể hiện trình độ kỹ thuật. Mẫu: https://github.com/vietnh1009/RAG-pipeline-visualizer (Streamlit; Indexing =
  loader → chunking → embedding → vector DB, Generation = pre-retrieval → retrieval → post-retrieval → prompt →
  generation; mỗi bước trả trace; cache theo chuỗi dấu vân tay SHA-256). Repo mẫu **không có file LICENSE** (README ghi
  MIT) → chỉ tái tạo kiến trúc, tự viết code, ghi công trên trang.
- Không chạy model trên web được: API live là Vercel Python Function, gói ~203 MiB / giới hạn 500 MB (ADR-0025,
  `docs/claude/architecture.md` mục "Deploy"); model embedding và reranker chạy trên máy mỗi cái ~2,2 GB; Windows chặn
  thư viện ML (chỉ chạy trong WSL2). Máy chủ model riêng (Hugging Face Spaces miễn phí: 2 vCPU, 16 GB, ngủ sau 48 giờ)
  hoặc API theo lượt thì thêm chi phí, khoá bí mật, rate limit.
- Bộ câu hỏi do mình chọn → mọi bước cần model **tính sẵn được**. Dữ liệu đo 2026-11-05: 20 content unit mới nhất
  (2026-10-04 → 2026-11-04), ~27.700 ký tự, 49 post tác giả tự viết tiếp, toàn bộ tiếng Việt chen từ Pháp, 7 topic +
  10 bài chưa thuộc cụm.
- Giá đo 2026-11-05: OpenAI `text-embedding-3-small` 62.500 trang / $1 (~800 token / trang ≈ $0,02 / 1 triệu token,
  1536 chiều, tối đa 8192 token — https://developers.openai.com/api/docs/guides/embeddings). Số đo đa ngôn ngữ OpenAI
  công bố (01/2024): MIRACL — truy xuất trên 18 ngôn ngữ — 44,0 (so với 31,4 của `text-embedding-ada-002`; trang OpenAI chặn đọc tự động, số lấy qua
  https://www.pinecone.io/learn/openai-embeddings-v3/); MIRACL
  **không có tiếng Việt** (https://huggingface.co/datasets/miracl/miracl). Claude Haiku 5.5 $0,10 vào / $0,50 ra mỗi 1 triệu token.
  Ước lượng cả demo: embedding ~$0,002; LLM (~60 lần biến đổi câu hỏi — 10 câu × 6 cách cần LLM, ~500 câu ngữ cảnh chunk, ≤ 10.000 cặp chấm — D8) ~$1–2.

## Quyết định

1. **D1 — Trang mới** "RAG pipeline visualization" trong dashboard Next.js (cùng sổ luật UI ADR-0029), route
   `/rag-pipeline`, tab "RAG pipeline". Mô phỏng kiến trúc repo mẫu, code tự viết, có dòng ghi công.
2. **D2 — Dữ liệu**: 20 content unit mới nhất = bài gốc + mọi post tác giả tự viết tiếp (`full_text`, ADR-0004), đóng
   băng tại 2026-11-05; **không** có reply cho follower. Làm mới = chạy lại bước chuẩn bị, không tự động theo cron.
3. **D3 — Chạy tĩnh**: phần nặng tính sẵn trên laptop (chunk mọi phương án, embedding, điểm cross-encoder, mọi vai LLM)
   → một file JSON; phần nhẹ chạy bằng TypeScript trong trình duyệt (BM25, trộn kết quả RRF / weighted / DBSF, top-K,
   MMR, lọc gần trùng, lọc metadata, đổi hạng). File không chứa vector thô: chỉ điểm câu hỏi × chunk và ma trận
   cosine chunk × chunk. File chứa nguyên văn 20 bài nên **không vào repo**: laptop publish lên Vercel Blob riêng tư
   (cùng đường với bản sao DB, ADR-0025), API chỉ đọc trả nguyên file qua một endpoint GET — endpoint chỉ phát file,
   không truy xuất phía máy chủ. **Ngân sách cỡ file < 4 MB** (Thy chốt sau review 2026-11-05): response của Vercel
   Function tối đa 4,5 MB, vượt thì lỗi 413 `FUNCTION_PAYLOAD_TOO_LARGE` (https://vercel.com/docs/functions/limitations);
   bước dựng làm tròn điểm; **bước dựng / publish tự từ chối** file vượt ngân sách (chốt chặn nằm trong code chạy thật,
   vì file ở `data/` gitignored nên CI không có; test kiểm chốt chặn bằng file giả quá cỡ). Vẫn vượt sau khi làm tròn
   thì chia thành 1 file chung (mọi phần không phụ thuộc câu hỏi: chunk, câu ngữ cảnh, bản tiếng Anh của chunk và câu
   ngữ cảnh, cosine chunk × chunk) + 1 file mỗi câu hỏi (mọi phần phụ thuộc câu hỏi, kể cả bản tiếng Anh của câu hỏi
   biến đổi, câu HyDE, câu trích), **mỗi file** < 4 MB. **Endpoint chỉ phát tên trong danh sách cố định**: `common`
   (file duy nhất khi chưa chia, hoặc file chung khi đã chia) và `q01`…`q10` (chỉ khi đã chia), ánh xạ sang pathname
   dưới tiền tố riêng của demo; tên khác → 404; không bao giờ ghép chuỗi người gọi vào pathname — Blob riêng tư này giữ
   cả bản sao DB (ADR-0025). Test gọi tên ngoài danh sách. File demo là dữ liệu trình bày tĩnh dựng từ SQLite, **không
   phải CSDL thứ hai**: SQLite vẫn là nguồn duy nhất (ADR-0010; câu "Blob chỉ chứa bản sao file SQLite" của ADR-0025
   nói về CSDL, không cấm file tĩnh này).
4. **D4 — Output = danh sách đoạn nguồn xếp hạng**, tô sáng chỗ khớp, hạng của đáp án đúng ở mỗi cấu hình; chế độ A/B
   so 2 cấu hình. Không có câu trả lời do LLM viết.
5. **D5 — Cách hiểu cổng F**: HyDE và mọi vai LLM trung gian không tính là "sinh câu trả lời" (xem khung đầu ADR).
6. **D6 — Embedding: OpenAI `text-embedding-3-small`**, thay bge-m3 **chỉ trong demo**; gom cụm vẫn dùng bge-m3
   (`src/nlp/embeddings.py:34#PRIMARY_MODEL_NAME`). Khoá `OPENAI_API_KEY` chỉ ở `.env` trên laptop, không lên Vercel.
7. **D7 — LLM: Claude Haiku 5.5** cho mọi vai: câu ngữ cảnh cho chunk (contextual chunking); 7 cách biến đổi câu hỏi
   (rewrite, expand, HyDE, multi-query, decompose, step-back, cùng "không biến đổi"); chấm sau truy xuất. Mỗi kết quả
   lưu tên model + phiên bản prompt. Chữ dùng để tìm giữ ngôn ngữ của bài (tiếng Việt); mỗi lần gọi trả thêm bản tiếng
   Anh để hiển thị trước (ADR-0031).
8. **D8 — Tinh gọn (Thy duyệt)**: mỗi cặp câu hỏi × chunk gọi LLM **một lần**, trả điểm liên quan + giữ / bỏ + câu
   trích; chấm **mọi** cặp (10 câu hỏi cố định × mọi chunk của mọi phương án chia đoạn — Thy chốt sau review
   2026-11-05: chỉ chấm cặp từng lọt top-20 thì đổi tham số hay lọc metadata có thể đẩy một chunk chưa chấm lên; ước
   lượng chưa đo ≤ 10.000 cặp, ~$1–2 với Haiku 5.5). **Câu trích là chuỗi con nguyên văn của
   chunk** (bước dựng file kiểm, sai thì bỏ) — không phải LLM viết lại. Mọi chữ LLM viết (câu hỏi biến đổi, câu trả lời
   giả của HyDE, câu ngữ cảnh, bản dịch tiếng Anh) chỉ hỗ trợ tìm và đọc, không bao giờ đứng ở chỗ kết quả. **Ràng buộc kỹ thuật**: LLM rerank chấm
   từng đoạn độc lập (pointwise) — kiểu xếp cả danh sách (listwise, như repo mẫu) phụ thuộc danh sách đầu vào nên không
   tính sẵn được cho mọi tổ hợp lựa chọn.
9. **D9 — Rerank cross-encoder** `BAAI/bge-reranker-v2-m3`, chấm sẵn trong WSL2 **mọi** cặp 10 câu hỏi × chunk
   (cùng lý do D8).
10. **D10 — Bộ 10 câu hỏi cố định** (Thy duyệt), mỗi câu phô ra một hiện tượng, đáp án đúng gắn theo id bài (bảng dưới).
11. **D11 — Ô gõ tự do chỉ chạy BM25** trong trình duyệt, tách theo âm tiết + bản bỏ dấu (tách từ ghép bằng underthesea
    không chạy trong trình duyệt); dense, rerank và LLM tắt cho câu tự gõ, có câu giải thích.
12. **D12 — Giải thích xuyên suốt**: mỗi bước, mỗi lựa chọn, mỗi con số có nghĩa, công thức, lý do, giới hạn, đọc được
    bởi cả kỹ sư lẫn người không làm kỹ thuật; chữ tiếng Việt / Pháp luôn kèm tiếng Anh cùng dòng; trang ghi rõ "minh
    hoạ cơ chế, không phải đánh giá" (20 bài, 10 câu hỏi).

**Bộ câu hỏi (D10)** — id = `posts.id` của content unit chứa đáp án.

| # | Câu hỏi | English | Đáp án | Hiện tượng |
|---|---|---|---|---|
| 1 | chu nha khong chiu bat suoi thi phai lam sao | What can I do if my landlord won't turn the heating on? | 17899007316608496 | Gõ không dấu |
| 2 | Mua đồ hiệu second-hand giá rẻ ở Pháp ở đâu? | Where can I buy cheap second-hand designer clothes in France? | 18042552590841773 | Diễn đạt khác chữ, khác ngôn ngữ ("đồ hiệu" / "đồ marque", "thrift") |
| 3 | Thuê nhà mùa đông ở Pháp cần để ý gì về sưởi và độ ẩm, chủ nhà không sưởi thì làm sao? | Renting in winter: what to check about heating and humidity, and what if the landlord won't heat? | 18128851717831169 + 17899007316608496 | Một câu nhiều ý, đáp án ở 2 bài |
| 4 | Nên chọn mentor / coach thế nào cho du học sinh? | How should an international student choose a mentor or coach? | 17923191900443021 hoặc 18117744790996401 | Hai bài gần trùng nội dung |
| 5 | Từ Cancale đi Saint-Malo bao xa, nên đi mùa nào? | How far is Saint-Malo from Cancale, and when is the best season to go? | 18156311638533948 (post viết tiếp) | Ý nằm ở post viết tiếp |
| 6 | Peut-on changer de filière facilement à l'université en France ? | Can you easily switch your field of study at a French university? | 18128894426508078 | Câu hỏi tiếng Pháp, bài tiếng Việt |
| 7 | Nhớ đồ ăn Việt quá, ở Pháp có cách nào không? | I miss Vietnamese food a lot; what are my options in France? | 18102395354566129 + 18133654129644298 | Câu mơ hồ (HyDE, step-back) |
| 8 | Đi brocante ở Versailles có rẻ hơn Paris không? | Is a brocante in Versailles cheaper than Paris? | 18042552590841773 (đoạn Versailles) | Bẫy từ khoá (bài hàu cũng nói về giá) |
| 9 | Bút ngòi 1,0 mm nào viết êm tay? | Which 1.0 mm pen writes smoothly? | 18645332647003724 | Số và tên sản phẩm |
| 10 | Gia hạn titre de séjour cần giấy tờ gì? | What documents do I need to renew a residence permit? | — (không có bài nào) | Câu không có đáp án |

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Máy chủ model riêng (Hugging Face Spaces) cho câu gõ tự do | Mọi bước chạy cho câu bất kỳ | Ngủ sau 48 giờ, CPU chậm khi rerank, thêm hạ tầng + rate limit | Thy chọn bản nhẹ |
| API model theo lượt | Không tự vận hành | Phí theo lượt, câu hỏi người xem gửi bên thứ ba, khoá bí mật | Như trên |
| Output có câu trả lời LLM (tính sẵn hoặc trực tiếp) | Giống chatbot | Đụng cổng F; "bọc" kết quả, khó quan sát hiệu năng truy xuất | Thy chọn danh sách đoạn nguồn xếp hạng (D4) |
| Toàn bộ ~171 content unit | Sát thực tế | Tổ hợp tính sẵn lớn hơn nhiều; chưa cần cho mục đích minh hoạ | Thy chọn 20 bài |
| Thêm 75 reply tác giả trả lời follower | Thêm ngữ cảnh hỏi–đáp | Thiếu câu hỏi của follower (chưa có ADR-0007), có thể nhắc người khác | Thy bỏ |
| bge-m3 / AITeamVN Vietnamese_Embedding / Qwen3-Embedding-0.6B (chạy máy), Voyage-4 (Anthropic giới thiệu) | Miễn phí / chuyên tiếng Việt / API | — | Thy chọn `text-embedding-3-small` thay bge-m3 |
| Haiku / Sonnet / Opus 5.5 | — | Sonnet, Opus đắt gấp 20–40 lần cho cùng khối lượng | Thy chọn Haiku 5.5 |
| Commit file dữ liệu vào repo public | Không cần endpoint, Vercel build có sẵn file | Nguyên văn bài nằm vĩnh viễn trong lịch sử repo và mọi bản clone; trái quy tắc không commit data | Thy chọn Vercel Blob riêng tư |
| Streamlit như repo mẫu | Nhanh dựng | Stack giao diện thứ hai, lệch design system, cần máy chủ riêng | Thy chọn trang trong Next.js |
| LLM rerank xếp cả danh sách (listwise) | Đúng repo mẫu | Không tính sẵn được cho mọi tổ hợp | Ràng buộc kỹ thuật (D8) |

## Hệ quả

- **Code (PR sau, cùng nhánh):** gói `src/rag_demo/` (chunker, gọi LLM / embedding, dựng file), lệnh
  `scripts/rag_demo_build.py` (bước mạng: OpenAI + Claude; bước WSL2: cross-encoder + tách từ), engine truy xuất
  TypeScript `src/dashboard/src/lib/ragDemo/`, trang `src/dashboard/src/app/rag-pipeline/`, test `tests/rag_demo/`.
  File dựng xong nằm ở `data/` (gitignored), publish lên Blob riêng tư bằng hàm tải lên dùng chung
  (`src/pipeline/publish.py:141#vercel_upload`) với pathname riêng — **không** gọi `publish()` (hàm đó sao SQLite và ghi
  trạng thái mà `job_health` đọc); `src/main.py` thêm một endpoint GET trả nguyên file, có header cache (file chỉ đổi
  khi dựng lại), không import `src/rag_demo/`. Publish chạy tay sau mỗi lần dựng, không gắn vào cron. SDK `openai` chỉ
  vào nhóm thư viện `pipeline` của `pyproject.toml` (gói API trên Vercel không kéo theo, giới hạn 500 MB — ADR-0025).
- **Docs + code sửa ở PR code** (khi trang và endpoint có thật): `docs/claude/architecture.md` (bảng Deploy, biến môi
  trường, cây route), `.env.example` + `docs/claude/dev-rules.md` (`OPENAI_API_KEY`, chỉ trên laptop), README ×3 (danh
  sách tab, ảnh chụp), `src/dashboard/README.md`, `docs/claude/design-system.md` (số trang), `ux-shots.mjs` /
  `screenshots.mjs` (route mới), thanh nav, comment UI-0001-kb-next ở `LandingSolution.tsx`; cột B các dòng
  `UI-0037-*` thêm neo `file:dòng#Tên`.
  Phần truy xuất (BM25, trộn, MMR, lọc) chỉ có **một bản trong sản phẩm** là TypeScript trong trình duyệt (D8 + D9 chấm
  mọi cặp nên Python không cần tự xếp hạng — Thy chốt sau review 2026-11-05). `tests/rag_demo/` giữ một bản Python tham
  chiếu ngắn (BM25 từ thư viện có sẵn) làm bài giải mẫu: test chạy chính code TypeScript bằng node (cách đã dùng ở
  RQ-01 cho `testVerdict`) và đòi **cùng thứ hạng**. Muốn cùng thứ hạng thì hai bên phải cùng lựa chọn: PR code chốt
  biến thể IDF (thư viện đã cố định biến thể của nó, nên thực chất là chọn thư viện rồi TypeScript chép theo), k1 / b (hằng số heuristic có nhãn + nguồn), cách tách token và cách phân hạng khi điểm bằng nhau, Thy
  duyệt. Test kiểm chốt chặn cỡ file (D3) bằng file giả quá cỡ, và test endpoint với tên ngoài danh sách → 404 (D3).
- **Docs (cùng commit):** `docs/decisions/README.md`, `docs/design/ui-contract.md` (+ giá trị cột Trang
  `rag-pipeline`, cũng ở `docs/design/topics-brief-for-claude-code.md`), `docs/claude/data-model.md` (mục Knowledge base
  trỏ tới ADR này), `docs/claude/architecture.md` (hàng LLM + hàng demo trong bảng tech stack), `docs/roadmap.md`
  (Phase E); `docs/status.md` ở `/checkpoint`. Harness riêng (`.claude/rules/nlp-research.md`: "Claude chỉ đặt tên
  cluster", "Embedding: bge-m3") sửa trong kho harness, commit riêng (ADR-0027).
- **Luật (`invariants.toml`):** thêm `planned_paths` cho các đường dẫn trên. **Không thêm `[[forbid]]`**: ADR không đổi tên hay
  đường dẫn nào, chỉ thu hẹp 3 phát biểu cũ (khung đầu ADR: ranh giới "LLM / Claude chỉ đặt tên cluster" và 2 dòng
  hợp đồng `UI-0001-kb-next`, `UI-0001-dropped-scope`) — đã sửa tại chỗ trong cùng commit; luật chữ cho trang viết ở
  PR giao diện, khi có chữ thật để kèm test "câu đúng không bị bắt". Luật sẵn có vẫn áp: `ADR0001-generation`, `ADR0001-rag-gen-scope`, `KB-no-separate-vectorstore`.
- **Rủi ro chấp nhận:** 20 bài + 10 câu không đủ để kết luận phương pháp nào tốt hơn (chỉ minh hoạ); bộ câu hỏi do tác
  giả chọn có thể thiên vị — giảm bằng các câu cố ý cho kỹ thuật "xịn" thua; `text-embedding-3-small` chưa có số đo
  tiếng Việt công khai; OpenAI có thể đổi giá / ngừng model; mỗi lượt mở trang tải file < 4 MB qua Function (D3) → theo dõi
  Usage (Blob + Functions) như ADR-0025 bước 5.
- **Xem lại khi:**
  1. Có ADR-0007 (lưu bình luận follower) → thêm tài liệu hỏi–đáp và câu hỏi thật.
  2. Knowledge base thật (ADR-0006) được dựng → trang đọc từ KB hay giữ bản đóng băng.
  3. Muốn dense / rerank / LLM cho câu gõ tự do → cần máy chủ model, ADR mới.
  4. OpenAI ngừng hoặc đổi `text-embedding-3-small` → dựng lại file, ghi model mới.
  5. Làm mới 20 bài → kiểm lại đáp án đúng của 10 câu (id bài cố định, nhưng bài mới có thể chứa đáp án tốt hơn).

### Hệ quả UI

- Dòng `docs/design/ui-contract.md` thêm: `UI-0037-rag-pipeline-page`, `UI-0037-static-precomputed`,
  `UI-0037-free-query-bm25-only` (cột B gồm cả "câu tự gõ không rời trình duyệt"), `UI-0037-explain-every-step`.
  Sửa: `UI-0001-kb-next` cột E — trước cổng F không có ô nhập câu hỏi, ngoại lệ duy nhất là ô của trang demo (chỉ trả
  đoạn nguồn xếp hạng trên 20 bài đóng băng, không gọi là knowledge base), và không có câu trả lời do LLM viết ở bất kỳ
  đâu; cột C thêm `rag-pipeline`; `UI-0001-dropped-scope` cột E — riêng `/rag-pipeline` có ô gõ câu hỏi, chỉ để xếp
  hạng đoạn nguồn. Cột Trang (C) thêm giá trị `rag-pipeline`.
