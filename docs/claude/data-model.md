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

### Central tendency: median cạnh mean (`src/analysis/engagement.py`, Layer 2, 2026-09-03)

```python
def median_engagement_rate(insights: list[PostInsights]) -> float:
    """Median of engagement_rate — dùng song song average_engagement_rate() (mean).
    Mean bị 1 bài viral kéo lệch; median phản ánh 'trải nghiệm điển hình' bền hơn."""

@dataclass(frozen=True)
class EngagementBucketStats:
    median: float
    mean: float
    n: int
    iqr_low: float   # Q1, statistics.quantiles(..., method="inclusive")
    iqr_high: float  # Q3
    insufficient_data: bool  # True nếu n < MIN_N_PER_BUCKET

def engagement_by_hour(posts, insights, *, timezone=None) -> dict[int, EngagementBucketStats]: ...
def engagement_by_weekday(posts, insights, *, timezone=None) -> dict[int, EngagementBucketStats]: ...
```

**Breaking change (2026-09-03)**: `engagement_by_hour`/`engagement_by_weekday` trước đây trả `dict[int, float]` (mean thô) — nay trả `dict[int, EngagementBucketStats]`. Lý do: case thực nghiệm median 412 vs mean 2.254 (gấp 5.5 lần, nguồn `Hwemo-Chung/threads-analytics`) cho thấy "giờ tốt nhất" theo mean có thể là "giờ tệ nhất" theo median — 1 con số mean đơn lẻ không đủ để kết luận, cần median (bền với outlier) + n + spread đi kèm để biết có đủ căn cứ diễn giải không. `MIN_N_PER_BUCKET = 5` (mượn `vunderkind/threads-analytics`) — bucket dưới ngưỡng này vẫn trả về số liệu thô (không loại bỏ) nhưng đánh dấu `insufficient_data=True`, tầng trình bày phải tôn trọng cờ này (không tuyên bố "giờ này tốt nhất" từ 1-2 bài). Đây là ứng dụng trực tiếp tầng 3 "Narrative Layering Principle" ở trên. Xem "Narrative Layering Principle" cho thứ tự trình bày đầy đủ.

### Suy diễn thống kê: `compare_groups()` (`src/analysis/significance.py`, Layer 4, 2026-09-03)

```python
@dataclass(frozen=True)
class ComparisonResult:
    median_a: float
    median_b: float
    n_a: int
    n_b: int
    p_value: float | None          # Mann-Whitney U, two-sided; None nếu 1 nhóm rỗng
    effect_size: float | None      # Cliff's delta [-1, 1]; None nếu 1 nhóm rỗng
    median_diff_ci_low: float | None   # bootstrap CI 95%, median(b) - median(a)
    median_diff_ci_high: float | None
    insufficient_data: bool        # True nếu min(n_a, n_b) < MIN_N_PER_BUCKET

def compare_groups(group_a: list[float], group_b: list[float], *, n_resamples: int = 1000, random_seed: int | None = None) -> ComparisonResult: ...
```

**Engine dùng chung** cho mọi so sánh 2 nhóm: viral vs non-viral (`is_viral`, Layer 3), có/không author reply event (`topic_affinity.py`, Layer 7), topic vs topic. Mann-Whitney U (không giả định phân phối chuẩn — đúng lý do median thắng mean ở Layer 2, engagement rate lệch phải mạnh) + Cliff's delta (effect size non-parametric tương ứng, dương = `group_a` xu hướng lớn hơn `group_b`) + bootstrap CI 95% (1000 resample, percentile method) trên `median(group_b) - median(group_a)`. Bộ 3 kiểm định port từ `vunderkind/threads-analytics`. `insufficient_data` dùng LẠI `MIN_N_PER_BUCKET` của `engagement.py` (1 nguồn sự thật "mẫu quá nhỏ để diễn giải" xuyên suốt dự án) — khác với 2 nhóm rỗng (không thể tính Mann-Whitney, trả `None` thay vì chỉ đánh cờ). Đây là tầng 5 "Narrative Layering Principle".

