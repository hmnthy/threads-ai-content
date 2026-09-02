# Data Model — Threads AI Content

> Đọc khi: làm việc trong `src/api/`, `src/analysis/`, hoặc cần biết field/metrics/response shape thật của Threads API, công thức Virality Index, hay mapping chủ đề↔template.
> Xem thêm: [`architecture.md`](architecture.md) cho tech stack/cấu trúc thư mục, [`CLAUDE.md`](../../CLAUDE.md) cho mission/status.

---

## Threads API Integration

**Docs**: https://developers.facebook.com/docs/threads/

### Endpoints cần thiết

```
GET /{user_id}/threads                   # Danh sách posts của kênh
GET /{user_id}/replies                   # Danh sách reply tác giả đã đăng
GET /{thread-id}/insights                # Metrics của 1 post
GET /{user_id}/threads_insights          # Metrics tổng kênh
POST /me/threads                         # Publish post mới (nếu tích hợp auto-post)
```

### Pagination

`GET /{user_id}/threads` và `GET /{user_id}/replies` đều trả kết quả theo **cursor pagination** chuẩn Graph API: response có thêm object `paging: { cursors: { before, after }, next: "<url trang tiếp theo>" }`. Không truyền `limit` → API tự dùng page size mặc định (phát hiện thực tế: 25/page).

`get_posts()` và `get_replies()` (`src/api/endpoints.py`) đều dùng chung helper `_paginate()` — gọi `ThreadsClient.get_url()` với URL tuyệt đối từ `paging.next` (URL này đã có sẵn `access_token`, không inject lại) cho tới khi response không còn `paging.next`. Đảm bảo lấy đủ toàn bộ lịch sử kênh, không chỉ page đầu.

`get_replies()` mới thêm (2026-08-29), dùng scope `threads_manage_replies` đã có sẵn ở Phase 1, tái dùng `POST_FIELDS` + model `ThreadsPost` với `/threads`.

**Verify live (2026-08-29)**: đã fetch thật cả 2 endpoint với pagination fix — `/replies` trả đúng shape như giả định (25/25 item validate sạch qua `ThreadsPost`, không có field lạ ngoài `POST_FIELDS`, các field optional như `thumbnail_url`/`quoted_post`/`reposted_post` chỉ đơn giản là không có mặt ở item nào chứ không sai kiểu). Số liệu thật của kênh `thydilammuon`: **140 posts**, **1,285 replies** (con số "25 posts" ghi ở lần verify trước chỉ là page 1 do bug pagination lúc đó — đã lỗi thời).

### Fields có thể lấy từ mỗi post

`id`, `text`, `timestamp`, `media_type`, `permalink`, `shortcode`, `username`,
`media_url`, `thumbnail_url`, `is_quote_post`, `quoted_post`, `reposted_post`, `children`

`media_type` values: `TEXT_POST`, `IMAGE`, `VIDEO`, `CAROUSEL_ALBUM`, `AUDIO`, `REPOST_FACADE`

**Fields cho thread reconstruction — verify live 2026-08-30** (test trên cả `/threads` và `/replies`, không dùng `POST_FIELDS` mặc định vì chưa từng request các field này trước đây):

