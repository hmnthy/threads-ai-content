"""File demo định dạng 2 tổng hợp cho test engine demo RAG (ADR-0041).

Câu tự đặt, không dùng chữ của bài thật.
"""

from typing import Any

# Đúng 2 mục bản Python ghi (`src/rag_demo/demo_file.py` PENDING_PARTS)
PENDING = (
    "dense score of transformed questions",
    "dense score of chunks with their context sentence",
)
WAYS = ["whole", "post", "fixed_300", "fixed_500", "fixed_800", "recursive_500", "semantic"]


def make_demo(
    texts: list[str],
    *,
    contexts: list[str | None] | None = None,
    dense: list[float] | None = None,
    question: str = "câu hỏi",
    transforms: dict[str, Any] | None = None,
    **changes: Any,
) -> dict[str, Any]:
    """File demo định dạng 2 tối thiểu: mỗi cách chia có cùng các chunk, chunk i = passage i, mọi
    chunk thuộc bài "u1" (một post, chữ 20 ký tự); câu hỏi không có đáp án (luật "none")."""
    n = len(texts)
    contexts = contexts if contexts is not None else [None] * n
    chunks = [{"id": i, "unit": "u1", "start": 0, "end": 1, "passage": i} for i in range(n)]
    base_transforms: dict[str, Any] = {
        "rewrite": question,
        "expand": question,
        "hyde": question,
        "multi_query": [question],
        "decompose": [question],
        "step_back": question,
    }
    base_transforms.update(transforms or {})
    for key in list(base_transforms):
        base_transforms[f"{key}_en"] = base_transforms[key]
    demo: dict[str, Any] = {
        "format": 2,
        "provenance": {
            "score_decimals": 6,
            "pending": list(PENDING),
            "llm_keep_min_score": 2,
            "topics": {"cluster_run_id": 1, "cluster_run_at": "2026-11-10T00:00:00+00:00"},
        },
        "units": [
            {
                "id": "u1",
                "text": "x" * 20,
                "sha256": "",
                "month": "2026-10",
                "topic": {"id": None, "label_en": "Unclustered"},
                "posts": [{"id": "p1", "start": 0, "end": 20}],
            }
        ],
        "passages": [
            {"unit": "u1", "text": t, "en": t, "context": c, "context_en": c}
            for t, c in zip(texts, contexts, strict=True)
        ],
        "ways": {way: [dict(c) for c in chunks] for way in WAYS},
        "cosine": {way: [0.0] * (n * (n - 1) // 2) for way in WAYS},
        "questions": [
            {
                "number": 1,
                "text": question,
                "english": question,
                "rule": "none",
                "gold_unit_ids": [],
                "gold_spans": {},
                "gold_chunks": {way: {} for way in WAYS},
                "transforms": base_transforms,
                "dense": dense if dense is not None else [0.0] * n,
                "cross_encoder": [0.0] * n,
                "llm": [{"score": 0, "quote": None, "quote_en": None, "quote_dropped": None}] * n,
            }
        ],
    }
    demo.update(changes)
    return demo
