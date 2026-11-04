# ADR-0036: Chốt trước luật bền cho kết luận về topic, trước khi chạy RQ-01

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-04
- **Người quyết**: Thy — chọn qua câu hỏi 2026-11-04, trước khi chạy bất kỳ lần xáo trộn nào: nhánh chính xáo trộn
  seed UMAP + thứ tự đầu vào + bỏ bài; K = 100 lần; ngưỡng 75% chốt ngay; sau review của code-reviewer: bỏ 3% bài (thay
  10%) và ghi ADR này cùng file pre-registration. Thiết kế do Claude đề xuất; nguồn trích dẫn do researcher kiểm.

> **Quan hệ với ADR-0024.** Thay đúng một câu của ADR-0024 quyết định 2: luật bền "chọn khi RQ-01 có số đo … không
> chọn hằng số trước khi có dữ liệu". Mọi phần khác của ADR-0024 giữ nguyên: tới khi luật này được áp vào sản phẩm,
> so sánh topic vẫn hiển thị dạng khám phá, và lịch sử "đạt ở k trong m cách chia" vẫn chỉ là bản ghi.

## Bối cảnh

- ADR-0024 (2026-10-18) chặn câu khẳng định về topic tới khi có luật bền đo bằng RQ-01, và hẹn chọn ngưỡng **sau** khi
  có số đo. Bằng chứng lúc đó: cùng số liệu, 5 cách chia cụm cho 0 / 2 / 0 / 1 / 1 kết luận đạt p Holm < 0.05.
- Khi soạn RQ-01 (2026-11-04), cách hẹn đó lộ một rủi ro: chọn ngưỡng sau khi thấy tỉ lệ giữ của từng kết luận thì
  ngưỡng có thể bị chọn để một topic "qua" hoặc "trượt". Ullmann, Hennig & Boulesteix (2022, *WIREs DMKD* 12(3),
  e1444, mục 1): càng thử nhiều cách gom cụm, càng dễ có một cách cho kết quả đẹp do may — lý do chốt luật trước khi
  xem kết quả.
- Có tiền lệ thiết kế cho dạng luật "giữ khi xuất hiện trong ≥ π các lần chạy lại": stability selection (Meinshausen &
  Bühlmann 2010, *JRSS-B* 72(4), mục 2.3–2.4: π_thr ∈ (0.6, 0.9), kết quả ít nhạy với π_thr). Mốc "bền" 0.75 và mốc ghép
  cụm 0.5 là **quy ước** của tài liệu gói R `fpc::clusterboot` (chưa kiểm được có trong bài Hennig 2007). Chưa có nghiên
  cứu nào đo đúng độ lặp lại của kết luận kiểm định từng cụm qua các lần gom cụm lại — cách đo là của dự án.
- Đo trước chi phí: một phép so Brunner-Munzel 100.000 hoán vị ≈ 3,2 giây → một lần gom cụm lại + so ≈ 1,8 phút; 100 lần
  ≈ 3 giờ mỗi nhánh.
- Toàn bộ thiết kế, ca biên và nguồn: `docs/rq/RQ-01-seed-stability.md` (pre-registration, cùng commit).

## Quyết định

1. **Luật bền** (thay câu "chọn khi RQ-01 có số đo" của ADR-0024): một kết luận (topic t, tỉ lệ m) chỉ được viết thành
   câu khẳng định khi verdict ở lần gom cụm tham chiếu là `higher` hoặc `lower` (p Holm < 0.05, không cờ
   `insufficient_data` — đúng `testVerdict` của sản phẩm) **và** kết luận giữ đúng hướng đó ở ≥ 75 trong 100 lần gom
   cụm lại của nhánh chính. **Giữ ở lần b** = topic có cụm khớp (Jaccard > 0.5) **và** cụm đó có verdict cùng hướng
   theo đúng `testVerdict` (p Holm của chính lần b < 0.05, không cờ `insufficient_data`) — cùng dấu δ thôi là chưa đủ.
2. **Nhánh chính** = mỗi lần b đổi seed UMAP (= b), đảo thứ tự bài và bỏ ⌈3% · N⌉ bài; topic còn "sống" khi cụm khớp có
   Jaccard > 0.5; mọi ca thiếu hoặc không đạt (không có cụm khớp, cờ mẫu nhỏ, p Holm ≥ 0.05 hoặc không xác định, δ = 0) tính là
   **không giữ**, mẫu số luôn là 100. Chi
   tiết, nhánh phụ và ca biên: file RQ-01.
3. **ADR sau RQ-01 chỉ được ghi lại và đưa luật này vào sản phẩm** (cách chạy, tần suất, chữ hiển thị), **không chọn
   lại** ngưỡng, K, mức bỏ bài hay mốc Jaccard. Bảng độ nhạy 0.6 / 0.9 chỉ để báo cáo.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ đúng chữ ADR-0024: chọn ngưỡng sau khi có số | Không cần ADR mới | Ngưỡng có thể bị chọn theo kết quả; người đọc chuyên môn sẽ hỏi | Thy chọn chốt trước (2026-11-04) |