| Field | Kết quả verify | Ghi chú |
|---|---|---|
| `root_post`, `replied_to` | ✅ Thật — trả `{"id": "..."}`. Mẫu nhỏ (limit=3) ban đầu trống, tưởng lỗi; test lại `limit=20` trên `/replies` thấy 9-10/20 item có data | Dùng cho `thread_reconstruction.py` — nối chuỗi self-reply thành 1 `ContentUnit` |
| `is_reply`, `is_reply_owned_by_me` | ✅ Thật — boolean đúng nghĩa (`is_reply=False` trên `/threads`, `True` trên `/replies`) | Phân biệt self-continuation (tác giả tự reply tiếp) vs audience reply |
| `has_replies` | ✅ Thật (test thêm ngoài dự kiến ban đầu) | Tín hiệu nhẹ "post có ai reply chưa" |
| `is_spoiler_media` | ✅ Thật, luôn `False` trong data hiện có | Tác giả chưa dùng spoiler |
| `text_attachment` | ✅ Thật, CÓ dùng — verify lại 2026-08-31 khi chạy pipeline ingest trên toàn bộ 140 posts + 1,285 replies (mẫu nhỏ 50+50 ngày 2026-08-30 không bắt được case này). Shape thật là **edge `{"plaintext": "..."}`**, không phải string phẳng như giả định ban đầu — `ThreadsPost` đã thêm `field_validator` tự flatten (giống `children`) | Dùng cho `ContentUnit.text_attachment` |
| `is_ghost_post`, `poll_attachment`, `gif_attachment`, `location_id` | ⚠️ Không lỗi nhưng **0/100 item có data** (test 50 post + 50 reply, 2026-08-30) | Nhiều khả năng tác giả chưa từng dùng các tính năng này — KHÔNG kết luận field sai, nhưng cũng chưa có bằng chứng field đúng. Lưu schema nullable, không dùng trong scoring tới khi có post thật dùng chúng |
| `enable_reply_approvals` | ⚠️ Tương tự — có thể chỉ là param lúc publish, không đọc lại được | Không dùng trong V1 |
| Metric **"shares"** | ❌ Không tồn tại — post-level insights chỉ có `views, likes, replies, reposts, quotes` (verify 2026-08-28) | Loại khỏi mọi công thức Engagement/Virality tới khi tìm được field thật (nếu có) |

### Metrics lấy từ API

**Post-level**: `views`, `likes`, `replies`, `reposts`, `quotes` — response shape: `period: "lifetime"`, `values: [{"value": N}]` (1 phần tử)
**Account-level**: `views`, `likes`, `replies`, `reposts`, `quotes`, `clicks`, `followers_count` (qua `get_account_insights`) + `follower_demographics` riêng (qua `get_follower_demographics`, bắt buộc `breakdown`)

> `reach` và `impressions` **không tồn tại** trong Threads API (khác Instagram)

**Response shape KHÔNG đồng nhất giữa các metric account-level (verify live 2026-08-28)**:
| Metric | Shape thật | Cách `_flatten_insights` xử lý |
|---|---|---|
| `views` | `period: "day"`, `values: [{"value": N}, ...]` — nhiều entry theo ngày | Cộng dồn (sum) toàn bộ `values` |
| `likes`, `replies`, `reposts`, `quotes`, `followers_count` | `total_value: {"value": N}` | Lấy `total_value["value"]` |
| `clicks` | `link_total_values: [{"value": N, "link_url": ...}, ...]` — theo từng link | Cộng dồn toàn bộ `value` |
| `follower_demographics` | **Bắt buộc** param `breakdown` (`country`/`city`/`age`/`gender`), nếu thiếu → lỗi `error_subcode 4279040`. Khi có, trả `total_value` dạng breakdown (không có key `"value"`) | Giữ nguyên dict breakdown |

`children` (field của post, dùng cho carousel album) cũng là dạng edge: `{"data": [{"id": ...}, ...]}`, không phải `list[str]` phẳng — `ThreadsPost` đã có validator tự flatten (`src/api/models.py`).

### Auth

- OAuth 2.0, token lưu trong `.env` (không commit)
- Scope Phase 1 (đang dùng): `threads_basic`, `threads_manage_insights`, `threads_content_publish`, `threads_manage_replies`
- Scope đã request sẵn cho Phase 2 (Standard Access, chưa dùng được đầy đủ — xem Phase 2 trong `CLAUDE.md`): `threads_trending_topics`, `threads_keyword_search`, `threads_read_replies`, `threads_profile_discovery`
- Long-lived token: 60 ngày — dùng `refresh_long_lived_token()` trong `src/api/auth.py` trước khi hết hạn; `should_warn_expiry()` cảnh báo khi còn ≤ 7 ngày (chỉ hoạt động sau lần refresh đầu tiên, vì Threads không cho tra hạn còn lại của 1 token bất kỳ)
- Rate limit chính tài khoản: `4,800 × số impressions` / 24h (rất cao, khó chạm)
- Token hiện tại lấy trực tiếp qua công cụ **"Tạo mã truy cập"** trong Meta Dashboard (App → Trường hợp sử dụng → Truy cập API Threads → Cài đặt → Công cụ tạo mã người dùng) — công cụ này trả ngay long-lived token cho tester đã approve, không cần tự dựng OAuth redirect flow

