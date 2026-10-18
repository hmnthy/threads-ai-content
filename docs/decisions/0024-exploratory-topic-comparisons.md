# ADR-0024: Kết luận so sánh topic trình bày dạng khám phá tới khi bền qua các cách chia cụm

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-18
- **Người quyết**: Thy — chọn phương án E sau khi đọc đề xuất kèm số đo (2026-10-18): đơn vị kết luận giữ là topic;
  trước deploy chấp nhận trình bày dạng khám phá; ngưỡng của luật bền chọn sau khi có số đo; làm RQ-01 ngay sau deploy.
  Claude Code đo và đề xuất.

> **Quan hệ với ADR-0023.** Không thay ADR-0023: phép so (Brunner-Munzel hoán vị + Cliff's δ kèm CI), nhóm so sánh và
> họ Holm giữ nguyên. ADR này **thu hẹp** đúng một quy tắc của ADR-0023 — "chỉ được khẳng định khi p Holm < 0.05" —
> bằng một điều kiện thứ hai: kết luận phải **bền qua các cách chia cụm**.

## Bối cảnh

### Câu hỏi

Landing (panel 1) trả lời "Which topics get a higher engagement rate than the rest of the channel?" bằng 1 câu khẳng
định khi p Holm < 0.05 (tại commit `4f51363`: `LandingProof.tsx` dòng 116–122, quy tắc ở `landing.ts` dòng
74–81). Trước khi deploy công khai cần biết: câu khẳng định đó có đứng được qua các
lần gom cụm không.

### Bằng chứng (DB thật, tới lần gom cụm 2026-10-18)

> Mọi con số dưới đây sinh lại bằng `uv run python -m scripts.topic_stability_report --reference-run 16
> --reference-cluster 8` (chỉ đọc DB, seed cố định); "mục N" trỏ tới mục N trong output.

**Thuật ngữ.** *Cách chia cụm* = kết quả gán mỗi bài vào 1 cụm hoặc nhiễu của 1 lần gom cụm (`cluster_runs.labels_json`).
*ARI* (Adjusted Rand Index) = mức giống nhau giữa 2 cách chia, 1 = y hệt, ~0 = như ngẫu nhiên.

1. **16 lần gom cụm (`cluster_runs.id` 2–17) chỉ là 5 cách chia khác nhau** (mục 1). Hai lần thuộc cùng cách chia khi
   nhãn của mọi unit giống hệt (cùng tập unit, cùng nhãn) — job hằng ngày trên cùng dữ liệu, seed cố định cho đúng như
   vậy. Cụm chỉ đổi khi có bài mới, và đổi mạnh: thêm 2 / 2 / 1 / 5 unit, ARI so với lần trước 0.48 / 0.30 / 0.31 /
   0.32 (`cluster_runs.ari_vs_previous`; ARI 0.22 của lần 2 so với lần 1 không còn trong bảng). Đếm "giữ qua N lần"
   theo ngày sẽ đếm lặp 1 bằng chứng. Không dùng "ARI = 1" làm tiêu chí: ARI chỉ tính trên unit chung của 2 lần
   (`src/pipeline/clustering_import.py`), nên lần có thêm bài mới vẫn có thể ra ARI 1.
2. **Số kết luận đạt p Holm < 0.05 đã lưu đổi theo ngày** (mục 2, `topic_comparisons`, 100.000 hoán vị): lần 9 (dữ
   liệu 09/10) 3/27; lần 10–11 0/24; lần 12–16 1/27 và lần 17 1/30 — cùng topic_11 engagement (lần 16, dữ liệu 17/10:
   n = 18 vs 131, δ +0.60 [+0.39; +0.81, unadjusted], p Holm 0.0005; lần 17: n = 13 vs 141, δ +0.53, p Holm 0.0144).
3. **Riêng cách chia cụm đã đủ đổi kết luận.** Giữ cố định số liệu (snapshot mới nhất của mọi bài), chạy lại
   `compare_topics()` (20.000 hoán vị; sàn p thô ≈ 0.00005, dưới ngưỡng Holm 0.05/30 ≈ 0.0017) trên lần cuối của mỗi
   cách chia (lần 3, 9, 11, 16, 17): số kết luận đạt là **0 / 2 / 0 / 1 / 1** (mục 3). Giữ cố định cả **tập bài** —
   chỉ 144 unit có mặt ở mọi cách chia — vẫn **0 / 2 / 0 / 1 / 1** (mục 4): khác biệt đến từ cách chia, không từ bài mới.
4. **Tín hiệu có thật nhưng hiện ra hay không tuỳ ranh giới cụm** (mục 5, theo dõi 18 bài của topic_11 ở lần 16). Ở 4
   cách chia còn lại, 9–11 bài trong số đó nằm chung một cụm. Cụm ôm gọn chúng thì đạt (lần 9: n = 12, δ +0.62; lần 17:
   n = 13, δ +0.53, p Holm 0.021). Khi chúng bị pha vào cụm 35 bài (lần 11: δ +0.04) hoặc 5 bài rơi vào nhiễu (lần 3:
   δ +0.36 trên cụm 13 bài) thì không đạt.
5. **Ổn định theo seed chưa đo trên dữ liệu hiện tại.** ADR-0018 đã thấy cùng 146 bài, 10 seed UMAP → 8–11 cụm, nhiễu
   30–40%: job "ổn định" mỗi ngày chỉ vì seed cố định. RQ-01 (`docs/roadmap.md`) chưa làm.

**Giới hạn:** 5 cách chia, cụm 4–35 bài (mục 3) — đủ để thấy vấn đề, không đủ để ước lượng xác suất một kết luận giữ
được. Lần 16–17 (cùng mốc số liệu 17/10): số p ở mục 3 (20.000 hoán vị) khác số lưu ở mục 2 (100.000) chỉ vì số lần
hoán vị — cùng n, δ, CI (lần 17: p Holm 0.021 so với 0.0144); các lần trước lưu trên snapshot cũ hơn, còn mục 4 dùng
tập bài khác. Lần gom cụm mới thêm cách chia vào output của script; số trên là ảnh chụp tới 2026-10-18.

## Quyết định

1. **Đơn vị kết luận vẫn là topic** (cụm), phương pháp và họ Holm theo ADR-0023.
2. **Một kết luận chỉ được viết thành câu khẳng định khi p Holm < 0.05 VÀ qua luật bền đo bằng RQ-01** (nhiều seed).
   Luật cụ thể — N cách chia khác nhau, hoặc K seed với ngưỡng X% — **chọn khi RQ-01 có số đo**, ghi bằng ADR mới;
   không chọn hằng số trước khi có dữ liệu. Tới lúc đó, so sánh topic hiển thị **dạng khám phá**: δ + CI (unadjusted) +
   p Holm của mọi topic, không câu "posts on X tend to get a higher / lower engagement rate", kèm 1 câu giới hạn: topic
   được tính lại khi có bài mới nên các phép so có thể đổi theo.
3. **Lịch sử theo cách chia:** mỗi topic kèm "đạt ở k trong m cách chia" — đếm theo **cách chia khác nhau** (lần gom
   cụm có nhãn khác lần trước, theo bằng chứng 1), không theo ngày. **RQ-01 làm ngay sau deploy.**

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| A. Chỉ công bố khi giữ qua N lần gom cụm | Đơn giản, dễ giải thích | Đếm theo ngày là đếm lặp (bằng chứng 1); dù đếm theo cách chia vẫn chậm (cách chia chỉ đổi khi có bài mới) và đo lịch sử với seed cố định, không đo độ nhạy; topic gộp/tách → id mới → mất bộ đếm | Thy giữ phần đếm (quyết định 3) làm lịch sử hiển thị, không làm cổng công bố một mình |
| B. Đa seed làm cổng ngay | Đo trực tiếp độ nhạy theo seed | Thêm K lần UMAP + HDBSCAN mỗi ngày, ghép cụm giữa seed; K và X chưa có số đo để chọn | Chọn làm RQ-01 sau deploy, ngưỡng chọn khi có số |
| C. Kết luận theo "lõi" bài (ma trận đồng cụm) | Khớp bằng chứng 4 | Đổi đơn vị phân tích của ADR-0023; khó giải thích; lõi nhỏ → n nhỏ | Thy chọn đơn vị topic; để mở nếu RQ-01 cho thấy tín hiệu luôn nằm ở lõi |
| D. Chỉ trình bày dạng khám phá, không kế hoạch nâng | Rẻ nhất, trung thực | Không bao giờ có câu trả lời | Thy chọn D **kèm** đường nâng qua RQ-01 (E) |

## Hệ quả

- **Code (`/decision-sweep` của ADR này):** panel 1 bỏ câu khẳng định và câu hover "Its posts tend to get a … rate";
  `testVerdict` (`src/dashboard/src/lib/landing.ts:74-81`) vẫn trả "higher"/"lower" để chọn topic được nêu tên, nhưng
  chữ dựng từ đó là gợi ý ("For now, … stands out", "a lead, not a finding") — qua `copy-reviewer`, Thy duyệt từng
  câu 2026-10-18, ghi `docs/design/ui-contract-audit.md`. Thy chọn thêm: đánh dấu cả topic thấp hơn — chưa có token
  màu, chuyển Claude Design.
- **Số liệu:** `scripts/topic_stability_report.py` (+ test) in mọi con số của ADR này.
- **Việc trước deploy (PR sau):** lịch sử "k trong m cách chia" — job/API phải nhận ra cách chia khác nhau
  (nhãn khác lần trước, như `distinct_partitions` của script) và ghép topic qua các cách chia bằng id bền `topic_N` (ADR-0018). Giới hạn: topic
  gộp/tách nhận id mới nên lịch sử bắt đầu lại từ 0 — ghi rõ trên UI.
- **RQ-01 (sau deploy):** gom cụm K seed trên embedding đã lưu, chạy `compare_topics` mỗi seed, ghép cụm theo thành
  viên; báo tỉ lệ seed mà mỗi kết luận đạt + ARI cặp seed. Số liệu này là căn cứ chọn luật bền.
- **Docs:** `docs/claude/data-model.md` (mục so sánh topic), README ×3 nếu mô tả câu kết luận trên landing,
  `docs/design/ui-contract.md`.
- **Luật (`docs/decisions/invariants.toml`):** `ADR0024-topic-claim` cấm câu khẳng định "tend to get a higher / lower …
  rate than the rest of the channel" trong `docs/**`, `src/**`, README và mockup (`mockups = true`); sửa phần `fix`
  của `ADR0023-more-engagement-question` (đang gợi ý chính câu khẳng định đó); `[[stale_asset]]`
  `ADR0024-landing-screenshot` (ảnh landing chụp panel 1).
- **Rủi ro chấp nhận:** landing không có "câu trả lời" cho tới khi RQ-01 xong; topic_11 (tín hiệu mạnh nhất hiện nay)
  chỉ hiện như kết quả khám phá.
- **Xem lại khi:**
  1. RQ-01 có số đo → ADR mới chọn luật bền (N cách chia / K seed + X%) và cho phép câu khẳng định trở lại.
  2. RQ-01 cho thấy tín hiệu luôn nằm ở một lõi bài nhỏ trong khi ranh giới cụm dao động → cân nhắc phương án C.
  3. Topic trung vị ≥ 20 bài (ADR-0023 "Xem lại khi" 1) — kết luận có thể bớt nhạy với vài bài đổi cụm.

### Hệ quả UI

- Thêm: `UI-0024-exploratory-comparisons` (không câu khẳng định khi chưa qua luật bền; câu giới hạn bắt buộc),
  `UI-0024-partition-history` (lịch sử "k trong m cách chia", code chưa có — Việc trước deploy).
- Sửa: `UI-0023-comparison-test` (cột E: bỏ câu kết luận "tend to get…", giữ δ, CI, hover "(1 + δ)/2"),
  `UI-0023-holm-family` (cột E: "câu khẳng định chỉ khi p Holm < `conclusion_alpha`" → thêm "và qua luật bền
  ADR-0024"). Nâng mốc "Cập nhật tới: ADR-0024".
- Mockup landing (`src/dashboard/mockups/landing.dc.html`) còn câu kết luận dạng khác — "N of T topics differ from the
  rest of the channel after correction" — mà regex của `ADR0024-topic-claim` không bắt: ghi audit cho Claude Design
  (theo chữ mới ở mục ADR-0024 của `ui-contract-audit.md`).
