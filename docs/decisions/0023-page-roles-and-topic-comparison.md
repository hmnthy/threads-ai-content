# ADR-0023: Vai trò 3 trang app và phương pháp so sánh topic với phần còn lại của kênh

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-09
- **Người quyết**: Thy (chốt 1a–1f theo khuyến nghị kèm số đo; chốt phương pháp kiểm định — Brunner-Munzel hoán vị
  — và họ Holm 27 cho cả landing sau khi xem bảng so sánh song song 3 phương pháp × 2 ngưỡng × 2 họ, 2026-10-09);
  đề xuất, đo và mô phỏng bởi Claude Code; lỗi vùng đuôi của bản xấp xỉ t do code-reviewer phát hiện

> **Đọc ADR này thế nào.** Mỗi con số sinh lại được bằng `uv run python -m scripts.topic_method_report` (chỉ đọc DB,
> seed cố định, ~25 phút vì có mô phỏng hoán vị); "mục N" trỏ tới mục N trong output. Số đo trên lần gom cụm
> 2026-10-09 (`cluster_runs.id = 9`). Thuật ngữ được định nghĩa ở lần dùng đầu. Phương pháp đi qua 3 bước, mỗi bước bị
> thay vì một bằng chứng đo được — mục "Bối cảnh" kể đủ 3 bước để người đọc thấy vì sao không dừng ở bước nào.

## Bối cảnh

### Câu hỏi

Ba trang app chưa có tài liệu nào nói mỗi trang trả lời câu hỏi gì; Overview và Analytics trùng nhau (brief Topics của
Claude Design, Việc 1). Trang Topics cần trả lời: **"chủ đề có liên quan tới engagement không?"** — với mỗi topic, bài
thuộc topic đó có xu hướng được tương tác nhiều hơn / ít hơn phần còn lại của kênh không. Landing (panel 1) đang hiện
median theo topic với nhãn `next` cho phần kiểm định, chờ quyết định này. Phần còn mở của ADR-0012 (sàn views cho bảng
top theo tỉ lệ) gộp vào đây vì cùng câu hỏi "so với nhóm nào, hiệu chỉnh thế nào".

### Dữ liệu (mục 1)

- **Đơn vị so sánh topic:** content unit = bài gốc + các reply tự nối của tác giả (ADR-0004). **146** unit có embedding
  trong lần gom cụm; HDBSCAN xếp **86** unit vào **9** topic (4–13 bài/topic) và **60** unit (41,1%) là **nhiễu** — bài
  không đủ gần cụm nào. Không unit nào trong tập này có views = 0 (ADR-0011).
- **Đơn vị mô phỏng và mục 7–8:** bài gốc đo được — **146** bài sau khi loại **6** bài views = 0. Đây là tập khác với
  tập unit có embedding; hai số đếm trùng nhau là ngẫu nhiên.
- **3 chỉ số** mỗi bài (đều chia cho views): engagement = (likes + replies + reposts + quotes) / views; share_rate =
  (reposts + quotes) / views (ADR-0012); conversation = replies / views.
- **Phân phối lệch phải**: skewness (độ lệch, 0 = đối xứng) 1.01 / 2.28 / 2.45; 97/146 bài có share_rate dưới mean
  (mục 8) — mean bị vài bài đột biến kéo lên, không đại diện "bài điển hình".
- **Việc chia topic không nhìn kết quả**: gom cụm chỉ nhận `(id, full_text)` (`src/pipeline/clustering_export.py:74`),
  không thấy views hay tương tác. So engagement giữa topic vì vậy không mắc lỗi "phân tích vòng tròn" (dùng chính kết
  quả để chia nhóm rồi kiểm định trên kết quả đó) — điều kiện tiên quyết để mọi phép so dưới đây có nghĩa.

### Đại lượng đo

Mọi phương pháp dưới đây đo cùng một thứ: **Cliff's δ** = P(bài topic > bài phần còn lại) − P(<), trong [−1, 1] (Cliff
1993) — ghép từng bài của topic với từng bài phần còn lại, lấy tỉ lệ cặp thắng trừ tỉ lệ cặp thua. δ = 0 nghĩa là không
nhóm nào có xu hướng cao hơn. Chỗ khác nhau giữa các phương pháp là **cách biết δ dao động bao nhiêu khi không có khác
biệt thật** — tức cách ra p.