### Định nghĩa viral: `is_viral()` (`src/analysis/virality.py`, Layer 3, 2026-09-03)

```python
def channel_virality_p90(insights: list[PostInsights]) -> float:
    """P90 của virality_index trên toàn kênh (hoặc 1 cửa sổ do người gọi tự lọc
    trước — hàm không tự áp cửa sổ thời gian)."""

def is_viral(virality_index_value: float, channel_p90: float, views: int, floor: int) -> bool:
    """virality_index_value > channel_p90 AND views >= floor.
    `floor` KHÔNG hardcode — người gọi tự tính từ phân phối views thật (VD P25/median)."""
```

Nhãn phái sinh THÊM, không thay `virality_index` (công thức intrinsic không đổi). Tiền lệ học thuật: Elmas 2023 (arXiv 2303.06120) + VIRALITYNET (arXiv 2605.02358) — kết hợp percentile-trong-kênh (tầng 4 "Narrative Layering Principle") VÀ floor tuyệt đối trên views (loại post "ăn may" vì mẫu bé — 1 view + 1 repost cũng đạt percentile cao nhưng vô nghĩa). `channel_p90` phải tính trên CÙNG cửa sổ thời gian với `views` đang xét — hàm không tự kiểm tra tính nhất quán này.

### Velocity & Momentum (cần `insights_snapshots`, KHÔNG dùng lifetime metric đơn lẻ)

```python
def view_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """(views_t2 - views_t1) / (t2 - t1, giờ)."""

def amplification_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """Δ(reposts + quotes) / Δt."""
```

```python
def window_velocity(snapshots: list[InsightSnapshot]) -> float:
    """Hệ số góc hồi quy tuyến tính views~time (numpy.polyfit bậc 1) trên TOÀN BỘ
    chuỗi snapshot trong 1 window — yêu cầu >=3 điểm, raise ValueError nếu <3
    (2 điểm dùng view_velocity)."""
```

**"Window velocity" (Layer 5, 2026-09-03)** — bổ sung `view_velocity`/`amplification_velocity` (2 điểm, "velocity hiện tại"), KHÔNG thay thế: với 1 post có ≥3 snapshot trong 1 window xác định (VD 24h — cron 4h → ~6 điểm), hồi quy trên TOÀN BỘ chuỗi ổn định hơn trước nhiễu do lịch cron không hoàn hảo, thay vì chỉ lấy 2 điểm đầu-cuối (nhạy với 1 điểm lỗi/trễ). Ở tầng trình bày, LUÔN hiện chuỗi snapshot thô (timestamp, views — tầng 1 "Narrative Layering Principle") TRƯỚC khi hiện slope tính ra (tầng 2/3).

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

### Reply-level analysis (`src/analysis/reply_thread.py`, Layer 6, 2026-09-03)

```python
def unique_repliers(root_post_id: str, conn: sqlite3.Connection) -> int:
    """Số người reply RIÊNG BIỆT (loại is_reply_owned_by_me=True). Dùng username
    khi có, fallback post.id khi thiếu (over-count có chủ đích, ghi rõ hạn chế)."""

def reply_depth(root_post_id: str, conn: sqlite3.Connection) -> int:
    """Độ sâu tối đa chuỗi replied_to_id tính từ root — 0/1/2+."""

def early_reply_velocity(root_post_id: str, conn: sqlite3.Connection, window_hours: float = 24.0) -> float:
    """Số reply audience / giờ trong window_hours đầu kể từ lúc root đăng."""
```

Tính trực tiếp trên graph đã có sẵn trong `posts` (`is_reply`/`replied_to_id`/`root_post_id`/`is_reply_owned_by_me`) — trước giờ 1.285 replies chỉ đóng góp vào `conversation_rate` (đếm gộp). Căn cứ chính thức: Meta Transparency Center liệt kê "engagement của descendant ở level 2 trong 1h/6h" là 1 prediction feature THẬT trong ranking — cho phép trích dẫn khi trình bày hạng mục này. `unique_repliers`/`early_reply_velocity` chỉ tính audience (loại self-continuation của tác giả); `reply_depth` tính trên toàn graph (audience có thể reply vào self-continuation, vẫn là 1 phần cấu trúc thread thật). So sánh nhóm dùng `compare_groups()` ở tầng gọi, không lặp logic thống kê trong module này.

