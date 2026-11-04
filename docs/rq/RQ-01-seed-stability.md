# RQ-01: Topic và kết luận so sánh topic có bền qua các lần gom cụm ngẫu nhiên khác nhau không?

- **Trạng thái**: Planned (pre-registration — cam kết trước phương pháp và ngưỡng; Thy chốt 2026-11-04, trước khi chạy
  bất kỳ lần xáo trộn nào)
- **Phục vụ**: methodology. Landing và trang `/topics` hiện chỉ được nói một topic "stands out" như **đầu mối**, chưa
  phải **kết luận** (ADR-0024), vì luật bền chưa được áp. RQ này đo độ bền và áp luật bền đã chốt trước; ADR-0036 (cùng
  commit với file này) ràng buộc luật, ADR sau RQ đưa luật vào sản phẩm.
- **Liên quan**: ADR-0036 (luật bền chốt trước), ADR-0023 (phép so topic với phần còn lại của kênh, họ Holm), ADR-0024 (kết luận dạng khám phá tới khi
  bền), ADR-0018 (danh tính topic bền, thí nghiệm 10 seed), ADR-0004 (embedding lưu sẵn); RQ-02, RQ-03 (đổi thuật toán /
  model — ngoài phạm vi RQ này).

## Câu hỏi

Giữ nguyên dữ liệu và tham số, chỉ đổi những thứ **tuỳ ý** của một lần gom cụm (seed UMAP, thứ tự bài đầu vào) cộng
một thay đổi nhỏ về tập bài:

1. **Mức cách chia** — các lần gom cụm giống nhau tới đâu?
2. **Mức topic** — mỗi topic trang đang hiện còn "sống" (có cụm khớp) trong bao nhiêu phần các lần xáo trộn?
3. **Mức kết luận** (câu hỏi chính) — kết luận "topic t có tỉ lệ m cao hơn / thấp hơn phần còn lại của kênh" (ADR-0023)
   giữ được trong bao nhiêu phần các lần xáo trộn, và kết luận nào qua được luật bền chốt ở dưới?

## Giả thuyết

RQ mô tả, không kiểm định một H0. Kỳ vọng ghi trước, dựa trên bằng chứng đã có:

- ADR-0018: cùng một tập bài, 10 seed UMAP cho 8–11 cụm, nhiễu 30–40% → kỳ vọng số cụm và tỉ lệ unclustered dao động rõ.
- ADR-0024: 5 cách chia thật cho 0 / 2 / 0 / 1 / 1 kết luận đạt p Holm < 0.05; tín hiệu chỉ hiện khi ranh giới cụm ôm
  gọn một nhóm bài → **kỳ vọng phần lớn cặp (topic, tỉ lệ) có tỉ lệ giữ dưới ngưỡng**, có thể không cặp nào qua luật.

Kết quả nào cũng được báo cáo như nhau, kể cả khi không kết luận nào qua.

## Dữ liệu

- **Đóng băng trước khi chạy:** sao DB thật sang `data/experiments/rq01/` (gitignored, riêng tư), ghi SHA-256 của file
  sao, mốc giờ snapshot mới nhất và id lần gom cụm production mới nhất (`cluster_runs.id`) làm **mốc tham chiếu**. Mọi
  bước đọc bản sao này.
- **Đơn vị:** content unit có chữ trong lần gom cụm tham chiếu — đúng tập unit job hằng ngày gom cụm. Bài không có chữ
  không có embedding nên ngoài phân tích, như production.
- **Embedding:** vector bge-m3 đã lưu (bảng `embeddings`, ADR-0004), không embed lại — chỉ bước UMAP + HDBSCAN thay đổi.
- **Tỉ lệ:** engagement rate, share rate, conversation rate từ snapshot mới nhất của mỗi bài **trong bản sao đóng
  băng**, dùng chung cho lần tham chiếu và mọi lần xáo trộn; bài views = 0 bị loại khỏi phép so và đếm riêng
  (ADR-0011), đúng như bước `compare` của job.