### Phương pháp qua 3 bước, mỗi bước bị thay vì một bằng chứng

| Bước | Phương pháp | Bằng chứng khiến phải thay |
|---|---|---|
| 1 | **Mann-Whitney** + CI bootstrap percentile (bộ có sẵn trong `compare_groups()`) | Mann-Whitney suy phương sai từ công thức, giả định 2 nhóm cùng phân phối. Topic thường khác độ phân tán so với kênh (IQR topic ÷ phần còn lại 0.18–1.52, mục 4). CI bootstrap của δ báo động giả 7.3–16.8% thay vì 5% (mục 5c) |
| 2 | **Brunner-Munzel xấp xỉ t** (Brunner & Munzel 2000) | Ước lượng phương sai từ dữ liệu → hết lỗi độ phân tán ở ngưỡng 0.05. Nhưng Holm ra quyết định ở ngưỡng chặt hơn nhiều (0.05/27 ≈ 0.00185), nơi xấp xỉ t sai **gấp 2–10 lần** với topic 4–13 bài khi 2 nhóm cùng phân phối (mục 5a; ~11 lần khi topic n = 5 phân tán hơn, mục 5b) — cam kết của Holm không giữ được |
| 3 | **Brunner-Munzel hoán vị có chuẩn hoá** (Neubert & Brunner 2007) — **chọn** | Cùng thống kê, nhưng phân phối tham chiếu dựng bằng cách xáo nhãn nhóm 100.000 lần → ở ngưỡng Holm không vượt mức đạt được ngoài sai số Monte Carlo trừ 1 ô; ở 0.05 có 2 ô vượt; bảo thủ khi topic đồng đều hơn kênh (bảng dưới) |

Tỉ lệ báo động giả khi **không có khác biệt thật**, ở ngưỡng 0.05 / 0.00185 — đúng chuẩn là **5% / 0.185%** (mục 5;
MW, BM-t: 40.000 mô phỏng/ô; BM hoán vị: 4.000 mô phỏng × 2.000 hoán vị/ô). Riêng cột BM hoán vị: với 2.000 hoán vị,
p chỉ nhận các bậc 2/2001, 4/2001, … nên mức chuẩn **đạt được** là **5.0% / 0.10%** (mục 5 in số này) — so cột đó
với 5.0% / 0.10%, không với 0.185%. Engine thật dùng 100.000 hoán vị: mức đạt được ở 0.05/27 là 184/100.001 ≈
0.184% (công thức `attainable_level` trong script, test `test_attainable_level_reflects_permutation_discreteness`).

| Kịch bản | n topic | Mann-Whitney | BM xấp xỉ t | BM hoán vị |
|---|---|---|---|---|
| 2 nhóm cùng phân phối thật (engagement) | 5 | 4.6% / 0.04% | 7.1% / **1.30%** | 5.0% / 0.12% |
| | 12 | 5.0% / 0.12% | 5.6% / 0.43% | 6.1% / 0.12% |
| Topic đồng đều hơn (độ lệch chuẩn ×0.5) | 5 | **0.19% / 0.00%** | 6.4% / 0.83% | 2.1% / 0.00% |
| | 12 | **0.47% / 0.00%** | 5.4% / 0.32% | 4.0% / 0.03% |
| Topic phân tán hơn (độ lệch chuẩn ×2) | 5 | **14.2% / 2.35%** | 7.6% / **2.06%** | 6.4% / **0.73%** |
| | 12 | **12.9% / 1.27%** | 5.4% / 0.44% | 5.5% / 0.10% |

- **Mann-Whitney** quá chặt ở vùng đuôi kể cả khi cùng độ phân tán, gần như mù khi topic đồng đều hơn, báo động giả
  13–14% khi topic phân tán hơn — bài toán Behrens-Fisher (so 2 nhóm khác độ phân tán).
