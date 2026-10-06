# Brief cho Claude Code v2: neo quyết định UI vào ADR, rồi chuẩn bị Topics

> Viết bởi: Claude Design, 2026-10-05. Người đọc: Claude Code (VSCode, có code, DB và git).
> Thay cho bản v1 ngày 2026-10-04. Bản v1 chưa tính ADR-0016/0017/0018 và chưa có Việc 0.
> Mục tiêu: mọi quyết định cấu trúc UI/UX đều chỉ ra được ADR nguồn; mọi ADR đều ghi nó buộc UI thay đổi gì.
> **Không neo số liệu.** Số liệu thay đổi theo cron là chuyện bình thường. Brief này chỉ neo **khái niệm, trường, trạng thái và ràng buộc trình bày**.
> Đọc kèm: `docs/design/landing-handoff.md` (§0 định nghĩa A/B/C), `docs/design/topics-proposal.md` (audit trường, nháp phương án; mọi số trong đó là ảnh chụp 01/10, chỉ để minh hoạ).

## Phân vai

| Việc | Claude Code | Claude Design |
|---|---|---|
| ADR, schema, endpoint, sổ luật | soạn, test, commit | đọc |
| `ui-contract.md`, cột A–D (sự thật kỹ thuật) | soạn và kiểm theo code | đọc |
| `ui-contract.md`, cột E (cách trình bày) | điền bản nháp | duyệt, đề xuất sửa qua brief |
| Mockup `.dc.html` | không sửa | dựng và sửa |
| Port mockup sang `src/dashboard/src/**` | làm sau khi mockup chốt | viết handoff |

Chiều thay đổi chỉ có một: ADR → `ui-contract.md` → mockup. Khi mockup cần thứ mà ADR chưa cho phép, Claude Design viết brief gửi sang, không tự quyết.

---

## Việc 0 (làm trước tiên): hợp đồng UI

### 0.1 Tạo `docs/design/ui-contract.md`

Mỗi dòng ứng với **một ràng buộc mà UI phải tuân**, xuất phát từ một ADR (hoặc từ một sự thật trong code nếu chưa có ADR, ghi `code:` cùng file:line).

```
| id | ADR | Khái niệm / trường (A) | Ràng buộc kỹ thuật (B) | Trang (C) | Kiểm bằng (D) | Trình bày (E) |
```

- **id**: `UI-<ADR>-<slug>`, ví dụ `UI-0018-id-not-name`. Không tái dùng id.
- **A**: tên khái niệm cùng trường thật (bảng.cột hoặc trường API), ví dụ `topics.topic_id`, `TopicOut.label_en`.
- **B**: điều kỹ thuật đúng, kiểm được bằng code, viết thành 1 câu khẳng định. Không chứa số liệu, chỉ chứa tham số cố định của code (ví dụ "tối đa 15 bài/cụm") kèm file:line.
- **C**: `landing`, `overview`, `analytics`, `topics`, hoặc `all`.
- **D**: mã luật trong `invariants.toml` nếu kiểm tự động được; `test:` cùng tên test; hoặc `manual`.
- **E**: quy tắc trình bày, 1 câu. Claude Code điền nháp, Claude Design duyệt.
- Đầu file ghi `Cập nhật tới: ADR-NNNN · <ngày>`. Đây là mốc mà cổng kiểm ở 0.4 dùng.
- ADR không có hệ quả UI vẫn ghi 1 dòng, cột B ghi "không có hệ quả UI" để biết ADR đó đã được xét.

**Phạm vi:** ADR-0001 tới ADR-0018, cộng `legacy-log.md` cho những quyết định còn hiệu lực có chạm UI (tách `/` thành landing, các route app, 1 màu nhấn ở Topic Explorer).

### 0.2 Dòng mẫu (Claude Design soạn từ việc đọc ADR, Claude Code **phải kiểm lại theo code** rồi sửa hoặc xoá)