- **n thật** (số unit, số topic tham chiếu, mốc snapshot) ghi vào mục Kết quả lúc đóng băng — không ghi trước ở đây vì
  dữ liệu còn tăng mỗi ngày tới lúc chạy.
- **Riêng tư:** kết quả thô chứa id bài → chỉ ở `data/experiments/rq01/`; file này chỉ ghi số tổng hợp và tên topic
  tiếng Anh, không trích chữ bài viết hay bình luận.

## Phương pháp

### Lần chạy tham chiếu

- **Cách chia tham chiếu = nhãn đã lưu** của lần gom cụm tham chiếu (`cluster_runs.labels_json`, topic từ
  `post_topic_labels`) — đúng cách chia trang đang hiện. **Không** chạy lại seed 42 để làm mốc.
- **Kết luận tham chiếu được tính lại** bằng `compare_topics()` trên bản sao đóng băng, cùng snapshot với mọi lần xáo
  trộn. Số đã lưu trong `topic_comparisons` (tính lúc job chạy, có thể trên snapshot cũ hơn) chỉ để đối chiếu.
- **Kiểm tái lập, trước khi chạy xáo trộn:** gọi `cluster_embeddings()` với seed 42, đưa bài theo đúng thứ tự job (thứ tự
  file export của `src/pipeline/clustering_export.py`: `list_content_units()`, bỏ bài không có chữ, không sắp xếp lại),
  **chỉ lấy unit có trong `labels_json`** (bài mới sau lần gom cụm tham chiếu bị lọc ra và đếm lại), vector đúng như
  lúc job chạy (đóng băng trước lần job NLP kế tiếp; ghi hash của các vector dùng) trên bản sao — phải ra đúng `labels_json` (chỉ được khác cách đánh số
  cụm). Lý do: thứ tự đầu vào đổi kết quả (ADR-0018: cùng seed 42, thí nghiệm ra 10 cụm, lần chạy thật ra 9 vì
  `load_vectors()` của `scripts/topic_identity_eval.py` sắp theo id). Không khớp → dừng, ghi lại phiên bản `umap-learn` /
  `hdbscan`, báo Thy; **không** đổi mốc tham chiếu.
- **Verdict tham chiếu** của mỗi cặp (t, m) theo đúng `testVerdict()` của sản phẩm (`src/dashboard/src/lib/landing.ts`):
  `higher` / `lower` khi p Holm < 0.05 và dòng không mang cờ `insufficient_data`; còn lại là không có kết luận.

### Hai nhánh xáo trộn, mỗi nhánh K = 100 lần, ghép cặp theo b

Với lần b = 1…100 và N = số unit tham chiếu: `rng = numpy.random.default_rng(b)`, `perm = rng.permutation(N)`, seed
UMAP = b.

| Nhánh | Đầu vào lần b | Dùng để |
|---|---|---|
| **P (chính)** | thứ tự `perm`, bỏ d = ⌈0.03 · N⌉ bài **cuối** của `perm`, giữ nguyên thứ tự phần còn lại | **áp luật bền** |
| **S (phụ)** | thứ tự `perm`, giữ đủ N bài | tách phần dao động do thuật toán khỏi phần do tập bài đổi |

Lần b của hai nhánh chỉ khác nhau ở d bài bị bỏ.

- **Tham số giữ y production** (`src/nlp/topics.py`): UMAP 3 chiều, `n_neighbors` 8; HDBSCAN `leaf`,
  `min_cluster_size` 4, khoảng cách euclid. Đổi seed bằng cách gán `UMAP_RANDOM_STATE` trước khi gọi
  `cluster_embeddings()`, như `scripts/topic_identity_eval.py`. Không dò tham số (RQ-02 / RQ-03 lo phần đó).
