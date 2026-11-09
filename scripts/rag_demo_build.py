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
  check         kiểm trên bài thật, không gọi mạng: vị trí đáp án nằm trong bài, mọi bài đáp án có
                chunk trúng ở cả 7 cách chia, file cặp cross-encoder đúng là file code hiện tại ghi
  live-check    so các bài đóng băng với bài đang sống trên Threads (đã xoá / ẩn / sửa chữ); chạy
                trước mỗi lần publish (ADR-0040 D3); chỉ đọc, cần token Threads trong `--env-file`
                (mặc định `.env`)
  assemble      ghép file demo `--out` (mặc định `data/rag_demo/demo.json`) từ kết quả đã tính sẵn,
                không gọi mạng; chạy mọi phép kiểm của `check` + `ce-check` trước, lỗi thì không
                ghi; từ chối file từ 4 MB trở lên (ADR-0037 D3)

Đọc DB ở chế độ chỉ đọc (`--db`, thường là `data/threads.db` của thư mục chính, vì worktree không có
DB thật). Vector lưu ở `--cache` (mặc định `data/rag_demo/embeddings.jsonl`, gitignored). Script chỉ
in số đếm, không in chữ bài.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import numpy as np
from dotenv import load_dotenv
from numpy.typing import NDArray

from src.api.auth import MissingCredentialsError, load_credentials
from src.api.client import ThreadsClient
from src.api.endpoints import get_posts, get_replies
from src.db.schema import connect_readonly
from src.rag_demo.chunking import Chunk, ChunkingWay, build_chunks, split_sentences
from src.rag_demo.corpus import CorpusChangedError, Unit, live_mismatches, load_units
from src.rag_demo.cross_encoder import (
    PAIRS_PATH,
    SCORES_PATH,
    CrossEncoderResultError,
    cross_encoder_pairs,
    pairs_bytes,
    pairs_file_is_current,
    parse_scores,
    read_scores,
    write_pairs,
)
from src.rag_demo.demo_file import (
    DEMO_FILE_MAX_BYTES,
    DEMO_PATH,
    PAID_QUESTION_TEXTS_SHA256,
    SCORE_DECIMALS,
    build_demo,
    non_gold_kept,
    question_texts_sha256,
    score_counts,
    select_outputs,
    write_demo,
)
from src.rag_demo.embedding import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingClient,
    EmbedReport,
    cache_key,
    cost_upper_bound_usd,
    embed_texts,
    token_upper_bound,
)
from src.rag_demo.llm_batch import collect, parse_rows, submit
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
from src.rag_demo.questions import QUESTIONS, check_gold, gold_chunk_ids

# Thư mục con của data/ mà .gitignore bỏ qua cho demo (test_build_outputs_are_gitignored)
PRIVATE_DIR = Path("data/rag_demo")
RESULTS_NAME = "results.jsonl"
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


SUBMITTED_JOBS = (Job.TRANSFORM, Job.CONTEXT, Job.RERANK)  # lô context mang cả request dịch


def requests_of(job: Job, units: Sequence[Unit], chunks: Sequence[Chunk]) -> list[LlmRequest]:
    """Request của một việc, dựng từ code hiện tại: một chỗ cho cả bước gửi lô và bước ghép file."""
    if job is Job.TRANSFORM:
        return transform_requests(QUESTIONS)
    if job is Job.RERANK:
        return rerank_requests(QUESTIONS, chunks)
    return context_requests(units, chunks)


def llm_requests(
    job: Job, units: Sequence[Unit], cache: EmbeddingCache
) -> tuple[list[LlmRequest], dict[str, str]]:
    """Request của một việc + bảng custom_id → chữ chunk (để kiểm câu trích của rerank)."""
    if job is Job.TRANSFORM:
        # không cần chunk: gửi được trước khi embed (chunk semantic cần vector câu)
        return requests_of(job, units, []), {}
    chunks = [c for cs in all_chunks(units, OfflineClient(), cache).values() for c in cs]
    passages = (
        {rerank_id(q, c.text): c.text for q in QUESTIONS for c in chunks}
        if job is Job.RERANK
        else {}
    )
    return requests_of(job, units, chunks), passages