### Topic Affinity (đổi tên từ `topic_trend_score` — không đo được "đang trend trên Threads" với Standard Access + ~2 post/ngày)

```python
def topic_affinity_score(topic_id: str, window_days: int) -> float:
    """Median virality/engagement CỦA CHÍNH KÊNH cho topic này trong window_days,
    so với baseline toàn kênh cùng window."""
```

**2 khái niệm thời gian tách biệt, không trộn**: `post_maturity_window` = 0-72h (lifecycle 1 post) vs `report_window` = 7d/14d/30d/90d (khung phân tích kênh — ưu tiên 30d/90d vì ~2 post/ngày, 7d chỉ ~14 post quá thưa để có ý nghĩa thống kê, giữ lại cho operational monitoring).

### Reply-strategy evidence (`src/analysis/topic_affinity.py`, Layer 7, 2026-09-03)

```python
def is_author_reply_event(post: ThreadsPost, root_content_unit: ContentUnit) -> bool:
    """True nếu post.is_reply_owned_by_me=True VÀ post KHÔNG thuộc
    root_content_unit.continuations — tác giả trả lời vào cuộc trò chuyện
    audience, không phải tự nối tiếp nội dung mình."""

def compare_virality_with_without_author_reply(
    posts_with_reply: list[float], posts_without_reply: list[float]
) -> ComparisonResult:
    """Tái sử dụng compare_groups() (Layer 4) — KHÔNG viết lại logic thống kê."""
```

**Correlation, not causation — PHẢI đọc trước khi diễn giải**: dù kết quả có ý nghĩa thống kê, KHÔNG kết luận "tác giả reply nhiều hơn LÀM cho post viral hơn". Confound đã biết: chiều nhân quả nhiều khả năng ngược lại — bài đang lên top khiến tác giả chủ động reply nhiều hơn để tận dụng đà, không phải reply là nguyên nhân. Kết quả chỉ có giá trị mô tả tương quan quan sát được, dùng để hình thành giả thuyết, không dùng để khẳng định 1 chiến lược content.

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
2. **Giữ nguyên ngữ liệu, không "clean" quá tay** — bỏ hẳn kế hoạch strip emoji/hashtag/"từ nước ngoài" trước embedding. Social media text: 1 token có thể emoji mang tín hiệu sentiment/virality thật (`"OpenAI cooked 😭🔥 #GPT6"` → xoá emoji/hashtag là mất signal). Giữ song song `raw_text` (bất biến, để rerun pipeline khi model tốt hơn — lưu tại `data/raw/`, KHÁC `data/cache/` hiện có vì cache TTL 6h còn raw archive không hết hạn) + `normalized_text` (nhẹ — chỉ whitespace/URL + Unicode NFC + gộp dấu thanh cũ/mới "oa"/"uy", thêm Layer 9 2026-09-03, xem `src/processing/text.py`; KHÔNG động vào emoji/hashtag/từ mượn — vẫn đúng tinh thần "không clean quá tay", chỉ chuẩn hoá CHÍNH TẢ tương đương, không đổi nghĩa/xoá tín hiệu).
3. **Ưu tiên "không chắc" hơn "chắc sai"** — `primary_language` cho phép `None`/unknown khi confidence thấp, không ép argmax. Ranh giới code-switching vs borrowing (từ mượn đã thành vocabulary, VD "deploy"/"model"/"production" trong cộng đồng tech Việt) không rõ ràng — kể cả human annotator cũng không thống nhất — nên dùng **continuous score**, không dùng boolean.

```python
@dataclass(frozen=True)
class LanguageInfo:
    primary_language: str | None   # None nếu confidence thấp — không ép argmax
    detected_languages: list[str]
    confidence: float
    language_mix_score: float      # Code-Mixing Index, thang 0-100 (Layer 9, xem dưới)
```

