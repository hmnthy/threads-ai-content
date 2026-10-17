from __future__ import annotations

import logging
from datetime import date as date_cls
from datetime import timedelta
from typing import Any, Final

import httpx

from src.api.cache import Cache
from src.api.client import ThreadsAPIError, ThreadsClient
from src.api.models import AccountInsights, DailyViewPoint, PostInsights, ThreadsPost, UserInfo

# Job chạy định kỳ trỏ stderr vào file log (`job_log.redirect_output`), nên cảnh báo ở đây
# vào `data/logs/scheduled_job.log` cùng kết quả job.
logger = logging.getLogger(__name__)

USER_FIELDS: Final = "id,username"
POST_FIELDS: Final = (
    "id,text,timestamp,media_type,permalink,shortcode,username,"
    "media_url,thumbnail_url,is_quote_post,quoted_post,reposted_post,children,"
    # Thread reconstruction fields — verify live 2026-08-30, xem docs/claude/data-model.md
    "root_post,replied_to,is_reply,is_reply_owned_by_me,has_replies,is_spoiler_media,"
    # Context field mở rộng — schema nullable, chưa dùng trong scoring (xem models.py)
    "text_attachment,is_ghost_post,poll_attachment,gif_attachment,location_id,"
    "enable_reply_approvals"
)
POST_INSIGHTS_METRICS: Final = "views,likes,replies,reposts,quotes"
# follower_demographics is deliberately excluded: confirmed live (2026-08-28) that Threads
# rejects it unless called separately with an explicit `breakdown` param — see
# get_follower_demographics() below.
ACCOUNT_INSIGHTS_METRICS: Final = "views,likes,replies,reposts,quotes,clicks,followers_count"
FOLLOWER_DEMOGRAPHICS_BREAKDOWNS: Final = ("country", "city", "age", "gender")


async def get_user_info(client: ThreadsClient, user_id: str) -> UserInfo:
    data = await client.get(f"/{user_id}", params={"fields": USER_FIELDS})
    return UserInfo.model_validate(data)


# Cỡ trang mặc định của Meta — verify live 2026-10-17: `/threads` và `/replies` trả 25
# item/trang khi không truyền `limit`. Truyền tường minh để biết đang thu nhỏ từ đâu.
PAGE_SIZE: Final = 25

# Field dạng edge lồng mà Meta có thể không mở được khi trả danh sách, dù gọi riêng từng
# bài thì được. Verify live 2026-10-17: bài `CAROUSEL_ALBUM` 17981465366835957 (2025-06-08) có 1
# ảnh con hỏng phía Meta (`GET /18069979258807415?fields=id` → HTTP 500 code 1). Danh sách
# mở `children` của bài này lỗi 500, kể cả trang 1 bài (lúc lỗi lúc qua); bỏ `children`
# thì qua. `GET /{id}?fields=children` của chính bài trả 2/3 ảnh con — Meta lặng lẽ bỏ ảnh
# hỏng. 61 bài gốc `CAROUSEL_ALBUM` còn lại: gọi riêng khớp 100% `children` đã lưu.
PER_ITEM_FALLBACK_FIELDS: Final = ("children",)


# Tham số của URL `paging.next` mà `_paginate` hiểu (đo live 2026-10-17: Meta trả đúng 4
# key này). Có key khác (VD Meta đổi sang phân trang theo thời gian) → dừng hẳn, không lặng
# lẽ gọi thiếu tham số.
KNOWN_NEXT_PARAMS: Final = frozenset({"access_token", "fields", "limit", "after"})


