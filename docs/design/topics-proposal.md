# Topics — audit + phương án (2026-10-02, nháp chờ Thy chọn)

> **Ghi chú 2026-10-05:** mọi số trong file là ảnh chụp ngày 01/10, chỉ để minh hoạ. Id `cluster_N` nay là `topic_N` (ADR-0018). Việc cần làm nằm ở `topics-brief-for-claude-code.md` v2; ràng buộc UI nằm ở `ui-contract.md` (Claude Code lập).

Đã đọc: `topics/page.tsx`, `TopicExplorer.tsx`, `lib/api.ts`, `src/main.py` (`/content-units`, `/topics`), `significance.py`, `stats.py` (split_measurable), `schema.py`, ADR-0004/0011, design-system §9, ảnh `docs/screenshots/topics.png`.

## 0. Audit nguồn số liệu

### Trang hiện tại
| Trường UI | Loại | Nguồn / ghi chú |
|---|---|---|
| 150 content units | A | `len(/content-units)` |
| 144 embedded, 6 không có chữ | A | `umap != null`, `full_text` rỗng — tính ở client |
| 9 cụm | A | `/topics` lọc `method='cluster'` |
| 36% unclustered (52/144) | A | đếm `topic == null` trong bài đã embed. DB có `cluster_runs.noise_ratio` = 36,1% nhưng API chưa trả |
| n và % từng cụm | A | client đếm lại từ `/content-units` (đúng: không dùng `TopicOut.post_count`) |
| Tên, mô tả cụm | A | `topics.label_en/description_en` (Claude, 1 lần/cụm). Mô tả chỉ nằm trong `title` tooltip → không đọc được trên cảm ứng/bàn phím |
| Bản đồ 3D | A | `umap_x/y/z`. Nhiễu tô cùng màu với cụm khác; chỉ hover; Plotly WebGL không Tab tới được |
| Banner, mô tả header | C | đúng ADR-0004 |

**Lỗ hổng theo tư duy dashboard:** trang không trả lời câu hỏi nào về hiệu quả; không có engagement; 3 mẫu số (150 / 144 embedded / 144 đo được) đứng lẫn; ADR-0011 chưa áp (không có dòng "excluded: no views recorded"); chất lượng gom cụm (validity_index, ARI) không hiện.

### Trường cần cho trang mới
| Trường | Loại | Nguồn / việc phải làm |
|---|---|---|
| engagement từng bài, lọc views = 0 | A | `/content-units` có `metrics.engagement_rate` + `popularity_index` (= views) → lọc được ở client, nhưng đúng ra nên qua `split_measurable()` ở API |
| `centroid_similarity` từng bài | A | `/content-units` `topic.centroid_similarity` |
| từ khoá c-TF-IDF, 3 bài gần tâm | A (DB) | `topics.keywords_json/representative_ids_json` — **chưa có trong `TopicOut`** |
| nhiễu 36,1%, `validity_index` 0,317, ARI 1,00/0,78/0,22 | A (DB) | `cluster_runs` — **chưa có endpoint** (`/research/runs`, roadmap E) <!-- consistency: allow ADR0004-ari-not-measurable --> |
| median/IQR/n từng cụm | B | `GET /topics` → `engagement` (PR 10); phép so theo topic: `GET /topics/comparisons` (Việc 3, 2026-10-09) |
| Cliff's δ, p, p Holm | B | `compare_groups()` có Brunner-Munzel + δ + CI của δ; `holm_adjust` có; nhóm so sánh đã chốt (ADR-0023); API theo topic `GET /topics/comparisons`, tính trong job NLP (Việc 3, 2026-10-09) |
| ARI 10 seed | — | research RQ-01, hiện ô trạng thái |
| CMI theo cụm | — | research RQ-04, không hiện số |
| Câu trả lời 1 dòng | C | sinh từ kết quả (VD "none clearly" chỉ khi mọi p Holm ≥ 0,05) |

**Cần kiểm trong DB:** 6 bài không chữ và 6 bài views = 0 có phải cùng 6 bài không. Code không đảm bảo điều đó; số trong landing (13 + … + 52 = 144) gợi ý là trùng.

Mockup Topics dùng số minh hoạ và ghi rõ là minh hoạ; số thật tính bằng `compare_groups()` (Brunner-Munzel hoán vị, ADR-0023), xuất cho Claude Design ở Việc 4.

## 1. Phương án

Câu hỏi của trang: **What does the channel write about, and does any topic get a higher engagement rate than the rest of the channel?** (chữ Thy duyệt 2026-10-09)

1. **Header** — tiêu đề, câu trả lời 1 dòng (sinh từ kết quả), dòng meta: run date · n · `validity_index` · nhiễu.
2. **Độ phủ** (thanh 1 dòng, không phải KPI card): 150 units → 144 embedded (6 no text) → 92 in 9 topics · 52 unclustered; 6 excluded: no views recorded.
3. **Panel 1 — Which topics get a higher engagement rate than the rest of the channel?** Bảng strip theo cụm (cùng ngữ vựng Proof panel 1 của landing): tên · n · strip + IQR · median · δ · p Holm. Đường dashed = median kênh. Cụm mang cờ `insufficient_data` (n < 5) mờ. Hàng nhiễu "not tested". Hàng = bộ chọn cụm.
4. **Panel 2 — What is this topic about?** Hồ sơ cụm đang chọn: tên + mô tả (ghi "named by Claude"), từ khoá, 3 bài gần tâm + `centroid_similarity`, danh sách mọi bài trong cụm (ngày, engagement, số phần nối). Bản đồ UMAP nhỏ bên cạnh, cụm chọn amber, nhiễu vòng rỗng.
5. **Panel 3 — How stable are these topics?** DBCV (`validity_index`), nhiễu, ARI 3 mức; 10 seed = ô research RQ-01. Khối phương pháp mở ra: pipeline, tham số, giới hạn.

Bỏ: 3 KPI card, tooltip mô tả, banner xanh (nội dung chuyển vào khối phương pháp).

## 2. Đề xuất cho câu hỏi mở
Nhóm so sánh: **cụm vs phần còn lại của kênh (gồm nhiễu)** — 2 nhóm độc lập, khớp `compare_groups()` (Brunner-Munzel + Cliff's δ kèm CI — ADR-0023). So với "median kênh" thì median đó đã chứa chính cụm, và cần test 1 mẫu khác engine. Median kênh vẫn là đường mốc trên biểu đồ. Họ Holm = mọi phép so có p xác định trên trang Topics, kể cả topic n < 5 (ADR-0023: 9 topic × 3 chỉ số = 27; landing dùng chung).
