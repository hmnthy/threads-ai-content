# ADR-0012: Đo "bài lan rộng" bằng tầng reach tương đối; đổi tên `virality_index` thành `share_rate`

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-06
- **Người quyết**: Thy (định nghĩa, ngưỡng, tên, 3 lựa chọn ngày 2026-10-06); Claude đề xuất hiệu chỉnh tăng trưởng + mốc chín và đo số

## Bối cảnh

- `virality_index` = (reposts + quotes) / views × 100 (`src/analysis/share_rate.py:15-25`) đo **tỉ lệ người xem
  đăng lại / trích dẫn**, không đo bài chạm tới bao nhiêu người. Thy: "viral" theo nghĩa mạng xã hội là **độ phủ**. Hai
  chiều này khác nhau thật: engagement rate median của "Top 20% reach" là 1.61% (n = 27) so với 2.13% ở dưới median
  (n = 67) — Cliff's δ = −0.32, CI 95% của hiệu median [0.06; 0.94] điểm %, p = 0.017, p Holm (2 phép so) = 0.033
  (`compare_groups()`). Tầng giữa (2.02%, n = 41) chưa phân biệt được với dưới median (δ = −0.12, CI [−0.34; 0.49]).
  Giải thích khả dĩ (giả thuyết, chưa kiểm): bài lan rộng chạm người lạ, họ tương tác ít hơn — nhưng views vừa là tử số
  của reach tương đối vừa là mẫu số của engagement rate, nên một phần δ âm có thể là cơ học (tương tác tăng chậm hơn
  views).
- Quyết định cũ (plan P1 ngày 2026-10-01, chưa thành ADR, chưa lên UI): nhãn = P90 `virality_index` + sàn views P25 →
  chỉ ~10 bài, quá ít để so sánh nhóm. `is_viral()` / `channel_virality_p90()` (2026-09-03) chưa từng được API gọi.
- **Views thô lệch theo thời điểm đăng**: Spearman ρ(views, tuổi bài) = −0.39, p = 8.5e−7, n = 146 (kênh lớn dần). Xếp
  theo views thô, top 20% có tuổi median 112 ngày so với 224 ngày ở nửa dưới — nhãn sẽ đo "đăng gần đây" chứ không đo
  nội dung, làm sai lệch so sánh chủ đề (Việc 1).
- **Bài mới chưa chín**: views còn tăng. 7 bài có snapshot đầu < 1 ngày sau khi đăng và snapshot cuối ≥ 14 ngày: thời gian
  đạt 90% views mới nhất median 1.4 ngày, P90 4.0 ngày, max 7.1 ngày (tại 2 ngày đã 91%, 7 ngày 97%, 14 ngày 99%).
- Số liệu sinh lại bằng `uv run python -m scripts.reach_report` (DB 2026-10-06, 6 bài views = 0 bị loại theo ADR-0011).

## Quyết định

1. **Đổi tên** `virality_index` → `share_rate` (UI "Share rate"; công thức giữ nguyên) ở code, API
   (`ContentUnitMetrics.share_rate`, `top_by_share_rate`, `WindowAnalyticsOut.share_rate`), dashboard và tài liệu.
   Chữ "viral" không còn xuất hiện ở đâu ngoài lịch sử quyết định.
2. **Tầng reach** (`src/analysis/reach.py`, `GET /analytics/reach`), toàn lịch sử kênh, bài gốc đo được:
   - reach tương đối = views ÷ median views của tối đa **20** bài gốc đo được đăng ngay trước (cần ≥ **10** bài trước);
   - bài đã chín và có mốc: ≥ **P80** → **"Top 20% reach"**, ≥ **P50** → **"Above median reach"** (biên ≥ là đạt);
   - **views thô** trả kèm làm tham chiếu (cùng phân vị, cùng nhóm bài), không dùng để xếp tầng.
3. **Độ chín**: bài có tuổi **tại snapshot mới nhất** (nơi lấy views — không phải tuổi tới hôm nay, vì cron có thể ngắt
   vài ngày, ADR-0017) nhỏ hơn mốc chín → `still_growing`, chưa xếp tầng, API không trả reach tương đối của nó. Mốc chín
   = P90 thời gian đạt 90% views mới nhất, tính lại mỗi lần từ `insights_snapshots`, chỉ trên đường cong có snapshot đầu
   < 1 ngày và snapshot cuối ≥ 14 ngày.