Dùng `lingua-py` (không phải `langdetect`) — hỗ trợ confidence score native, robust hơn trên short text (gap `langdetect` gặp theo paper).

**Layer 9 (2026-09-03) — Code-Mixing Index (CMI) thay công thức span-based cũ**: `language_mix_score` trước đây tính bằng `detect_multiple_languages_of()` (`1 - độ dài span ngôn ngữ ưu thế / tổng độ dài`) — hàm này CHÍNH lingua-py gắn nhãn "experimental", kém tin cậy trên đoạn ngắn (social media post điển hình). Thay bằng **Code-Mixing Index**, định nghĩa học thuật gốc (Gambäck & Das, "On Measuring the Complexity of Code-Mixing", 2014):

```
CMI = 100 * (1 - max(w_i) / (n - u))   nếu n > u
CMI = 0                                 nếu n = u
```

`n` = tổng số token, `u` = số token "language-independent" (LID không gán được ngôn ngữ — "unknown"), `w_i` = số token ngôn ngữ i, `max(w_i)` = số token ngôn ngữ chiếm ưu thế trong phần còn lại. **Thang 0-100** (KHÁC thang 0.0-1.0 của công thức cũ) — cố tình giữ đúng thang chuẩn để so sánh trực tiếp với benchmark VietMix (CMI≈21.7 trên data Threads VI-EN thật, xem `docs/research/vietnamese-nlp-foundations-2026-09.html`) — "kênh này CMI=X so với 21.7 của VietMix" là 1 con số citable thật cho report.

**LID cấp từ — hybrid** (`src/nlp/language.py` `_token_language()`): (1) dict tra cứu trực tiếp cho từ mượn chuyên ngành đã biết trước (`_BORROWED_TERMS` — "alternance", "CDI", "CV", "entretien", "stage", "titre de séjour"...) — đáng tin hơn LID thống kê trên 1 từ đơn lẻ rất ngắn; (2) `lingua-py.detect_language_of()` chạy PER-TOKEN làm fallback (API ổn định, KHÁC `detect_multiple_languages_of` đã bỏ); (3) fallback cuối `"unknown"` — nguyên tắc 3 ở trên áp dụng luôn ở cấp từ, không chỉ cấp câu.

**Lưu ý chưa hoàn thành**: `MIN_CONFIDENCE_FOR_PRIMARY = 0.5` VẪN LÀ hypothesis chưa calibrate bằng data thật — Layer 9 chỉ rà soát lại giá trị này, chưa có bước calibrate thực nghiệm (cần review tay 1 mẫu post thật + nhãn confidence kỳ vọng, chưa làm trong đợt sửa này).

**Vì sao bỏ `underthesea`**: content trộn VI/FR/EN tự nhiên — tokenizer riêng tiếng Việt sẽ segment sai phần tiếng Pháp/Anh. sentence-transformers multilingual tự xử lý đa ngôn ngữ ở tầng embedding.

**Vì sao 2 hệ thống phân loại song song, không phải 1**: đây là 2 bài toán khác nhau. Fixed-category (6 lớp cố định) phục vụ **chọn đúng template carousel** — cần nhãn cố định, có thể dùng ngay. Cluster khám phá phục vụ **phân tích/gap analysis/visualize** — không giới hạn số lượng/tên chủ đề, có thể phát hiện chủ đề mới chưa từng nghĩ tới, đúng tinh thần "Topic gap analysis" đã ghi trong roadmap từ đầu. Cả 2 dùng chung embedding, khác nhau ở bước sau.

**Vì sao SVM-RBF làm model chính, LogisticRegression chỉ là baseline**: LogReg là mô hình tuyến tính, chỉ nên đóng vai trò benchmark để biết SVM-RBF (bắt được ranh giới phi tuyến trên embedding) có thực sự tốt hơn không — không phải chọn 1 trong 2 rồi bỏ, mà giữ cả 2 trong bảng kết quả để so sánh minh bạch.