async def _paginate(client: ThreadsClient, path: str, fields: str) -> list[dict[str, Any]]:
    """Đi hết phân trang cursor (`paging.next`) để lấy toàn bộ lịch sử kênh, không chỉ
    trang đầu. Mỗi trang gọi lại `path` với cursor `after` lấy từ `paging.next` (không
    gọi thẳng URL `next`), để khi Meta lỗi có thể thử lại đúng vị trí đó với trang nhỏ hơn
    (`_fetch_page`). Guard tiến triển: cursor lặp lại → dừng hẳn (vòng lặp retry/fallback
    sai cursor sẽ quay về chỗ cũ mãi thay vì kết thúc). Bài trùng id chỉ bỏ qua + cảnh báo,
    không dừng: trước đây trùng là vô hại (`upsert_post` ghi đè cùng dòng), và có thể xảy ra
    thật nếu cursor của Meta tính theo vị trí mà Thy đăng bài lúc job đang phân trang —
    chưa verify live cursor theo item hay theo vị trí."""
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()
    retried: list[Exception] = []
    duplicates = 0
    after: str | None = None
    try:
        while True:
            page = await _fetch_page(client, path, fields, after, retried)
            for item in page.get("data", []):
                if item["id"] in seen_ids:
                    duplicates += 1
                    continue
                seen_ids.add(item["id"])
                items.append(item)
            next_url = page.get("paging", {}).get("next")
            if not next_url:
                return items
            after = _next_cursor(path, next_url)
            if after in seen_cursors:
                raise ValueError(f"{path}: paging.next repeats an earlier cursor")
            seen_cursors.add(after)
    finally:
        if duplicates:
            logger.warning("%s: skipped %d posts returned twice while paging", path, duplicates)
        if retried:
            # 1 dòng tóm tắt mỗi edge thay vì 1 dòng mỗi lần lỗi (~20 lần/lượt khi đo
            # live) — đủ để theo dõi Meta có tệ dần không mà không làm ngập log. Ở `finally`
            # để vẫn ghi khi edge cuối cùng thất bại (log có ngữ cảnh "trước đó N lần lỗi").
            logger.warning(
                "%s: retried %d server errors with smaller pages (last: %s)",
                path,
                len(retried),
                _describe(retried[-1]),
            )


def _describe(error: Exception) -> str:
    """Tên loại lỗi + thông điệp: `str(httpx.ReadTimeout(...))` có thể rỗng, log chỉ còn
    "last: )" nếu không ghi kèm tên loại."""
    return f"{type(error).__name__}: {error}"


def _next_cursor(path: str, next_url: str) -> str:
    params = httpx.URL(next_url).params
    unknown = set(params.keys()) - KNOWN_NEXT_PARAMS
    if unknown:
        raise ValueError(f"{path}: paging.next has unexpected params {sorted(unknown)}")
    after: str | None = params.get("after")
    if not after:
        # Không có cursor thì không đi tiếp được — dừng hẳn thay vì lặp lại trang cũ
        raise ValueError(f"{path}: paging.next has no `after` cursor")
    return after


async def _fetch_page(
    client: ThreadsClient,
    path: str,
    fields: str,
    after: str | None,
    retried: list[Exception],
) -> dict[str, Any]:
    """Lấy 1 trang bắt đầu sau cursor `after`, chịu được lỗi 5xx phía Meta.

    Verify live 2026-10-17 (job snapshot lỗi 16/17 lần 13→17/10): Meta trả HTTP 500
    "An unknown error has occurred." (code 1) ở các trang chứa bài cũ nhất, và cùng vị trí
    đó lại qua khi xin ít bài hơn — lỗi phụ thuộc số bài × số field trong 1 lần gọi, không
    phải token hay quyền. Nên khi gặp 5xx: chia đôi `limit` (25 → 12 → 6 → 3 → 1) và gọi
    lại đúng cursor đó — cùng cursor + `limit` nhỏ hơn trả phần đầu của trang đó (live
    2026-10-17: không trùng/sót bài; guard ở `_paginate` phòng trường hợp khác). Hết thời gian chờ
    (timeout) xử lý như 5xx — cùng nguyên nhân "trang quá nặng". Lỗi 4xx (token, tham số
    sai, rate limit) ném ra ngay — thử lại không chữa được. Mỗi lỗi đã vượt qua được thêm
    vào `retried` để `_paginate` ghi 1 dòng tóm tắt.
    """
    limit = PAGE_SIZE
    while True:
        params: dict[str, Any] = {"fields": fields, "limit": limit}
        if after:
            params["after"] = after
        try:
            return await client.get(path, params=params)
        except (ThreadsAPIError, httpx.TimeoutException) as error:
            if isinstance(error, ThreadsAPIError) and error.status_code < 500:
                raise
            if limit == 1:
                return await _fetch_single_item_page(client, path, fields, after, error)
            retried.append(error)
            limit //= 2


