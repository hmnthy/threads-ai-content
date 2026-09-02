"""Bước 1/3 của clustering pipeline — chạy trên Windows. Ghi `language_primary`/
`language_mix_score` vào `content_units` (Bước 3 — `lingua-language-detector`
KHÔNG phụ thuộc scipy, chạy ổn định trên Windows) và xuất `(id, full_text)` của
content unit ra `data/nlp_exchange/texts_export.json` để `src/pipeline/
cluster_wsl.py` đọc vào.

QUAN TRỌNG #1 (2026-09-02) — vì sao embedding KHÔNG chạy ở đây: dù `src/nlp/
embeddings.py` viết đúng thiết kế, verify lại hôm nay cho thấy `scipy.linalg.
_flapack` bị Smart App Control chặn LẠI (đã từng chạy được hôm 2026-09-01, giờ
block lại) — tức là lần "tự hết" hôm qua chỉ là may rủi (reputation check không
ổn định), KHÔNG phải đã sửa dứt điểm. Toàn bộ phần ML thật (embedding + UMAP +
HDBSCAN) chuyển hẳn sang chạy trong WSL2 (xem `src/pipeline/cluster_wsl.py`) —
môi trường Linux không nằm trong phạm vi kiểm soát của Smart App Control, ổn
định hơn là dựa vào Windows "có lúc chặn có lúc không". Xem docs/claude/
architecture.md decision log 2026-09-02.

QUAN TRỌNG #2 (2026-09-02) — vì sao lọc `full_text` rỗng: content unit có
`full_text` rỗng (whitespace-only) bị LOẠI KHỎI export cluster — verify thật cho
thấy toàn bộ 6/141 trường hợp này là `REPOST_FACADE` (tác giả repost bài người
khác, không thêm caption riêng — Threads lưu dạng "vỏ" không có `text` lẫn
`text_attachment`). Lọc theo tiêu chí "full_text rỗng" (không hardcode
`media_type == REPOST_FACADE`) vì đúng bản chất vấn đề là "không có text để
embed" — tổng quát hơn, vẫn đúng nếu sau này phát sinh loại post khác cũng rỗng
text. Không lọc, HDBSCAN sẽ gom các post này thành 1 "cluster" giả (embedding
của chuỗi rỗng gần giống hệt nhau) — không phải chủ đề thật, làm méo kết quả.
Language detection (`detect_language_info`) vẫn chạy trên MỌI content unit kể cả
unit bị loại khỏi export — hàm đã tự xử lý đúng chuỗi rỗng (trả về
`primary_language=None`), không cần lọc riêng; các unit này vẫn có
`language_primary`/`language_mix_score` trong DB, chỉ không có `umap_x/y/z`/
topic (không được cluster).

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.clustering_export`
"""

from __future__ import annotations

import json
from pathlib import Path

from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    list_content_units,
    update_content_unit_language,
)
from src.nlp.language import detect_language_info

EXPORT_PATH = Path("data/nlp_exchange/texts_export.json")


def run_export(db_path: Path = DEFAULT_DB_PATH) -> dict[str, int | str]:
    conn = connect(db_path)
    rows = list_content_units(conn)

    for row in rows:
        info = detect_language_info(row["full_text"])
        update_content_unit_language(
            conn,
            row["id"],
            primary_language=info.primary_language,
            mix_score=info.language_mix_score,
        )
    conn.commit()
    conn.close()

    clusterable = [row for row in rows if (row["full_text"] or "").strip()]
    n_excluded = len(rows) - len(clusterable)
    ids = [row["id"] for row in clusterable]
    texts = [row["full_text"] for row in clusterable]

    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump({"ids": ids, "texts": texts}, f)

    return {
        "content_units_total": len(rows),
        "content_units_exported": len(ids),
        "excluded_empty_full_text": n_excluded,
        "export_path": str(EXPORT_PATH),
    }


if __name__ == "__main__":
    result = run_export()
    print(result)