| id | ADR | A | B | C | D | E |
|---|---|---|---|---|---|---|
| UI-0018-id-not-name | 0018 | `topics.topic_id` (`topic_N`) | Id bền, không tái dùng; tên có thể đổi khi id giữ nguyên | all | manual | Khoá, link, trạng thái chọn dùng `topic_id`; tên chỉ để hiển thị |
| UI-0018-label-provenance | 0018 | `topics.labeled_at`, `label_model`, `label_prompt_version`, `topic_label_history.reason` | Tên do model sinh, có lịch sử và lý do (`new/split/merged/drift/config_change/retired`) | topics, landing | manual | Tên luôn đi kèm "named by Claude"; Topics có chỗ xem ngày đặt tên và lý do |
| UI-0018-retired | 0018 | `topic_label_history` reason `retired` | Topic có thể biến mất qua các lần chạy | topics | manual | Có trạng thái trình bày cho topic `retired`; không hiển thị như một cụm đang sống |
| UI-0016-label-input | 0016 | `src/nlp/topics.py` (số bài đưa vào prompt) | Prompt đặt tên nhận tối đa N bài gần tâm (kiểm N) cùng từ khoá c-TF-IDF | landing | manual | Mô tả pipeline ghi đúng N; **landing hiện ghi "3 posts", cần kiểm** |
| UI-0016-no-old-model | 0016 | — | Không nhắc tên model đặt tên cũ ngoài `docs/decisions/` | all | `ADR0016-opus-labeling` | Ghi nguồn tên là "named by Claude", không cần tên model trên UI tầng B |
| UI-0017-night-gaps | 0017 | `insight_snapshots` | Snapshot hở ban đêm; khoảng trống lấy từ `scripts/snapshot_coverage.py` | overview, analytics | manual | Biểu đồ chuỗi thời gian không nối liền qua khoảng hở; khoảng hở được vẽ ra |
| UI-0017-velocity-deferred | 0017 | `window_velocity` | Velocity 24h cần ≥ 3 điểm, thường không đủ | overview | test: (tên test velocity) | Ô deferred ghi lý do "not enough snapshots", không để trống |
| UI-0017-run-time | 0017 | `cluster_runs.run_at` | Cụm và tên cập nhật theo lần chạy job NLP | topics, landing | manual | Trang có mốc "clustered <ngày giờ>" |
| UI-0011-excluded | 0011 | `split_measurable` | Bài views = 0 bị loại khỏi phân phối rate | all | (mã luật hiện có nếu có) | Ghi "N excluded: no views recorded" cạnh mọi phân phối |
| UI-0004-dbcv-named | 0004 | `cluster_runs.validity_index` | Chỉ số chất lượng cụm luôn ghi kèm tên hàm | topics, landing | `ADR0004-dbcv-unnamed` | Hiện dạng `validity_index (<tên hàm>)` |
| UI-0001-status-labels | 0001 | — | Nhãn trạng thái chỉ `live / next / research`; không "coming soon" <!-- consistency: allow ADR0001-coming-soon --> | all | `ADR0001-coming-soon` | Pill trạng thái dùng đúng 3 nhãn |

### 0.3 Thêm mục "Hệ quả UI" vào mẫu ADR

Sửa `docs/decisions/0000-template.md`: thêm vào cuối mục `## Hệ quả` một mục con.

```
### Hệ quả UI
- Dòng `ui-contract.md` thêm / sửa / bỏ: `UI-NNNN-...` (hoặc "không có hệ quả UI").
```

Từ ADR-0019 trở đi, ADR nào thiếu mục này thì không được commit. *(Claude Code: đã làm, áp từ ADR-0020 — xem "Chỗ lệch" cuối file.)* Nếu `check.py` làm được thì thêm thành luật; không làm được thì ghi vào checklist của `consistency-auditor`.

### 0.4 Cho sổ luật quét mockup

- Thêm `src/dashboard/mockups/**` và `docs/design/**/*.dc.html` vào `paths` của mọi luật `[[forbid]]` dạng chữ có áp dụng cho nội dung hiển thị (tối thiểu: `ADR0001-*`, `ADR0004-dbcv-unnamed`, `ADR0009-old-name*`, `ADR0016-opus-labeling`). *(Claude Code: làm bằng `mockup_paths` + `mockups = true`, mức cảnh báo — `paths` vô tác dụng vì mockup nằm trong `exclude`; xem "Chỗ lệch".)*
- Bỏ câu "Mockup không bị sổ luật kiểm" trong `CLAUDE.md` của project Claude Design, ghi lại câu đó trong brief trả về để Thy chép.
- Chạy `check --all`. Mọi vi phạm trong mockup ghi vào `docs/design/ui-contract-audit.md`, **không sửa mockup**.

