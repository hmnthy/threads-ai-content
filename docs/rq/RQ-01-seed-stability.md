# RQ-01: Topic và kết luận so sánh topic có bền qua các lần gom cụm ngẫu nhiên khác nhau không?

- **Trạng thái**: Done — chạy 2026-11-04 (pre-registration — cam kết trước phương pháp và ngưỡng; Thy chốt 2026-11-04,
  trước khi chạy bất kỳ lần xáo trộn nào; code ở commit `b2589e1`, trước lần chạy)
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

Phụ lục 2026-11-04 (sau khi file này merge, trước khi chạy) — đã viết: `scripts/rq01_seed_stability.py`, hằng số +
luật ở `src/analysis/topic_stability.py`. Hai chỗ đổi cách chia việc giữa các bước, phương pháp không đổi:

- đóng băng là bước riêng `freeze` chạy trên Windows, trước `replicates`: khoá SQLite qua `/mnt/c` giữa WSL2 và
  Windows không đáng tin khi job đang ghi;
- AMI / ARI chỉ cần nhãn nên tính ở cuối bước `replicates` (WSL2), không ở `evaluate`: scikit-learn chỉ được import ở
  bước WSL2 (Smart App Control).

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

Chạy 2026-11-04 (20:48–21:50 UTC), đúng phương pháp ở trên. Số liệu dưới đây sinh lại bằng
`scripts/rq01_seed_stability.py`: bước `evaluate` in số của luật, mức topic và mức cách chia (`evaluation.json`); bước
`report` in các số dẫn xuất còn lại — phân phối số kết luận mỗi lần, phần ở cụm không khớp, cỡ họ Holm, thời gian mỗi
lần so (cả họ Holm của lần đó), phần thăm dò (`report.json`).

**Dữ liệu đóng băng.** Lần gom cụm tham chiếu 32 (2026-11-04 11:30 UTC): 165 unit có chữ, 11 topic, 65 unit
unclustered (39%), DBCV `validity_index` 0,246. Snapshot mới nhất của bản sao: 2026-11-04 19:17 UTC. Không có unit nào
mới hơn lần tham chiếu bị lọc ra. Nhánh P bỏ d = ⌈0,03 · 165⌉ = 5 bài mỗi lần (160 unit).

**Kiểm tái lập: đạt.** Seed 42 + thứ tự job + vector đã lưu ra đúng `labels_json` của lần 32, trùng cả cách đánh số cụm;
DBCV tái lập trùng số đã lưu. Verdict tính lại (snapshot 19:17 UTC) trùng 33 / 33 dòng `topic_comparisons` đã lưu lúc
job chạy (snapshot 11:17 UTC) — 8 giờ views thêm không đổi verdict nào.

**Mức kết luận (câu hỏi chính).**

- Lần tham chiếu: **0 / 33** cặp (topic, tỉ lệ) có verdict `higher` / `lower` — 27 "not distinguishable", 6 "too few
  posts" (2 topic 4 unit: Cheap Shopping Deals in France, Food Finds and Vietnamese Cuisine in France).
- **Luật bền: 0 kết luận qua.** Điều kiện đầu (verdict tham chiếu) đã không cặp nào đạt, nên tỉ lệ giữ không quyết
  thêm gì. Bảng độ nhạy 0,6 / 0,9 cũng 0. Không ca nào có CI Wilson chứa 0,75.
- Tỉ lệ giữ theo hướng — mọi cặp đều tính, kể cả cặp không có verdict tham chiếu (K = 100, CI 95% Wilson):

| Cặp | Nhánh P | Nhánh S |
|---|---|---|
| Studying in France Advice · engagement · higher | 9 / 100 [0,05; 0,16] | 6 / 100 [0,03; 0,12] |
| Studying and Living in France · conversation · lower | 2 / 100 [0,01; 0,07] | 0 / 100 [0,00; 0,04] |
| Studying in France Advice · share rate · higher | 1 / 100 [0,00; 0,05] | 0 / 100 [0,00; 0,04] |
| 63 hướng còn lại của 33 cặp | 0 / 100 [0,00; 0,04] | 0 / 100 [0,00; 0,04] |

  Với cặp giữ nhiều nhất (Studying in France Advice · engagement, nhánh P): 67 / 100 lần topic không còn sống (không
  cụm nào có J > 0,5), 24 lần sống nhưng "not distinguishable", 9 lần `higher` — tức 9 / 33 trong các lần topic sống.