def run_llm_estimate(units: Sequence[Unit], cache: EmbeddingCache) -> None:
    """Chặn trên phía vào theo byte UTF-8 (cùng giả định tokenizer theo byte).

    Mọi token vào tính theo giá ghi cache (×1,25, đắt nhất), nên vẫn là chặn trên cho việc có cache.
    Phía ra không ước lượng ở đây; số thật lấy từ `usage` khi thu lô."""
    print(f"Model: {LLM_MODEL} · effort {EFFORT}")
    for job in SUBMITTED_JOBS:
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


def build_problems(
    units: Sequence[Unit], by_way: dict[ChunkingWay, list[Chunk]], pairs_path: Path
) -> list[str]:
    """Mọi lỗi của dữ liệu đã dựng so với bài thật và code hiện tại.

    Chỉ chứng minh file cặp cross-encoder khớp code; file điểm khớp file cặp là việc của `ce-check`
    (`read_scores`). Rỗng + `ce-check` qua + `live-check` 0 lỗi mới dùng được để đóng file demo."""
    problems: list[str] = []
    if question_texts_sha256(QUESTIONS) != PAID_QUESTION_TEXTS_SHA256:
        problems.append(
            "chữ câu hỏi khác lúc gửi lô Haiku: tăng PROMPT_VERSIONS của transform + rerank, gửi "
            "lại lô, rồi cập nhật PAID_QUESTION_TEXTS_SHA256"
        )
    try:
        check_gold(units, QUESTIONS)
    except CorpusChangedError as error:
        problems.append(str(error))
    for question in QUESTIONS:
        for way, chunks in by_way.items():
            for unit_id, ids in gold_chunk_ids(question, chunks).items():
                if not ids:
                    problems.append(
                        f"câu {question.number}, cách {way.value}: không chunk nào trúng {unit_id}"
                    )
    chunks = [c for way_chunks in by_way.values() for c in way_chunks]
    if not pairs_path.exists():
        problems.append(f"chưa có file cặp cross-encoder {pairs_path}")
    elif not pairs_file_is_current(cross_encoder_pairs(QUESTIONS, chunks), pairs_path):
        problems.append("file cặp cross-encoder không còn khớp chunk / câu hỏi hiện tại")
    return problems


def run_check(units: Sequence[Unit], cache: EmbeddingCache, pairs_path: Path) -> int:
    by_way = all_chunks(units, OfflineClient(), cache)
    problems = build_problems(units, by_way, pairs_path)
    gold = sum(len(q.gold_unit_ids) for q in QUESTIONS)
    print(
        f"Kiểm {len(units)} bài, {len(QUESTIONS)} câu hỏi ({gold} bài đáp án) × {len(by_way)} "
        f"cách chia, file cặp {pairs_path}: {len(problems)} lỗi"
    )
    for problem in problems:
        print(f"  - {problem}")
    return 1 if problems else 0


def fetch_live_texts(env_file: Path) -> dict[str, str]:
    """Mã post → chữ của mọi post + reply của kênh, đọc thẳng API (không cache), chỉ GET.

    `override=True`: `src/api/auth.py` đã `load_dotenv()` lúc import (tìm `.env` gần nhất, thường là
    bản sao trong worktree, token có thể cũ); không ghi đè thì `--env-file` không có tác dụng."""
    load_dotenv(env_file, override=True)
    credentials = load_credentials()

    async def fetch() -> dict[str, str]:
        async with ThreadsClient(access_token=credentials.access_token) as client:
            posts = await get_posts(client, credentials.user_id)
            replies = await get_replies(client, credentials.user_id)
        return {post.id: post.text or "" for post in [*posts, *replies]}

    return asyncio.run(fetch())


def run_live_check(units: Sequence[Unit], live_texts: dict[str, str]) -> int:
    problems = live_mismatches(units, live_texts)
    print(
        f"So {len(units)} bài với {len(live_texts)} post + reply đang sống trên Threads: "
        f"{len(problems)} lỗi"
    )
    for problem in problems:
        print(f"  - {problem}")
    return 1 if problems else 0


