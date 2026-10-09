# RQ-NN: <Câu hỏi, dạng câu hỏi>

- **Trạng thái**: Planned | Running | Done | Inconclusive
- **Phục vụ**: <knowledge base / hiểu kênh / methodology> — vì sao câu trả lời quan trọng cho dự án
- **Liên quan**: ADR-xxxx, RQ-yy

## Giả thuyết

H0 / H1 (hoặc kỳ vọng mô tả nếu là RQ khám phá).

## Dữ liệu

Nguồn (bảng SQLite, lọc gì), n thật, ngày snapshot. Cái gì bị loại và vì sao.

## Phương pháp

Các bước, model/tham số, seed, baseline so sánh. Code ở đâu (`src/...` hoặc `experiments/...`).

## Metric và ngưỡng quyết định (điền TRƯỚC khi chạy)

| Metric | Vì sao chọn | Ngưỡng để kết luận |
|---|---|---|

## Kết quả

Bảng số kèm n, effect size, CI 95% (của δ từ `compare_groups()`; bootstrap chỉ cho metric không có CI từ kiểm định hay công thức). Link run trong `experiments/registry.jsonl`.

## Diễn giải

Theo Narrative Layering (`docs/claude/data-model.md`): chỉ khẳng định khi có kiểm định + effect size + CI; nếu không thì chỉ mô tả.

## Giới hạn

n nhỏ, 1 annotator, dữ liệu 1 kênh, confounder đã biết, điều chưa kiểm được.

## Tái lập

Lệnh chạy chính xác, seed, commit hash, run id.