- **Kết luận mới mỗi lần** (verdict `higher` / `lower` ở bất kỳ cụm nào của lần b):
  - nhánh P: 34 / 100 lần có ít nhất 1 kết luận (33 lần 1, 1 lần 2), median 0 [IQR 0; 1]; tổng 35 kết luận (32
    engagement `higher`, 2 conversation `lower`, 1 share rate `higher`), 23 / 35 ở cụm không khớp topic tham chiếu nào
    (median mỗi lần 0 [0; 0]);
  - nhánh S: 26 / 100 lần (24 lần 1, 2 lần 2); tổng 28 kết luận (27 engagement `higher`, 1 share rate `higher`), 22 / 28
    ở cụm không khớp;
  - họ Holm mỗi lần = 3 × số cụm: P 27–45, S 27–48 phép so.
- **Thăm dò sau khi xem số (không thuộc pre-registration, không thuộc luật):** xếp mỗi kết luận theo topic tham chiếu
  góp nhiều bài nhất vào cụm của nó — chỉ so giữa các topic, bài unclustered ở lần tham chiếu không được tính khi chọn
  (không có ca hoà nào).
  - Nhánh P: 28 / 35 là cụm mà Studying in France Advice góp nhiều nhất; 4 cụm chỉ gồm bài unclustered ở lần tham
    chiếu; 2 cụm Studying and Living in France; 1 cụm France Study Costs and Alternance Policy. Nhánh S: 24 / 28 Studying
    in France Advice, 2 France Study Costs and Alternance Policy, 2 cụm chỉ gồm bài unclustered ở lần tham chiếu.
  - Thành phần 28 cụm Studying in France Advice (nhánh P): cả 28 đều chứa bài unclustered ở lần tham chiếu; median 8
    [IQR 5,75; 9] bài của topic và 5 [4; 6] bài unclustered trong cụm 13 [9; 15] bài; 7 / 28 cụm có nhiều bài
    unclustered hơn bài của topic, 9 / 28 cụm có bài của topic chiếm không quá nửa. Nhánh S (24 cụm): median 8 bài của
    topic, 5 bài unclustered, cụm 13,5 bài; 4 / 24 và 7 / 24 tương ứng.
  - Cliff's δ của các kết luận engagement `higher`: P 0,44–0,80, S 0,50–0,83.

**Mức topic** (độ bền = trung bình J lớn nhất; "sống" = J > 0,5):

| Topic (n unit tham chiếu) | J trung bình P / S | Sống P / S |
|---|---|---|
| Brocante and Vintage Market Hunting (14) | 0,84 / 0,85 | 98 / 99 |
| Alternance Experiences and Interview Advice (9) | 0,70 / 0,74 | 87 / 97 |
| Renting and Tenant Rights France (7) | 0,66 / 0,67 | 90 / 95 |
| Applying to Data Science Masters (10) | 0,61 / 0,62 | 82 / 89 |
| France Study Costs and Alternance Policy (11) | 0,53 / 0,54 | 58 / 56 |
| Food and Drink Finds in France (13) | 0,51 / 0,52 | 41 / 54 |
| Studying and Living in France (8) | 0,49 / 0,48 | 45 / 39 |
| Shopping Deals and Beauty in France (8) | 0,48 / 0,47 | 37 / 29 |
| Studying in France Advice (12) | 0,45 / 0,44 | 33 / 28 |
| Food Finds and Vietnamese Cuisine in France (4) | 0,37 / 0,42 | 15 / 25 |
| Cheap Shopping Deals in France (4) | 0,26 / 0,31 | 6 / 14 |

**Mức cách chia** (median [IQR], n = 100 lần so tham chiếu / 4.950 cặp mỗi nhánh):

| Chỉ số | P: vs tham chiếu | P: theo cặp | S: vs tham chiếu | S: theo cặp |
|---|---|---|---|---|
| AMI, unclustered là một nhãn | 0,50 [0,48; 0,53] | 0,48 [0,45; 0,52] | 0,51 [0,49; 0,54] | 0,51 [0,48; 0,54] |
| ARI, unclustered là một nhãn | 0,33 [0,30; 0,37] | 0,29 [0,25; 0,34] | 0,34 [0,32; 0,38] | 0,33 [0,29; 0,38] |
| AMI, chỉ unit có cụm ở cả hai lần | 0,88 [0,87; 0,91] | 0,87 [0,84; 0,90] | 0,89 [0,87; 0,92] | 0,88 [0,85; 0,91] |
| ARI, chỉ unit có cụm ở cả hai lần | 0,83 [0,80; 0,86] | 0,80 [0,75; 0,85] | 0,83 [0,80; 0,88] | 0,81 [0,76; 0,87] |

