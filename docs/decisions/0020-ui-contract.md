# ADR-0020: Neo thiết kế UI vào quyết định kỹ thuật bằng hợp đồng UI

- **Trạng thái**: Accepted
- **Ngày**: 2026-10-06
- **Người quyết**: Thy (chọn: Claude Code là nguồn sự thật kỹ thuật, Claude Design làm UI/UX trên nền đó; làm Việc 0
  sau khi nhập gói thiết kế; vi phạm trong mockup chỉ cảnh báo), cơ chế đề xuất bởi Claude Design (brief Topics v2,
  2026-10-05) và Claude Code

## Bối cảnh

- Hai công cụ làm song song trên một repo: Claude Code giữ code, DB, ADR, sổ luật; Claude Design dựng mockup
  `.dc.html` và handoff. Thy đặt mục tiêu (2026-10-06): **không neo số liệu, mà neo quyết định UI/UX vào quyết định kỹ
  thuật**; hai bên không được mâu thuẫn; Claude Design không được làm sai hay can thiệp phần kỹ thuật.
- Thực tế đã lệch, và không có tín hiệu nào báo:
  - Landing mockup chốt 2026-10-01 vẫn dùng id `cluster_N` (ADR-0018 đổi sang `topic_N` bền), ghi job NLP "daily 03:00"
    (ADR-0017 dời sang 12:30), và ghi "3 bài gần tâm + từ khoá c-TF-IDF được gửi cho Claude" — code gửi tối đa 15 bài,
    không gửi từ khoá (`src/nlp/topics.py:124`).
  - Chính các dòng mẫu trong brief sai tên trường: `cluster_runs.validity_index` (cột thật là `dbcv`),
    `topics.topic_id` (cột thật là `id`), bảng `insight_snapshots` (thật là `insights_snapshots`).
  - `src/dashboard/mockups/**` nằm trong `exclude` của sổ luật (ADR-0008), nên không luật nào quét mockup của Claude
    Design; ADR không ghi nó buộc UI đổi gì, và không có tài liệu nào nối "quyết định X" với "khối UI Y".
- Kiểm 49 ràng buộc theo code (3 lượt đọc độc lập ADR-0001 → 0019 + legacy-log, mỗi ràng buộc kèm `file:line`; hợp
  đồng có thêm 5 dòng "không có hệ quả UI" và 2 dòng của ADR này): khi bật quét, 19 chỗ trong 4 mockup vi phạm luật hiện có — 13 id `cluster_N`, 1 lịch "daily 03:00", 4 tên cũ "Threads AI
  Content", 1 báo nhầm (chữ "sắp có" nằm trong nội dung bài thật dùng làm dữ liệu mẫu).

## Quyết định

1. **`docs/design/ui-contract.md` là đầu vào kỹ thuật duy nhất cho cấu trúc UI.** Mỗi dòng: id `UI-<ADR>-<slug>`, ADR
   nguồn, trường thật (A), ràng buộc kỹ thuật 1 câu kèm `file:line` (B), trang (C), cách kiểm — mã luật / test /
   manual (D), quy tắc trình bày (E). Claude Code viết và kiểm A–D theo code, viết nháp E; Claude Design duyệt E và đề
   xuất sửa qua brief. Chiều thay đổi chỉ có một: **ADR → hợp đồng → mockup → code**. Hợp đồng không chứa số liệu thay
   đổi theo cron.
2. **ADR từ 0020 có mục `### Hệ quả UI`** (thêm / sửa / bỏ dòng nào, hoặc "không có hệ quả UI"); dòng hợp đồng cập nhật
   trong cùng commit và nâng mốc "Cập nhật tới". `scripts/consistency/check.py` chặn commit khi: có ADR mới hơn mốc, ADR
   chưa có dòng nào, id trùng, cột D trỏ tới luật/test không có, ADR từ 0020 thiếu mục "Hệ quả UI".
3. **Mockup được sổ luật quét ở mức cảnh báo.** Luật về chữ hiển thị có `mockups = true` quét
   `src/dashboard/mockups/*.dc.html` và `docs/design/*.dc.html`; vi phạm ở đó không chặn commit, được in ở hook đầu
   phiên ("Mockup warnings"), ghi vào `docs/design/ui-contract-audit.md`, và Claude Design sửa ở vòng thiết kế kế tiếp.
   Khi port sang code, cùng luật đó chặn commit như mọi file khác.