async def _fetch_single_item_page(
    client: ThreadsClient,
    path: str,
    fields: str,
    after: str | None,
    error: Exception,
) -> dict[str, Any]:
    """Trang 1 bài vẫn lỗi 5xx/timeout: lấy bài đó không kèm `PER_ITEM_FALLBACK_FIELDS`, rồi gọi
    riêng bài để lấy các field đó và ghép lại — `raw_json` lưu nguyên bài nên cố giữ
    `children` (121 bài `CAROUSEL_ALBUM` trong DB đều có, đếm 2026-10-17).

    Gọi riêng cũng lỗi ngẫu nhiên với bài có ảnh con hỏng (verify live 2026-10-17: 3 lần
    qua, 1 lần 500), và khi qua thì thiếu ảnh hỏng. Khi đó vẫn giữ bài, chỉ thiếu các field
    này: field fallback không dùng trong phân tích, còn để job chết vì 1 ảnh con hỏng là
    mất snapshot của mọi bài (13→17/10). Log ghi số ảnh con lấy được để thấy khi `raw_json`
    đổi (bài đó dao động 3 / 2 / 0 ảnh con giữa các lượt — `data-model.md`). Không có
    field nào để bỏ, hoặc trang đã bỏ field vẫn lỗi → ném lỗi (job dừng, log ghi vị trí)
    thay vì lặng lẽ bỏ sót bài."""
    requested = fields.split(",")
    dropped = [name for name in requested if name in PER_ITEM_FALLBACK_FIELDS]
    if not dropped:
        raise error
    reduced = ",".join(name for name in requested if name not in PER_ITEM_FALLBACK_FIELDS)
    params: dict[str, Any] = {"fields": reduced, "limit": 1}
    if after:
        params["after"] = after
    page = await client.get(path, params=params)
    for item in page.get("data", []):
        try:
            extra = await client.get(f"/{item['id']}", params={"fields": ",".join(dropped)})
            outcome = f"{len(extra.get('children', {}).get('data', []))} children"
        except (ThreadsAPIError, httpx.TimeoutException) as own_error:
            if isinstance(own_error, ThreadsAPIError) and own_error.status_code < 500:
                raise
            extra = {}
            outcome = f"failed too ({_describe(own_error)}), kept without {','.join(dropped)}"
        item.update({name: extra[name] for name in dropped if name in extra})
        logger.warning(
            "%s: post %s fetched without %s on the list (%s), then on its own: %s",
            path,
            item["id"],
            ",".join(dropped),
            _describe(error),
            outcome,
        )
    return page


async def get_posts(
    client: ThreadsClient, user_id: str, cache: Cache | None = None
) -> list[ThreadsPost]:
    """Fetch every post for user_id across the account's full history (paginated),
    serving from cache when available and fresh."""
    cache_key = f"posts_{user_id}"
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return [ThreadsPost.model_validate(item) for item in cached]

    raw_posts = await _paginate(client, f"/{user_id}/threads", POST_FIELDS)
    posts = [ThreadsPost.model_validate(item) for item in raw_posts]

    if cache is not None:
        cache.set(cache_key, [post.model_dump(mode="json") for post in posts])
    return posts


async def get_replies(
    client: ThreadsClient, user_id: str, cache: Cache | None = None
) -> list[ThreadsPost]:
    """Fetch every reply user_id has posted across the account's full history
    (paginated), serving from cache when available and fresh.

    NOTE: reuses POST_FIELDS and the ThreadsPost shape as a starting assumption —
    the real `/replies` response has NOT been verified live yet (unlike `/threads`
    and `/threads_insights`, see docs/claude/data-model.md). Verify against a real
    account before relying on this for analysis.
    """
    cache_key = f"replies_{user_id}"
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return [ThreadsPost.model_validate(item) for item in cached]

    raw_replies = await _paginate(client, f"/{user_id}/replies", POST_FIELDS)
    replies = [ThreadsPost.model_validate(item) for item in raw_replies]

    if cache is not None:
        cache.set(cache_key, [reply.model_dump(mode="json") for reply in replies])
    return replies


async def get_post_insights(client: ThreadsClient, post_id: str) -> PostInsights:
    data = await client.get(f"/{post_id}/insights", params={"metric": POST_INSIGHTS_METRICS})
    metrics = _flatten_insights(data)
    return PostInsights(post_id=post_id, **metrics)