- **BM xấp xỉ t** sai ở vùng đuôi trong mọi kịch bản mẫu nhỏ.
- **BM hoán vị**, ở ngưỡng Holm (nơi kết luận được quyết): không vượt mức đạt được ngoài sai số Monte Carlo ở ô nào trừ
  một — topic rất nhỏ (n = 5) **và** phân tán hơn kênh (0.73% so với 0.10%, ~gấp 7; MW gấp ~13 và BM-t gấp ~11 so
  với 0.185%). Ở ngưỡng 0.05 có 2 ô vượt: cùng ô đó (6.4%, ~4 sai số Monte Carlo) và ô "cùng phân phối, n = 12"
  (6.1%, ~3 sai số — xem dưới). Chiều ngược lại, nó **bảo thủ** khi
  topic đồng đều hơn kênh: 2.1% (n = 5) và 4.0% (n = 12) thay vì 5% ở ngưỡng 0.05 — mất bớt khả năng phát hiện
  khác biệt thật, không sinh kết luận sai. Đây là kịch bản phổ biến: 7/9 topic có IQR engagement nhỏ hơn phần còn
  lại (share_rate, conversation: 5/9 — mục 4). Mức bảo thủ trên đo ở tỉ số độ lệch chuẩn 0.5; tỉ số IQR thật của 7
  topic đó từ 0.34 đến 0.81 (trung vị 0.58), quanh điểm đã đo — tỉ số IQR không đồng nhất với tỉ số độ lệch chuẩn
  nên đây chỉ là gần đúng. Vẫn hơn hẳn MW ở cùng ô (0.19% / 0.47%, gần như mù). Hoán vị chỉ
  chính xác tuyệt đối khi 2 nhóm cùng phân phối; khi khác độ phân tán nó đúng dần theo cỡ mẫu. Vẫn là sai số nhỏ nhất
  trong 3 cách ở ô đó. Ô "cùng phân phối, n = 12" ra 6.1% ở 0.05 — cao hơn 5% khoảng 3 lần sai số Monte Carlo
  (±0.35 điểm % với 4.000 mô phỏng); ở ngưỡng Holm cùng ô đúng mức (0.12%). Theo lý thuyết, khi 2 nhóm cùng phân phối
  hoán vị chính xác (đổi nhãn không đổi phân phối) nên không được vượt 5%; ~3 sai số trong 6 ô ở ngưỡng 0.05 vẫn hiếm
  nếu chỉ do ngẫu nhiên → **chưa rõ nguyên nhân**, ghi vào "Xem lại khi" (chạy lại ô này với nhiều mô phỏng hơn).
- Trong mô phỏng, cột BM xấp xỉ t lấy p Mann-Whitney ở những lần 2 nhóm tách hẳn (SE = 0, xấp xỉ t không xác định)
  để lần đó không bị đếm nhầm là "không phát hiện" — chỉ ảnh hưởng vài lần ở n nhỏ, không ảnh hưởng engine.
- Mô phỏng (b) dùng phân phối chuẩn tổng hợp, không dùng engagement thật → việc chọn phương pháp dựa trên **tính chất
  của phương pháp**, không dựa trên kết quả nó cho ra trên dữ liệu kênh.

## Quyết định

**Vai trò trang (1a).** Mỗi trang app trả lời đúng 1 câu hỏi: `/overview` — kênh đang thế nào trong cửa sổ đã chọn?
· `/analytics` — bài nào, giờ nào hiệu quả? · `/topics` — kênh viết về gì, và chủ đề có liên quan tới engagement
không? Mỗi khối theo thứ tự đọc của landing: **câu hỏi → câu trả lời 1 dòng → bằng chứng → "Method and limits"**,
nhưng giữ hình khối tầng A (card có viền trên nền sáng, không dải tối) — `docs/claude/design-system.md` §7.

**So sánh topic (1b, 1h).** Mỗi topic so với **phần còn lại của kênh, gồm bài nhiễu**, bằng **Brunner-Munzel hoán vị có
chuẩn hoá** trong engine dùng chung `compare_groups()`:
- Thống kê T = (p̂ − ½) / SE, p̂ = P(bài phần còn lại > bài topic) + ½P(=), SE ước lượng từ "placement" (mỗi bài thắng
  bao nhiêu phần trăm bài nhóm kia) — không giả định cùng độ phân tán.