### Trạng thái setup Meta Developer

1. [x] Tìm hiểu API docs
2. [x] Tạo Meta Developer App (`threads-thydilammuon`)
3. [x] Thêm Threads API use case
4. [x] Lấy App ID + App Secret (dùng cặp **Threads-specific**, không dùng App ID/Secret tổng)
5. [x] Add `thydilammuon` làm Threads Tester — đã accept lời mời (Threads app → Settings → Account → Website permissions → Invites)
6. [x] Generate long-lived Access Token trực tiếp qua "Tạo mã truy cập" (bỏ qua bước exchange short-lived thủ công)
7. [x] Lấy User ID qua `GET https://graph.threads.net/v1.0/me?fields=id,username&access_token=<TOKEN>`
8. [x] Điền đủ 4 giá trị vào `.env`

Setup Meta Developer đã **hoàn tất**.

---

## Metric Architecture (redesign 2026-08-30, thay hẳn `virality_index` gộp cũ)

> **Nguyên tắc bao trùm**: tách bạch **intrinsic performance** (đo cái gì đã xảy ra) khỏi **explanatory variables** (giải thích tại sao) — không trộn chung 1 công thức kiểu `score = likes + replies + recency + length + topic...`. Mọi hằng số heuristic (grace period, half-life...) là **initial hypothesis cần calibrate lại bằng data thật**, không phải "chân lý" — ghi rõ trong docstring.

### Base indexes (`src/analysis/`, chỉ dùng field đã verified: `views, likes, replies, reposts, quotes` — không có "shares")

```python
def popularity_index(insights: PostInsights) -> int:
    """views — Threads không có reach/impressions, đây là proxy tốt nhất đã verify."""

def engagement_rate(insights: PostInsights) -> float:
    """(likes + replies + reposts + quotes) / views * 100.
    SỬA lỗi: PostInsights.engagement_rate hiện tại (src/api/models.py) THIẾU quotes."""

def virality_index(insights: PostInsights) -> float:
    """(reposts + quotes) / views * 100 — 'bao nhiêu người xem redistribute tiếp'.
    CHỈ nhận insights — không nhận post/age/topic (đó là explanatory variables riêng)."""

def conversation_rate(insights: PostInsights) -> float:
    """replies / views * 100. V2: nâng cấp bằng unique repliers/reply depth qua ContentUnit."""
```

### Velocity & Momentum (cần `insights_snapshots`, KHÔNG dùng lifetime metric đơn lẻ)

```python
def view_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """(views_t2 - views_t1) / (t2 - t1, giờ)."""

def amplification_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """Δ(reposts + quotes) / Δt."""
```

`MomentumIndex = CurrentVelocity / HistoricalMedianVelocity(age, publish_slot)` — **V2, không phải V1**: cần đủ nhiều post × nhiều snapshot tích luỹ hàng tháng mới có "historical median" ý nghĩa. Chỉ hook sẵn interface, chưa implement.

### Longevity

```python
def late_engagement_share(snap_24h: InsightSnapshot, snap_72h: InsightSnapshot) -> float:
    """(Interactions_72h - Interactions_24h) / Interactions_72h,
    Interactions = likes+replies+reposts+quotes. Phân biệt burst-and-die (~95% ở 24h)
    vs long-tail (tăng dần tới 72h) — khớp quan sát thật: post viral trên Threads
    có thể sống tới 3 ngày."""
```