**Vì sao LLM chỉ dùng ở bước labeling cluster, không dùng để classify trực tiếp**: dùng LLM đúng việc nó giỏi nhất — tóm tắt ngôn ngữ tự nhiên sau khi đã có cấu trúc thật từ NLP pipeline (HDBSCAN), không thay thế phần NLP core bằng 1 API call.

**Ranh giới Claude LLM trong pipeline (chốt tường minh 2026-09-03)** — research thị trường (`docs/research/market-scan-2026-09.html`) xác nhận kiến trúc hiện tại ĐÚNG hướng, không cần sửa code, chỉ cần công bố rõ: Claude **CHỈ** dùng ở duy nhất 1 điểm — `label_cluster_with_claude()` (`src/nlp/topics.py`), tóm tắt 1 cluster đã tồn tại (do HDBSCAN tìm ra) thành tên + mô tả tiếng Anh. Claude **KHÔNG BAO GIỜ**: (a) classify/gán nhãn topic trực tiếp cho 1 post (việc đó là HDBSCAN + SVM-RBF/LogReg), (b) tạo embedding (việc đó là `sentence-transformers`), (c) tham gia bất kỳ bước NLP core nào khác (LID, clustering, tokenization). Ranh giới này khớp nguyên tắc chung của dự án: dùng LLM đúng việc "tóm tắt ngôn ngữ tự nhiên", không dùng LLM như black-box thay thế phương pháp luận NLP có cấu trúc — giữ tính reproducible/explainable của pipeline (HDBSCAN/SVM cho kết quả xác định lại được từ embedding, LLM không).

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

Raw-embedding-space **kém ổn định hẳn** khi bỏ 6 điểm neo (noise tăng từ 13%→59%) — chứng tỏ kết quả trước đó "có vẻ ổn" phần lớn dựa vào 1 nhóm điểm suy biến, không phải cấu trúc chủ đề thật. UMAP-space **ổn định và sạch hơn** khi bỏ nhiễu (9%→3%). Kết luận methodology: **cluster trên toạ độ UMAP đã giảm chiều, không phải embedding gốc** — đảo ngược quyết định thiết kế ban đầu, dựa trên bằng chứng thực nghiệm chứ không phải lý thuyết suông. Đã xác nhận và triển khai vào `cluster_embeddings()` (2026-09-02) — không còn là DRAFT.

**Công cụ**: mọi biểu đồ so sánh dùng SVG thuần (không dùng Plotly `scatter3d`/WebGL — artifact sandbox không render WebGL, `scatter3d` cho canvas trống không báo lỗi rõ ràng; small-multiples 2D (X-Y/X-Z/Y-Z) từ cùng toạ độ 3D cho khả năng đánh giá tương đương mà không cần rotate).

### Narrative Layering Principle

> Thêm 2026-09-03 — quy tắc **trình bày**, áp dụng cho MỌI output phân tích hướng ra ngoài (dashboard, report, README) — không phải logic code, nhưng mọi hàm mới trong `src/analysis/` (Layer 2-9) được thiết kế để cắm vừa đúng 6 tầng này, không tầng nào được nhảy cóc lên trước tầng thấp hơn nó phụ thuộc.

Một câu chuyện thống kê tử tế không nhảy thẳng từ số thô sang kết luận — nó đi qua từng tầng, mỗi tầng trả lời 1 câu hỏi cụ thể hơn tầng trước:

1. **Số thô** (`views`/`likes`/`replies`/`reposts`/`quotes`) — "chuyện gì đã xảy ra".
2. **Rate đơn giản** (`engagement_rate`/`virality_index`/`conversation_rate`) — chuẩn hoá số thô theo `views` để so sánh được giữa các post khác quy mô.
3. **Central tendency + spread** (median, IQR — xem `engagement_by_hour`/`engagement_by_weekday` Layer 2) — 1 con số đại diện cho CẢ NHÓM, kèm độ phân tán, không phải 1 con số đơn lẻ đánh lừa (VD mean bị kéo lệch bởi 1 outlier viral).
4. **Vị trí trong phân phối kênh** (percentile — VD `channel_virality_p90` Layer 3) — post/giờ/nhóm này đứng đâu so với lịch sử CHÍNH kênh đó, không so với benchmark ngoài không liên quan.
5. **Suy diễn thống kê** (kiểm định + effect size + CI — `compare_groups()` Layer 4) — khác biệt quan sát được có đáng tin không, hay chỉ là nhiễu do mẫu nhỏ; effect size trả lời "khác biệt lớn tới đâu", CI trả lời "khoảng tin cậy tới đâu".
6. **Diễn giải bằng lời** — câu kết luận cuối cùng, PHẢI trích dẫn ngược lại số liệu ở tầng 1-5 (không được nói suông "giờ này tốt hơn" mà không kèm median/n/p-value đứng sau nó).