- p 2 phía từ phân phối của T qua **100.000** lần xáo nhãn, mỗi lần tính lại cả p̂ lẫn SE (chuẩn hoá lại — điều giữ nó
  đúng khi độ phân tán khác nhau); p = 2 × đuôi nhỏ hơn, hiệu chỉnh +1. Seed cố định khi số liệu cần tái lập (script,
  API). Sai số Monte Carlo ở p = 0.002 ≈ ±0.0002 (p = 2 × đuôi nhỏ hơn q = p/2 → SE = 2·√(q(1−q)/B)).
- **CI 95% của δ lấy từ cùng phân phối hoán vị** (Pauly, Asendorf & Konietschke 2016: đảo T bằng phân vị 2.5/97.5 của
  phân phối hoán vị thay cho phân vị t) → CI loại trừ 0 khi và chỉ khi p < 0.05 (trừ sát ngưỡng, lệch 1 bậc rời rạc).
- **Trường hợp biên:** 2 nhóm tách hẳn (δ = ±1) → SE = 0, p hoán vị vẫn xác định (chính xác như hoán vị đếm tổ hợp),
  không có CI. 1 nhóm < 2 bài hoặc đầu vào có NaN → không chạy được hoán vị → p Mann-Whitney, ghi `test_method =
  "mann_whitney"`. Mọi giá trị bằng nhau → p = 1.
- **Mann-Whitney vẫn được tính** (`p_value_mann_whitney`) làm phân tích độ nhạy; bản xấp xỉ t giữ ở
  `brunner_munzel_asymptotic()` để báo cáo đặt 3 cách cạnh nhau. Cả hai không lên UI.
- Chênh median (topic − phần còn lại) chỉ để **mô tả**, không dùng để kết luận.

**Hiệu chỉnh nhiều phép so (1c).** Họ Holm (Holm 1979) = **mọi phép so có p xác định cùng hiện trên 1 trang, kể cả
topic n < `MIN_N_PER_BUCKET` (5)** — gộp topic nhỏ vào họ là chọn bảo thủ. Trang Topics: 9 topic × 3 chỉ số = 27. Holm
kiểm soát xác suất có ≥ 1 kết luận sai trong cả họ (FWER) mà không cần các phép so độc lập (9 nhóm "phần còn lại" chồng
lên nhau). **Chỉ được khẳng định khi p Holm < 0.05**; CI ghi "unadjusted" (chưa hiệu chỉnh — chỉ nói độ chính xác của
ước lượng). Topic n < 5 vẫn có p trong họ nhưng không có câu kết luận. **Landing dùng đúng p Holm của họ 27** dù panel chỉ
hiện engagement — mỗi topic có một con số và một câu kết luận ở mọi nơi (bằng chứng ở mục "Họ Holm" dưới).

**Mean (1d).** UI chỉ hiện **median + IQR + n** (IQR có tooltip "interquartile range: the range the middle 50% of posts fall in");
API vẫn trả `mean` cho phân tích và script.

**Lịch sử tên (1e).** Trang Topics ghi ngày đặt tên + số lần chạy liên tiếp giữ tên (từ `topic_events_json`); danh
sách đổi tên + lý do chỉ hiện khi topic đã đổi tên sau lần đặt đầu. Hiện cả 9 topic đặt tên 2026-10-05
(`config_change`, ADR-0018) và giữ tên qua 4 lần chạy liền (mục 9) — một danh sách đổi tên lúc này sẽ rỗng.

**Sàn views cho bảng top theo tỉ lệ (1f).** Bảng top theo engagement / share_rate / conversation chỉ xếp bài có views
≥ **P25 views của bài gốc đo được**, tính lại từ dữ liệu mỗi lần (quy tắc, không phải hằng số), bằng
`statistics.quantiles(method="inclusive")` — nội suy tuyến tính (Hyndman & Fan 1996 loại 7), cùng cách tính IQR của
`distribution_stats`. Bài dưới sàn được đếm và ghi riêng.

## Bằng chứng

### Kết quả trên dữ liệu thật (mục 2) — 3/27 phép so đạt p Holm < 0.05