Chỉ tính được cho post **có đủ snapshot phủ 24h và 72h** — 140 post cũ (1 snapshot duy nhất) không tính được, chỉ áp dụng post mới từ lúc job snapshot chạy.

### Freshness (tách hẳn khỏi virality)

```python
def freshness_weight(
    age_hours: float,
    *,
    grace_hours: float = 12.0,      # hypothesis ban đầu — CHƯA calibrate
    half_life_hours: float = 48.0,  # hypothesis ban đầu — CHƯA calibrate
) -> float:
    age_hours = max(age_hours, 0.0)
    if age_hours <= grace_hours:
        return 1.0
    return 0.5 ** ((age_hours - grace_hours) / half_life_hours)
```

**Chỉ dùng khi hỏi "bài nào đang hot NGAY BÂY GIỜ"** — KHÔNG nhân vào `virality_index`/báo cáo trend theo tuần/tháng (post 20 ngày trước vẫn có thể là bài viral nhất quý — nhân recency vào sẽ xoá sổ sai semantic). `grace_hours=12`/`half_life_hours=48` là hypothesis dựa trên quan sát cá nhân tác giả (audience VN thức dậy trễ hơn giờ đăng ở Pháp), **cần calibrate lại bằng dữ liệu khi đủ snapshot** — đúng tinh thần "initial heuristic later calibrated using observed engagement distributions" cho portfolio.

**Confounding factor cần nhớ**: low engagement 6h đầu có thể do audience VN đang ngủ (giờ Pháp buổi tối), KHÔNG đồng nghĩa content dở — đây là lý do velocity/momentum quan trọng hơn recency đơn thuần (2 post cùng age=12h có thể 1 bài đang tăng tốc, 1 bài đang giảm tốc — recency không phân biệt được, velocity thì có).

### Topic Affinity (đổi tên từ `topic_trend_score` — không đo được "đang trend trên Threads" với Standard Access + ~2 post/ngày)

```python
def topic_affinity_score(topic_id: str, window_days: int) -> float:
    """Median virality/engagement CỦA CHÍNH KÊNH cho topic này trong window_days,
    so với baseline toàn kênh cùng window."""
```

**2 khái niệm thời gian tách biệt, không trộn**: `post_maturity_window` = 0-72h (lifecycle 1 post) vs `report_window` = 7d/14d/30d/90d (khung phân tích kênh — ưu tiên 30d/90d vì ~2 post/ngày, 7d chỉ ~14 post quá thưa để có ý nghĩa thống kê, giữ lại cho operational monitoring).

### Timing Fit

```python
def audience_activity_profile() -> dict[int, float]:
    """Infer giờ audience active từ chính velocity data kênh: group Δviews/hour theo
    publish_hour + hour_since_publish, lấy median. Đối chiếu get_follower_demographics(
    breakdown="country") (đã build, CHƯA gọi live — cần verify) để có empirical evidence
    cho hypothesis timezone VN/Pháp."""
```

### V2 (không scope vào sprint hiện tại — cần data tích luỹ hàng tháng)

`MomentumIndex`, maturation curve/`Projected72h` theo publish_slot (cần "vài trăm post" — với ~2 post/ngày là hàng tháng), multimodal (vision/ASR ảnh/video), ghost-post/poll/location đưa vào scoring (hiện chỉ lưu schema).

---

## Chủ đề content hiện có (từ carousel templates)

| Chủ đề | Template | Posts điển hình |
|--------|----------|-----------------|
| Alternance | Alternance/ (7 slides) | Kinh nghiệm alternance, tìm chỗ thực tập |
| CV | CV/ (9 slides) | Cách viết CV Pháp, tips hồ sơ |
| Entretien | Entretien/ (12 slides) | Tips phỏng vấn, câu hỏi thường gặp |
| Lifestyle / Đi đâu chơi gì | Photos/ | Địa điểm, trải nghiệm tại Pháp |
| Data / Insights | Scripts | Posts dạng data, số liệu |
| Divers | Scripts | Các chủ đề tổng hợp khác |