**Vì sao thứ tự này bắt buộc, không được đảo**: nhảy thẳng từ tầng 1/2 lên tầng 6 (VD "8h tối là giờ đăng tốt nhất" chỉ dựa trên mean của 2 bài) là đúng lỗi phương pháp luận đã sửa ở Layer 2 — case thực nghiệm median 412 vs mean 2.254 (gấp 5.5 lần, "best hour theo mean lại là worst theo median", nguồn `Hwemo-Chung/threads-analytics`, trích trong `docs/research/`) chứng minh tầng 3 (central tendency đúng loại) có thể đảo ngược hoàn toàn kết luận nếu bỏ qua. Tương tự, tầng 5 (suy diễn thống kê) là điều kiện để tầng 6 được phép dùng ngôn ngữ khẳng định ("A cao hơn B có ý nghĩa thống kê") thay vì chỉ mô tả ("A quan sát được cao hơn B") — thiếu tầng 5, tầng 6 chỉ được phép mô tả, không được phép khẳng định nhân quả/ý nghĩa thống kê.

**Áp dụng cụ thể cho từng layer bên dưới**: Layer 2 (median/IQR = tầng 3), Layer 3 `is_viral`/`channel_virality_p90` (tầng 4), Layer 4 `compare_groups()` (tầng 5, engine dùng chung cho mọi so sánh nhóm ở Layer 3/6/7), Layer 5 velocity (luôn hiện chuỗi snapshot thô — tầng 1 — trước khi hiện slope tính ra — tầng 2/3), Layer 6/7 reply analysis (tầng 1-2 thô, dùng `compare_groups()` khi cần tầng 5).

### Methodology log: hiệu chỉnh tham số HDBSCAN cho số lượng topic (thực nghiệm 2026-09-03)

> Viết ở dạng report — cùng mục đích với report methodology phía trên (nguồn cho trang "Methodology" công khai sau này). Ghi lại đầy đủ 3 cấu hình đã thử, số liệu, và lý do chọn cấu hình cuối — không chỉ công bố kết quả cuối cùng.

**Bối cảnh**: cấu hình mặc định ban đầu (`HDBSCAN_MIN_CLUSTER_SIZE=5`, `cluster_selection_method` mặc định `'eom'`, `UMAP_N_NEIGHBORS=15`, xem thực nghiệm phía trên) chỉ tách được **2 cluster** trên 135 content unit sạch — dù đã đổi không gian clustering (raw embedding → UMAP). Tác giả (chính người viết 141 bài, domain expert thật của kênh) đánh giá 2 là quá thô, ước tính kênh có khoảng **6-8 chủ đề chính, tối đa 12 nếu chia nhỏ**. Chẩn đoán: `eom` (Excess of Mass, mặc định `hdbscan`) thiên về gộp thành ít cluster lớn hơn `leaf`; `UMAP_N_NEIGHBORS=15` khá cao so với n=135, thiên về giữ cấu trúc toàn cục/thô thay vì cục bộ.

