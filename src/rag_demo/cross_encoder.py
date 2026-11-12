"""Cross-encoder rerank của demo RAG (ADR-0037 D9): phần chạy trên Windows.

Model `BAAI/bge-reranker-v2-m3` cần torch nên chỉ chạy trong WSL2 (`cross_encoder_wsl.py`). Hai bên
nói chuyện qua 2 file JSON trong `data/rag_demo/` (gitignored, chứa chữ bài thật), theo khuôn của
bước gom cụm (`src/pipeline/clustering_export.py` → `cluster_wsl.py` → `clustering_import.py`):

1. Windows ghi `cross_encoder_pairs.json`: mọi cặp câu hỏi gốc × chữ chunk khác nhau, cùng mã cặp
   với LLM rerank (`rerank_id`) để bước đóng file demo ghép hai cách chấm theo một khoá.
2. WSL2 chấm, ghi `cross_encoder_scores.json` kèm digest của file cặp, phiên bản model và độ dài.
3. Windows đọc lại bằng `read_scores`: từ chối kết quả của một file cặp khác, thiếu cặp, thừa cặp,
   hoặc điểm không hữu hạn.

Chấm trên chữ gốc của chunk, không kèm câu ngữ cảnh (ADR-0039 D2), và trên câu hỏi gốc, giống LLM
rerank. Module này chỉ dùng thư viện chuẩn (+ các module demo khác), để WSL2 import được.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.rag_demo.chunking import Chunk
from src.rag_demo.llm_jobs import rerank_id
from src.rag_demo.questions import Question

CROSS_ENCODER_MODEL = "BAAI/bge-reranker-v2-m3"
# Commit trên Hugging Face, tải 2026-11-08: chạy lại phải ra cùng trọng số
CROSS_ENCODER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
# Độ dài tối đa của một cặp (câu hỏi + chunk + token đặc biệt), Thy chốt 2026-11-08 (phương án A):
# - Số đo 2026-11-08 trên 4.700 cặp: dài nhất 790 token, trung vị 120, p95 260; 50 cặp (1,1%) vượt
#   512, cả 50 thuộc 5 chunk của cách "không chia", 4 trong 5 là bài đáp án (câu 2, 4, 7, 8). Đáp án
#   câu 8 nằm ở ký tự 1141–1363 của bài dài 2625 ký tự.
# - 512 (mặc định FlagEmbedding, ví dụ model card) cắt đuôi đúng các bài đó: cách "không chia" sẽ
#   thua vì bị cắt chứ không vì cách chia, làm lệch phép so sánh 7 cách chia mà trang muốn cho thấy.
# - 1024 không cắt cặp nào; model có 8194 vị trí (`max_position_embeddings`), và ví dụ chấm điểm của
#   FlagEmbedding cho chính model này dùng `--reranker_max_length 1024`
#   (github.com/FlagOpen/FlagEmbedding, examples/finetune/reranker/README.md).
# - Giới hạn đã biết: tài liệu không nói model được fine-tune trên cặp dài bao nhiêu (ví dụ
#   fine-tune dùng passage_max_len 512), nên điểm của 5 chunk dài có thể kém tin cậy hơn; trang
#   ghi rõ.
# Bước WSL2 dừng nếu có cặp nào vượt mức này, không bao giờ cắt ngầm.
CROSS_ENCODER_MAX_LENGTH = 1024
PAIRS_PATH = Path("data/rag_demo/cross_encoder_pairs.json")
SCORES_PATH = Path("data/rag_demo/cross_encoder_scores.json")


class CrossEncoderResultError(ValueError):
    """File điểm từ WSL2 không khớp file cặp hiện tại."""


@dataclass(frozen=True)
class Pair:
    id: str
    question: str
    passage: str


def cross_encoder_pairs(questions: Sequence[Question], chunks: Sequence[Chunk]) -> list[Pair]:
    """Mọi cặp câu hỏi gốc × chữ chunk khác nhau.

    Chunk trùng chữ giữa các cách chia chỉ chấm một lần."""
    texts = list(dict.fromkeys(chunk.text for chunk in chunks))
    return [Pair(rerank_id(q, text), q.text, text) for q in questions for text in texts]


def pairs_bytes(pairs: Sequence[Pair]) -> bytes:
    """Đúng các byte của file cặp: ghi file và kiểm file cũ dùng chung một cách dựng."""
    if len({pair.id for pair in pairs}) != len(pairs):
        raise ValueError("mã cặp trùng nhau")
    payload = {
        "model": CROSS_ENCODER_MODEL,
        "revision": CROSS_ENCODER_REVISION,
        "pairs": [{"id": p.id, "question": p.question, "passage": p.passage} for p in pairs],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def write_pairs(pairs: Sequence[Pair], path: Path = PAIRS_PATH) -> str:
    """Ghi file cặp cho WSL2; trả sha256 của đúng các byte đã ghi."""
    data = pairs_bytes(pairs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def pairs_file_is_current(pairs: Sequence[Pair], path: Path = PAIRS_PATH) -> bool:
    """File cặp trên đĩa có đúng là file mà code hiện tại sẽ ghi không.

    `read_scores` chỉ chứng minh file điểm khớp file cặp; hàm này chứng minh file cặp vẫn khớp chunk
    và câu hỏi của code hiện tại (VD sửa cách chia sau khi chấm thì điểm cũ không còn dùng được)."""
    return path.read_bytes() == pairs_bytes(pairs)


def read_scores(pairs_path: Path = PAIRS_PATH, scores_path: Path = SCORES_PATH) -> dict[str, float]:
    """Điểm thô (logit) theo mã cặp, sau khi kiểm file điểm khớp file cặp hiện tại."""
    return parse_scores(pairs_path.read_bytes(), scores_path.read_bytes())


def parse_scores(pairs_data: bytes, scores_data: bytes) -> dict[str, float]:
    """Như `read_scores` nhưng từ byte đã đọc (băm được đúng các byte đã dùng)."""
    digest = hashlib.sha256(pairs_data).hexdigest()
    pair_ids = {pair["id"] for pair in json.loads(pairs_data)["pairs"]}
    result = json.loads(scores_data)
    # file sửa tay / bị cắt có thể là JSON hợp lệ nhưng sai dạng: báo lỗi, không traceback
    if not isinstance(result, dict) or not isinstance(result.get("scores"), dict):
        raise CrossEncoderResultError("file điểm không phải object có 'scores' dạng object")
    if result.get("pairs_digest") != digest:
        raise CrossEncoderResultError("file điểm thuộc một file cặp khác — chạy lại bước WSL2")
    for key, expected in (
        ("model", CROSS_ENCODER_MODEL),
        ("revision", CROSS_ENCODER_REVISION),
        ("max_length", CROSS_ENCODER_MAX_LENGTH),
    ):
        if result.get(key) != expected:
            raise CrossEncoderResultError(f"{key} = {result.get(key)!r}, cần {expected!r}")
    scores: dict[str, float] = result["scores"]
    longest = result.get("longest_pair_tokens")
    if isinstance(longest, bool) or not isinstance(longest, int):
        raise CrossEncoderResultError(
            "thiếu độ dài cặp dài nhất — không chứng minh được là không cắt chữ"
        )
    if longest > CROSS_ENCODER_MAX_LENGTH:
        raise CrossEncoderResultError("có cặp dài hơn độ dài tối đa — điểm đã bị cắt chữ")
    if set(scores) != pair_ids:
        missing, extra = len(pair_ids - set(scores)), len(set(scores) - pair_ids)
        raise CrossEncoderResultError(f"thiếu {missing} cặp, thừa {extra} cặp")
    for pair_id, score in scores.items():
        if (
            isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(score)
        ):
            raise CrossEncoderResultError(f"{pair_id}: điểm không hữu hạn {score!r}")
    return {pair_id: float(score) for pair_id, score in scores.items()}


def sigmoid(logit: float) -> float:
    """Đưa logit về [0, 1] như model card (`normalize=True`); thứ hạng không đổi, chỉ dễ đọc hơn."""
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    z = math.exp(logit)
    return z / (1.0 + z)