| Topic · chỉ số | n | δ [CI 95%, unadjusted] | p Holm — BM hoán vị | MW (độ nhạy) | BM-t (loại) |
|---|---|---|---|---|---|
| topic_8 Studying in France Advice · engagement | 12 | +0.62 [+0.43; +0.81] | 0.001 | 0.011 | < 0.001 |
| topic_8 · share_rate | 12 | +0.59 [+0.39; +0.81] | 0.007 | 0.016 | < 0.001 |
| topic_0 Cheap Shopping Deals in France · conversation | 10 | +0.55 [+0.31; +0.80] | 0.030 | 0.090 | 0.003 |
| topic_4 France Study Costs and Alternance Policy · engagement | 8 | −0.47 [−0.73; −0.20] | **0.147 ✘** | 0.596 ✘ | 0.020 |

- 2 kết luận của topic_8 đạt với cả 3 phương pháp; riêng engagement còn đạt với mọi nhóm so sánh (mục 3 chỉ chạy
  engagement: bỏ nhiễu δ +0.71; 12/12 bài trên median kênh) — kết luận vững nhất.
- topic_0 (conversation) có độ phân tán gần bằng kênh (IQR ÷ 0.88). Giả thuyết: Mann-Whitney trượt vì **quá chặt ở
  vùng đuôi** — ô gần nhất của mục 5a (engagement, n = 10) cho 0.11% thay vì 0.185%; mục 5a không mô phỏng riêng
  conversation, nên đây là suy luận, không phải số đo trên chính chỉ số đó.
- topic_4 chỉ đạt với BM xấp xỉ t — đúng phương pháp đã chứng minh dễ dãi ở vùng đuôi → **không kết luận**. CI của δ
  vẫn loại trừ 0 vì CI chưa hiệu chỉnh; UI ghi "not distinguishable after correction".
- **Về tính trung thực:** phương pháp đổi 2 lần sau khi đã thấy kết quả. Lần 1 (MW → BM-t) thêm kết luận, lần 2 (BM-t
  → hoán vị) bớt kết luận; cả 2 lần đều do bằng chứng về tính chất phương pháp (mô phỏng không dùng engagement thật),
  không do kết quả. Báo cáo giữ cột 3 phương pháp để ai cũng thấy kết luận nào phụ thuộc phương pháp.
- ADR-0012 (tầng reach) chạy lại bằng engine mới (`scripts/reach_report.py`, DB thư mục chính 2026-10-09): top 20% reach vs dưới
  median, engagement δ −0.32 [−0.56; −0.07], p hoán vị 0.015, p Holm 0.031 (Mann-Whitney p = 0.015, chưa hiệu chỉnh) —
  kết luận giữ nguyên.

### Họ Holm cho landing: 27 hay 9 (mục 2, BM hoán vị)

| | Họ 27 (cả trang Topics) | Họ 9 (chỉ engagement như panel landing) |
|---|---|---|
| Ngưỡng bước đầu | 0.05/27 = 0.00185 | 0.05/9 = 0.0056 |
| topic_8 engagement | ✔ p Holm 0.001 | ✔ 0.0004 |
| topic_4 engagement | ✘ 0.147 | ✔ **0.049** |

Họ 9 sẽ khiến landing ghi "bài về học phí/alternance có engagement **thấp hơn** kênh" trong khi trang Topics của cùng
sản phẩm ghi "**not distinguishable**" — cùng topic, 2 kết luận ngược nhau. Đổi lại họ 27 chặt hơn: ngưỡng bước đầu
0.00185 thay vì 0.0056, với n = 8 cần δ ≈ 0.75 để phát hiện 80% số lần (mục 6; so với 0.56 ở 1 phép so 0.05). Chọn
họ 27.

### Sức mạnh thống kê (mục 6) — "chưa phân biệt được" là kết quả dự kiến