### 0.5 Kiểm landing theo hợp đồng

Đọc `src/dashboard/mockups/landing.dc.html` và `docs/design/landing-handoff.md`, so với từng dòng có `C` = `landing` hoặc `all`. Ghi vào `docs/design/ui-contract-audit.md`:

```
| ui-contract id | Vị trí trong landing (dòng) | Hiện tại | Phải là | Mức (cấu trúc / chữ) |
```

Hai chỗ đã biết, cần xác nhận:
- `cluster_N` dùng làm id cho state và cho dữ liệu (dòng ~192, 492–522, 622, 680). Theo ADR-0018 phải là `topic_N`.
- Node "Name" ghi "3 posts nearest the centre" (dòng ~368, 560). Kiểm số bài thật trong `src/nlp/topics.py`.

Số liệu cũ trong landing (150, 0,317, 36,1%…) **không** ghi vào audit này. Phần số sẽ xử lý riêng.

### 0.6 Việc nhỏ đi kèm
- `docs/claude/design-system.md` §0 dòng 1 ghi "File này (v3.1)"; đầu file đã là v3.2. Sửa cho thống nhất.

---

## Việc 1: ADR vai trò 3 trang app

Chưa có tài liệu nào quy định mỗi trang trả lời câu hỏi gì; Overview và Analytics đang trùng nhau. Đề xuất để Thy duyệt:

| Trang | Câu hỏi chính |
|---|---|
| `/overview` | Kênh đang thế nào trong cửa sổ đã chọn? |
| `/analytics` | Bài nào, giờ nào hiệu quả? |
| `/topics` | Kênh viết về gì, và chủ đề có liên quan tới engagement không? |

ADR này cần chốt:
- **1a. Cấu trúc trang tầng A.** Có nhận trình tự "câu hỏi → câu trả lời 1 dòng → bằng chứng → phương pháp" không, trong khi vẫn giữ hình khối tầng A (card 12px có viền, không dải tối). Minh hoạ: `docs/design/layout-tiers.dc.html` (1a / 1b). Nếu nhận thì sửa design-system §7.
- **1b. Nhóm so sánh cho Cliff's δ và p.** (i) cụm so với phần còn lại, gồm nhiễu (Claude Design đề xuất; khớp `compare_groups`); (ii) cụm so với phần còn lại, bỏ nhiễu; (iii) cụm so với median kênh (test 1 mẫu, cần engine khác). Median kênh vẫn là đường mốc trên biểu đồ.
- **1c. Họ test Holm.** 9 test (chỉ engagement) hay 27 test (3 chỉ số).
- **1d. Mean.** Ẩn trên UI hay giữ dạng phụ. Áp dụng cho `HeroBand`, `KpiStrip`, `AnalyticsBreakdown`, `PostingTimeHeatmap`.
- **1e. Lịch sử tên cụm (ADR-0018) có lên trang Topics không,** và ở mức nào: chỉ ngày đặt tên, hay cả danh sách đổi tên.

Có hệ quả UI → điền mục "Hệ quả UI" (0.3) và thêm dòng vào `ui-contract.md`.

## Việc 2: kiểm cấu trúc dữ liệu (query, không sửa code)

Ghi vào `docs/design/topics-data-audit.md`. Mỗi mục gồm câu SQL hoặc lệnh, **kết luận cấu trúc**, và ngày chạy. Số đếm chỉ để minh hoạ.

