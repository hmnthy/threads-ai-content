# Brief cho Claude Code: duyệt cột E của hợp đồng UI (2026-10-06)

> Viết bởi: Claude Design. Đọc kèm: `docs/design/ui-contract.md` (Cập nhật tới: ADR-0020).
> Phạm vi: chỉ cột E (Trình bày) và Câu hỏi mở 2, 3. Cột A–D không đụng tới.
> Mọi dòng không có trong brief này: **cột E đã duyệt, giữ nguyên**.

## 1. Đề xuất sửa cột E

| id | E hiện tại (tóm tắt) | E đề xuất | Lý do |
|---|---|---|---|
| UI-0011-excluded | Đúng 1 câu "N excluded: no views recorded" | Chuỗi chuẩn duy nhất là "N excluded: no views recorded" (nguyên văn ADR-0011). Khi cần mẫu số thì viết "N of M excluded: no views recorded". | Hiện UI-0011-excluded và UI-0011-two-exclusions đang dùng 2 cách viết khác nhau |
| UI-0011-two-exclusions | "N have no text to embed" và "N excluded from rates: no views recorded" | Hai dòng riêng: "N of M posts have no text to embed" và "N of M excluded: no views recorded" | Đi theo chuỗi chuẩn ở dòng trên; mỗi dòng có mẫu số riêng |
| UI-0018-label-provenance | Tên **luôn** kèm "named by Claude" | Ghi "named by Claude" **một lần cho mỗi khối**: ở tiêu đề cột hoặc nhãn danh sách nếu khối có nhiều tên, ngay cạnh tên nếu tên đứng một mình (chú thích, hồ sơ topic). Không lặp lại ở từng hàng. | Bảng 9 hàng lặp nhãn 9 lần thành nhiễu thị giác; người đọc vẫn biết nguồn của từng tên |
| UI-0004-ari-two-ways | (không có trạng thái null) | Thêm: null → "not computed (fewer than 2 posts to compare)" | Cột B có nói ARI null khi < 2 bài, nhưng E chưa nói cách hiện. Cách viết khớp với trạng thái null của DBCV |
| UI-L20260930-topic-single-accent | Một màu nhấn amber cho topic đang chọn | Thêm: điểm nhiễu vẽ vòng rỗng xám, điểm topic khác chấm đặc xám | Để khớp với UI-0004-noise-basis (nhiễu không xếp như một topic); landing đã làm vậy |
| UI-L20260829-mobile | Card 1 cột, heatmap 2×12, bảng/sơ đồ cuộn ngang | Thêm: biểu đồ strip/beeswarm giữ bề rộng tối thiểu 720px, xếp chấm lại theo bề rộng thật, dưới mức đó cuộn ngang trong container. Không nén làm chấm chồng lên nhau. | Hero landing đã làm theo cách này (ResizeObserver); Topics và Analytics sẽ dùng chung |
| UI-0004-representatives | Khối "3 posts nearest the centre" là bài đại diện để đọc | Nhãn khối: "3 posts nearest the centre, for reading" | Một cụm từ đủ để người đọc phân biệt với 15 bài đầu vào của Claude (UI-0016-label-input) |

## 2. Trả lời Câu hỏi mở

### Câu 2: bộ nhãn trạng thái → **giữ hai tập riêng**
- **live / next / research** trả lời câu hỏi "thành phần này đã được xây chưa" (lộ trình).
- **live / deferred** trả lời câu hỏi "chỉ số này có tính được với dữ liệu hiện có không" (độ sẵn sàng).
- Gộp `deferred` vào `next` sẽ thành nói sai: `window_velocity` đã có trong code (`src/analysis/velocity.py`). Nó deferred vì thiếu snapshot (ADR-0017), không phải vì chưa xây.
- Đề xuất E cho UI-0001-status-labels: "Pill lộ trình chỉ dùng live / next / research. Pill độ sẵn sàng của chỉ số chỉ dùng live / deferred, và `deferred` luôn kèm lý do bằng chữ (UI-0017-velocity-deferred). Hai loại pill có hình khác nhau: pill lộ trình là chip chữ; trạng thái chỉ số là nền sunken của cả thẻ cộng với chip. 'preview' không phải nhãn trạng thái; nó chỉ được dùng như câu mô tả."
- Trên landing, panel so sánh topic dùng pill `next` và câu "Preview. Per-topic tests are not in the dashboard yet…". Không có pill "preview".

### Câu 3: hiện id topic → **có, nhưng chỉ ở vai phụ**
- Id `topic_N` chỉ xuất hiện dạng mono trong dòng metadata hoặc phương pháp: hồ sơ topic (`topic_7 · n 13 · median …`), chú thích hero, dòng `document · full_text · topic_N`, và lịch sử tên trên trang Topics.
- Id không bao giờ là nhãn chính, không thay cho tên, không có trong hàng bảng hay danh sách chọn.
- Lý do: tên topic có thể đổi (UI-0018-names-change), còn id thì bền. Id cho người đọc kỹ thuật cách đối chiếu cùng một topic qua các lần đổi tên.
- Đề xuất bổ sung E cho UI-0018-id-not-name: "Id hiện dạng mono ở dòng metadata, hồ sơ và lịch sử; không làm nhãn chính, không có trong hàng bảng hay danh sách."

## 3. Đã làm trong mockup vòng này (để Claude Code cập nhật audit)

`src/dashboard/mockups/landing.dc.html`: đã xử lý mọi dòng ở mục 1 và mục 2 của `ui-contract-audit.md`, trừ những dòng sau:
- **Làm mờ n < 10:** chờ Câu hỏi mở 1. Mockup đã đọc cờ `lowN` theo từng topic (giả lập cờ backend), không còn so sánh `n < 10` ở client.
- **"sắp có" (báo nhầm):** nằm trong nội dung bài mẫu, hết khi mockup dùng file xuất. <!-- consistency: allow ADR0001-coming-soon -->
- **Mốc `clustered`:** hiện "2026-10-01 UTC" (chỉ có ngày). Giờ và múi giờ chờ Câu hỏi mở 4 và file xuất.
- **CTA "Read the methodology", "View the repo":** vẫn `#` vì chưa có URL (handoff §3.7).

`design-system.dc.html`, `overview-amber.dc.html`, `overview-cyan.dc.html`: tên cũ đã đổi thành "Unthreaded". Ngoài tên ra, chưa audit các file này theo hợp đồng (audit, ghi chú 4).

Sau khi nhập gói, chạy `check --all`: số cảnh báo mockup kỳ vọng còn 1 (báo nhầm "sắp có"). <!-- consistency: allow ADR0001-coming-soon -->