δ nhỏ nhất **Mann-Whitney** phát hiện được với xác suất 80% (quy ước Cohen 1988), mô phỏng 4.000 lần/ô từ phân phối
engagement thật, nhóm topic dịch lên một khoảng. Mann-Whitney dùng làm **đại diện**: trong mô hình dịch vị trí (cùng
độ phân tán) nó đúng mức ở 0.05 và hơi chặt ở 0.05/27, nên bảng là ước lượng thận trọng. Power của BM hoán vị **chưa
đo trực tiếp** (quá tốn mô phỏng); dự kiến gần bảng này khi topic phân tán như kênh, nhưng **thấp hơn** với topic
đồng đều hơn kênh (bản hoán vị bảo thủ ở đó — 7/9 topic hiện nay) → bảng lạc quan cho các topic này. BM-t lạc quan vì
dễ dãi (mục 6 in cả hai):

| n topic | 5 | 8 | 10 | 13 |
|---|---|---|---|---|
| α = 0.05 (1 phép so) | 0.64 | 0.56 | 0.50 | 0.45 |
| α = 0.05 / 27 (bước chặt nhất của Holm) | 0.87 | 0.75 | 0.68 | 0.62 |

Ngưỡng "lớn" thường dùng là |δ| ≥ 0.474 (Romano et al. 2006). Với cỡ topic hiện tại, trang chỉ phát hiện được chênh
lệch rất lớn → UI ghi "not distinguishable after correction", **không bao giờ** "no difference".

### Độ nhiễu của tỉ lệ theo views (mục 7) — căn cứ cho sàn P25

| Nhóm views (tứ phân vị) | Sai số chuẩn nhị thức của engagement (median) | share_rate = 0 |
|---|---|---|
| Q1: 346–1.868 views | 0.43 điểm % | 17/37 bài |
| Q4: 12.465–161.625 views | 0.08 điểm % | 1/37 bài |

Sai số chuẩn nhị thức = √(p(1−p)/views) — xấp xỉ bậc độ lớn (1 người có thể vừa like vừa reply nên tương tác không
phải phép thử độc lập). Tỉ lệ của bài ít views dao động ~5 lần nhiều hơn; ở 1.000 views, 1 lượt repost đã là 0.1 điểm %.
Không sàn, bảng top bị nhóm này chiếm: 4/10 (engagement), 4/10 (share_rate), 7/10 (conversation) bài top-10 có views
dưới sàn P25 = 1.900 views. Spearman ρ(views, engagement) = −0.20 chỉ mô tả — hai đại lượng chung mẫu số views
(bài học ADR-0012), không diễn giải cơ chế.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| 1b-(ii) topic vs phần còn lại **bỏ nhiễu** | Nhóm so "thuần topic" | Bỏ 41% kênh; "phần còn lại" không còn là kênh | Kết luận như (i) (mục 3), nhưng khó đọc hơn |
| 1b-(iii) topic vs **1 con số** median kênh (Wilcoxon 1 mẫu) | Khớp đường mốc trên biểu đồ | Median đó chứa chính topic và có sai số riêng mà phép test coi như hằng số; cần engine khác | Sai về mặt suy diễn |
| 1c họ Holm 9 (chỉ engagement) | Ít phép so → dễ đạt | Trang hiện cả 3 chỉ số; landing và trang Topics có thể kết luận ngược nhau (topic_4) | Thy chọn họ 27 cho mọi nơi |
| 1d giữ mean ở dòng phụ | Đủ thông tin | Mean ≠ bài điển hình khi lệch phải (97/146 bài dưới mean share_rate) | Gây hiểu sai |
| 1f-(b) chỉ xếp bài đã "chín" theo tầng reach | Dùng lại ADR-0012 | Loại cả bài mới nhiều views; trộn 2 câu hỏi (reach vs tỉ lệ) | Thy chọn sàn P25 |
| 1f-(c) không lọc, ghi views cạnh bài | Không mất bài nào | Người đọc tự cân sai số — top-10 vẫn bị bài ít views chiếm | Thy chọn sàn P25 |
| Mann-Whitney + CI bootstrap percentile (bộ cũ) | Có sẵn, tất định, quen thuộc | Behrens-Fisher (báo động giả 13–14% hoặc mù); quá chặt ở vùng đuôi; CI báo động giả tới 16.8% | Mục 5 |
| Brunner-Munzel xấp xỉ t | Tất định, tức thì | Báo động giả gấp 2–10 lần ở ngưỡng Holm khi n = 4–13 (tới ~11 lần khi topic phân tán hơn) | Mục 5a, 5b |
| Xấp xỉ t nhưng chỉ kết luận khi n ≥ 15 | Rẻ | Gần như mọi topic hiện có mất kết luận; n = 13 vẫn sai gấp đôi | Thy chọn hoán vị |