1. **Các mẫu số tồn tại:** root post → content unit → có `full_text` → có embedding/UMAP → đo được theo `split_measurable`. Bước nào loại bài, và vì lý do gì.
2. **Hai tập loại có trùng nhau không:** unit không có chữ, unit có views = 0. Nếu không đảm bảo trùng thì UI phải hiện 2 dòng loại riêng → thêm dòng vào `ui-contract.md`.
3. **Trường của topic:** `keywords_json`, `representative_ids_json`, các cột nhãn của ADR-0018. Trường nào có thể null, và khi nào.
4. **Mẫu số của nhiễu** khi tính `cluster_runs.noise_ratio`.
5. **Các cột của `cluster_runs`:** tên hàm sinh `validity_index`, tham số HDBSCAN/UMAP, `topic_events_json`, ARI (nếu có).
6. **`centroid_similarity`:** có cho mọi bài trong cụm không, và miền giá trị.
7. **Ngưỡng mẫu nhỏ:** code dùng `MIN_N_PER_BUCKET = 5`, landing làm mờ cụm có n < 10. Chốt một ngưỡng cho UI → thêm dòng vào `ui-contract.md`.
8. **Cửa sổ Overview** cắt theo ngày nào (`max_date` của daily views?).

## Việc 3: endpoint cho Topics

Làm sau khi Việc 1 đã chốt. Tên endpoint là gợi ý; khớp convention trong `src/main.py`.

- **`GET /topics` mở rộng:** `keywords`, `representative_ids`, `n_embedded`, `n_measurable`, cùng các trường nhãn của ADR-0018 (`labeled_at`, `label_model`, `label_prompt_version`, và lịch sử nếu 1e chọn hiện).
- **`GET /topics/run`** (hoặc `/research/runs/latest`, theo roadmap E): `run_id`, `run_at`, `n_input`, `n_clusters`, `n_noise`, `noise_ratio`, `validity_index`, `validity_fn` (bắt buộc), tham số, `topic_events`, `ari` (null kèm `ari_status` ∈ `live / next / research`).
- **`GET /topics/stats`:** mỗi topic một dòng, thêm dòng nhiễu và dòng kênh. Các trường: `topic_id`, `n`, `n_excluded_no_views`, `median`, `q1`, `q3` (`window_stats`), `cliffs_delta` cùng CI, `p_raw`, `p_holm` (`compare_groups` cộng hàm Holm mới), `low_n`, `comparison` (chuỗi mô tả nhóm so sánh). Dòng nhiễu có `tested: false`.
- **Holm:** hàm thuần trong `significance.py`, test với ví dụ tính tay.
- **Test:** Pydantic khớp response thật; `tổng n các topic + n_noise == n_embedded`; dòng kênh khớp `/analytics/overview` **tại cùng thời điểm chạy** (so 2 endpoint với nhau, không so với số cố định).

## Việc 4: xuất cho Claude Design

Đặt trong `docs/design/data/topics/`. Commit hay gitignore do Claude Code quyết; nếu có nội dung bài thật thì không commit.

```
content-units.json · topics.json · topics-run.json · topics-stats.json · analytics-overview.json
manifest.json   # commit sha, run_id, thời điểm xuất, lệnh đã chạy
```

Số trong các file này chỉ dùng để mockup trông giống thật. Cấu trúc trang không dựa vào giá trị cụ thể nào.

## Ngoài phạm vi
- Không sửa `TopicExplorer.tsx`, `topics/page.tsx` hay bất kỳ mockup nào.
- Không chạy lại clustering, không đổi tham số.
- Không làm CMI (RQ-04) hay ARI 10 seed (RQ-01); các mục này để trạng thái `research`.
- Không đổi tên tab "Topic Explorer" (câu hỏi riêng cho Thy).

## Trả về cho Claude Design
1. `docs/design/ui-contract.md` (Việc 0), cùng `docs/design/ui-contract-audit.md` (0.4 + 0.5).
2. ADR vai trò 3 trang (Việc 1): số hiệu và đường dẫn.
3. `docs/design/topics-data-audit.md` (Việc 2).
4. `docs/design/data/topics/` (Việc 4).
5. Bảng chỗ lệch dưới đây.

## Chỗ lệch giữa brief và code/DB (Claude Code điền)

