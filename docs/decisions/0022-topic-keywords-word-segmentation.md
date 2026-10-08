# ADR-0022: Tách từ khoá topic theo từ (underthesea, trong WSL2) và bỏ stopword có nhãn

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-08
- **Người quyết**: Thy (chọn phương án V5 sau khi xem số đo trước/sau; chọn chạy bước tách từ trong WSL2 sau code
  review, 2026-10-08); đề xuất và đo bởi Claude Code

## Bối cảnh

- Từ khoá của mỗi topic (c-TF-IDF, `src/nlp/topic_profile.py`) hiện trên landing và sắp lên trang Topics. Lần gom cụm
  2026-10-07 (9 cụm, 146 bài có chữ) cho ra từ khoá lẫn 3 loại nhiễu:
  - **Từ chức năng, đại từ, teencode**: "một", "điều", "các em", "tui" (3 topic), "tớ", "ko", "hổng", "nh" — 12/72 từ
    khoá. Bộ lọc có sẵn chỉ bỏ từ có mặt ở ≥ 80% số cụm (`MAX_CLUSTER_SHARE_FOR_KEYWORD`); các từ trên có mặt ở 2–7/9 cụm
    nên lọt qua.
  - **Từ chức năng tiếng Pháp**: "de" (6/9 cụm).
  - **Mảnh âm tiết của từ ghép**: "dụng" (của "áp dụng"), "chất", "nguyên", "miễn" — vì 1 token = 1 âm tiết.
- copy-reviewer và code-reviewer cùng chỉ ra đây là lỗi phương pháp một tech lead NLP sẽ thấy ngay; Thy chọn sửa trước khi
  công khai landing (2026-10-08).