- **Vì sao seed và thứ tự:** hai thứ ngẫu nhiên có thật trong job (ADR-0018: UMAP nhạy cả với thứ tự). Seed cố định
  chỉ cho tái lập, không cho độ bền (tài liệu UMAP: "UMAP is a stochastic algorithm"; seed cố định để kết quả "can be
  reproduced exactly").
- **Vì sao bỏ 3% bài (lựa chọn thiết kế, Thy chốt 2026-11-04):** mô phỏng tập bài đổi giữa hai lần gom cụm. ADR-0024
  (bằng chứng 1): giữa hai cách chia thật liên tiếp chỉ thêm 1–5 bài; 3% của tập hiện tại ≈ 5 bài = mức lớn nhất đó.
  Mức cao hơn sẽ làm topic ít bài đi và phép so yếu đi, lẫn vào tỉ lệ giữ một phần không do ranh giới cụm.
- **Vì sao K = 100:** tài liệu `fpc::clusterboot`: "B=100 is recommended"; sai số chuẩn Monte Carlo của một tỉ lệ p
  trên K lần là √(p(1−p)/K) ≤ 0.05. Thy chốt 2026-11-04.
- **Chi phí đo trước:** một phép so (100.000 hoán vị) ≈ 3,2 giây trên laptop → khoảng 1,8 phút mỗi lần, khoảng 3 giờ
  mỗi nhánh.

### Ghép cụm của lần xáo trộn với topic tham chiếu

- Với topic tham chiếu t và lần b: chỉ xét unit có mặt ở lần b (S_b). Tính Jaccard
  J(t, c) = |t ∩ c| ÷ |(t ∩ S_b) ∪ c| với mọi cụm c của lần b. Unclustered không phải một cụm.
- **t "còn sống" ở lần b khi J lớn nhất > 0.5**; cụm khớp = cụm đạt J đó. Mốc 0.5 = ngưỡng "dissolved cluster" của
  `fpc::clusterboot` (`dissolution = 0.5`) — **quy ước của phần mềm**, không suy ra từ dữ liệu này.
- **Không cần luật phá hoà:** J > 0.5 kéo theo cụm khớp chứa quá nửa t ∩ S_b và t ∩ S_b chứa quá nửa cụm khớp, nên cụm khớp là
  duy nhất và không cụm nào khớp hai topic tham chiếu.
- **Độ bền topic** = trung bình J lớn nhất qua 100 lần (cách tính của `clusterboot`); lần không có cụm nào, hoặc t không
  còn bài nào trong S_b, tính J = 0. Đối chiếu với các mốc diễn giải của tài liệu `fpc` (< 0.6 không tin được;
  0.6–0.75 có mẫu hình nhưng thành viên không chắc; ≥ 0.75 bền; ≥ 0.85 rất bền) **chỉ để định hướng**: đó là quy ước phần
  mềm (chưa kiểm được có trong bài Hennig 2007), đặt cho bootstrap hoặc bỏ nửa mẫu — ở đây xáo trộn nhẹ hơn nhiều nên J
  cao hơn theo cấu tạo.

### Kết luận ở một lần xáo trộn

Chạy `compare_topics()` (`src/analysis/topic_comparison.py`) y như job: mỗi cụm của lần b so với phần còn lại gồm cả
unclustered, Brunner-Munzel hoán vị 100.000 lần, seed 0, Holm trên họ của chính lần b (mọi phép so có p xác định).

Kết luận (t, m) **giữ ở lần b theo hướng higher** khi đủ cả 4 điều kiện (hướng lower: thay điều kiện 4 bằng δ_b < 0):

1. t còn sống ở lần b (J > 0.5);
2. dòng của cụm khớp không mang cờ `insufficient_data` (min(n topic, n phần còn lại) trên bài có views > 0 nhỏ hơn
   `MIN_N_PER_BUCKET` = 5);
3. p Holm có giá trị và < 0.05 (`CONCLUSION_ALPHA`, ADR-0023);
4. δ_b > 0.

- **Tỉ lệ giữ theo hướng**, như `partition_history`: r_higher(t, m) và r_lower(t, m) = số lần giữ theo hướng đó ÷ 100.
  **Mẫu số luôn là K = 100**: lần không có cụm nào, lần t không còn bài nào, lần p Holm không có giá trị (mọi giá trị
  bằng nhau), lần δ_b = 0 hoặc không có δ đều tính là **không giữ**. (δ = 0 không thể đi cùng p Holm < 0.05 vì thống kê
  Brunner-Munzel khi đó bằng 0; PR code dùng một hàm verdict Python duy nhất, có test đối chiếu từng ca với `testVerdict`.)
- Tính cho **mọi** cặp (t, m) của lần tham chiếu, cả hai hướng, kể cả cặp không có verdict ở lần tham chiếu (để thấy luật
  sẽ khẳng định gì nếu ngày đó cách chia khác). Kèm CI 95% Wilson (z = 1.96, không hiệu chỉnh liên tục).
- **Kết luận mới:** mỗi lần b đếm số cặp (cụm, tỉ lệ) có verdict `higher` / `lower`, và bao nhiêu trong đó nằm ở cụm
  không khớp topic tham chiếu nào — median + IQR qua 100 lần. Nối với bằng chứng 0 / 2 / 0 / 1 / 1 của ADR-0024 và giữ
  phép đo khỏi chỉ nhìn một chiều.

### Mức cách chia (mô tả)

- **AMI** (chính; `sklearn.metrics.adjusted_mutual_info_score`, `average_method = "arithmetic"`, mặc định của
  scikit-learn) và **ARI** (`adjusted_rand_index` trong `src/nlp/topic_profile.py`, cùng hàm sinh số ARI đang hiện trên
  trang). AMI là chính vì cụm ở đây lệch cỡ và có cụm nhỏ: Romano và cộng sự (2016) khuyên ARI khi cụm tham chiếu lớn và
  đều cỡ, AMI khi lệch cỡ và có cụm nhỏ (áp theo nghĩa tương tự: ở đây "tham chiếu" là một lần chạy khác, không phải
  nhãn đúng).
- Tính 2 cách, như `ari_all` / `ari_clustered` của `src/pipeline/clustering_import.py`: (a) unclustered là một nhãn;
  (b) chỉ unit được gom cụm ở cả hai lần — vì một khối unclustered lớn làm cả hai chỉ số "thưởng" việc đồng ý về phần
  unclustered.
- **Hai kiểu so:** mỗi lần b với lần tham chiếu (trên unit chung), và **mọi cặp lần xáo trộn** (b, b′), b < b′ — 4.950
  cặp mỗi nhánh — để số không phụ thuộc việc lần tham chiếu có "lạ" hay không (ADR-0024 hứa "ARI cặp seed").
- Kèm phân phối số cụm, tỉ lệ unclustered, DBCV (`validity_index` của `hdbscan`, qua `_dbcv()` trong
  `src/pipeline/cluster_wsl.py` — cùng số trang đang hiện) qua 100 lần: median + IQR + n.

### Phân tích thăm dò (không thuộc luật)

ADR-0024 "Xem lại khi" 2: tín hiệu có nằm ở một **lõi** bài nhỏ trong khi ranh giới cụm dao động không. Với mỗi topic
có r_higher hoặc r_lower > 0 ở nhánh P, xét các bài thuộc t ở lần tham chiếu: tỉ lệ đồng cụm của mỗi cặp bài = số lần
hai bài cùng cụm ÷ số lần **cả hai** cùng có mặt. Lõi = thành phần liên thông lớn nhất của đồ thị nối các cặp có tỉ lệ
≥ 0.75 (lựa chọn thiết kế, dùng lại mốc của luật, chỉ để thăm dò). Chỉ mô tả, dùng để quyết có cần xem lại phương án C
của ADR-0024 không.

### Code

Theo mẫu `scripts/topic_identity_eval.py` (ADR-0018), viết ở PR sau, **sau khi** file này được merge:

- bước `replicates` chạy trong WSL2 (UMAP + HDBSCAN bị Smart App Control chặn trên Windows): kiểm tái lập, rồi gọi
  đúng `cluster_embeddings()` của production cho 2 nhánh × 100 lần, ghi nhãn từng lần;
- bước `evaluate` gọi `compare_topics()` và tính mọi số ở trên.

Có test cho ghép cụm, tỉ lệ giữ theo hướng (cả các ca tính là không giữ), CI Wilson và cách bỏ bài trên dữ liệu giả.

## Metric và ngưỡng quyết định (chốt 2026-11-04, TRƯỚC khi chạy)

| Metric | Vì sao chọn | Ngưỡng để kết luận |
|---|---|---|
| **Tỉ lệ giữ theo hướng**, nhánh P | Đo trực tiếp điều ADR-0024 lo: kết luận có phụ thuộc vào một cách chia tuỳ ý không | **Luật bền:** một kết luận (t, m) chỉ được viết thành câu khẳng định khi verdict tham chiếu là `higher` hoặc `lower` (p Holm < 0.05, không cờ mẫu nhỏ) **và** tỉ lệ giữ theo đúng hướng đó ≥ **0.75**, tức ≥ 75 / 100 lần. Quyết định theo ước lượng điểm; CI Wilson chỉ báo cáo |
| Ngưỡng 0.75 | Thy chốt 2026-11-04 trước khi chạy, để ngưỡng không bị chọn theo kết quả; ADR-0036 thay câu "chọn khi có số đo" của ADR-0024, và ADR sau RQ chỉ được ghi lại luật này, không chọn lại. Tiền lệ thiết kế: stability selection (Meinshausen & Bühlmann 2010) giữ cấu trúc xuất hiện trong ≥ π_thr các lần chạy lại, π_thr ∈ (0.6, 0.9); 0.75 cũng là mốc "bền" của `fpc`. **Chỉ mượn mẫu thiết kế**: cận sai số của bài đó cần giả định không có ở đây | Bảng độ nhạy ở 0.6 và 0.9 chỉ để báo cáo, **không** được dùng để đổi luật |
| Jaccard ghép cụm | Cách tính của `fpc::clusterboot` | Còn sống khi J > 0.5 (quy ước `fpc`) |
| Độ bền topic (trung bình J) | Mức topic, độc lập với tỉ lệ engagement | Mô tả; không phải cổng |
| AMI / ARI (so với tham chiếu và theo cặp), số cụm, tỉ lệ unclustered, DBCV, số kết luận mới mỗi lần | Mức cách chia | Mô tả: median + IQR + n |

**Ca sát ngưỡng (để đọc đúng, không đổi luật):** quyết theo ước lượng điểm với K = 100 nên một kết luận có tỉ lệ giữ thật
0.70 vẫn qua với xác suất khoảng 16%, và một kết luận có tỉ lệ thật 0.80 trượt với xác suất khoảng 9% (phân phối nhị
thức). Phần Diễn giải gọi tên các ca có CI Wilson chứa 0.75.

**Không có tiền lệ trực tiếp** cho việc đo độ lặp lại của *kết luận kiểm định từng cụm* qua các lần gom cụm lại: cách
đo này là của dự án, ghép từ hai tiền lệ trên. Kết quả sẽ ghi rõ như vậy.

**Sai lầm loại I:** ở một lần chạy, Holm kiểm soát xác suất có ít nhất một khẳng định sai (FWER) ở 5% với mọi tổ hợp
topic khác / không khác — **với điều kiện** p hoán vị đúng mức (ADR-0023: xấp xỉ, trừ topic rất nhỏ và phân tán hơn
kênh) và cách chia không phụ thuộc engagement (xem Giới hạn). Với một lần tham chiếu cố định, luật bền chỉ thu hẹp tập
khẳng định nên không làm tăng mức này; áp lặp lại mỗi ngày thì có — ADR sau RQ xử lý. Mục đích của luật là chống **phụ
thuộc vào lựa chọn tuỳ ý** (seed, thứ tự, vài bài), không phải kiểm soát lại sai lầm loại I.

## Kết quả

_Chưa chạy._

## Diễn giải

_Chưa chạy._

## Giới hạn

- Một kênh, một model embedding, một bộ tham số; topic nhỏ (từ 4 bài) nên vài bài đổi cụm là đủ đổi kết luận.
- Bỏ ngẫu nhiên 3% bài chỉ xấp xỉ việc thêm bài mới: bài mới là bài **gần đây**, không ngẫu nhiên.
- Các mốc 0.5 / 0.75 là quy ước, không suy ra từ dữ liệu này.
- **Sai số Monte Carlo của p hoán vị:** sát ngưỡng Holm nhỏ nhất (0.05 ÷ (3 × số topic); lần gom cụm 32 ngày 2026-11-04: 11 topic × 3 = 33 phép so ≈ 0.0015), p của engine
  là 2 · min(đuôi) nên sai số chuẩn = 2 · √(q(1 − q) ÷ B) với q = p ÷ 2 — khoảng 11–12% tương đối với B = 100.000, nên một phép so sát ngưỡng có thể đổi phía chỉ vì hoán vị.
- **Chọn lọc khi kiểm định trên cụm:** cụm được tạo từ chữ (embedding), phép so dùng engagement — khác tình huống "dùng
  cùng dữ liệu để vừa chia cụm vừa kiểm định" của Gao, Bien & Witten (2024). Nhưng chữ và engagement có thể liên quan
  (chính là điều dự án muốn tìm), nên không khẳng định là hoàn toàn không có vấn đề chọn lọc.
- **Chi phí vận hành:** áp luật mỗi ngày nghĩa là khoảng 3 giờ tính toán trên laptop. ADR sau RQ quyết cách chạy (tần suất,
  số hoán vị), không phải RQ này.

## Tái lập

_Điền khi chạy:_ commit, SHA-256 của DB đóng băng, id lần gom cụm tham chiếu, kết quả kiểm tái lập seed 42, lệnh chạy
hai bước, phiên bản `umap-learn`, `hdbscan` và `scikit-learn` trong venv WSL2.

## Nguồn

- Hennig, C. (2007). Cluster-wise assessment of cluster stability. *Computational Statistics & Data Analysis* 52(1),
  258–271. Mốc diễn giải và `B = 100` lấy từ tài liệu gói R `fpc::clusterboot`, không từ bài báo (chưa đọc được bản đầy
  đủ).
- Meinshausen, N. & Bühlmann, P. (2010). Stability selection. *JRSS-B* 72(4), 417–473 (arXiv:0809.2932, mục 2.3–2.4).
- Romano, S., Vinh, N. X., Bailey, J. & Verspoor, K. (2016). Adjusting for chance clustering comparison measures. *JMLR*
  17 (arXiv:1512.01286).
- Vinh, N. X., Epps, J. & Bailey, J. (2010). Information theoretic measures for clusterings comparison. *JMLR* 11,
  2837–2854.
- Gao, L. L., Bien, J. & Witten, D. (2024). Selective inference for hierarchical clustering. *JASA* 119(545), 332–342.
- Ullmann, T., Hennig, C. & Boulesteix, A.-L. (2022). Validation of cluster analysis results on validation data: a
  systematic framework. *WIREs Data Mining and Knowledge Discovery* 12(3), e1444 — mục 1: càng thử nhiều cách gom cụm,
  càng dễ có một cách cho kết quả đẹp do may; lý do chốt luật trước khi xem kết quả.
- Tài liệu UMAP, mục "Reproducibility"; FAQ của BERTopic (UMAP ngẫu nhiên nên kết quả đổi giữa các lần chạy).