## Hệ quả

- **Giới hạn chấp nhận:** BM hoán vị còn lệch khi topic rất nhỏ VÀ phân tán hơn kênh (0.73% so với mức đạt được
  0.10% của mô phỏng, ~gấp 7, ở n = 5, mục 5b) — topic n < 5 đã không có kết luận; n = 5–9 ghi giới hạn này trong
  "Method and limits". Ngược lại nó bảo thủ khi topic đồng đều hơn kênh (2.1% thay vì 5% ở n = 5, mục 5b) — chiều
  này chỉ làm mất bớt kết luận, không sinh kết luận sai, nhưng "not distinguishable" càng không có nghĩa "no
  difference". p có sai số Monte
  Carlo (≈ ±0.0002 ở p = 0.002) và phụ thuộc seed — seed cố định ở mọi chỗ số liệu được trình bày. Tính 27 phép so mất
  ~1 phút → Việc 3 tính sẵn trong job hằng ngày, không tính theo request. Phân tích là quan sát/thăm dò, không nhân quả;
  thành viên cụm có thể đổi giữa các lần chạy nên p đổi theo.
- **Code (PR này):** `src/analysis/significance.py` (`compare_groups` dùng `brunner_munzel_permutation`, thêm
  `brunner_munzel_asymptotic`, `test_method`, `p_value_mann_whitney`, `effect_size_ci_*`; CI chênh median giữ bootstrap
  cũ để mô tả), `scripts/topic_method_report.py` + test, `scripts/reach_report.py` in thêm phương pháp + CI của δ; UI bỏ
  mean và dùng chung `DistributionCaption` (IQR có tooltip, n = 0 → "—") ở `HeroBand`, `KpiStrip`,
  `AnalyticsBreakdown`, `PostingTimeHeatmap`; chữ landing (`LandingProof`, `LandingTechStack`) và README ×3 mô tả
  phương pháp mới ("engine live, per-topic comparisons on the dashboard next").
- **Việc 3 (PR sau):** endpoint so sánh theo topic (δ, CI, p, p Holm họ 27, `test_method`, cờ n nhỏ; dòng nhiễu và
  dòng kênh không kiểm định) tính sẵn trong job, sàn P25 cho bảng top ở `/analytics/overview`, landing panel 1 chuyển
  `next` → `live`.
- **Docs:** `docs/claude/data-model.md` (mục suy diễn thống kê + so sánh topic), `docs/claude/design-system.md` §7,
  `docs/claude/architecture.md`, `.claude/rules/nlp-research.md` (CI của δ; hiệu chuẩn ở mọi ngưỡng quyết định thật),
  tài liệu của Claude Design (`topics-proposal.md`, `topics-brief-for-claude-code.md`, `landing-handoff.md`, ghi ở
  `ui-contract-audit.md` mục 3).