6 chủ đề trên là **fixed category** dùng để chọn template carousel — xem "NLP Pipeline" bên dưới để biết cách chúng khác với **cluster khám phá được** (unsupervised).

---

## NLP Pipeline

> Redesign 2026-08-30 — thay thế hoàn toàn cách tiếp cận cũ ("keyword matching + Claude classification"). Đây là portfolio thể hiện chuyên môn NLP/ML, nên pipeline có tokenization → vector hoá → classify/cluster đúng phương pháp luận, không dùng LLM như black-box classifier.

**Quan trọng — giới hạn cần hiểu trước khi đọc**: Threads (nền tảng) có dùng NLP/embedding/graph-based ranking nội bộ để vận hành — nhưng đó là hệ thống **của Meta, không public, không truy cập được** qua Threads API (Standard Access chỉ đọc data tài khoản `thydilammuon`, không có signal ranking/graph nội bộ của Meta). Pipeline dưới đây là hệ thống **độc lập, tự phân tích data của chính tài khoản** — không phải "kết nối vào AI của Threads".

**Quy ước ngôn ngữ**: pipeline nội bộ (code, docs) tiếng Việt như toàn dự án. **Mọi output hướng ra ngoài** (dashboard UI copy, tên/mô tả topic do LLM sinh, RAG response) — **tiếng Anh 100%**.

### ContentUnit — abstraction cho thread dài + text attachment

Threads cho phép: (a) post đơn ≤500 ký tự, (b) `text_attachment` tới 10.000 ký tự (từ 09/2025 — đọc được qua field hay không **chưa verify**), (c) chuỗi self-reply liên tiếp (5-15 post) nối thành 1 "bài dài" (verify field `root_post`/`replied_to`/`is_reply_owned_by_me` — xem bảng ở "Threads API Integration"). `ThreadsPost` (`src/api/models.py`) vẫn là raw ingestion layer map 1:1 media object, **không đổi**. `ContentUnit` là layer derived, xây TỪ 1+ `ThreadsPost`:

```python
@dataclass(frozen=True)
class ContentUnit:
    root: ThreadsPost
    continuations: list[ThreadsPost]   # self-reply do CHÍNH tác giả đăng tiếp (is_reply_owned_by_me=True)
    text_attachment: str | None
    full_text: str                     # root.text + " ".join(continuations text)
    media: list[ThreadsPost]
```

**Audience replies KHÔNG gộp vào `full_text`** — chúng là tín hiệu `conversation_rate`, không phải nội dung. Embedding/topic detection chạy trên `full_text` của `ContentUnit`, không phải riêng root post.

**Schema mở rộng cho field mới Meta công bố** (context feature, KHÔNG nhét vào scoring formula tới khi có post thật dùng): `is_ephemeral` (ghost post tự hết hạn 24h → cohort longevity riêng), `format_type`, `location_id`, `reply_approvals_enabled` (nếu bật → `conversation_rate` bị selection bias).

### Kiến trúc NLP

```
Raw post (root + continuations, giữ NGUYÊN — không strip emoji/hashtag)
      ↓ text.py            raw_text (bất biến) + normalized_text (chỉ whitespace + URL, tối thiểu)
      ↓ language.py        LanguageInfo (metadata, KHÔNG rẽ nhánh xử lý downstream)
      ↓ embed()            sentence-transformers multilingual (bge-m3 / multilingual-e5-large)
      │                    — luôn chạy trên MỌI post, không có bước "chọn model theo ngôn ngữ"
      │
      ├─ Fixed-category classification (6 lớp, cho carousel routing)
      │  SVM-RBF (model chính) + LogisticRegression (baseline so sánh)
      │  train/eval bằng stratified k-fold CV trên gold label user tự gán (140/140 post)
      │
      └─ Unsupervised topic discovery (khám phá + visualize, cho analytics)
         UMAP (giảm chiều → 3D) + HDBSCAN (cluster trên embedding gốc, density-based)
         → LLM (Claude) tóm tắt mỗi cluster → tên + mô tả TIẾNG ANH
         → so sánh với 6 category cố định (ARI/purity score)
```

