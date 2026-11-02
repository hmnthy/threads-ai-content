# ADR-0034: Gắn nhãn chuỗi views theo ngày Pacific của Meta, ngày đăng bài theo giờ Paris

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-01
- **Người quyết**: Thy chọn PR riêng + ADR riêng (2026-11-01, sau PR 2b); chọn múi giờ cho ngày đăng bài qua câu hỏi
  2026-11-01: phương án B "bài theo giờ Paris". Bằng chứng và cách làm do Claude đề xuất.

## Bối cảnh

- Code cũ gắn nhãn chuỗi `account_daily_views` (`threads_insights?metric=views&period=day`) bằng cách lùi `end_time`
  1 ngày khi giờ là `07`. Lần soát PR 2b (ADR-0032) thấy 8/10 bài đăng riêng lẻ có đỉnh views ở ngày TRƯỚC ngày đăng.
  Vì vậy `OverviewDashboard` phải bù tạm 1 ngày khi cắt chuỗi, và tổng views của `/analytics/window` cùng "Peak week"
  lệch 1 ngày so với tập bài trong cửa sổ.
- Verify live 2026-11-01 (730 điểm): `end_time` là `07:00Z` khi Pacific ở giờ mùa hè và `08:00Z` khi ở giờ mùa đông.
  Code cũ chỉ lùi ngày khi giờ là `07`, nên:
  - ngày mùa hè bị gắn sớm 1 ngày, ngày mùa đông đúng;
  - có 2 ngày trống (2024-11-03, 2025-11-02);
  - có 2 ngày trùng nhãn (2025-03-09, 2026-03-08), mất views của 1 ngày.
- Docs Meta không nói `end_time` là đầu hay cuối ngày. Data nói `end_time` là **đầu** ngày:
  - Bài đầu tiên của kênh (2025-04-14, 13:49 giờ Pacific) có 339 views đầu tiên ở điểm `2025-04-14T07:00:00+0000`.
  - Trên n = 14 bài đăng riêng lẻ, ngày views tăng mạnh nhất trùng ngày đăng ở 11/14 = 79% (CI 95% Wilson 52–92%)
    khi coi `end_time` là đầu ngày, so với 1/14 = 7% (1–31%) khi coi là cuối ngày.
  - Số đo đầy đủ: `docs/claude/data-model.md`, mục "Methodology log: nhãn ngày của chuỗi views theo ngày".
- Meta chỉ trả TỔNG mỗi ngày, nên không cắt lại chuỗi theo múi giờ khác được. Ngày đăng bài thì chọn được đồng hồ.
  Trên 169 bài gốc, chỉ 1 bài có ngày đăng khác nhau giữa giờ Pacific và giờ Paris: tác giả đăng trong khoảng 8h–23h
  giờ Paris.

## Quyết định

1. Mỗi điểm của chuỗi views mang **ngày Pacific của chính `end_time`**, tính bằng tzdata
   (`src/models/days.py:30#meta_day_of_end_time`). Không gõ cứng giờ: cách này đúng cho cả `07` lẫn `08`. Nếu
   `end_time` không rơi đúng nửa đêm Pacific thì vẫn gắn nhãn nhưng ghi cảnh báo vào log.
2. **Ngày đăng bài = ngày giờ Paris** (`src/models/days.py:56#author_day`, `src/dashboard/src/lib/dates.ts:76#parisDay`).
   Quy ước này dùng cho bộ lọc bài của `/analytics/window` và cho `firstPostDate`, ngày mà biểu đồ Overview bắt đầu.
   Đó là ngày in trên thẻ bài, cũng là ngày sống thật của tác giả.
3. Dữ liệu đã lưu được dời nhãn **một lần**:
   - `_migrate` dời mỗi dòng theo luật giờ mùa hè của Pacific (`src/db/schema.py:385#_relabel_daily_views_to_meta_day`):
     dòng nhãn L thành L + 1 khi nửa đêm đầu ngày L + 1 ở giờ mùa hè, ngược lại giữ L.
   - Bước dời chạy trong 1 transaction `BEGIN IMMEDIATE`, kiểm và ghi dấu `data_migrations` bên trong transaction đó.
   - Lần lấy chuỗi kế tiếp tải lại đủ 729 ngày một lần (`src/pipeline/daily_views.py:51#DAILY_VIEWS_REFETCH_MIGRATION`).
     Lần này lấp 2 ngày đã mất và ghi đè mọi dòng mà một job còn chạy code cũ có thể ghi chen.
   - Code mới từ chối ghi vào bảng chưa dời nhãn.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| A. Một đồng hồ: ngày đăng cũng theo giờ Pacific | Chuỗi views và tập bài cùng 1 định nghĩa ngày | Bài đăng 0h–9h sáng Paris vào ngày trước so với ngày in trên thẻ bài | Thy chọn B: ngày của tác giả, khớp thẻ bài |
