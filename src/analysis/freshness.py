from __future__ import annotations


def freshness_weight(
    age_hours: float,
    *,
    grace_hours: float = 12.0,  # hypothesis ban đầu — CHƯA calibrate
    half_life_hours: float = 48.0,  # hypothesis ban đầu — CHƯA calibrate
) -> float:
    """Trọng số "đang hot NGAY BÂY GIỜ" — tách hẳn khỏi `virality_index` (xem
    docs/claude/data-model.md "Metric Architecture" mục "Freshness").

    CHỈ dùng khi hỏi "bài nào đang hot ngay bây giờ" — KHÔNG nhân vào
    `virality_index`/báo cáo trend theo tuần/tháng: 1 post đăng 20 ngày trước vẫn
    có thể là bài viral nhất quý, nhân recency vào sẽ xoá sổ sai semantic (trộn
    intrinsic performance với 1 explanatory variable, đúng lỗi phương pháp luận
    đã sửa ở `virality_index` v1 — xem decisions log trong architecture.md).

    `grace_hours=12`/`half_life_hours=48` là hypothesis dựa trên quan sát cá nhân
    tác giả (audience VN thức dậy trễ hơn giờ đăng ở Pháp) — CHƯA calibrate bằng
    dữ liệu thật khi đủ snapshot tích luỹ. Confounding factor cần nhớ: low
    engagement trong vài giờ đầu có thể do audience VN đang ngủ (giờ Pháp buổi
    tối), KHÔNG đồng nghĩa content dở — đây là lý do velocity/momentum (V2) quan
    trọng hơn recency đơn thuần khi so sánh 2 post cùng age nhưng khác tốc độ.
    """
    age_hours = max(age_hours, 0.0)
    if age_hours <= grace_hours:
        return 1.0
    # float(...): mypy strict infers `Any` from `float ** float` (typeshed's
    # __pow__ overloads allow a complex result for some operand combinations).
    return float(0.5 ** ((age_hours - grace_hours) / half_life_hours))