Kết quả hiện tại (2026-10-06): mốc chín 4.0 ngày (n = 7 đường cong); 135 bài xếp tầng — 27 "Top 20% reach" (reach
tương đối ≥ 3.42×), 41 "Above median reach" (≥ 1.11×), 67 dưới median; 10 bài chưa có mốc, 1 bài đang tăng. Sau hiệu
chỉnh ρ(reach tương đối, tuổi bài) = 0.04, p = 0.62, n = 135; tuổi median 3 tầng gần nhau (156 / 183 / 161 ngày). Top 20%
theo reach tương đối trùng 20/27 bài với top 20% theo views thô.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| P90 `virality_index` + sàn views P25 (2026-10-01) | Có tiền lệ (Elmas 2023, arXiv 2303.06120) | Đo chia sẻ, không đo độ phủ; ~10 bài | Sai khái niệm Thy muốn đo |
| Một ngưỡng views ≥ P50, gọi là "viral" (đề xuất đầu của Thy) | Đơn giản | Một nửa số bài mang nhãn "viral" | Thy đổi sang 2 tầng, tên tự giải thích |
| Views thô toàn lịch sử | Dễ giải thích | Lệch theo tuổi bài (ρ = −0.39) | Thy chọn "hiện cả hai": xếp theo bản hiệu chỉnh, views thô làm tham chiếu |
| Xếp tầng ngay, không chờ chín | Không có trạng thái chờ | Bài mới bị xếp thấp rồi đổi tầng | Thy chọn đo mốc chín từ snapshot |
| Cửa sổ mốc 10 hoặc 30 bài | — | — | Độ nhạy (chỉ đổi cửa sổ, giữ cần ≥ 10 bài trước): top 20% trùng 24/27 (10 bài) và 23/27 (30 bài) với cửa sổ 20 → kết luận không phụ thuộc mạnh vào con số này; 20 là lựa chọn thiết kế |

## Hệ quả

- Code: `src/analysis/virality.py` → `src/analysis/share_rate.py` (bỏ `is_viral`, `channel_virality_p90`);
  `src/analysis/reach.py` mới; `insight_views_series()` trong `src/db/schema.py`; `compute_reach()` + endpoint trong
  `src/main.py`; `compare_virality_with_without_author_reply` → `compare_with_without_author_reply`; dashboard đổi nhãn
  "Virality" → "Share rate" và có type `ReachTiers` (chưa có giao diện tầng — chờ mockup, ADR-0020).
- Docs: `docs/claude/data-model.md` (mục "Tầng reach"), README ×3, `docs/design/ui-contract.md`.
- Luật: `ADR0012-old-share-name` (tên cũ trong code/API), `ADR0012-old-label-wording` (chữ "viral" ở mọi mặt, kể cả mockup),
  `ADR0012-raw-views-as-reach` (views thô không được gọi là "reach" — chữ này dành cho tầng), `[[stale_asset]]` ảnh
  overview / analytics / landing.
- **Rủi ro chấp nhận**: mốc chín dựa trên n = 7 đường cong (snapshot chỉ có từ 2026-08-31) — `n_curves` luôn trả kèm. Hai
  mốc đủ điều kiện đường cong (1 ngày, 14 ngày) và cửa sổ 20 bài là lựa chọn thiết kế, có nhãn trong `reach.py`.
  Bài vừa qua mốc chín thường đã đạt ≥ ~90% views cuối (reach tương đối thấp hơn ≤ ~10%), nhưng theo định nghĩa P90 khoảng
  1/10 bài chậm hơn (tới 7.1 ngày trên n = 7) — chỉ ảnh hưởng vài bài gần nhất.
  Khi nhiều reach tương đối bằng nhau, tỉ lệ thật mỗi tầng có thể lệch khỏi 20% / 50% — UI đọc `counts`, không suy từ tên.
- **Để lại cho Việc 1** (brief Topics): sàn views cho bảng top theo rate (trước là P25), so sánh biến giải thích giữa các
  tầng + hiệu chỉnh Holm, nhóm so sánh.
- **Xem lại khi**: `n_curves` ≥ 30 (mốc chín ổn định hơn — xem lại 2 mốc đủ điều kiện); hoặc kênh đổi nhịp đăng khiến
  20 bài trải dài hơn ~3 tháng; hoặc độ nhạy 10/30 bài trùng dưới 2/3 top 20%.

### Hệ quả UI

- Sửa: `UI-0011-no-zero-rate`, `UI-L20260903-window-median` (tên trường `share_rate`); `UI-L20260830-insight-fields`
  ("reach" chỉ dùng cho tầng reach tương đối, không cho views thô hay một trường API).
- Thêm: `UI-0012-share-rate-name`, `UI-0012-reach-tiers`, `UI-0012-raw-views-reference`, `UI-0012-not-tiered`.
- Mockup còn chữ "Virality" / "viral" → cảnh báo, ghi vào `docs/design/ui-contract-audit.md` cho Claude Design.