| Mục brief | Brief nói | Thực tế | Xử lý |
|---|---|---|---|
| 0.1, 0.3 phạm vi | Hợp đồng ADR-0001 → 0018; luật "Hệ quả UI" từ ADR-0019 | ADR-0019 (quy trình git) đã có trước brief | Hợp đồng tới ADR-0020 (chính quyết định này); luật áp từ ADR-0020 |
| 0.2 UI-0018-id-not-name | Trường `topics.topic_id` | Cột thật là `topics.id`; `topic_id` nằm ở `post_topic_labels` / `TopicLabel` | Sửa cột A |
| 0.2 UI-0018-label-provenance | `retired` là một lý do đặt tên | `retired` là dòng đóng, `labeled_at` = lúc xoá, không phải một lần đặt tên | Sửa cột B |
| 0.2 UI-0018-retired | Có trạng thái trình bày cho topic retired | Topic retired bị xoá khỏi bảng `topics`, `GET /topics` không bao giờ trả nó | Chỉ hiện trong lịch sử |
| 0.2 UI-0016-label-input | Tối đa N bài gần tâm cùng từ khoá c-TF-IDF | N = 15, xếp theo độ gần tâm; **không** gửi từ khoá; số 3 là bài đại diện hiển thị | Sửa; thêm dòng UI-0004-representatives |
| 0.2 UI-0017-night-gaps | Bảng `insight_snapshots` | Bảng `insights_snapshots`, trường `fetched_at`; ngưỡng hở 5h ở `snapshot_coverage` | Sửa A, B |
| 0.2 UI-0017-velocity-deferred | "test: (tên test velocity)" | `test_window_velocity_raises_below_three_snapshots` | Điền tên test |
| 0.2 UI-0011-excluded | Trang `all`; D là mã luật | ADR-0011 cố ý không có luật regex; chỉ trang có phân phối rate | D = test; C sửa |
| 0.2 UI-0004-dbcv-named | Cột `cluster_runs.validity_index`; trình bày `validity_index (<tên hàm>)` | Cột là `dbcv` (+ `dbcv_relative`); `validity_index` chính là tên hàm | Sửa A, E |
| 0.2 UI-0001-status-labels | Chỉ live / next / research, trang `all` | Thẻ chỉ số ở Overview dùng thêm `deferred` | Đã chốt 2026-10-06: giữ hai tập riêng (cột E của UI-0001-status-labels) |
| 0.4 cơ chế | Thêm mockup vào `paths` của luật | Mockup nằm trong `exclude` nên `paths` vô tác dụng | `mockup_paths` + `mockups = true`, mức cảnh báo (Thy chọn) |
| 0.4 luật | `ADR0004-dbcv-unnamed`, `ADR0017-nlp-3am` sẽ bắt lỗi mockup | Luật DBCV báo nhầm `validity_index (DBCV)`; luật 3am không bắt "daily 03:00" đứng một mình | Sửa cả hai luật; thêm `ADR0018-cluster-id-display` <!-- consistency: allow ADR0017-nlp-3am --> |
| 0.5 "3 posts" | Cần kiểm số bài thật | Đúng ở khối hồ sơ cụm (3 bài đại diện); sai ở mô tả bước đặt tên | Ghi audit |
| Việc 2.7 | `MIN_N_PER_BUCKET = 5` vs landing mờ n < 10 | `HDBSCAN_MIN_CLUSTER_SIZE = 4` → cụm 4–9 bài có thật, hai ngưỡng cho kết quả khác | Đã chốt 2026-10-06: một ngưỡng = 5, UI đọc cờ backend (UI-L20260903-small-n-flag) |
| Việc 3 | Trường `n_input`, `n_noise`, `validity_fn` | Cột thật `n_units`; số nhiễu không lưu riêng (suy từ `noise_ratio` / `labels_json`); `validity_index` lấy từ cột `dbcv` | Ghi nhận khi làm Việc 3 |
| landing-handoff §0 | Gọi Claude 1 lần mỗi cụm | Từ ADR-0018 chỉ gọi cho cụm cần đặt lại tên | Ghi audit |

## Claude Design làm gì khi nhận đủ
1. Duyệt cột E của `ui-contract.md`, gửi đề xuất sửa qua brief nếu có.
2. Sửa landing theo `ui-contract-audit.md` (phần cấu trúc).
3. Dựng `src/dashboard/mockups/topics.dc.html`. Mỗi quyết định cấu trúc trong handoff ghi id `UI-…` mà nó tuân theo.