4. **Claude Code không sửa nội dung mockup**; được sửa sự thật kỹ thuật trong tài liệu của Claude Design (handoff,
   brief) và ghi rõ chỗ sửa.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược | Vì sao không chọn |
|---|---|---|---|
| Quét mockup và chặn commit ngay | Không thể bỏ qua | 19 cảnh báo hôm nay → toàn repo bị khoá tới khi bên kia sửa; Claude Code không được sửa mockup | Thy chọn chỉ cảnh báo; xem lại ở điều kiện bên dưới |
| Không quét mockup, chỉ kiểm tay qua audit mỗi gói | Đơn giản | Chính là cách đã để lọt `cluster_N`, "03:00", "3 posts" | Lỗi chỉ lộ khi có người nhớ đi tìm |
| Chỉ thêm mục "Hệ quả UI" vào ADR, không có file hợp đồng | Ít tài liệu | Không có chỗ tra "khối UI này tuân theo quyết định nào"; ADR cũ không được xét lại | Thiếu bản đồ hai chiều |
| Hợp đồng không có máy kiểm | Không cần code | Mục nát như legacy-log (dòng lỗi thời không ai biết) | Mọi quyết định khác trong repo đều có cảnh sát (ADR-0008) |

## Hệ quả

- Code: `scripts/consistency/check.py` — kiểm thứ 7 `ui_contract` (tách ô theo `|` chưa escape, dòng sai số cột bị báo),
  mức `warn` cho vi phạm trong mockup, `--count` in thêm dòng `mockup-warnings: N`; `.claude/hooks/session_status.py` in dòng "Mockup warnings". Test trong
  `tests/scripts/test_consistency.py`.
- Sổ luật (`docs/decisions/invariants.toml`): `[settings]` thêm `mockup_paths`, `ui_contract`, `ui_impact_from = 20`;
  26 luật về chữ hiển thị bật `mockups = true` (gồm mọi luật mà cột D của hợp đồng viện dẫn cho trang có mockup); luật
  mới `ADR0018-cluster-id-display` (id `cluster_N` trên mặt hiển thị và tài liệu, cũng quét mockup); `docs/design/*.dc.html`
  trước đây bị mọi luật quét ở mức lỗi, nay chỉ luật `mockups = true` ở mức cảnh báo (cùng chế độ với mọi mockup); `ADR0017-nlp-3am` bắt thêm nhãn lịch đứng một mình "daily 03:00"; `ADR0004-dbcv-unnamed` chấp nhận
  dạng `validity_index (DBCV)` và quét cả `docs/design/`; `ADR0016-prompt-caching` quét thêm code dashboard và
  `docs/design/`.
- Tài liệu: `docs/design/ui-contract.md` (mới, ADR-0001 → 0020), `docs/design/ui-contract-audit.md` (mới — cảnh báo
  mockup + audit landing), mẫu `docs/decisions/0000-template.md` có mục "Hệ quả UI", `docs/claude/dev-rules.md` (phối
  hợp Claude Code / Claude Design), `.claude/rules/dashboard.md`, skill `/record-decision` + `/decision-sweep` + agent
  `consistency-auditor` (bước "Hệ quả UI" + hợp đồng), hook nhắc sau khi ghi ADR, brief Topics điền bảng "chỗ lệch".
- Câu cần Thy chép sang project Claude Design (Claude Code không ghi được vào đó): bỏ câu "Mockup không bị sổ luật kiểm",
  thay bằng "Mockup bị sổ luật quét ở mức cảnh báo; đầu mỗi phiên thiết kế đọc `docs/design/ui-contract.md` và
  `docs/design/ui-contract-audit.md`."
- Rủi ro chấp nhận: cột E là bản nháp của Claude Code cho tới khi Claude Design duyệt; số dòng trong `file:line` có thể
  trôi khi code đổi (máy chỉ kiểm file còn tồn tại, không kiểm số dòng) — rà lại các dòng của ADR liên quan mỗi khi sửa
  ADR đó; cảnh báo có thể bị lờ đi.
- Xem lại khi: cảnh báo mockup còn nguyên sau 2 gói thiết kế liên tiếp (→ chuyển sang chặn); hợp đồng vượt ~100 dòng
  (→ tách theo trang); có công cụ thiết kế thứ ba ghi vào repo.

### Hệ quả UI

- Thêm toàn bộ hợp đồng (ADR-0001 → ADR-0019 + quyết định legacy còn hiệu lực) và 2 dòng của chính ADR này:
  `UI-0020-contract-gate`, `UI-0020-mockup-scan`.
