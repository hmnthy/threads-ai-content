# ADR-0030: Hộp Key numbers — một component, số 28px căn trái, cao theo nội dung

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-31
- **Người quyết**: Thy (gửi 6 ảnh hộp số lệch nhau, chọn 4 phương án qua câu hỏi kèm mockup 2026-10-31: số to xếp
  dọc, cao theo nội dung + dính khi cuộn, luôn tên "Key numbers" + dòng phạm vi, thanh tỉ lệ + gộp median/IQR/n);
  luật K1–K6 và máy đo do Claude đề xuất

## Bối cảnh

- Thy so các hộp số trên các trang: khoảng trống trong hộp lúc to lúc nhỏ, không theo nội dung; cùng một vai mà chỗ
  gọi "Key numbers", chỗ gọi "This topic in numbers".
- Nguyên nhân trong code (2026-10-31):
  - luật 2026-10-29 "hộp số kéo dài bằng cột bên cạnh" (`docs/claude/design-system.md` §3) được làm bằng `flex-1
    justify-evenly` trên danh sách (`src/dashboard/src/components/AppBlock.tsx:152`): hộp bị kéo cao bằng cột trái, rồi
    khoảng thừa được rải giữa các dòng — cột trái càng dài, lỗ hổng càng to;
  - trang Topics tự viết hộp thứ 2 cho cùng vai (`src/dashboard/src/components/TopicsView.tsx:404`): nhãn trái, số
    phải, tên riêng — vi phạm C2 mà máy đo không thấy vì C2 là luật [mắt];
  - số chính 15px bằng cỡ nhãn, nên hộp tên "Key numbers" mà mắt không bắt được số; median, IQR, n của cùng một kết
    quả nằm ở 3 dòng rời.
- Máy đo mới (K1–K3) trên bản live `unthreaded-analytics.vercel.app` 2026-10-31: 6 hộp số trên `/topics`, cả 6 vi phạm
  — 42 vi phạm máy mới (K1×7, K2×17, K3×18). Landing chưa có hộp Key numbers (panel landing là bản riêng). Tổng UX gate:
  105 = 63 của ADR-0029 + 42.

## Quyết định

1. **Một component, một tên** (K1): mọi hộp số là `KeyNumbers` của `AppBlock.tsx` (`data-ux="key-numbers"`), tiêu đề
   luôn "Key numbers"; phạm vi hẹp hơn khối chứa nó ghi ở dòng nhãn 12px phía trên tiêu đề.
2. **Số to, căn trái, xếp dọc** (K2, K6): số chính vai metric 28px tabular w700 trên dòng riêng → nhãn 15px w600 →
   ghi chú 13px; tối đa 4 số. Căn phải chỉ dành cho cột số cùng đơn vị trong bảng.
3. **Cao theo nội dung, dính khi cuộn** (K3): không kéo giãn, không rải khoảng thừa; ở cột phụ thì `position: sticky`.
   Thay luật 2026-10-29 "hộp số kéo dài bằng cột bên cạnh".
4. **Số trực quan** (K4, K5): số là một phần của số trước có thanh tỉ lệ 4px + chữ "N% of <số cha>"; một kết quả thống
   kê là một dòng (median là số chính, IQR + n ở ghi chú).
5. Cưỡng chế như ADR-0029: K1–K3 là luật [máy] trong `ux-shots.mjs`, K4–K6 do `@agent-ux-reviewer` chấm; không chặn
   commit. Sửa component và các trang là PR 2 của sổ luật.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Số to bên trái, nhãn + ghi chú bên phải | Hộp thấp hơn | Chật khi cột phụ chỉ ~400px | Thy chọn xếp dọc |
| Căn phải (nhãn trái, số phải — kiểu hộp Topics hiện tại) | Gọn, giống bảng | Số trong hộp khác đơn vị nên không so theo cột; mắt nhảy qua ~250px trống; ghi chú và thanh tỉ lệ tách khỏi số | Thy hỏi, rồi chốt xếp dọc |
| Giữ số 15px, chỉ sửa khoảng cách và tên | Ít thay đổi | Số vẫn không nổi | Thy chọn số to |
| Giữ hộp kéo dài, dồn số lên đỉnh | Giữ luật 2026-10-29 | Nền ấm trống kéo dài dưới đáy hộp | Thy chọn cao theo nội dung + dính |
| Tên theo phạm vi ("<phạm vi> in numbers") | Rõ nghĩa từng chỗ | Mỗi trang một tên; máy khó kiểm | Thy chọn một tên + dòng phạm vi |

## Hệ quả

- Docs: `docs/claude/design-system.md` §3 (vai metric gồm số trong hộp Key numbers; body bỏ "số chính 15px"; lớp màu
  "Kết quả" bỏ câu kéo dài), §3b nhóm luật K mới + câu ngoại lệ ở L5, §12, §13. Harness: `.claude/agents/ux-reviewer.md`
  (chấm K4–K6, bảng vai thêm hộp số), `.claude/rules/dashboard.md` (dòng hộp số) — commit riêng vào kho harness
  (ADR-0027).
- Code: `src/dashboard/scripts/ux-shots.mjs` (`RULES.keyNumbers` + phép đo K1–K3, xuất `RULES` + `measure`);
  `src/dashboard/scripts/ux-shots-fixtures.mjs` (trang mẫu đúng/sai cho từng nhánh của K1–K3, chạy tay; bỏ một phép
  kiểm thì ít nhất một trang mẫu phải hỏng — phép đo sticky sai nhiều lượt review vì so chiều cao thay cơ chế CSS, nên
  phép đo bố cục cần trang mẫu và kiểm đột biến chứ không chỉ đọc code). Component `KeyNumbers` và các hộp trên
  `/topics` sửa ở PR 2.
- Luật: `ADR0030-key-numbers-box` cấm trong docs và harness các câu cũ "hộp số kéo dài bằng cột", "số chính 15px" và tên
  "This topic in numbers". Không quét `src/`: code hiện tại còn vi phạm (nợ chấp nhận, PR 2 sửa); máy đo giữ phần code.
- **Nợ chấp nhận**: 42 vi phạm K trên `/topics` tới PR 2. PR 2, khi sửa xong component: thêm `src/**` vào `paths` của
  `ADR0030-key-numbers-box` (kèm sửa comment cũ trong `AppBlock.tsx`), gắn `data-ux="kn-value"` / `"kn-label"`, đưa `below` của
  `AnswerRow` ra ngoài lưới 2 cột (hộp dính trượt trong cả lưới — K3), và cập nhật số dòng mà `UI-0030-key-numbers` trích.
- **Xem lại khi**: có hộp cần hơn 4 số hoặc cần so số theo cột (khi đó là bảng, không phải hộp số); landing thêm hộp
  Key numbers; hoặc thang chữ đổi cỡ metric.

### Hệ quả UI

- Thêm: `UI-0030-key-numbers` (một component, một tên + dòng phạm vi, số 28px căn trái xếp dọc, cao theo nội dung + dính,
  thanh tỉ lệ, một kết quả thống kê một dòng).
- Nâng mốc "Cập nhật tới: ADR-0030" của `docs/design/ui-contract.md`.
