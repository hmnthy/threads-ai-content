---
name: new-rq
description: Create a new research-question write-up (docs/rq/RQ-xx) from the project template, with the decision criteria fixed before any experiment runs.
argument-hint: "<RQ-number> <question>, e.g. '01 Are the HDBSCAN clusters stable across seeds?'"
disable-model-invocation: true
---

# /new-rq — mở 1 câu hỏi nghiên cứu

Đầu vào: **$ARGUMENTS**

## RQ hiện có

!`ls docs/rq 2>/dev/null || echo "(chưa có docs/rq/)"`

## Các bước

1. Đối chiếu bảng RQ trong `docs/roadmap.md` (section D). RQ nằm ngoài bảng → hỏi Thy trước khi tạo.
2. Tạo `docs/rq/RQ-NN-ten-ngan.md` theo `${CLAUDE_SKILL_DIR}/template.md`. Nếu `docs/rq/README.md` chưa có thì tạo bảng chỉ mục (RQ · câu hỏi · trạng thái · kết luận 1 dòng).
3. Điền **trước khi chạy bất cứ thí nghiệm nào**: câu hỏi, giả thuyết, dữ liệu dự kiến, phương pháp, metric chính, **ngưỡng quyết định** (pre-registration — cam kết trước tiêu chí kết luận để tránh chọn kết quả đẹp sau khi thấy số).
4. Để trống phần Kết quả / Diễn giải; trạng thái `Planned`.
5. RQ công khai được (sẽ vào repo public) → viết tiếng Việt, dễ dịch; **không** chép nguyên văn bình luận follower hay nội dung `docs/research/`.
6. Thêm dòng vào `docs/rq/README.md`, gợi ý `/checkpoint`.
