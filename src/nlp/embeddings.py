"""Embedding đa ngôn ngữ cho `ContentUnit.full_text` bằng `sentence-transformers`.

Luôn chạy trên MỌI post — KHÔNG có bước "chọn model theo ngôn ngữ" (nguyên tắc 1,
xem `src/nlp/language.py` + docs/claude/data-model.md "3 nguyên tắc từ paper..."):
`language.py` và `embed_texts()` là 2 nhánh ĐỘC LẬP, không nhánh nào gate nhánh kia.

Thử `BAAI/bge-m3` trước; nếu tải/load model lỗi hoặc quá chậm, fallback
`intfloat/multilingual-e5-large` — `load_embedding_model()` trả kèm tên model
THẬT đang dùng để ghi rõ trong report/log, không giấu việc đã fallback.

QUAN TRỌNG (2026-09-02): môi trường Windows chạy agent này chặn `scipy.linalg.
_flapack` bằng Smart App Control (Windows 11 Home — KHÔNG có UI allowlist cho
user thường, khác WDAC/AppLocker, xem docs/claude/architecture.md decision log
2026-09-02) — `sentence-transformers` phụ thuộc `scikit-learn`→`scipy` ở tầng
import. Đã verify hành vi KHÔNG ổn định: chạy được thật 1 lần (2026-09-01, tải
bge-m3 thành công), rồi bị chặn LẠI ngay hôm sau (2026-09-02) không có thay đổi
gì ở code/dependency — kết luận: đây là hành vi flaky (khả năng do reputation
check bất đồng bộ của Smart App Control), KHÔNG PHẢI đã fix ổn định. Vì vậy
pipeline thật KHÔNG gọi `embed_texts()` trên Windows nữa — chuyển hẳn sang WSL2
(xem `src/pipeline/cluster_wsl.py`). Hàm này vẫn giữ nguyên (đúng thiết kế,
dùng lại y hệt trong WSL do Linux không bị Smart App Control chi phối), chỉ
không còn được gọi từ code path chạy trên Windows.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from sentence_transformers import SentenceTransformer

PRIMARY_MODEL_NAME = "BAAI/bge-m3"
FALLBACK_MODEL_NAME = "intfloat/multilingual-e5-large"


@lru_cache(maxsize=1)
def load_embedding_model() -> tuple[SentenceTransformer, str]:
    """Thử PRIMARY_MODEL_NAME trước; fallback FALLBACK_MODEL_NAME nếu lỗi (network,
    OOM, hoặc quá chậm). Cache theo tiến trình (lru_cache) — model transformer chỉ
    load 1 lần, tái dùng cho mọi lệnh gọi `embed_texts()` tiếp theo."""
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(PRIMARY_MODEL_NAME), PRIMARY_MODEL_NAME
    except Exception:  # noqa: BLE001 — fallback có chủ đích khi model chính lỗi/quá chậm
        return SentenceTransformer(FALLBACK_MODEL_NAME), FALLBACK_MODEL_NAME


def embed_texts(texts: list[str]) -> tuple[np.ndarray, str]:
    """Trả (embeddings, model_name_thật_đang_dùng). Chạy trên `ContentUnit.full_text`
    — KHÔNG chạy trên `normalized_text` (giữ đúng ngữ liệu gốc nhất có thể, xem
    nguyên tắc 2 tại data-model.md)."""
    model, model_name = load_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    import numpy as np

    return np.asarray(embeddings), model_name