| Chỉ thêm câu ràng buộc trong file RQ, không ADR | Nhanh | File RQ không thay được câu của một ADR đã Accepted; ADR sau RQ vẫn có thể chọn lại | Thy chọn ghi ADR cùng PR |
| X = 0.6 / X = 0.9 | Lỏng hơn / chặt bằng ví dụ của Meinshausen & Bühlmann | 0.6: kết luận dễ phụ thuộc cách chia; 0.9: có thể không topic nào đạt | Thy chọn 0.75 (giữa khoảng tiền lệ, trùng mốc "bền" của `fpc`) |
| Bỏ 10% bài | Bảo thủ hơn | Mạnh gấp nhiều lần mức đổi thật giữa hai cách chia (1–5 bài, ADR-0024); topic ít bài đi nên phép so yếu đi, tỉ lệ giữ thấp xuống một phần do thiếu bài | Thy đổi sang 3% sau review |
| K = 50 / K = 200 | Nhanh gấp đôi / chính xác hơn | Sai số chuẩn tới ≈ 0.07 / thêm khoảng 3 giờ mỗi nhánh | Thy chọn K = 100 (mặc định khuyên dùng của `clusterboot`, sai số chuẩn ≤ 0.05) |

## Hệ quả

- **Docs (cùng commit):** `docs/rq/RQ-01-seed-stability.md` + `docs/rq/README.md` (mới); `docs/claude/data-model.md`
  (mục so sánh topic trỏ tới ADR này); `docs/roadmap.md` (hàng RQ-01); `docs/status.md`; `docs/decisions/README.md`.
- **Code:** chỉ đổi 8 chỗ chữ hiển thị (Hệ quả UI) và vài comment. PR sau viết `scripts/` cho RQ-01 (bước WSL2 `replicates` + bước `evaluate`), chạy, điền kết quả
  vào file RQ; ADR sau RQ đưa luật vào job / API / chữ hiển thị.
- **Luật (`invariants.toml`):** `ADR0036-rule-chosen-later` cấm câu cũ "ngưỡng / luật bền sẽ chọn sau RQ-01" (`chọn
  luật bền` đứng sau "ADR mới", "ADR" hay "RQ-01"; "luật chọn sau RQ-01"; "chọn khi RQ-01 có số đo"; "chưa có luật bền", "chưa có luật nên hiện chưa có câu khẳng định") trong `docs/**`, `src/**`
  và README;
  câu đúng "ADR-0036 chọn luật bền …" không bị bắt. `ADR0036-stability-rule-not-set` cấm 4 câu hiển thị cũ ("no stability rule is set yet", "that rule is not set yet", "the rule will come from
  re-clustering", "that measurement will set the rule"; `mockups = true`). `planned_paths` bỏ `docs/rq` (thư mục đã có), giữ `docs/rq/**` cho các file RQ chưa tạo.
- **Rủi ro chấp nhận:** luật có thể không cho kết luận nào qua (kỳ vọng ghi trước trong file RQ) — landing vẫn không có
  câu khẳng định; một kết luận có tỉ lệ giữ thật 0.70 vẫn qua với xác suất khoảng 16%, thật 0.80 trượt khoảng 9% (K = 100,
  quyết theo ước lượng điểm).
- **Xem lại khi:**
  1. Bước kiểm tái lập (seed 42 + thứ tự job phải ra đúng nhãn đã lưu) thất bại → dừng, báo Thy; không đổi mốc tham
     chiếu.
  2. Áp luật hằng ngày quá tốn (≈ 3 giờ mỗi lần) → ADR sau RQ đổi **cách chạy** (tần suất, số hoán vị), không đổi luật.
  3. Đổi model embedding hay tham số gom cụm (RQ-02 / RQ-03) → luật giữ, nhưng phải đo lại tỉ lệ giữ trên cấu hình mới.

### Hệ quả UI

- Dòng `docs/design/ui-contract.md` thêm: `UI-0036-rule-set-not-run` — 8 chỗ chữ nói "chưa có luật", "luật sẽ đến từ phép
  đo" hoặc tả phép đo thiếu việc bỏ bài (câu trả lời, gạch đầu dòng, hàng "Stability across random seeds" và Limits của
  khối Stability `/topics` + landing; Limits khối 01 `/topics`; Limits panel Proof; mục "Random seed" và "Lead vs
  finding") đổi thành luật "fixed in advance", các lần gom cụm lại với seed khác "have not been
  done yet"; mục "Lead vs finding" nêu luật (100 lần, ≥ 75 giữ hướng, bỏ 3%). Phát hiện bởi consistency-auditor +
  copy-reviewer 2026-11-04; Thy duyệt bộ chữ (bản A, rồi bộ sửa: mục "Lead vs finding" định nghĩa đủ "giữ" —
  tìm lại topic (công thức Jaccard), đủ bài, p Holm < 0.05, cùng hướng; lần chạy lại có bỏ 3% bài — sau code-reviewer,
  ux-reviewer, copy-reviewer).
  Sửa: `UI-0024-exploratory-comparisons` cột B "chưa áp luật bền" (luật chốt ở đây, áp sau RQ-01); kết luận vẫn là gợi ý.
