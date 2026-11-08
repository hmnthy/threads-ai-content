"""Bước dựng dữ liệu demo RAG (ADR-0037 D3), chạy tay trên laptop, không gắn vào cron.

Lệnh con:
  estimate  đếm chữ cần embed và chặn trên chi phí; không gọi mạng, không cần khoá
  embed     gọi OpenAI cho câu (để chia semantic), mọi chunk của 7 cách chia và 10 câu hỏi; cần
            `OPENAI_API_KEY` trong `.env`
  llm-estimate  đếm request của 3 việc Haiku và chặn trên phía vào; không gọi mạng
  llm-submit    gửi lô Message Batches của một việc (`--job transform | context | rerank`); cần
                `ANTHROPIC_API_KEY`; context và rerank cần embed xong trước (chunk semantic)
  llm-collect   thu lô đã gửi; chưa xong thì chỉ báo trạng thái
  ce-export     ghi mọi cặp câu hỏi gốc × chunk cho cross-encoder chạy trong WSL2
                (`src/rag_demo/cross_encoder_wsl.py`); cần embed xong trước (chunk semantic)
  ce-check      đọc điểm WSL2 trả về, kiểm khớp file cặp (digest, model, độ dài, đủ cặp)

Đọc DB ở chế độ chỉ đọc (`--db`, thường là `data/threads.db` của thư mục chính, vì worktree không có
DB thật). Vector lưu ở `--cache` (mặc định `data/rag_demo/embeddings.jsonl`, gitignored). Script chỉ
in số đếm, không in chữ bài.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import numpy as np
from dotenv import load_dotenv
from numpy.typing import NDArray

from src.db.schema import connect_readonly
from src.rag_demo.chunking import Chunk, ChunkingWay, build_chunks, split_sentences
from src.rag_demo.corpus import Unit, load_units
from src.rag_demo.cross_encoder import (
    PAIRS_PATH,
    SCORES_PATH,
    cross_encoder_pairs,
    read_scores,
    write_pairs,
)
from src.rag_demo.embedding import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingClient,
    EmbedReport,
    cost_upper_bound_usd,
    embed_texts,
    token_upper_bound,
)
from src.rag_demo.llm_batch import collect, submit
from src.rag_demo.llm_jobs import (
    EFFORT,
    LLM_MODEL,
    PROMPT_VERSIONS,
    Job,
    LlmRequest,
    context_requests,
    cost_usd,
    rerank_id,
    rerank_requests,
    transform_requests,
)
from src.rag_demo.questions import QUESTIONS

DEFAULT_CACHE = Path("data/rag_demo/embeddings.jsonl")
DEFAULT_LLM_DIR = Path("data/rag_demo/llm")
OPENAI_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_KEY_ENV = "ANTHROPIC_API_KEY"
# Mốc mô tả của ADR-0039 ("đoạn quá ngắn để chấm"), chỉ để báo cáo, không quyết định gì trong code
DESCRIPTIVE_SHORT_CHARS = 40


def sentence_texts(units: Sequence[Unit]) -> dict[str, list[str]]:
    return {u.id: [u.full_text[a:b] for a, b in split_sentences(u.full_text)] for u in units}


def fixed_way_chunks(units: Sequence[Unit]) -> dict[ChunkingWay, list[Chunk]]:
    """Mọi cách chia không cần vector."""
    return {way: build_chunks(units, way) for way in ChunkingWay if way is not ChunkingWay.SEMANTIC}


def estimate_texts(units: Sequence[Unit]) -> list[str]:
    """Chữ sẽ gửi đi, kể cả chặn trên cho chunk semantic: chúng chia các câu không chồng lấn, nên
    tổng chữ không vượt tổng `full_text`."""
    sentences = [text for texts in sentence_texts(units).values() for text in texts]
    chunks = [c.text for chunks in fixed_way_chunks(units).values() for c in chunks]
    semantic_bound = [u.full_text for u in units]
    questions = [q.text for q in QUESTIONS]
    return list(dict.fromkeys(sentences + chunks + questions)) + semantic_bound


def run_estimate(units: Sequence[Unit]) -> None:
    sentences = sentence_texts(units)
    by_way = fixed_way_chunks(units)
    texts = estimate_texts(units)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Câu (để chia semantic): {sum(len(t) for t in sentences.values())}")
    for way, chunks in by_way.items():
        print(f"Chunk {way.value}: {len(chunks)}")
    print(f"Câu hỏi: {len(QUESTIONS)}")
    print(f"Chữ khác nhau + chặn trên semantic: {len(texts)}")
    print(f"Chặn trên token (byte UTF-8): {token_upper_bound(texts)}")
    print(f"Chặn trên chi phí: ${cost_upper_bound_usd(texts):.4f}")


class OfflineEmbeddings:
    """Dùng khi chỉ đọc cache: chữ nào chưa có vector thì dừng, không gọi mạng."""

    def create(self, *, model: str, input: list[str]) -> NoReturn:
        raise RuntimeError(f"{len(input)} chữ chưa có vector trong cache: chạy lệnh embed trước")


class OfflineClient:
    @property
    def embeddings(self) -> OfflineEmbeddings:
        return OfflineEmbeddings()


def semantic_chunks(
    units: Sequence[Unit], client: EmbeddingClient, cache: EmbeddingCache
) -> tuple[list[Chunk], EmbedReport]:
    sentences = sentence_texts(units)
    flat = [text for unit in units for text in sentences[unit.id]]
    matrix, report = embed_texts(flat, client=client, cache=cache)
    vectors: dict[str, NDArray[np.float64]] = {}
    row = 0
    for unit in units:
        count = len(sentences[unit.id])
        vectors[unit.id] = matrix[row : row + count]
        row += count
    return build_chunks(units, ChunkingWay.SEMANTIC, sentence_vectors=vectors), report


def all_chunks(
    units: Sequence[Unit], client: EmbeddingClient, cache: EmbeddingCache
) -> dict[ChunkingWay, list[Chunk]]:
    by_way = fixed_way_chunks(units)
    by_way[ChunkingWay.SEMANTIC], _ = semantic_chunks(units, client, cache)
    return by_way


def run_embed(units: Sequence[Unit], client: EmbeddingClient, cache: EmbeddingCache) -> None:
    semantic, sentence_report = semantic_chunks(units, client, cache)
    by_way = fixed_way_chunks(units)
    by_way[ChunkingWay.SEMANTIC] = semantic
    texts = [c.text for chunks in by_way.values() for c in chunks] + [q.text for q in QUESTIONS]
    _, rest_report = embed_texts(texts, client=client, cache=cache)

    lengths = sorted(c.end - c.start for c in semantic)
    short = sum(1 for n in lengths if n < DESCRIPTIVE_SHORT_CHARS)
    tokens = sentence_report.tokens + rest_report.tokens
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Câu: {sentence_report.texts} khác nhau, {sentence_report.requested} vừa gọi")
    print(f"Chunk + câu hỏi: {rest_report.texts} khác nhau, {rest_report.requested} vừa gọi")
    cost = sentence_report.cost_usd + rest_report.cost_usd
    print(f"Token thật lần này: {tokens} · chi phí ${cost:.4f}")
    print(f"Chunk semantic thật: {len(semantic)}")
    median = lengths[len(lengths) // 2]
    print(
        f"Độ dài chunk semantic (ký tự): nhỏ nhất {lengths[0]}, trung vị {median}, "
        f"lớn nhất {lengths[-1]}; dưới {DESCRIPTIVE_SHORT_CHARS}: {short}"
    )


def llm_requests(
    job: Job, units: Sequence[Unit], cache: EmbeddingCache
) -> tuple[list[LlmRequest], dict[str, str]]:
    """Request của một việc + bảng custom_id → chữ chunk (để kiểm câu trích của rerank)."""
    if job is Job.TRANSFORM:
        return transform_requests(QUESTIONS), {}
    chunks = [c for cs in all_chunks(units, OfflineClient(), cache).values() for c in cs]
    if job is Job.RERANK:
        passages = {rerank_id(q, c.text): c.text for q in QUESTIONS for c in chunks}
        return rerank_requests(QUESTIONS, chunks), passages
    return context_requests(units, chunks), {}


def run_llm_estimate(units: Sequence[Unit], cache: EmbeddingCache) -> None:
    """Chặn trên phía vào theo byte UTF-8 (cùng giả định tokenizer theo byte).

    Mọi token vào tính theo giá ghi cache (×1,25, đắt nhất), nên vẫn là chặn trên cho việc có cache.
    Phía ra không ước lượng ở đây; số thật lấy từ `usage` khi thu lô."""
    print(f"Model: {LLM_MODEL} · effort {EFFORT}")
    for job in (Job.TRANSFORM, Job.CONTEXT, Job.RERANK):
        requests, _ = llm_requests(job, units, cache)
        bytes_in = sum(len(json.dumps(r.params, ensure_ascii=False).encode()) for r in requests)
        print(
            f"{job.value} (prompt {PROMPT_VERSIONS[job]}): {len(requests)} request · chặn trên "
            f"token vào {bytes_in} (${cost_usd(0, 0, cache_write_tokens=bytes_in):.3f} theo giá lô)"
        )


def run_ce_export(units: Sequence[Unit], cache: EmbeddingCache, path: Path) -> None:
    chunks = [
        c for way_chunks in all_chunks(units, OfflineClient(), cache).values() for c in way_chunks
    ]
    pairs = cross_encoder_pairs(QUESTIONS, chunks)
    digest = write_pairs(pairs, path)
    print(f"Cross-encoder: {len(pairs)} cặp → {path} (sha256 {digest[:12]}…)")


def require_env(name: str) -> bool:
    load_dotenv()
    if os.environ.get(name, "").strip():
        return True
    print(f"Thiếu {name} trong .env: chưa gọi API nào.", file=sys.stderr)
    return False


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument(
        "command",
        choices=[
            "estimate",
            "embed",
            "llm-estimate",
            "llm-submit",
            "llm-collect",
            "ce-export",
            "ce-check",
        ],
    )
    parser.add_argument("--db", type=Path, help="SQLite thật, mở chỉ đọc (mọi lệnh trừ ce-check)")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--job", type=Job, choices=list(Job), help="việc Haiku (llm-*)")
    parser.add_argument("--llm-dir", type=Path, default=DEFAULT_LLM_DIR)
    parser.add_argument("--ce-pairs", type=Path, default=PAIRS_PATH, help="file cặp (ce-*)")
    parser.add_argument("--ce-scores", type=Path, default=SCORES_PATH, help="file điểm (ce-check)")
    args = parser.parse_args(argv)
    if args.command == "ce-check":
        # không cần DB: chỉ so 2 file trong data/rag_demo/
        scores = read_scores(args.ce_pairs, args.ce_scores)
        logits = sorted(scores.values())
        print(
            f"Cross-encoder: {len(logits)} cặp khớp file cặp · logit min / trung vị / max = "
            f"{logits[0]:.3f} / {logits[len(logits) // 2]:.3f} / {logits[-1]:.3f}"
        )
        return 0
    if args.db is None:
        parser.error(f"{args.command} cần --db")

    units = load_units(connect_readonly(args.db))
    cache = EmbeddingCache(args.cache)
    if args.command == "estimate":
        run_estimate(units)
        return 0
    if args.command == "llm-estimate":
        run_llm_estimate(units, cache)
        return 0
    if args.command == "ce-export":
        run_ce_export(units, cache, args.ce_pairs)
        return 0
    if args.command == "embed":
        if not require_env(OPENAI_KEY_ENV):
            return 2
        from openai import OpenAI

        run_embed(units, OpenAI(), cache)
        return 0

    if args.job is None or args.job is Job.TRANSLATE:
        print(
            "Cần --job transform | context | rerank (translate đi cùng context).", file=sys.stderr
        )
        return 2
    if not require_env(ANTHROPIC_KEY_ENV):
        return 2
    from anthropic import Anthropic

    # Không tự thử lại: SDK mặc định gửi lại POST khi timeout / lỗi 5xx; nếu lô đã được tạo mà mất
    # phản hồi, lần gửi lại tạo lô thứ hai (trả tiền hai lần) mà file trạng thái chỉ biết lô sau.
    # Lỗi mạng thì dừng, người chạy xem Console trước khi gửi lại.
    api = Anthropic(max_retries=0).messages.batches
    results_path = args.llm_dir / "results.jsonl"
    requests, passages = llm_requests(args.job, units, cache)
    if args.command == "llm-submit":
        batch_id, count = submit(args.job, requests, api, args.llm_dir, results_path)
        print(
            f"{args.job.value}: "
            + (f"đã gửi lô {batch_id}, {count} request" if batch_id else "không còn request nào")
        )
        return 0
    report = collect(args.job, api, args.llm_dir, results_path, passages.get)
    cost = cost_usd(
        report.input_tokens,
        report.output_tokens,
        cache_write_tokens=report.cache_write_tokens,
        cache_read_tokens=report.cache_read_tokens,
    )
    print(
        f"{args.job.value}: {report.status} · thành công {report.succeeded} · "
        f"lỗi {report.failed} · "
        f"token vào {report.input_tokens} (+ ghi cache {report.cache_write_tokens}, đọc cache "
        f"{report.cache_read_tokens}), ra {report.output_tokens} · "
        f"chi phí theo bảng giá ${cost:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