**Phương pháp**: sweep có hệ thống trên lưới `cluster_selection_method ∈ {eom, leaf}` × `min_cluster_size ∈ {3,4,5}` × `UMAP_N_NEIGHBORS ∈ {5,8,10,15}` (24 tổ hợp), chạy trong WSL2 (script tạm `src/pipeline/cluster_sweep.py`, xoá sau khi chốt). Với mỗi tổ hợp: số cluster, % noise, và **DBCV** (`hdbscan.relative_validity_` — density-based cluster validation, không cần nhãn ground-truth, đo mức chênh lệch mật độ trong-cluster vs ngoài-cluster). Kết quả `eom` xác nhận lại đúng như cấu hình mặc định: **luôn hội tụ về 2-3 cluster** ở mọi `min_cluster_size`/`n_neighbors`, DBCV cao (0.26–0.75) nhưng số cluster không đổi — xác nhận `eom` không phải tham số cần chỉnh, mà `cluster_selection_method` mới là đòn bẩy chính. Toàn bộ ứng viên khả thi (≥6 cluster) đều nằm ở `leaf`.

**3 ứng viên gần nhất với kỳ vọng domain, review trực tiếp nội dung từng cluster** (không chỉ nhìn số, in mẫu bài thật từng cluster — script tạm `src/pipeline/cluster_preview.py`, xoá sau khi chốt):

| Ứng viên | `n_neighbors` | `min_cluster_size` | Số cluster | Noise | DBCV |
|---|---|---|---|---|---|
| A | 10 | 5 | 7 | 33/135 (24.4%) | 0.089 |
| B | 10 | 4 | 8 | 46/135 (34.1%) | **0.205** |
| C | 15 | 3 | 12 | 47/135 (34.8%) | 0.083 |

- **A (7 cluster)**: đời sống/văn hoá Pháp-Việt chung, vui chơi cuối tuần, du học, review đồ ăn, đi chợ/giá cả, career/finance, alternance. Mạch lạc, ít noise nhất, nhưng gộp "học/lỗi tiếng Pháp" chung vào cluster đời sống chung — thiếu 1 chủ đề tác giả cho là tách biệt.
- **B (8 cluster)**: giống A nhưng tách thêm cluster "học/lỗi tiếng Pháp + văn hoá công sở Pháp" (rõ nét, khác hẳn cluster du học) và cluster "thuê nhà + đời sống thường ngày" (hơi lẫn 2 ý phụ, nhưng vẫn đọc được chủ đề chính). DBCV cao nhất trong cả 3 ứng viên — không chỉ nhiều cluster hơn A, mà mật độ trong-cluster/ngoài-cluster tách bạch rõ hơn cả.
- **C (12 cluster)**: tách quá tay — cluster "review đồ ăn" (A/B gộp 1) vỡ thành 3 mảnh chồng chéo (matcha/cà phê, so sánh Pháp-Việt, sản phẩm mỹ phẩm/retail), có 2 cluster chỉ n=3 (housing riêng, tư vấn du học riêng) — sát ngưỡng `min_cluster_size`, khó phân biệt với noise thật. DBCV **thấp nhất trong 3 ứng viên** (0.083, thấp hơn cả A) dù nhiều cluster nhất — bằng chứng định lượng cho thấy các cluster thêm vào không có mật độ/ranh giới rõ, nhiều khả năng là mảnh vỡ của cluster lớn hơn bị ép tách bởi `min_cluster_size` quá nhỏ so với n=135, không phải chủ đề thật riêng biệt.

**Kết luận methodology**: **B** là lựa chọn cân bằng nhất theo cả 2 tiêu chí — định lượng (DBCV cao nhất, tốt hơn cả A) và định tính (nội dung từng cluster đọc mạch lạc, khớp với 8 chủ đề tác giả tự ước tính là "6-8 chủ đề chính"). C tuy đúng số lượng tối đa tác giả kỳ vọng (12) nhưng bằng chứng (DBCV thấp nhất + nội dung cluster chồng chéo/vỡ vụn) cho thấy đây là over-fitting tham số trên tập dữ liệu nhỏ (n=135), không phải cấu trúc chủ đề thật — minh hoạ đúng nguyên tắc "domain expectation là giả thuyết cần đối chiếu bằng chứng, không phải câu trả lời đúng sẵn". **Chốt**: `HDBSCAN_MIN_CLUSTER_SIZE=4`, `cluster_selection_method="leaf"`, `UMAP_N_NEIGHBORS=10`.

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