### 3 nguyên tắc từ paper "Challenges of Computational Processing of Code-Switching" (áp dụng 2026-08-30)

1. **Code-switching là metadata, không phải routing constraint** — không có bước "language detection → chọn model xử lý riêng cho ngôn ngữ đó" (error propagation: nếu LID sai, mọi bước sau sai theo). 2 nhánh `language.py`/`embed()` chạy song song, độc lập.
2. **Giữ nguyên ngữ liệu, không "clean" quá tay** — bỏ hẳn kế hoạch strip emoji/hashtag/"từ nước ngoài" trước embedding. Social media text: 1 token có thể emoji mang tín hiệu sentiment/virality thật (`"OpenAI cooked 😭🔥 #GPT6"` → xoá emoji/hashtag là mất signal). Giữ song song `raw_text` (bất biến, để rerun pipeline khi model tốt hơn — lưu tại `data/raw/`, KHÁC `data/cache/` hiện có vì cache TTL 6h còn raw archive không hết hạn) + `normalized_text` (nhẹ).
3. **Ưu tiên "không chắc" hơn "chắc sai"** — `primary_language` cho phép `None`/unknown khi confidence thấp, không ép argmax. Ranh giới code-switching vs borrowing (từ mượn đã thành vocabulary, VD "deploy"/"model"/"production" trong cộng đồng tech Việt) không rõ ràng — kể cả human annotator cũng không thống nhất — nên dùng **continuous score**, không dùng boolean.

```python
@dataclass(frozen=True)
class LanguageInfo:
    primary_language: str | None   # None nếu confidence thấp — không ép argmax
    detected_languages: list[str]
    confidence: float
    language_mix_score: float      # continuous — KHÔNG phải bool, tránh false positive với từ mượn
```

Dùng `lingua-py` (không phải `langdetect`) — hỗ trợ confidence score native, robust hơn trên short text (gap `langdetect` gặp theo paper), có `detect_multiple_languages_of()` để tính `language_mix_score = 1 - (độ dài span ngôn ngữ ưu thế / tổng độ dài)`.

**Vì sao bỏ `underthesea`**: content trộn VI/FR/EN tự nhiên — tokenizer riêng tiếng Việt sẽ segment sai phần tiếng Pháp/Anh. sentence-transformers multilingual tự xử lý đa ngôn ngữ ở tầng embedding.

**Vì sao 2 hệ thống phân loại song song, không phải 1**: đây là 2 bài toán khác nhau. Fixed-category (6 lớp cố định) phục vụ **chọn đúng template carousel** — cần nhãn cố định, có thể dùng ngay. Cluster khám phá phục vụ **phân tích/gap analysis/visualize** — không giới hạn số lượng/tên chủ đề, có thể phát hiện chủ đề mới chưa từng nghĩ tới, đúng tinh thần "Topic gap analysis" đã ghi trong roadmap từ đầu. Cả 2 dùng chung embedding, khác nhau ở bước sau.

**Vì sao SVM-RBF làm model chính, LogisticRegression chỉ là baseline**: LogReg là mô hình tuyến tính, chỉ nên đóng vai trò benchmark để biết SVM-RBF (bắt được ranh giới phi tuyến trên embedding) có thực sự tốt hơn không — không phải chọn 1 trong 2 rồi bỏ, mà giữ cả 2 trong bảng kết quả để so sánh minh bạch.

**Vì sao LLM chỉ dùng ở bước labeling cluster, không dùng để classify trực tiếp**: dùng LLM đúng việc nó giỏi nhất — tóm tắt ngôn ngữ tự nhiên sau khi đã có cấu trúc thật từ NLP pipeline (HDBSCAN), không thay thế phần NLP core bằng 1 API call.

> Velocity/Momentum/Longevity/Freshness/Topic Affinity — xem "Metric Architecture" phía trên, không lặp lại ở đây.