def out_is_private(path: Path) -> bool:
    """File demo chứa nguyên văn bài: trong một cây git chỉ được nằm dưới `data/rag_demo/`.

    `data/` KHÔNG bị gitignore cả thư mục (`.gitignore` chỉ liệt kê từng thư mục con), nên chốt
    ở đúng `data/rag_demo/`. Cây git = thư mục cha gần nhất có `.git` (thư mục ở checkout chính,
    file ở worktree): worktree nằm trong checkout chính, nên ghi vào `<chính>/src/` cũng bị chặn.
    Giả định mọi cây git gặp ở đây là repo này (bỏ qua `data/rag_demo/`; có test `check-ignore`).
    Không thuộc cây git nào (VD thư mục tạm của test) thì được. Không gọi `git check-ignore` để
    bước dựng không phụ thuộc git."""
    resolved = path.resolve()
    for root in resolved.parents:
        if (root / ".git").exists():
            # nằm HẲN bên trong: `is_relative_to` nhận cả chính thư mục, khi đó file tạm
            # `data/rag_demo.tmp` rơi vào data/ (không bị bỏ qua)
            return (root / PRIVATE_DIR).resolve() in resolved.parents
    return True


def run_assemble(
    units: Sequence[Unit],
    cache: EmbeddingCache,
    pairs_path: Path,
    scores_path: Path,
    results_path: Path,
    out_path: Path,
) -> int:
    """Ghép file demo; mọi lỗi → in ra, trả 1, không ghi file (file cũ, nếu có, giữ nguyên)."""
    if not out_is_private(out_path):
        print(
            f"Chưa ghép được: {out_path} nằm trong cây git nhưng ngoài {PRIVATE_DIR.as_posix()}/ "
            "— file chứa nguyên văn bài, chỉ được ghi vào chỗ gitignored"
        )
        return 1
    # Không bao giờ ghi đè đầu vào: kết quả đã trả tiền không chạy lại ra y hệt
    inputs = [cache.path, pairs_path, scores_path, results_path]
    inputs += [DEFAULT_CACHE, PAIRS_PATH, SCORES_PATH, DEFAULT_LLM_DIR / RESULTS_NAME]
    out = out_path.resolve()
    refusal = (
        "không phải .json"
        if out.suffix != ".json"
        else "trùng một file đầu vào"
        if out in {p.resolve() for p in inputs}
        else "nằm trong thư mục kết quả Haiku"
        if {results_path.parent.resolve(), DEFAULT_LLM_DIR.resolve()} & set(out.parents)
        else ""
    )
    if refusal:
        print(f"Chưa ghép được: {out_path} {refusal}")
        return 1
    try:
        by_way = all_chunks(units, OfflineClient(), cache)
    except RuntimeError as error:  # cache thiếu vector câu (chunk semantic)
        print(f"Chưa ghép được: {error}")
        return 1
    problems = build_problems(units, by_way, pairs_path)
    if problems:
        print(f"Chưa ghép được: {len(problems)} lỗi của lệnh check")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    chunks = [c for way_chunks in by_way.values() for c in way_chunks]
    requests = [r for job in SUBMITTED_JOBS for r in requests_of(job, units, chunks)]
    texts = list(dict.fromkeys([c.text for c in chunks] + [q.text for q in QUESTIONS]))
    vectors = {text: v for text in texts if (v := cache.get(cache_key(text, EMBEDDING_MODEL)))}
    try:
        # mỗi file đọc đúng một lần: hash ghi vào file demo là hash của chính các byte đã dùng
        pairs_data, scores_data = pairs_path.read_bytes(), scores_path.read_bytes()
        results_data = results_path.read_bytes()
        if pairs_data != pairs_bytes(cross_encoder_pairs(QUESTIONS, chunks)):
            # build_problems đã kiểm một lần đọc trước; file có thể đã đổi từ đó
            raise CrossEncoderResultError("file cặp cross-encoder đổi giữa lúc kiểm và lúc ghép")
        logits = parse_scores(pairs_data, scores_data)
        selection = select_outputs(parse_rows(results_data, str(results_path)), requests)
        provenance = {
            "cross_encoder_pairs_sha256": hashlib.sha256(pairs_data).hexdigest(),
            "cross_encoder_scores_sha256": hashlib.sha256(scores_data).hexdigest(),
            "llm_results_sha256": hashlib.sha256(results_data).hexdigest(),
            "llm_rows_used": len(selection.outputs),
            "llm_rows_with_fingerprint": selection.fingerprinted,
            "llm_rows_skipped": {
                "not_in_current_set": selection.not_wanted,
                "failed": selection.failed,
                "other_prompt_version": selection.superseded,
            },
        }
        demo = build_demo(
            units, by_way, QUESTIONS, selection.outputs, logits, vectors, inputs=provenance
        )
        # mọi phép tính trên file chạy TRƯỚC khi ghi: lỗi nào cũng xảy ra khi file cũ còn nguyên
        scores = score_counts(demo)
        kept = non_gold_kept(demo)
        size, digest = write_demo(demo, out_path)
    except (ValueError, OSError, KeyError, TypeError) as error:
        # gồm DemoFileError, CrossEncoderResultError, file thiếu, JSON / dòng kết quả hỏng,
        # file thiếu khoá, giá trị sai kiểu
        print(f"Chưa ghép được: {type(error).__name__}: {error}")
        return 1
    print(
        f"File demo {out_path}: {size} byte ({size / DEMO_FILE_MAX_BYTES:.0%} ngân sách "
        f"{DEMO_FILE_MAX_BYTES}) · sha256 {digest[:12]}…"
    )
    print(
        f"{len(units)} bài · {len(demo['passages'])} đoạn khác nhau · chunk theo cách chia "
        + ", ".join(f"{way} {len(records)}" for way, records in demo["ways"].items())
    )
    print(
        f"Kết quả Haiku dùng {len(selection.outputs)} (có dấu vân tay để đối chiếu: "
        f"{selection.fingerprinted}) · bỏ qua: {selection.not_wanted} không thuộc tập hiện tại, "
        f"{selection.failed} thất bại, {selection.superseded} khác phiên bản prompt hiện tại"
    )
    print("Điểm Haiku 0/1/2/3: " + "/".join(str(scores[s]) for s in range(4)))
    per_question = ", ".join(f"câu {n} {c}" for n, c in kept.items() if c)
    print(
        f"Đoạn Haiku giữ mà không trúng đáp án: {sum(kept.values())}"
        + (f" ({per_question})" if per_question else "")
    )
    for kind, ties in demo["provenance"]["rounding_ties"].items():
        per_way = ", ".join(f"{way} {n}" for way, n in ties["by_way"].items())
        print(
            f"Cặp hoà do làm tròn {SCORE_DECIMALS} chữ số (điểm thô khác nhau), {kind}: "
            f"{ties['passages']} trên mọi đoạn · theo cách chia: {per_way}"
        )
    print("Chưa có (mục 2): " + "; ".join(demo["provenance"]["pending"]))
    return 0