Số cụm: P 11,5 [11; 12], S 12 [11; 12]. Tỉ lệ unclustered: P 0,37 [0,33; 0,41], S 0,38 [0,34; 0,41]. DBCV
`validity_index`: P 0,29 [0,26; 0,32], S 0,29 [0,26; 0,31] (n = 100 mỗi nhánh).

**Phân tích lõi thăm dò** (topic có tỉ lệ giữ > 0 ở nhánh P): Studying and Living in France — lõi 2 / 8 unit; Studying
in France Advice — lõi 2 / 12 unit.

## Diễn giải

- **Không có câu khẳng định nào về topic được phép**, đúng kỳ vọng ghi trước. Nguyên nhân nằm ở lần tham chiếu: hôm đó
  không phép so nào đạt p Holm < 0,05 với đủ bài. Trang `/topics` và landing tiếp tục hiện so sánh dạng khám phá.
- **Nếu hôm đó cách chia khác, kết luận gắn với topic cũng không bền** — giả định ở đây là lần 32 có thể đổi chỗ cho
  bất kỳ lần gom cụm lại nào. Cặp giữ nhiều nhất chỉ đạt 9 / 100 lần, xa mốc 75 / 100; CI Wilson [0,05; 0,16] loại trừ
  cả mốc độ nhạy 0,6. Cả hai bước đều chặn: topic đó chỉ còn sống ở 33 / 100 lần, và kể cả trong các lần sống chỉ
  9 / 33 lần ra `higher` (0,27, CI Wilson [0,15; 0,44]) — vẫn xa 0,75.
- **Số kết luận đạt p Holm < 0,05 phụ thuộc cách chia** (phép đo đã chốt trước): 34 / 100 lần ở nhánh P và 26 / 100 ở
  nhánh S có ít nhất một kết luận, phần lớn ở cụm không khớp topic tham chiếu nào theo J > 0,5. Khớp bằng chứng
  0 / 2 / 0 / 1 / 1 của ADR-0024.
- **Các kết luận đó lặp lại quanh cùng một vùng bài** (thăm dò sau khi xem số; 100 lần gom cụm lại dùng cùng một tập
  bài và cùng tỉ lệ, nên đây không phải lặp lại độc lập). 28 / 35 kết luận (nhánh P) nằm ở cụm mà Studying in France
  Advice góp nhiều bài nhất trong các topic — nhưng mọi cụm đó đều trộn thêm bài unclustered ở lần tham chiếu, và ở
  khoảng 1 / 3 số cụm bài của topic chiếm không quá nửa. Giả thuyết: một vùng bài gồm một phần topic này cộng một số
  bài unclustered có engagement cao hơn kênh, còn ranh giới cụm quanh vùng đó đổi theo seed và thứ tự, nên không câu
  khẳng định nào gắn được vào một topic cố định. Kiểm giả thuyết này cần một RQ riêng, chốt trước — không dùng số ở
  đây để khẳng định.
- **Ranh giới giữa các cụm khá ổn định; việc bài nào bị unclustered thì không.** Chỉ trên bài có cụm ở cả hai lần, AMI
  ≈ 0,88 và ARI ≈ 0,83. Tính cả unclustered là một nhãn thì AMI ≈ 0,50: khoảng 37% bài là unclustered và tập đó đổi
  nhiều giữa các lần. So theo cặp gần bằng so với tham chiếu (AMI 0,48 so với 0,50 ở nhánh P), nên về mặt cách chia lần
  32 không phải một lần "lạ".
- **Mức topic phân tầng rõ.** Chỉ Brocante and Vintage Market Hunting có độ bền ≥ 0,75 (mốc "bền" của `fpc`, chỉ để
  định hướng). Ba topic ở 0,6–0,75 (có mẫu hình, thành viên chưa chắc). Bảy topic dưới 0,6; hai topic 4 unit hiếm khi
  tái hiện (sống 6–25 / 100). Ngoài hai topic đó, cỡ topic không xếp theo độ bền (VD 7 unit đứng thứ 3, 12 unit đứng thứ 9). Topic
  chủ đề rộng ("Studying … in France") dao động nhiều là giả thuyết, chưa đo.
- **Ở mức cách chia, nhánh P và S gần như trùng** (AMI theo cặp 0,48 so với 0,51) — giả thuyết: phần lớn dao động đến từ
  thuật toán (seed UMAP + thứ tự đầu vào). Ở mức topic, chênh số lần sống P–S lớn nhất là 13 / 100 (Food and Drink Finds
  in France 41 so với 54), không theo một chiều. Hai nhánh ghép cặp (cùng seed, cùng hoán vị, chỉ khác 5 bài bị bỏ), nên
  phép so đúng là một phép thử ghép cặp theo topic — chưa chạy, không thuộc pre-registration. Vì vậy chưa tách được tác
  động riêng của việc bỏ 3% bài ở mức topic.