### Methodology log: clustering space cho HDBSCAN (thực nghiệm 2026-09-02)

> Viết ở dạng report — nguồn để đăng lên trang "Methodology" của dashboard/web analytics sau này (output hướng ra ngoài, sẽ dịch/viết lại tiếng Anh khi lên web, xem quy tắc ngôn ngữ ở dưới). Đây là quá trình thật, kể cả phần đã sai và sửa lại — không "làm sạch" lịch sử.

**Bối cảnh môi trường**: `hdbscan`/`umap-learn`/`scikit-learn`/`sentence-transformers` không import được trên Windows của máy chạy dự án — chẩn đoán ra là **Smart App Control** (tính năng Windows 11 Home, khác WDAC/AppLocker doanh nghiệp — xác nhận qua registry `HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState=1` và việc cmdlet `Get-AppLockerPolicy` không tồn tại trên máy). Đặc điểm quan trọng: Smart App Control **không có UI cho user thường allowlist 1 file** — chỉ có thể tắt hẳn, và theo tài liệu Microsoft, tắt rồi **không bật lại được nếu không cài lại Windows**. Đánh đổi đó không tương xứng chỉ để chạy 1 thư viện Python, nên quyết định **không tắt**.

Verify thêm cho thấy hành vi này **flaky theo thời gian**, không phải "chặn cố định": `sentence-transformers`/bge-m3 chạy được thật 1 lần (2026-09-01), rồi bị chặn lại đúng lỗi cũ ngày hôm sau (2026-09-02) mà không đổi gì ở code/dependency — nghi do reputation-check bất đồng bộ của Smart App Control. Kết luận: không dựa vào Windows cho bất kỳ bước ML thật nào (embedding lẫn clustering), kể cả khi có lúc chạy được.

**Giải pháp**: chuyển toàn bộ embedding + UMAP + HDBSCAN sang chạy trong **WSL2** (đã cài sẵn trên máy, không cần `wsl --install`/reboot). Smart App Control chỉ kiểm soát PE/DLL của Windows — binary ELF trong WSL2 nằm ngoài phạm vi đó hoàn toàn, không phải "mẹo né" mà là khác boundary hệ điều hành. Kiến trúc cầu nối 3 bước, dùng lại nguyên hàm `embed_texts()`/`cluster_embeddings()` đã viết (không viết logic riêng cho WSL, tránh 2 bản lệch nhau):
1. `src/pipeline/clustering_export.py` (Windows) — xuất `(id, full_text)` ra `data/nlp_exchange/texts_export.json`
2. `src/pipeline/cluster_wsl.py` (chạy trong WSL2 Ubuntu, venv `~/threads-clustering-env`) — embed + cluster, ghi `data/nlp_exchange/cluster_results.json`
3. `src/pipeline/clustering_import.py` (Windows) — đọc kết quả, ghi toạ độ UMAP + chạy LLM labeling vào SQLite

**Thực nghiệm — raw embedding space vs UMAP space cho input của HDBSCAN**: thiết kế gốc của `cluster_embeddings()` (`src/nlp/topics.py`) cho HDBSCAN chạy trên embedding gốc 1024 chiều (lý do ghi trong docstring cũ: "giữ đúng density thật, không bị méo bởi UMAP"). Chạy thật trên 141 post: kết quả suy biến — 1 cluster chiếm **82%** dữ liệu (116/141), không tách được chủ đề nào. Chẩn đoán: curse of dimensionality — khoảng cách Euclidean mất khả năng phân biệt trên không gian nhiều chiều với ít điểm dữ liệu. Thử lại HDBSCAN trên chính toạ độ UMAP 3D (đã tính sẵn cho visualize, không thêm bước giảm chiều trung gian nào khác — dataset nhỏ, chưa cần) cho kết quả cân đối hơn hẳn (47/73/8 + 13 noise thay vì 116/6 + 19 noise).