| C. Giữ ngày UTC cho bài (cắt `timestamp`) | Ít thay đổi nhất | Vẫn 2 định nghĩa ngày; UTC không phải ngày của tác giả, cũng không phải của Meta | Không giải quyết lệch |
| Gắn nhãn chuỗi theo ngày Paris hoặc UTC | Một đồng hồ cho mọi thứ | Meta chỉ trả tổng theo ngày Pacific, đổi tên ngày không đổi được ranh giới thật | Sai sự thật |
| Chỉ dời +1 ngày cho mọi dòng | Đơn giản | Sai với 252 ngày mùa đông (đang đúng) | Data verify live bác |
| Dời bằng cách xoá bảng rồi tải lại | Không cần luật giờ mùa hè | Meta chỉ giữ 729 ngày → mất các ngày cũ hơn đã lưu | Mất dữ liệu |

## Hệ quả

- Code:
  - `src/models/days.py` (mới) là nơi duy nhất đổi thời điểm thành ngày.
  - `src/api/endpoints.py` gắn nhãn chuỗi qua module đó; `src/db/schema.py` có bảng `data_migrations`, migration dời
    nhãn và bộ lọc bài theo ngày Paris; `src/pipeline/daily_views.py` có lần tải lại một lần.
  - Dashboard: `src/dashboard/src/lib/dates.ts` (`parisDay`), `src/dashboard/src/lib/load.ts` (`firstPostDate`) và
    `OverviewDashboard` gỡ phần bù 1 ngày.
- Test:
  - nhãn `07` / `08` và mỗi ngày đúng 1 nhãn qua 2 lần đổi giờ;
  - invariant "ngày views tăng mạnh nhất trùng ngày đăng" trên số thật của 3 bài riêng lẻ (2 mùa hè, 1 mùa đông);
  - migration: đúng, chạy một lần, rollback khi lỗi, chờ khoá;
  - tải lại một lần; bộ lọc ngày Paris ở biên nửa đêm.
- Kiểm trên bản sao DB thật: 728/728 ngày trùng giá trị live, tổng views không đổi, chỉ thiếu đúng 2 ngày đã mất.
  "Peak week" dời từ 2026-08-17 → 08-23 sang 2026-08-18 → 08-24, cùng tổng.
- Vận hành:
  - Sau khi pull, lần chạy job đầu tiên dời nhãn rồi tải lại 729 ngày.
  - Pull khi không có job nào đang chạy. Nếu một job snapshot chạy code cũ còn ghi sau cả lần tải lại, nó có thể để lại
    1 ngày sai ở mép cửa sổ 7 ngày.
  - Bản sao DB công khai (ADR-0025) đúng sau lần publish kế tiếp. Trong khoảng giữa lúc dashboard mới deploy và lúc
    đó, biểu đồ live cắt mất ngày đầu tiên.
- Giới hạn chấp nhận:
  - Bài đăng 0h–9h sáng giờ Paris được tính vào cửa sổ theo ngày Paris, nhưng views đầu của nó nằm ở ngày Pacific
    trước đó. Trang ghi giới hạn này trong "Method and limits".
  - Nửa đêm Pacific là 9h sáng Paris phần lớn năm, nhưng là 8h trong vài tuần mà Mỹ và châu Âu đổi giờ khác ngày.
  - Docs Meta mô tả `views` của tài khoản là số lần profile được xem. Nghĩa của đại lượng nằm ngoài ADR này.
- Luật: `ADR0034-old-day-label` (mô tả cũ "end_time luôn 07:00", lùi ngày theo giờ `07`, phần bù `addDays(…, -1)`) và
  `ADR0034-utc-post-day` (cắt ngày UTC từ timestamp của bài trong `src/`).
- Xem lại khi: `end_time` không còn rơi vào nửa đêm Pacific (log có cảnh báo), Meta trả chuỗi theo múi giờ khác, hoặc
  tác giả thường đăng bài trước 9h sáng giờ Paris.

### Hệ quả UI

- Thêm `UI-0034-meta-day`: nhãn ngày của biểu đồ; phụ đề biểu đồ ghi "with days in Pacific time"; bước Method
  "Which day" kèm dòng công thức tên múi giờ IANA và quy tắc bài thuộc cửa sổ.
- Thêm `UI-0034-paris-post-day`: bộ lọc bài của cửa sổ và điểm bắt đầu biểu đồ theo ngày Paris. Giới hạn trước 9h
  sáng Paris ghi kèm số content unit bị ảnh hưởng, tính lúc chạy (`dayMismatch`), không gõ cứng; mẫu số = mọi content
  unit đã thu, có hoặc chưa có views. Ngày dưới mỗi bài ở khối 02 ghi "· Paris time"; mốc toàn kênh ở "What to know" ghi
  rõ n là số content unit có views.
- Sửa `UI-0032-overview-brush-first`: chuỗi cắt từ ngày Paris của content unit đầu tiên, không còn ngày UTC.
- Nâng mốc "Cập nhật tới: ADR-0034" của `docs/design/ui-contract.md`.
