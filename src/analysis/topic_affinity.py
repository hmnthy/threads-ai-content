"""Layer 7 — bằng chứng chiến lược reply chủ động của tác giả → virality. Tên
file đã được reference trong comment của `virality.py` từ trước (dành chỗ),
module thật viết ở đây (2026-09-03).

**"Author reply event"**: 1 post `is_reply_owned_by_me=True` mà KHÔNG thuộc
`continuations` của chính `ContentUnit` gốc — tức tác giả đang trả lời vào cuộc
trò chuyện của AUDIENCE (reply vào 1 audience reply, hoặc quay lại trả lời thêm
sau khi đã có audience tham gia), khác hẳn self-continuation (tác giả tự nối
tiếp nội dung của chính mình ngay từ đầu, đã gộp vào `full_text` của
`ContentUnit`, xem docs/claude/data-model.md mục "ContentUnit").
"""

from __future__ import annotations

from src.analysis.significance import ComparisonResult, compare_groups
from src.api.models import ThreadsPost
from src.models.content_unit import ContentUnit


def is_author_reply_event(post: ThreadsPost, root_content_unit: ContentUnit) -> bool:
    """True nếu `post.is_reply_owned_by_me=True` VÀ `post` không nằm trong
    `root_content_unit.continuations` — tác giả đang chủ động trả lời vào cuộc
    trò chuyện của audience, không phải tự nối tiếp nội dung của chính mình.
    """
    if not post.is_reply_owned_by_me:
        return False
    continuation_ids = {continuation.id for continuation in root_content_unit.continuations}
    return post.id not in continuation_ids


def compare_virality_with_without_author_reply(
    posts_with_reply: list[float], posts_without_reply: list[float]
) -> ComparisonResult:
    """So sánh virality_index (hoặc velocity — tuỳ metric người gọi truyền vào)
    của root-post CÓ author reply event trong 24h đầu (`post_maturity_window`,
    xem "Metric Architecture") vs KHÔNG có. TÁI SỬ DỤNG `compare_groups()`
    (`src/analysis/significance.py`) — không viết lại Mann-Whitney U/Cliff's
    delta/bootstrap CI ở đây.

    **CẢNH BÁO BẮT BUỘC ĐỌC TRƯỚC KHI DIỄN GIẢI KẾT QUẢ — correlation, not
    causation.** Ngay cả khi kết quả có ý nghĩa thống kê (p-value nhỏ, effect
    size lớn), KHÔNG được kết luận "tác giả reply nhiều hơn LÀM cho post viral
    hơn". Confound đã biết: chiều nhân quả nhiều khả năng NGƯỢC LẠI — 1 bài đang
    lên top (đã viral, nhiều audience reply) khiến tác giả CHỦ ĐỘNG reply nhiều
    hơn để tận dụng đà, không phải reply của tác giả là nguyên nhân khiến bài
    viral. Kết quả từ hàm này chỉ có giá trị mô tả tương quan quan sát được —
    dùng để đặt câu hỏi/hình thành giả thuyết cho nghiên cứu sâu hơn (VD thiết kế
    thực nghiệm A/B thật), không dùng để khẳng định chiến lược "reply nhiều hơn
    để viral hơn" đã được chứng minh.
    """
    return compare_groups(posts_with_reply, posts_without_reply)
