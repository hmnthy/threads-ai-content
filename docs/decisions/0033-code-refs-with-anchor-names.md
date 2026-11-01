# ADR-0033: Tham chiếu code trong docs ghi kèm tên neo, máy kiểm và tự dời số dòng

- **Trạng thái**: Accepted
- **Ngày**: 2026-11-01
- **Người quyết**: Thy (chọn qua câu hỏi 2026-11-01 sau PR 2b: cách ghi "số dòng + tên, máy tự sửa số", phạm vi
  "toàn bộ docs"); cách làm do Claude đề xuất

## Bối cảnh

- Docs dẫn chứng bằng tham chiếu `file:dòng` — 259 chỗ trong các file `.md`, phần lớn ở `docs/design/ui-contract.md`
  (cột B của hợp đồng UI, ADR-0020), còn lại ở ADR và tài liệu thiết kế. Số dòng trôi mỗi khi code thêm/bớt dòng.
  PR 2b (ADR-0032) phải dời tay 3 lượt và vẫn sót: code-reviewer bắt lệch ở cả 3 lượt soát.
- Khảo sát 2026-11-01 trên `main` (`4b857b5`): 2 tham chiếu trỏ quá cuối file, 8 trỏ vào dòng trống. Thử cho máy đoán
  tên dựa vào chữ trong backtick đứng trước tham chiếu: 47 / 99 báo lệch, xem bằng mắt thì khoảng một nửa là báo nhầm
  (chữ đứng trước là tên trường nhắc trong câu, không phải đích) → không dùng đoán để chặn commit được.
- Lúc chuyển đổi (đọc code tại commit đưa từng tham chiếu vào tài liệu, rồi soát nghĩa từng ca): 58 / 251 tham chiếu so
  được đã lệch và được sửa số dòng — VD `src/main.py:129-134` ghi là nơi trả `centroid_similarity` nhưng đã thành đoạn <!-- consistency: allow ref-anchor — ví dụ tham chiếu lệch trước khi sửa -->
  cấu hình CORS; "title API" trỏ vào `class TopicLabel`.

## Quyết định

1. Mọi tham chiếu code trong file `.md` ghi **`path:N#Tên`**, `path:N-M#Tên`, hoặc `:N#Tên` (`:N` trần thuộc file nhắc
   gần nhất trước nó trong tài liệu; tên file ngắn được khi repo chỉ có đúng 1 file trùng tên). Tên là hàm / lớp / biến /
   khoá / từ phải có trong dòng N..M — ưu tiên tên được định nghĩa ở dòng đó.
2. Kiểm tra `ref_anchor` (kiểm tra thứ 8 của `scripts/consistency/check.py`, mã luật `ref-anchor`) chặn commit khi
   tham chiếu thiếu tên neo, số dòng quá cuối file, hoặc dòng N..M không còn chứa Tên. Áp mọi file `.md` (trừ `exclude`
   của sổ luật), kể cả ADR cũ. Không bỏ qua im lặng: thứ trông như tham chiếu mà không đọc được (VD dạng x.py:L3, tên neo
   có dấu chấm), tên file ngắn khớp từ 2 file, hoặc `:N#Tên` không biết thuộc file nào cũng là vi phạm. Tài liệu được
   đọc theo khối markdown (đoạn văn, mục danh sách, dòng bảng, tiêu đề), gần CommonMark — code span vắt dòng và span
   nhiều backtick vẫn được đọc, `:N` trần chỉ nối với file nhắc trước nó trong cùng khối.
3. `uv run python -m scripts.consistency.check --fix-refs` dời số dòng theo diff của file code so với HEAD (tham
   chiếu đúng ở HEAD thì giữ đúng dòng tác giả chọn, kể cả dòng dùng Tên); diff không cho biết thì chỉ dời khi chỗ mới
   xác định duy nhất (đúng 1 dòng định nghĩa Tên, hoặc đúng 1 dòng chứa Tên); nhiều chỗ thì để người chọn — dời nhầm
   rồi thì kiểm tra cũng qua. Thử trên repo thật: chèn 2 dòng đầu `src/main.py` → 31 tham chiếu báo lệch; dời theo
   diff sửa đủ 31, còn 0 — cách chỉ dùng "chỗ duy nhất" chỉ dời được 4, và có ca dời sang dòng định nghĩa thay vì dòng
   dùng Tên mà tác giả chọn.