**Phát hiện phụ làm nhiễu thực nghiệm**: 6/141 post có `full_text` rỗng, toàn bộ đều là `media_type=REPOST_FACADE` (tác giả repost bài người khác không thêm caption — Threads lưu dạng "vỏ", không có `text` lẫn `text_attachment`). Embedding của chuỗi rỗng gần giống hệt nhau nên HDBSCAN gom 6 post này thành 1 "cluster" giả ở cả 2 phương pháp — không phải chủ đề thật. Quyết định: loại content unit có `full_text` rỗng khỏi bước export cluster (lọc theo tiêu chí "rỗng", không hardcode `media_type`, vì đúng bản chất là "không có gì để embed" — tổng quát hơn cho các trường hợp tương lai).

**Kết quả sau khi loại nhiễu (135 post sạch)** — chênh lệch giữa 2 phương pháp rõ ràng hơn nhiều, không còn mập mờ:

| | Raw embedding (1024D) | UMAP space (3D) |
|---|---|---|
| Số cluster | 2 (40/15) | 2 (50/81) |
| Noise | 80/135 (**59%**) | 4/135 (**3%**) |

Raw-embedding-space **kém ổn định hẳn** khi bỏ 6 điểm neo (noise tăng từ 13%→59%) — chứng tỏ kết quả trước đó "có vẻ ổn" phần lớn dựa vào 1 nhóm điểm suy biến, không phải cấu trúc chủ đề thật. UMAP-space **ổn định và sạch hơn** khi bỏ nhiễu (9%→3%). Kết luận methodology: **cluster trên toạ độ UMAP đã giảm chiều, không phải embedding gốc** — đảo ngược quyết định thiết kế ban đầu, dựa trên bằng chứng thực nghiệm chứ không phải lý thuyết suông. *(Trạng thái tới lúc ghi report này: đã có đủ bằng chứng, đang chờ xác nhận cuối trước khi sửa `cluster_embeddings()` — xem `docs/next-steps.md`.)*

**Công cụ**: mọi biểu đồ so sánh dùng SVG thuần (không dùng Plotly `scatter3d`/WebGL — artifact sandbox không render WebGL, `scatter3d` cho canvas trống không báo lỗi rõ ràng; small-multiples 2D (X-Y/X-Z/Y-Z) từ cùng toạ độ 3D cho khả năng đánh giá tương đương mà không cần rotate).

### Storage

- `data/raw/` — archive JSON vĩnh viễn (KHÁC `data/cache/` hiện có, TTL 6h) — cho phép rerun pipeline từ đầu khi model NLP tốt hơn, không cần crawl lại
- SQLite: `posts`, `content_units`, `insights_snapshots` (time-series), `topics` (id, label_en, description_en, method: "fixed"|"cluster", centroid_embedding), `post_topic_labels` (post_id, topic_id, method, confidence)
- Vector store riêng (Chroma hoặc FAISS) — tách khỏi SQLite, phục vụ semantic search cho RAG, tái dùng chính embedding đã tính ở bước `embed()` (chạy trên `ContentUnit.full_text`)

### RAG (Retrieval-Augmented Generation)

Tái dùng trực tiếp vector store ở trên — không xây hạ tầng riêng:
1. **Retrieval**: query → semantic search trên vector store → top-k post/reply liên quan
2. **Generation**: đưa post lấy được làm context cho Claude → trả lời/tóm tắt/gợi ý **grounded trên content thật đã đăng**

Ứng dụng cụ thể: hỗ trợ bước Content Generation (Giai đoạn 3) — thay vì chỉ dựa vài ví dụ giọng văn tĩnh, RAG kéo đúng post liên quan chủ đề nhất làm few-shot context động.

### Phạm vi V1

- Chỉ 140 posts — **1,285 replies để sau** (mang tính tương tác/hội thoại, phù hợp hướng phân tích khác — graph tương tác — không phải NLP content pipeline này)
- Velocity: xây hạ tầng nhưng chấp nhận chưa có data lịch sử, tích luỹ dần
- RAG: bản nhẹ (retrieval + generation cơ bản), không multi-turn phức tạp