- **Lõi thăm dò không ủng hộ phương án C của ADR-0024 theo đúng phép đo đã chốt:** trong các bài của hai topic có tín
  hiệu, lõi chỉ có 2 / 8 và 2 / 12 bài. Phép đo này không xét bài unclustered ở lần tham chiếu, mà phần thăm dò ở trên
  cho thấy nhiều kết luận chứa chúng — nên "Xem lại khi" 2 của ADR-0024 vẫn để ngỏ.
- **Giới hạn của chính lần chạy này:** chỉ một lần tham chiếu (lần 32). Một ngày khác có verdict ở lần tham chiếu thì
  luật mới thật sự được thử trên tỉ lệ giữ; kết quả ở đây nói rằng với dữ liệu hiện tại, khả năng qua luật là rất thấp.
- **Hệ quả (ADR-0036 quyết định 3, ADR sau RQ):** ghi lại luật và đưa vào sản phẩm; chữ hiển thị đang nói các lần gom
  cụm lại "have not been done yet" sẽ lỗi thời. Chi phí đo thật cao hơn ước trước (Phương pháp, "Chi phí đo trước":
  ≈ 1,8 phút mỗi lần, ≈ 3 giờ mỗi nhánh): trong lần chạy, median 136 / 143 giây mỗi lần so — cả họ Holm của lần đó,
  27–48 phép so (nhánh P / S, 8 tiến trình song song, n = 100 mỗi nhánh) → tuần tự ≈ 3,8 / 4,0 giờ mỗi nhánh (100 lần ×
  median), ≈ 7,6 / 8,0 giờ cho cả 201 lần so; ≈ 1 giờ với 8 tiến trình. ADR sau RQ quyết cách chạy.

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

- Commit code: `b2589e1`. Danh tính code (SHA-256 đồ thị import, ghi trong `evaluation.json`): replicates `42916eef8e02…`,
  so sánh `1eab32834b30…`.
- DB đóng băng 2026-11-04 20:48 UTC, SHA-256 `8b517c9c23a62324fcac6020bb0258a620c43a3aae48aedc22bc9acb76d087b3`; lần
  gom cụm tham chiếu 32; SHA-256 vector đã dùng (theo thứ tự job) `26d8450bb4c7…`.
- Kiểm tái lập seed 42: đạt, trùng cả cách đánh số cụm và DBCV. `perm` đánh chỉ số trên thứ tự job (thứ tự rowid của
  `content_units`, bỏ bài không có chữ), không trên id đã sắp.
- Lệnh (từ cùng một checkout, kết quả thô ở `data/experiments/rq01/`, riêng tư):
  1. `uv run python -m scripts.rq01_seed_stability freeze --source <thư mục chính>/data/threads.db`
  2. trong WSL2, venv `~/threads-clustering-env`: `python3 -m scripts.rq01_seed_stability replicates`
  3. `uv run python -m scripts.rq01_seed_stability evaluate --workers 8`
  4. `uv run python -m scripts.rq01_seed_stability report` (thêm sau lần chạy, chỉ đọc kết quả đã có, không tính lại
     phép so nào). Muốn chạy lại đúng bước 1–3 thì checkout `b2589e1`: ở các commit sau, danh tính code của
     `replicates` đã đổi nên `evaluate` từ chối dữ liệu cũ (đúng thiết kế).
- Phiên bản WSL2 (gom cụm, DBCV, AMI / ARI): Python 3.12.3, `umap-learn` 0.5.12, `hdbscan` 0.8.44, `scikit-learn` 1.9.0,
  `numpy` 2.5.2, `scipy` 1.18.1, `numba` 0.67.0, `pynndescent` 0.6.0. Windows (phép so): Python 3.12.4, `numpy` 2.5.2,
  `scipy` 1.18.1.
- Chi phí đo thật (bước `report`): thời gian gom cụm 13,0 / 13,3 giây cho 100 lần mỗi nhánh P / S (median 0,13 giây
  mỗi lần; không tính kiểm tái lập và biên dịch numba); median 136 / 143 giây mỗi lần so (cả họ Holm của lần đó,
  100.000 hoán vị mỗi phép so, 8 tiến trình). Ngoài script: bước `evaluate` chạy khoảng 20:49–21:50 UTC (giờ ghi file); một lần so chạy một mình ở bản
  nháp ≈ 161 giây (đo tay, trước lần chạy).

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