4. Tham chiếu cố ý trỏ code của lúc viết (ADR / audit kể lại trạng thái cũ) giữ nguyên số cũ, **không** gắn `#Tên`,
   và ghi `<!-- consistency: allow ref-anchor — lý do -->` trên cùng dòng (hoặc ở dòng ngay trước, khi dòng đó chỉ có
   chú thích). Allow miễn kiểm cả dòng, và `--fix-refs` không dời gì trên dòng đó — nên dòng có allow chỉ chứa tham
   chiếu lịch sử.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Chỉ ghi tên, bỏ số dòng (`file#Tên`) | Không bao giờ lệch | Người đọc phải tự tìm trong file | Thy chọn giữ số dòng để nhảy nhanh |
| Kiểm nhẹ: chỉ chặn số quá cuối file / dòng trống | Không phải sửa 259 tham chiếu | Chỉ bắt 10 lỗi hiện có, trỏ nhầm sang hàm khác vẫn lọt | Không giải quyết lệch thật |
| Máy đoán tên từ câu văn | Không đổi cách ghi | ~ nửa số báo lệch là báo nhầm | Không chặn commit được |
| Chỉ ui-contract + ADR từ 0033 | Không chạm ADR cũ | ADR cũ vẫn trôi | Thy chọn toàn bộ docs |

## Hệ quả

- Code: `scripts/consistency/check.py` (kiểm tra 8 + cờ `--fix-refs`); test trong `tests/scripts/test_consistency.py`.
- Docs: 249 tham chiếu gắn tên neo (`docs/design/ui-contract.md`, ADR 0012 / 0020 / 0023 / 0024 / 0025 / 0031 / 0032,
  `docs/design/topics-data-audit.md`, `docs/design/landing-handoff.md`); 10 tham chiếu lịch sử trên 5 dòng giữ số cũ, ghi
  allow (ADR-0029, ADR-0030 ×2, 2 dòng nhật ký có ngày của `docs/design/ui-contract-audit.md`). Cách ghi nêu trong
  `docs/decisions/0000-template.md` và phần "Máy giữ hợp đồng này đúng" của `docs/design/ui-contract.md`.
- Luật: không thêm mẫu regex vào `docs/decisions/invariants.toml` — kiểm tra là code (như `dead-path`), mã `ref-anchor`.
- Giới hạn chấp nhận: máy chỉ kiểm "dòng còn chứa Tên", không kiểm đó là chỗ định nghĩa — dòng chứa lời gọi tên đó
  vẫn qua; tên neo quá chung (VD `button`) hoặc khoảng dòng quá rộng (VD `src/main.py:330-1041#app` cho câu "API chỉ có
  GET") bảo vệ yếu hơn tên hàm — khẳng định về cả file nên dựa vào test ở cột "Kiểm bằng". Bộ đọc markdown chỉ gần
  CommonMark: tham chiếu trong chú thích HTML hay khối code thụt lề vẫn bị kiểm (báo nhầm thì thêm allow). Harness riêng (`.claude/rules/docs.md`) chưa nhắc cách
  ghi — sửa trong kho harness (ADR-0027).
- Xem lại khi: cần tham chiếu code trong tài liệu không phải `.md` (HTML, notebook), hoặc `--fix-refs` thường xuyên
  không tự dời được vì tên neo trùng nhiều chỗ.

### Hệ quả UI

- Thêm `UI-0033-no-ui-impact` (không có hệ quả UI); nâng mốc "Cập nhật tới: ADR-0033" của `docs/design/ui-contract.md`.
