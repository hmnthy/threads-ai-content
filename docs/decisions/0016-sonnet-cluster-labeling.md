# ADR-0016: Đặt tên cụm bằng `claude-sonnet-5-5` thay cho `claude-opus-5`

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-04
- **Người quyết**: Thy (chọn Sonnet 5.5), Claude so sánh trên data thật

## Bối cảnh

Quyết định 2026-09-03 (`legacy-log.md`, dòng "Chốt `CLUSTER_LABELING_MODEL`") giữ `claude-opus-5` vì tên cụm tốt hơn với bài Việt/Pháp trộn và "chi phí task labeling nhỏ". Một tháng sau:

- Job NLP đặt tên lại **mọi** cụm mỗi đêm (~9–11 lời gọi, tối đa 15 bài/cụm), kể cả khi cụm không đổi. Credit trả trước còn $1.77 (Console 2026-10-04) — với Opus, chi phí đặt tên hằng đêm không còn "không đáng kể".
- Key cũ hết hạn 2026-10-02 → job lỗi 401 đêm 2026-10-03 (`data/logs/nlp_cluster_job.log`); key mới tạo 2026-10-04. Không liên quan model nhưng là dịp rà lại chi phí.
- So sánh trên **9 cụm thật** (cùng đầu vào job import: bài xếp theo độ gần tâm cụm, tối đa 15 bài; DB ngày 2026-10-01): Sonnet 5.5 cho tên đúng chủ đề ở 9/9 cụm, mô tả chi tiết tương đương. Khác biệt nhìn thấy: vài tên của Sonnet chung chung hơn ("Life Abroad in France" thay cho "Life as a Vietnamese in France") và không thống nhất kiểu viết hoa ("Shopping and prices in France"). Đây là đánh giá định tính của 1 người trên n = 9 — không phải đo lường.

Kèm theo: README ×3 ghi "prompt caching" ở dòng Claude API, nhưng code không có `cache_control` và Console báo "Prompt caching: Not enabled". Prompt đặt tên mỗi cụm khác nhau nên cache không giúp gì — đây là mô tả sai, sửa trong cùng ADR.

## Quyết định

`CLUSTER_LABELING_MODEL = "claude-sonnet-5-5"` (`src/nlp/topics.py`); prompt, `max_tokens`, `effort: low` giữ nguyên. Tên cụm hiện có được thay ở lần chạy job NLP kế tiếp. Docs bỏ cụm "prompt caching".

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Giữ `claude-opus-5` | Tên sắc hơn một chút | Đắt nhất; model đời cũ | Chi phí hằng đêm so với credit còn lại |
| `claude-haiku-4-5` | Rẻ nhất | Chưa so trên data thật; rủi ro tên kém với bài trộn ngôn ngữ | Thy chọn Sonnet — cân bằng chất lượng/chi phí |
| Chỉ đặt tên lại cụm đã đổi (giữ tên khi thành viên gần như giữ nguyên) | Giảm số lời gọi về ~0 ở phần lớn các đêm, tên ổn định | Cần ngưỡng "gần như giữ nguyên" có căn cứ + test | Bổ sung, không thay thế — để ADR sau |

## Hệ quả

- `src/nlp/topics.py`: đổi hằng số + chú thích trỏ ADR này.
- `README.md` / `README.vi.md` / `README.fr.md`, `docs/claude/architecture.md`: bảng Tech Stack ghi `claude-sonnet-5-5`, bỏ "prompt caching".
- Sổ luật: `ADR0016-opus-labeling` (cấm nhắc `claude-opus-5` ngoài `docs/decisions/`), `ADR0016-prompt-caching` (cấm hứa prompt caching ở README ×3 và `docs/claude/`).
- Tên cụm trên dashboard đổi sau lần chạy job kế tiếp (2026-10-05 03:00) → ảnh `topics` trong README sẽ cũ; chụp lại cùng đợt UI P1.
- Xem lại khi: Thy thấy tên cụm sau lần chạy thật kém rõ rệt (quay lại Opus 5.5 hoặc thêm chỉ dẫn "Title Case, nêu rõ góc nhìn người Việt" vào prompt), hoặc khi làm phương án "chỉ đặt tên lại cụm đã đổi".