- **Luật (`docs/decisions/invariants.toml`):** `ADR0023-mean-on-ui` (UI đọc `mean` để hiển thị; câu README cũ),
  `ADR0023-mean-secondary` (diễn đạt lại "mean là số phụ"), `ADR0023-old-test-engine` (mô tả Mann-Whitney là engine),
  `ADR0023-bootstrap-ci-primary` (CI bootstrap là CI chính), `ADR0023-holm-wait` (câu "chờ chốt nhóm so sánh"),
  `ADR0023-holm-family-wording` (định nghĩa họ Holm là "phép so có kết luận" thay vì "có p xác định"),
  `ADR0023-normal-approx-p` (p xấp xỉ chuẩn của mockup cũ), `ADR0023-perm-claim-overstated` (câu "không vượt mức
  báo động giả ở cả 2 ngưỡng") — luật có `mockups = true` quét cả mockup (cảnh báo); `[[stale_asset]]` ảnh README
  overview / analytics.
- **Xem lại khi:**
  1. Topic trung vị ≥ 20 bài (power đủ cho |δ| ~0.4) — cân nhắc đưa thêm biến giải thích (độ dài bài, giờ đăng) vào
     một mô hình thay vì so từng topic.
  2. Topic thường ≤ 5 bài và phân tán hơn kênh — giới hạn của bản hoán vị thành vấn đề thật; cân nhắc gộp topic nhỏ
     hoặc nâng `MIN_N_PER_BUCKET` cho câu kết luận.
  3. Một trang hiện > 30 phép so có kết luận — cân nhắc kiểm soát FDR (Benjamini-Hochberg) thay FWER.
  4. Bảng top theo tỉ lệ cần giữ bài ít views — cân nhắc co tỉ lệ về median kênh theo views (empirical Bayes) thay sàn.
  5. Ô "cùng phân phối, n = 12" ở ngưỡng 0.05 (6.1%) chưa giải thích được — chạy lại với ≥ 20.000 mô phỏng; nếu vẫn
     vượt 5% ngoài sai số thì tìm lỗi trong cách tính p hoán vị trước khi tin kết quả sát ngưỡng.

### Hệ quả UI

- Thêm: `UI-0023-page-questions`, `UI-0023-no-mean`, `UI-0023-comparison-group`, `UI-0023-comparison-test`,
  `UI-0023-holm-family`, `UI-0023-views-floor` (ràng buộc cho Việc 3, code chưa có sàn — ghi rõ ở cột B).
- Sửa: `UI-0018-label-provenance` (cột E: ngày đặt tên + số lần chạy giữ tên; danh sách đổi tên chỉ khi có),
  `UI-L20260903-window-median` (cột E: dòng phụ IQR + n, không mean). Nâng mốc "Cập nhật tới: ADR-0023".
- Mockup landing còn mô tả Mann-Whitney (2 chỗ) → cảnh báo `ADR0023-old-test-engine`, ghi audit cho Claude Design.

## Nguồn

Đối chiếu thư mục (tác giả, năm, tạp chí, số, trang, DOI) bằng Crossref / trang nhà xuất bản, 2026-10-09 — chưa đọc
toàn văn; chi tiết kỹ thuật dùng ở trên (thống kê, phân phối hoán vị) được kiểm bằng code và mô phỏng, không dựa vào
trích dẫn.

- Brunner, E. & Munzel, U. (2000). The nonparametric Behrens-Fisher problem: asymptotic theory and a small-sample
  approximation. *Biometrical Journal* 42(1), 17–25. doi:10.1002/(SICI)1521-4036(200001)42:1<17::AID-BIMJ17>3.0.CO;2-U
- Neubert, K. & Brunner, E. (2007). A studentized permutation test for the non-parametric Behrens–Fisher problem.
  *Computational Statistics & Data Analysis* 51(10), 5192–5204. doi:10.1016/j.csda.2006.05.024
- Pauly, M., Asendorf, T. & Konietschke, F. (2016). Permutation-based inference for the AUC: a unified approach for
  continuous and discontinuous data. *Biometrical Journal* 58(6), 1319–1337. doi:10.1002/bimj.201500105
- Karch, J. D. (2021). Psychologists should use Brunner-Munzel's instead of Mann-Whitney's U test as the default
  nonparametric procedure. *Advances in Methods and Practices in Psychological Science* 4(2), article 2515245921999602.
  doi:10.1177/2515245921999602
- Cliff, N. (1993). Dominance statistics: ordinal analyses to answer ordinal questions. *Psychological Bulletin* 114(3),
  494–509. doi:10.1037/0033-2909.114.3.494
- Romano, J., Kromrey, J. D., Coraggio, J. & Skowronek, J. (2006). Appropriate statistics for ordinal level data:
  should we really be using t-test and Cohen's d for evaluating group differences on the NSSE and other surveys?
  Annual meeting of the Florida Association of Institutional Research (bài hội nghị, không DOI) — ngưỡng diễn giải δ
  (|δ| < 0.147 / 0.33 / 0.474).
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics* 6(2),
  65–70. JSTOR 4615733.
- Hyndman, R. J. & Fan, Y. (1996). Sample quantiles in statistical packages. *The American Statistician* 50(4), 361–365.
  doi:10.1080/00031305.1996.10473566
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.) — quy ước power 80%.
