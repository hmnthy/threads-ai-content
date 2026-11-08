"""Embedding OpenAI cho demo RAG (ADR-0037 D6): chỉ ở bước dựng trên laptop, không trên Vercel.

Module không import `openai`: client được đưa từ ngoài vào (script dựng tạo client thật, test dùng
client giả), nên test không gọi mạng và không cần khoá. Vector lưu cache theo (model, sha256 của
chữ) trong file JSONL ở `data/` (gitignored, chứa vector của chữ bài) để chạy lại không trả tiền
lần hai.

Ước lượng chi phí trước khi gọi là **chặn trên**, không phải ước lượng giữa: tokenizer BPE theo
byte coi mỗi token là ít nhất 1 byte UTF-8, nên số token không vượt số byte. Số token thật lấy từ
`usage` của response sau khi gọi.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

EMBEDDING_MODEL = "text-embedding-3-small"  # ADR-0037 D6
# Đọc 2026-11-07 tại https://developers.openai.com/api/docs/models/text-embedding-3-small
PRICE_USD_PER_MILLION_TOKENS = 0.02
# Số chữ mỗi request. Lựa chọn thiết kế: một lô lỗi chỉ mất ít việc; tổng chỉ vài trăm chữ nên không
# cần tối ưu số request.
BATCH_SIZE = 128


class _EmbeddingItem(Protocol):
    @property
    def index(self) -> int: ...

    @property
    def embedding(self) -> list[float]: ...


class _Usage(Protocol):
    @property
    def total_tokens(self) -> int: ...


class _EmbeddingResponse(Protocol):
    @property
    def data(self) -> Sequence[_EmbeddingItem]: ...

    @property
    def usage(self) -> _Usage: ...


class _Embeddings(Protocol):
    def create(self, *, model: str, input: list[str]) -> _EmbeddingResponse: ...


class EmbeddingClient(Protocol):
    """Phần của `openai.OpenAI` mà module dùng."""

    @property
    def embeddings(self) -> _Embeddings: ...


@dataclass(frozen=True)
class EmbedReport:
    texts: int  # số chữ khác nhau được hỏi
    from_cache: int
    requested: int
    tokens: int  # token thật theo `usage`, chỉ của phần vừa gọi

    @property
    def cost_usd(self) -> float:
        return self.tokens * PRICE_USD_PER_MILLION_TOKENS / 1_000_000


def token_upper_bound(texts: Iterable[str]) -> int:
    """Chặn trên số token: tổng số byte UTF-8 (xem docstring module)."""
    return sum(len(text.encode("utf-8")) for text in texts)


def cost_upper_bound_usd(texts: Iterable[str]) -> float:
    return token_upper_bound(texts) * PRICE_USD_PER_MILLION_TOKENS / 1_000_000


def cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()


class EmbeddingCache:
    """File JSONL, mỗi dòng `{"key", "model", "vector"}`; chỉ ghi thêm, không sửa dòng cũ.

    Tiến trình chết giữa lúc ghi để lại một dòng cuối dở (không có `\\n`): khi mở, dòng đó được
    bỏ qua (`dropped_partial_line`), file không bị đụng tới, vì các lệnh chỉ đọc cũng mở cache và
    có thể chạy song song với một lệnh đang ghi. Chỉ ngay trước khi CHÍNH tiến trình này ghi thêm,
    `add` mới cắt dòng dở (hoặc thêm `\\n` còn thiếu) để dòng mới không dính vào nó; file đã đổi
    kích thước kể từ lúc mở (tiến trình khác đang ghi) thì dừng. Dòng hỏng ở giữa file là lỗi
    thật → `ValueError`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._vectors: dict[str, list[float]] = {}
        self.dropped_partial_line = False
        self._seen_size = 0  # số byte lúc mở
        self._keep_bytes: int | None = None  # cắt file về số byte này trước lần ghi đầu
        self._needs_newline = False
        if not path.exists():
            return
        data = path.read_bytes()
        self._seen_size = len(data)
        good_end = 0
        lines = data.split(b"\n")
        for number, line in enumerate(lines, start=1):
            is_last = number == len(lines)
            if line.strip():
                try:
                    row = json.loads(line)
                except ValueError:  # JSON dở hoặc byte không giải mã được (đuôi NUL khi máy sập)
                    if not is_last:
                        raise ValueError(f"{path}: dòng {number} hỏng") from None
                    self._keep_bytes = good_end
                    self.dropped_partial_line = True
                    break
                self._vectors[row["key"]] = row["vector"]
            good_end += len(line) + (0 if is_last else 1)
        else:
            # dòng cuối đủ JSON nhưng mất `\n`: lần ghi sau phải bắt đầu dòng mới
            self._needs_newline = bool(data) and not data.endswith(b"\n")

    def get(self, key: str) -> list[float] | None:
        return self._vectors.get(key)

    def _repair_before_append(self) -> None:
        if self._keep_bytes is None and not self._needs_newline:
            return
        if self.path.stat().st_size != self._seen_size:
            raise RuntimeError(f"{self.path} đã đổi từ lúc mở (tiến trình khác đang ghi?)")
        if self._keep_bytes is not None:
            with self.path.open("r+b") as file:
                file.truncate(self._keep_bytes)
        else:
            with self.path.open("ab") as file:
                file.write(b"\n")
        self._keep_bytes, self._needs_newline = None, False

    def add(self, entries: Sequence[tuple[str, str, list[float]]]) -> None:
        """Ghi cả lô một lần sau khi lô đã kiểm xong."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._repair_before_append()
        with self.path.open("a", encoding="utf-8") as file:
            for key, model, vector in entries:
                file.write(json.dumps({"key": key, "model": model, "vector": vector}) + "\n")
                self._vectors[key] = vector


def _checked_batch(response: _EmbeddingResponse, batch: Sequence[str]) -> list[list[float]]:
    """Vector theo đúng thứ tự `batch`, sau khi kiểm số lượng, chỉ số và giá trị hữu hạn."""
    items = sorted(response.data, key=lambda item: item.index)
    if [item.index for item in items] != list(range(len(batch))):
        raise ValueError(f"response có {len(items)} vector cho {len(batch)} chữ, chỉ số lệch")
    vectors = [list(item.embedding) for item in items]
    if any(not vector or not all(math.isfinite(x) for x in vector) for vector in vectors):
        raise ValueError("response có vector rỗng hoặc giá trị không hữu hạn")
    return vectors


def embed_texts(
    texts: Sequence[str],
    *,
    client: EmbeddingClient,
    cache: EmbeddingCache,
    model: str = EMBEDDING_MODEL,
    batch_size: int = BATCH_SIZE,
) -> tuple[NDArray[np.float64], EmbedReport]:
    """Một hàng vector cho mỗi chữ, theo thứ tự đầu vào.

    Chữ trùng hoặc đã có trong cache không gọi lại."""
    if any(not text.strip() for text in texts):
        raise ValueError("không embed chữ rỗng")
    unique = list(dict.fromkeys(texts))
    missing = [text for text in unique if cache.get(cache_key(text, model)) is None]
    tokens = 0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors = _checked_batch(response, batch)
        tokens += response.usage.total_tokens
        cache.add(
            [(cache_key(text, model), model, v) for text, v in zip(batch, vectors, strict=True)]
        )

    rows = [cache.get(cache_key(text, model)) for text in texts]
    # kiểm trước np.array: numpy tự ném lỗi khó đọc ("inhomogeneous shape") khi độ dài lệch
    if len({len(row) for row in rows if row is not None}) > 1:
        raise ValueError("vector trong cache không cùng số chiều")
    matrix = np.array(rows, dtype=np.float64)
    report = EmbedReport(
        texts=len(unique),
        from_cache=len(unique) - len(missing),
        requested=len(missing),
        tokens=tokens,
    )
    return matrix, report