def require_env(name: str) -> bool:
    load_dotenv()
    if os.environ.get(name, "").strip():
        return True
    print(f"Thiếu {name} trong .env: chưa gọi API nào.", file=sys.stderr)
    return False


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # lỗi cũng in chữ Việt
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
            "check",
            "live-check",
            "assemble",
        ],
    )
    parser.add_argument("--db", type=Path, help="SQLite thật, mở chỉ đọc (mọi lệnh trừ ce-check)")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--job", type=Job, choices=list(Job), help="việc Haiku (llm-*)")
    parser.add_argument("--llm-dir", type=Path, default=DEFAULT_LLM_DIR)
    parser.add_argument("--ce-pairs", type=Path, default=PAIRS_PATH, help="file cặp (ce-*)")
    parser.add_argument("--ce-scores", type=Path, default=SCORES_PATH, help="file điểm (ce-check)")
    parser.add_argument("--out", type=Path, default=DEMO_PATH, help="file demo (assemble)")
    parser.add_argument(
        "--env-file", type=Path, default=Path(".env"), help="file chứa token Threads (live-check)"
    )
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
    if args.command == "check":
        return run_check(units, cache, args.ce_pairs)
    if args.command == "assemble":
        return run_assemble(
            units,
            cache,
            args.ce_pairs,
            args.ce_scores,
            args.llm_dir / RESULTS_NAME,
            args.out,
        )
    if args.command == "live-check":
        if not args.env_file.is_file():
            # `load_dotenv` gặp file không có chỉ trả False: lệnh sẽ chạy tiếp bằng token đã nạp lúc
            # import (`src/api/auth.py`), tức `--env-file` gõ sai mà không ai biết
            print(f"Không thấy file {args.env_file}: chưa gọi API nào.", file=sys.stderr)
            return 2
        try:
            live_texts = fetch_live_texts(args.env_file)
        except MissingCredentialsError as error:
            print(f"{error}: chưa gọi API nào.", file=sys.stderr)
            return 2
        return run_live_check(units, live_texts)
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
    results_path = args.llm_dir / RESULTS_NAME
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