async def get_account_insights(client: ThreadsClient, user_id: str) -> AccountInsights:
    data = await client.get(
        f"/{user_id}/threads_insights", params={"metric": ACCOUNT_INSIGHTS_METRICS}
    )
    metrics = _flatten_insights(data)
    return AccountInsights(**metrics)


# Verify live 2026-09-03 (`since` further back than this errors: "since param is
# not valid. Metrics data is available for the last 2 years"). Days before the
# channel existed just come back with value=0, no gaps — so a `since` this far
# back is always safe, it never raises for being "too early" in the other direction.
DAILY_VIEWS_LOOKBACK_CAP_DAYS: Final = 729


async def get_account_daily_views(
    client: ThreadsClient, user_id: str, since: date_cls, until: date_cls
) -> list[DailyViewPoint]:
    """Account-level `views`, `period="day"` — KHÔNG sum qua `_flatten_insights`
    như `get_account_insights` (hàm đó cộng dồn thành 1 tổng, mất breakdown theo
    ngày). Giữ nguyên từng điểm — dùng cho biểu đồ Timeline Brush (Overview mới),
    KHÁC hẳn `insights_snapshots` (lifetime cumulative theo 1 post cụ thể)."""
    data = await client.get(
        f"/{user_id}/threads_insights",
        params={
            "metric": "views",
            "period": "day",
            "since": since.isoformat(),
            "until": until.isoformat(),
        },
    )
    raw_values = data.get("data", [{}])[0].get("values", [])
    points: list[DailyViewPoint] = []
    for item in raw_values:
        end_time = item["end_time"]  # "YYYY-MM-DDTHH:MM:SS+0000", luôn "07:00:00"
        end_date = date_cls.fromisoformat(end_time[:10])
        # "D 07:00 UTC" = "D 00:00" giờ Pacific (UTC-7) — mốc KẾT THÚC ngày lịch
        # Pacific (D-1), nên bucket này đại diện ngày (D-1), không phải ngày D.
        # Chỉ áp dụng quy đổi khi khớp đúng giả định đã verify (07:00 UTC); nếu
        # Meta đổi giờ boundary trong tương lai, giữ nguyên end_date thay vì đoán.
        bucket_date = end_date - timedelta(days=1) if end_time[11:13] == "07" else end_date
        points.append(DailyViewPoint(date=bucket_date.isoformat(), views=item["value"]))
    return points


async def get_follower_demographics(
    client: ThreadsClient, user_id: str, breakdown: str = "country"
) -> dict[str, Any]:
    """follower_demographics requires an explicit breakdown; confirmed live 2026-08-28
    that Meta rejects the metric entirely without one (error_subcode 4279040)."""
    if breakdown not in FOLLOWER_DEMOGRAPHICS_BREAKDOWNS:
        raise ValueError(f"breakdown must be one of {FOLLOWER_DEMOGRAPHICS_BREAKDOWNS}")
    data = await client.get(
        f"/{user_id}/threads_insights",
        params={"metric": "follower_demographics", "breakdown": breakdown},
    )
    metrics = _flatten_insights(data)
    result: dict[str, Any] = metrics.get("follower_demographics", {})
    return result


def _flatten_insights(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten the Graph Insights response shape into {metric_name: value}.

    Confirmed live against the real API (2026-08-28) that the shape is NOT uniform
    across metrics:
    - post-level metrics (period="lifetime"): `values: [{"value": N}]`, one entry
    - account-level "views" (period="day"): `values: [{"value": N}, ...]`, one entry
      per day in the queried window — summed here to get a period total
    - account-level likes/replies/reposts/quotes/followers_count: `total_value: {"value": N}`
    - "clicks": `link_total_values: [{"value": N, "link_url": ...}, ...]` — summed
    - "follower_demographics" (only when called with a `breakdown`): `total_value`
      is a breakdown dict with no "value" key, kept as-is
    """
    metrics: dict[str, Any] = {}
    for item in data.get("data", []):
        name = item["name"]
        if "total_value" in item:
            total_value = item["total_value"]
            metrics[name] = total_value.get("value", total_value)
        elif "link_total_values" in item:
            metrics[name] = sum(v["value"] for v in item["link_total_values"])
        elif "values" in item:
            metrics[name] = sum(v["value"] for v in item["values"])
    return metrics