- Tài liệu: BERTopic khuyên lọc stopword ở vectorizer, **sau** embed + gom cụm, nên không ảnh hưởng chất lượng cụm
  ([Vectorizers](https://maartengr.github.io/BERTopic/getting_started/vectorizers/vectorizers.html)). Không tìm thấy hướng
  dẫn stopword cho topic modelling trên mạng xã hội tiếng Việt trộn Pháp/Anh → danh sách dưới đây là **lựa chọn thiết kế
  có đo đạc**, không phải chuẩn ngành.
- Đo trên dữ liệu thật (5 phương án, script trong phiên 2026-10-08, chỉ đọc DB):
  - Danh sách `stopwords/vietnamese-stopwords` (MIT, 1.942 dòng) **phá từ ghép** ("phỏng vấn" → "vấn", "thời gian" →
    "thời"/"gian") và thiếu teencode ("tui", "ko", "hông", "nha" không có).
  - `stopwords-iso` fr/en (MIT) **xoá từ có nghĩa** trùng âm tiết Việt / từ mượn: "eu" (từ khoá chính của topic học phí),
    "du" (của "du học"), "vn", "cv", "ta", "an".
  - underthesea 9.5.0 (`word_tokenize`, Apache-2.0) tách 146 bài ~4 giây, ghép đúng "chất_lượng", "văn_hóa",
    "phỏng_vấn", "thời_gian", "du_học", "miễn_giảm"; nhưng model học trên văn bản báo chí nên dính teencode/emoji/tiếng
    Pháp vào từ bên cạnh ("đắt_nha", "ko_tệ", "thi_IELTS", "🇨_🇵") và chỉ ghép từ, không ghép cụm ("đồ cũ", "tiếng pháp"
    thành 2 từ rời).
  - `import underthesea` tự nạp các module tuỳ chọn và kéo **torch, transformers, scikit-learn** (đo bằng
    `python -X importtime`) — nhóm thư viện chỉ được chạy trong WSL2 vì Smart App Control chặn DLL của chúng trên Windows
    "lúc được lúc không" (`.claude/rules/nlp-research.md`). Chạy được trên Windows trong thí nghiệm không bảo đảm job
    hằng ngày chạy được.

## Quyết định

1. Từ khoá topic tách theo **từ** bằng `underthesea.word_tokenize` (khoá `underthesea==9.5.0` + engine
   `underthesea-core==3.3.2`), **trong WSL2** ở bước cluster (`src/pipeline/cluster_wsl.py`, trước embed): văn bản đã
   tách ghi vào `cluster_results.json` (`keyword_segments`; phiên bản bộ tách từ lưu vào `params` của `cluster_runs`);
   bước import trên Windows chỉ đọc, không
   import underthesea. Trước khi tách: chuẩn hoá NFC, đổi emoji/ký hiệu thành khoảng trắng; bỏ tiền tố lược âm tiếng Pháp
   ("l'alternance" → "alternance"), giữ từ có gạch nối ("île-de-france"); phần có chữ số thành khoảng trống, không nối
   chữ qua chỗ đã xoá ("covid-19" → "covid", "salaire_100k" → "salaire", không thành "salairek"). Thêm bigram của **2 từ đơn liền nhau** để giữ cụm có nghĩa ("đồ cũ", "tiếng pháp", "trên app"); từ ghép và
   bigram cùng cụm dùng chung 1 khoá ("đồ_cũ").
2. Bỏ **stopword có nhãn** trong `src/nlp/stopwords.py` — 6 nhóm: từ chức năng tiếng Việt, từ chức năng ghép ("có thể",
   "thậm chí"), đại từ xưng hô (cố ý không có "anh" — trùng "tiếng Anh"), teencode/viết tắt, từ chức năng tiếng Pháp và
   tiếng Anh không trùng âm tiết Việt. Chỉ nhóm **"dính keo"** được bóc ở mép từ ghép, **theo hướng**: tiểu từ cuối câu
   ("nha", "nè") chỉ ở mép phải ("nha_sĩ" giữ); phần còn lại ("ko", "hông" — trên dữ liệu thật luôn là tiểu từ hỏi khi
   dính mép phải, "ngon_hông"; "vs", "đc", từ chức năng Pháp/Anh) ở cả 2 mép; có danh sách từ ghép được bảo vệ
   ("tây_ban_nha", "bồ_đào_nha", "bên_hông", "lỗ_hổng"). Chỗ bóc để lại khoảng chặn
   bigram ("giá ko_tệ" không thành "giá tệ"). Từ chức năng tiếng Việt **không** bị bóc ở mép vì chúng là âm tiết của từ
   ghép có nghĩa ("điều_kiện", "chuẩn_bị", "từ_chối").
3. Chỉ áp ở bước chọn từ khoá, **sau** gom cụm: văn bản embed, cụm, id `topic_N` và tên topic (Claude đặt từ bài, không từ
   từ khoá — UI-0016-label-input) không đổi.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| V0 giữ nguyên | Không đổi gì | 12/72 từ khoá là từ chức năng/đại từ/teencode | Lỗi hiện rõ trên landing |
| V2 danh sách chuẩn (vietnamese-stopwords + stopwords-iso fr/en) | Có nguồn, có licence | Phá từ ghép; xoá "eu", "du", "vn" | Hại nhiều hơn lợi trên dữ liệu này |
| V3 danh sách nhỏ có nhãn, giữ tách âm tiết | Không thêm thư viện | Còn ~6 mảnh âm tiết ("chất", "sát", "nguyên", "văn"/"hóa") | Thy chọn V5 (đúng ngôn ngữ học hơn) |
| V4 underthesea, không bigram | Hết mảnh âm tiết | Mất cụm "đồ cũ", "tiếng pháp", "người pháp" | Thua V5 |
| **V5 underthesea + bigram 2 từ đơn + danh sách nhỏ** | Hết từ chức năng và mảnh âm tiết; giữ cụm có nghĩa | Thêm thư viện; còn vài từ chung ("chỗ", "đủ", "sang", "ngoài") | **Chọn** |
| V5 nhưng tách từ ở bước import trên Windows (+ kiểm tra / giữ từ khoá cũ khi lỗi) | Ít sửa pipeline | Nạp torch/transformers trên Windows (trái rule WSL2); job có thể mất 1 lần chạy khi Smart App Control chặn | Thy chọn tách trong WSL2 |
| Lọc theo từ loại (`underthesea.pos_tag`) thay danh sách tay | Có cơ sở ngôn ngữ học | Chưa đo; model báo chí có thể gán sai từ loại cho teencode | Để RQ-10 |

## Hệ quả

- Số đo sau (cùng lần gom cụm 2026-10-07, top-8 của 9 topic): từ chức năng/đại từ/teencode/tiếng Pháp 12 → 0; mảnh
  âm tiết ~4 → 0; xuất hiện "áp dụng", "miễn giảm", "hồ sơ", "người pháp", "tiếng anh", "uber eats", "formations"; còn
  ~5 từ chung chung ("chỗ", "mắt", "ngoài", "đủ", "sang"). Đại từ "anh" có mặt ở 7/9 cụm (dưới ngưỡng 80%) nhưng không
  vào top-8 topic nào. Từ dài nhất do bộ tách từ ghép: 4 âm tiết. Con số top-8 chỉ nói về 1 lần chạy — cơ chế được giữ
  bằng test danh sách đáp án chạy model thật trên từ lõi của kênh
  (`test_underthesea_keeps_core_channel_vocabulary_intact`, `slow`; gồm cả từ không được vỡ: "điều_kiện", "nha_sĩ",
  "lỗ_hổng", "tây_ban_nha", "bồ_đào_nha"); mỗi quy tắc bóc còn có test nhanh cho cả 2 chiều (bị bóc / được giữ).
- Code review bắt 2 lỗi trước khi commit, ghi lại để lần chỉnh danh sách sau không lặp: (1) bản đầu bóc cả từ chức năng
  tiếng Việt ở mép từ ghép ("điều_kiện" → "kiện", "chuẩn_bị" → "chuẩn"), rồi bóc nhóm "dính keo" ở cả 2 mép
  ("tây_ban_nha" → "tây_ban", "nha_sĩ" → "sĩ"), và bản xử lý chữ số đầu tiên nối chữ qua chỗ xoá ("delf_b2" → "delf_b")
  — mỗi quy tắc làm sạch token phải chạy trên toàn bộ dữ liệu thật (in "token gốc → token sau") và mỗi mục được bóc phải
  có từ ghép "không được vỡ" trong test; (2) underthesea kéo torch/transformers khi import — thư viện mới cho bước
  Windows phải kiểm import gián tiếp.
- Code: `src/nlp/stopwords.py` (mới), `src/nlp/topic_profile.py` (`underthesea_segment`, `word_segments`, `Segments`,
  `_terms`; `class_tfidf_keywords` nhận văn bản đã tách), `src/pipeline/cluster_wsl.py` (tách từ, ghi
  `keyword_segments`), `src/pipeline/clustering_import.py` (đọc `keyword_segments`, từ chối kết quả thiếu trường này),
  `pyproject.toml` + `uv.lock` (underthesea + underthesea-core cho test và Phase C). Test nhanh dùng bộ tách giả, không
  nạp model; 1 test `slow` chạy underthesea thật.
- **Vận hành**: bước cluster chạy trong WSL2 venv `~/threads-clustering-env` (ngoài `uv.lock`) → sau khi merge, trước
  lần chạy 12:30 kế tiếp, cài vào đó `underthesea==9.5.0 underthesea-core==3.3.2` (dry-run 2026-10-08: chỉ thêm 5 gói,
  không nâng gói đang có). Thiếu gói → bước cluster lỗi sau vài giây (tách từ chạy trước embed), DB không đổi. Bước import
  trên Windows không import underthesea (đo: `torch`, `transformers` không có trong `sys.modules`).
- Từ khoá trong DB chỉ đổi ở lần gom cụm + import kế tiếp (job hằng ngày) — không cần chạy lại riêng.
- Rủi ro chấp nhận: kết quả tách từ phụ thuộc phiên bản model → đổi phiên bản underthesea = đo lại từ khoá trước/sau
  rồi mới nâng; danh sách stopword là lựa chọn tay (mỗi nhóm có nhãn; nhóm teencode và từ chức năng ghép có số đếm).
- Không có luật `[[forbid]]` mới cho khái niệm cũ ngoài 1 luật: câu "1 token = 1 âm tiết" (mô tả cũ của token từ khoá)
  không còn đúng ở `docs/` và `src/`.
- **Xem lại khi**: (1) RQ-10 cho thấy lọc theo từ loại cho từ khoá tốt hơn danh sách tay trên cùng dữ liệu; (2) ≥ 2 topic
  có từ khoá là từ chung chung chiếm ≥ 3/8 chỗ sau một lần gom cụm; (3) nâng underthesea hoặc đổi model tách từ;
  (4) kênh viết thêm nhiều tiếng Pháp/Anh làm danh sách từ chức năng Pháp/Anh không còn đủ; (5) Phase C chuyển cả bước
  import sang WSL2 (khi đó có thể tách từ ngay ở bước import).

### Hệ quả UI

- Thêm `UI-0022-keyword-words`: từ khoá là từ hoặc bigram (1 hoặc nhiều âm tiết; dài nhất đo được 4), không còn từ chức
  năng/teencode; layout chip từ khoá phải xuống dòng được với cụm dài. Nhãn "Keywords (c-TF-IDF)" giữ nguyên.
- Sửa ref của `UI-0016-label-input` (`topic_profile.py` đổi số dòng). Nâng mốc "Cập nhật tới: ADR-0022".
