# ADR-0001: Thu hẹp scope — bỏ generation giọng văn, carousel, KOL engine; tập trung NLP → knowledge base

- **Trạng thái**: Accepted
- **Ngày**: 2026-09-30
- **Người quyết**: Thy

## Bối cảnh

Tới 2026-09-30 dự án ôm 4 mục tiêu song song: (1) analytics + NLP, (2) generate bài theo giọng văn tác giả (`src/generation/`, few-shot từ `content/Scripts/`), (3) generate ảnh carousel (`src/carousel/`, Pillow + 41MB font Google Sans + mapping topic↔template), (4) "KOL Strategy Engine" nghiên cứu hệ sinh thái Threads (cần Meta Advanced Access). Chỉ (1) có code thật; (2)(3) chỉ có docs + asset, (4) chỉ là định hướng. Sprint plan v3 (21-22 ngày) chưa tick được mục nào dù phần lớn (1) đã xong — dấu hiệu plan quá rộng để theo dõi.

## Quyết định

**Bỏ vĩnh viễn** (2), (3), (4). Dự án tập trung theo đúng thứ tự:
1. Phân tích NLP sâu, viết thành các câu hỏi nghiên cứu (RQ) có phương pháp và giới hạn rõ ràng.
2. Knowledge base (cơ sở tri thức) tra cứu được, cập nhật liên tục, có đo chất lượng truy xuất.
3. Chỉ khi KB qua cổng chất lượng (`docs/roadmap.md` Phase F): landing thương hiệu thydilammuon + chatbot hỏi đáp dựa trên KB.

## Phương án đã cân nhắc

| Phương án | Vì sao không chọn |
|---|---|
| Giữ generation giọng văn như "Giai đoạn 3" | Không có metric tự động cho "đúng giọng văn" (sprint v3 tự ghi là rủi ro lịch cao nhất); chiếm công sức mà không làm sâu thêm phần NLP |
| Giữ carousel như "nếu còn thời gian" | 25-40h cho việc overlay text lên ảnh — không phải năng lực NLP/MLE, và cần đo toạ độ 28 slide thủ công |
| Giữ KOL engine làm roadmap dài hạn | Phụ thuộc Meta App Review ngoài tầm kiểm soát; giữ trong CLAUDE.md chỉ tốn context mỗi phiên |

## Hệ quả

- Xoá `src/carousel/` (font), dependency `pillow`; gỡ khối "AI Content Generation — coming soon" trên landing; cập nhật 3 README và docs.
- Bộ phân loại 6 nhãn cố định (vốn để chọn template carousel) **giữ lại làm câu hỏi nghiên cứu độc lập** (RQ-08), không còn là thành phần sản phẩm.
- Dashboard **tiếp tục phát triển** (trang KB explorer, trang kết quả nghiên cứu).
- Git history vẫn chứa font và docs cũ — khi tạo repo public phải `git filter-repo` trên bản clone mới, không copy history (xem `docs/roadmap.md`).
- Xem lại quyết định này: chỉ khi chatbot đã chạy ổn định và có nhu cầu thật từ tác giả về generation — khi đó là 1 ADR mới, không "mở lại" ADR này.
