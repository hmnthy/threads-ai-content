# ADR-0011: Bài có views = 0 là dữ liệu thiếu — loại khỏi mọi phân phối rate, báo số bị loại

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy (chọn "loại + ghi số bị loại"), code-reviewer phát hiện, Claude đề xuất

## Bối cảnh

Code-reviewer (2026-09-30), kiểm lại bằng truy vấn chỉ-đọc trên `data/threads.db`: **6/150 root post** (đăng 02/2026) có `views = 0` và mọi bộ đếm khác = 0 ở **cả 72 snapshot** của từng bài. Đây là insight không trả về, không phải bài có 0% tương tác.

`PostInsights.engagement_rate` (và `virality_index`, `conversation_rate`) trả `0.0` khi `views == 0` — guard chống chia 0 đúng, nhưng khi đưa vào phân phối thì 6 số 0 giả này:
- kéo median engagement toàn kênh xuống 1.92% (n=150) thay vì 1.99% (n=144);
- nằm trong ô heatmap giờ/thứ (ô 9h Paris n=4 có 2 bài như vậy; thứ Hai có 2).

Dashboard vừa đưa n lên UI (nhánh `feat/dashboard-honesty-p0`), nên n bị thổi phồng hiện ra trước người xem.

## Quyết định

Một bài có `views == 0` ở snapshot mới nhất là **thiếu dữ liệu** với mọi rate chia cho views. Nó bị loại khỏi mọi phân phối rate (median/mean/IQR, bucket giờ/thứ, bảng xếp hạng theo rate) và số bài bị loại được trả ra cùng kết quả (`excluded_no_views`) để UI ghi rõ. Không bao giờ biến "không có views" thành "0%".

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ là 0% | Không phải sửa | Số 0 giả kéo lệch median và n | Sai nghĩa dữ liệu |
| Verify live 6 bài trước rồi mới quyết | Biết nguyên nhân (bài ẩn/xoá?) | Chậm; kết luận "loại khỏi rate" không đổi dù nguyên nhân là gì | Thy chọn loại ngay |

## Hệ quả

- `src/analysis/stats.py`: `split_measurable()` tách cặp (post, insight) có `views > 0`; `src/main.py` dùng nó ở `/analytics/overview` và `/analytics/window`, trả thêm `excluded_no_views`.
- Dashboard ghi "N excluded: no views recorded" cạnh các số liệu tổng hợp.
- Quy tắc viết vào `.claude/rules/python.md` (mọi phân phối rate mới phải đi qua `split_measurable()`).
- Sổ luật: **không có luật regex** — đây là hành vi code, được giữ bằng test (`tests/analysis/test_stats.py`, `tests/test_main.py`), không phải bằng chữ trong docs.
- Xem lại khi: verify live cho thấy Threads trả views = 0 cho bài thật có người xem (khi đó cần phân biệt "0 thật" với "thiếu"), hoặc số bài bị loại vượt ~10% (có thể lỗi ingest).
