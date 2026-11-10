"""Ghép file dữ liệu demo RAG mà trình duyệt đọc (ADR-0037 D3, ADR-0038 D6–D7, ADR-0040).

Mọi số trong file lấy từ kết quả đã tính sẵn và đã trả tiền (embedding, Haiku, cross-encoder): bước
này không gọi mạng. Python chỉ chép, đánh dấu chunk trúng đáp án và làm tròn; không xếp hạng — xếp
hạng chỉ có một bản là TypeScript trong trình duyệt (ADR-0037 Hệ quả).

Đơn vị "đoạn" (passage) = một cặp (bài, chữ chunk) khác nhau: chunk trùng chữ giữa các cách chia chỉ
lưu một lần, nên điểm cũng chỉ lưu một lần (mã cặp rerank / cross-encoder chỉ băm chữ chunk).

File chứa nguyên văn bài nên không vào repo (`data/rag_demo/` gitignored); không chứa vector thô,
`usage`, mã lô hay output thô của Haiku (chỉ phục vụ kiểm toán, không phục vụ trang).
"""

import contextlib
import hashlib
import json
import math
import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.rag_demo.chunking import Chunk, ChunkingWay
from src.rag_demo.corpus import Unit, content_hash
from src.rag_demo.cross_encoder import (
    CROSS_ENCODER_MAX_LENGTH,
    CROSS_ENCODER_MODEL,
    CROSS_ENCODER_REVISION,
)
from src.rag_demo.embedding import EMBEDDING_MODEL
from src.rag_demo.llm_batch import is_current
from src.rag_demo.llm_jobs import (
    EFFORT,
    LLM_MODEL,
    PROMPT_VERSIONS,
    RERANK_KEEP_MIN_SCORE,
    Job,
    LlmRequest,
    check_output,
    context_id,
    job_of,
    prompt_fingerprint,
    quote_drop_reason,
    rerank_id,
    transform_id,
)
from src.rag_demo.questions import Question, gold_chunk_ids
from src.rag_demo.unit_metadata import TopicSnapshot

DEMO_PATH = Path("data/rag_demo/demo.json")
# Đổi cấu trúc file thì tăng số này; trang từ chối số lạ thay vì đọc sai. 2 (ADR-0041): mỗi bài có
# tháng đăng + topic, `provenance.topics` ghi lần gom cụm, điểm làm tròn nửa ra xa số 0.
DEMO_FILE_FORMAT = 2
# ADR-0037 D3: response của Vercel Function tối đa 4,5 MB (vượt → 413); Thy chốt ngân sách < 4 MB
# (byte, không phải MiB, để chặt hơn).
DEMO_FILE_MAX_BYTES = 4_000_000
# Thy chọn A1 2026-11-08: 6 chữ số thập phân cho mọi điểm lưu trong file, cùng mức với hằng hoà
# của BM25 (ADR-0038 D4), để mọi điểm của trang dùng cùng kiểu luật hoà (nay ADR-0041 Luật chung 2).
# Hằng có 2 bản: bản này và `src/dashboard/src/lib/ragDemo/bm25.ts:11#SCORE_DECIMALS`; engine từ
# chối file có `provenance.score_decimals` khác bản của nó (ADR-0041 Hệ quả). Làm tròn chia trục số
# thành ô rộng 1e-6: hai điểm cùng ô thành bằng nhau (lệch nhau có thể tới gần 1e-6), hai điểm khác
# ô vẫn khác nhau dù lệch rất ít. Lựa chọn thiết kế: cỡ file không phải ràng buộc (đo 2026-11-08:
# 4 chữ số ~1,8 MB, 6 chữ số ~2,2 MB khi có đủ phần của mục 2).
SCORE_DECIMALS = 6
_SCORE_STEP = Decimal(1).scaleb(-SCORE_DECIMALS)
# Phần file chưa có, làm ở mục 2 của 3e (embed chữ chỉ có sau Haiku). Trang làm theo ADR-0041 Luật
# chung 8 ("hybrid rơi về BM25", "dense trần cần phần còn chờ"). Lọc gần trùng và MMR luôn dùng
# cosine của chữ gốc, nên cosine kèm câu ngữ cảnh không còn là phần chờ (bỏ ở định dạng 2).
PENDING_PARTS = (
    "dense score of transformed questions",
    "dense score of chunks with their context sentence",
)


class DemoFileError(ValueError):
    """Dữ liệu chưa đủ / không khớp để ghép file. Thông báo chỉ ghi mã, không ghi chữ bài."""


def utf16_offset(text: str, index: int) -> int:
    """Vị trí theo điểm mã của Python → vị trí theo đơn vị UTF-16 mà chuỗi JavaScript dùng.

    Emoji ngoài BMP là 1 điểm mã nhưng 2 đơn vị UTF-16: không đổi thì mọi vị trí sau emoji đầu
    tiên lệch trên trang (ADR-0038 D7: trình duyệt không tự tính vị trí)."""
    return len(text[:index].encode("utf-16-le")) // 2


@dataclass(frozen=True)
class Selection:
    outputs: dict[str, dict[str, Any]]
    not_wanted: int  # dòng của request không còn trong tập (VD bài bị xoá, ADR-0040)
    failed: int  # dòng thất bại của request còn trong tập
    superseded: int  # dòng thành công của phiên bản prompt khác bản hiện tại (thường là cũ)
    fingerprinted: int  # dòng được dùng có dấu vân tay để đối chiếu (dòng cũ không có)


def select_outputs(rows: Iterable[Mapping[str, Any]], requests: Sequence[LlmRequest]) -> Selection:
    """Output đã kiểm của đúng các request mà code hiện tại dựng.

    Dòng của request không còn trong tập (VD bài bị xoá, ADR-0040) và dòng thất bại bị bỏ qua.
    Dòng thành công của phiên bản prompt cũ là dòng đã bị thay (`is_current`, cùng định nghĩa
    với bước gửi lô), cũng bỏ qua; mã chỉ có dòng cũ thì dừng. Thiếu dòng thành công, từ 2 dòng
    thành công cùng phiên bản cho một mã (đo 2026-11-08: 0 ca, nên gặp là lỗi — dừng để Thy quyết,
    không tự chọn), sai việc, sai model → dừng. Dòng cũ không có `prompt_fingerprint` vẫn nhận
    (5.182 dòng đầu ghi trước khi có trường này); có thì phải khớp code hiện tại.
    """
    wanted = {request.custom_id: request.job for request in requests}
    current: dict[str, list[Mapping[str, Any]]] = {}
    old_versions: dict[str, set[str]] = {}
    not_wanted = failed = superseded = 0
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping) or not isinstance(row.get("custom_id"), str):
            problems.append(f"dòng {number}: không phải object có custom_id")
            continue
        custom_id = row["custom_id"]
        if custom_id not in wanted:
            not_wanted += 1
            continue
        if not row.get("ok"):
            failed += 1
            continue
        job = wanted[custom_id]
        if row.get("job") != job.value:
            problems.append(f"{custom_id}: việc {row.get('job')!r}, cần {job.value!r}")
        elif is_current(dict(row)):
            current.setdefault(custom_id, []).append(row)
        else:
            # đã bị thay bởi lô của phiên bản prompt mới (cùng mã, ghi thêm cạnh dòng cũ)
            old_versions.setdefault(custom_id, set()).add(str(row.get("prompt_version")))
            superseded += 1
    if problems:
        raise DemoFileError(_summary(problems))
    outputs: dict[str, dict[str, Any]] = {}
    fingerprints = {job: prompt_fingerprint(job) for job in set(wanted.values())}
    for custom_id, job in wanted.items():
        matches = current.get(custom_id, [])
        if not matches:
            if custom_id in old_versions:
                versions = ", ".join(sorted(old_versions[custom_id]))
                problems.append(f"{custom_id}: chỉ có prompt {versions}, khác hiện tại")
            else:
                problems.append(f"{custom_id}: chưa có kết quả thành công")
            continue
        if len(matches) > 1:
            problems.append(f"{custom_id}: {len(matches)} kết quả thành công cùng phiên bản")
            continue
        (row,) = matches
        if row.get("model") != LLM_MODEL:
            problems.append(f"{custom_id}: model {row.get('model')!r}, cần {LLM_MODEL!r}")
        elif row.get("prompt_fingerprint") not in (None, fingerprints[job]):
            problems.append(f"{custom_id}: dấu vân tay request khác code hiện tại")
        elif not isinstance(row.get("output"), dict):
            problems.append(f"{custom_id}: dòng thành công không có output")
        elif reason := _bad_output(job, row["output"]):
            problems.append(f"{custom_id}: output sai dạng ({reason})")
        else:
            outputs[custom_id] = dict(row["output"])
    if problems:
        raise DemoFileError(_summary(problems))
    fingerprinted = sum(
        1 for custom_id in outputs if current[custom_id][0].get("prompt_fingerprint") is not None
    )
    return Selection(outputs, not_wanted, failed, superseded, fingerprinted)


# Dạng output rerank SAU `check_output` (bước thu lô lưu bản đã chuẩn hoá)
_RERANK_STORED_KEYS = {"score", "keep", "quote", "quote_en", "quote_dropped"}


def _bad_output(job: Job, output: Mapping[str, Any]) -> str:
    """Kiểm lại dạng output đã lưu ngay lúc dùng ("" = đúng): file trên đĩa có thể đã bị sửa tay
    hay ghi bởi luật hậu kiểm cũ, bước thu lô kiểm rồi không có nghĩa là bây giờ còn đúng."""
    if job is not Job.RERANK:
        try:
            check_output(job, dict(output))
        except ValueError as error:
            return str(error)
        return ""
    if set(output) != _RERANK_STORED_KEYS:
        return f"khoá {sorted(output)}"
    score = output["score"]
    if isinstance(score, bool) or not isinstance(score, int) or score not in (0, 1, 2, 3):
        return f"điểm {score!r}"
    if output["keep"] is not (score >= RERANK_KEEP_MIN_SCORE):
        return "keep không khớp điểm"
    if not all(isinstance(output[key], str) for key in ("quote", "quote_en")):
        return "câu trích không phải chuỗi"
    if not isinstance(output["quote_dropped"], bool):
        return "quote_dropped không phải bool"
    # các bất biến `check_output` luôn tạo ra (ADR-0037 D8)
    has_quote = bool(output["quote"] or output["quote_en"])
    if score < RERANK_KEEP_MIN_SCORE and has_quote:
        return "câu trích ở điểm dưới mức giữ"
    if output["quote_dropped"] and has_quote:
        return "câu trích đã bỏ mà vẫn còn"
    if output["quote_en"] and not output["quote"]:
        return "quote_en mà không có quote"
    return ""


def _summary(problems: Sequence[str]) -> str:
    shown = "; ".join(problems[:5]) + (f" (+{len(problems) - 5})" if len(problems) > 5 else "")
    return f"{len(problems)} kết quả Haiku không dùng được: {shown}"


def _score(value: float) -> float:
    """Làm tròn 6 chữ số đúng như `Number(x.toFixed(6))` của trang (ADR-0041 Luật chung 5): nửa ô
    ra xa số 0, trên giá trị nhị phân chính xác — `Decimal(float)`, không `Decimal(str)`. `round`
    của Python làm tròn nửa về số chẵn: đo 2026-11-10, logit −11,0390625 (câu 9, đoạn 403) ra
    −11,039062 thay vì −11,039063."""
    number = float(value)
    if not math.isfinite(number):
        raise DemoFileError("điểm không hữu hạn")
    rounded = float(Decimal(number).quantize(_SCORE_STEP, rounding=ROUND_HALF_UP))
    # `+ 0.0` đổi -0.0 (giá trị trong (-5e-7, 0) sau làm tròn) thành 0.0: JSON không ghi "-0.0"
    return rounded + 0.0


# sha256 của [[số, chữ], …] lúc gửi các lô Haiku 2026-11-07 (chữ không đổi từ đó). Mã request
# `tf-qNN` / `rr-qNN-…` chỉ ghi số câu, không băm chữ: sửa chữ một câu thì bước gửi lô vẫn coi là
# xong, và file demo nhận output Haiku chấm theo câu cũ mà không báo. Đổi chữ → tăng
# `PROMPT_VERSIONS` của transform và rerank (gửi lại lô), rồi mới cập nhật hằng này.
PAID_QUESTION_TEXTS_SHA256 = "d225c86b8f16b99e09164d934db11da7cb70ea1785323002c820607a68af31c0"


def question_texts_sha256(questions: Sequence[Question]) -> str:
    payload = json.dumps([[q.number, q.text] for q in questions], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rounding_ties(values: Sequence[float]) -> int:
    """Số cặp (i < j) bằng nhau sau làm tròn mà điểm thô khác nhau: hoà do chính việc làm tròn
    sinh ra — số đo trong Bối cảnh của ADR-0041."""
    groups: dict[float, Counter[float]] = {}
    for value in values:
        groups.setdefault(_score(value), Counter())[value] += 1
    total = 0
    for raw in groups.values():
        size = sum(raw.values())
        total += size * (size - 1) // 2 - sum(m * (m - 1) // 2 for m in raw.values())
    return total


def _unit_matrix(vectors: Sequence[Sequence[float]]) -> NDArray[np.float64]:
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.all(np.isfinite(matrix)) or np.any(norms == 0):
        raise DemoFileError("vector rỗng hoặc không hữu hạn")
    unit: NDArray[np.float64] = matrix / norms
    return unit


def _upper_triangle(matrix: NDArray[np.float64]) -> list[float]:
    """Nửa trên (không đường chéo), đọc theo hàng: (0,1), (0,2), …, (1,2), …"""
    rows, cols = np.triu_indices(matrix.shape[0], k=1)
    return [_score(value) for value in matrix[rows, cols]]


def _context_of(
    outputs: Mapping[str, Mapping[str, Any]], document: str, chunk: Chunk
) -> dict[str, Any]:
    custom_id = context_id(document, chunk)
    if custom_id not in outputs:
        raise DemoFileError(f"bài {chunk.unit_id}: thiếu câu ngữ cảnh / bản dịch ({custom_id})")
    out = outputs[custom_id]
    if job_of(custom_id) is Job.TRANSLATE:
        # chunk là cả bài: chỉ dịch, không có câu ngữ cảnh (ADR-0039 D2)
        return {"en": out["chunk_en"], "context": None, "context_en": None}
    return {"en": out["chunk_en"], "context": out["context"], "context_en": out["context_en"]}


def code_provenance() -> dict[str, object]:
    """Phần provenance do code hiện tại quyết định, không phụ thuộc dữ liệu đầu vào. `publish` so
    đúng phần này với file: file dựng bằng cấu hình cũ (model, phiên bản prompt, phần còn chờ…)
    không được đè bản công khai. Một nguồn cho cả `build_demo` lẫn `publish`, để thêm trường là
    tự được kiểm."""
    return {
        "embedding_model": EMBEDDING_MODEL,
        "llm_model": LLM_MODEL,
        "llm_effort": EFFORT,
        "prompt_versions": {job.value: PROMPT_VERSIONS[job] for job in Job},
        "llm_keep_min_score": RERANK_KEEP_MIN_SCORE,
        "cross_encoder": {
            "model": CROSS_ENCODER_MODEL,
            "revision": CROSS_ENCODER_REVISION,
            "max_length": CROSS_ENCODER_MAX_LENGTH,
            "score": "raw logit",
        },
        "score_decimals": SCORE_DECIMALS,
        "offsets": "utf-16 code units, half-open",
        "cosine_layout": "upper triangle by row, per chunking way, in chunk id order",
        "pending": list(PENDING_PARTS),
    }


def build_demo(
    units: Sequence[Unit],
    by_way: Mapping[ChunkingWay, Sequence[Chunk]],
    questions: Sequence[Question],
    outputs: Mapping[str, Mapping[str, Any]],
    cross_encoder_logits: Mapping[str, float],
    vector_of: Mapping[str, Sequence[float]],
    inputs: Mapping[str, Any] | None = None,
    *,
    metadata: TopicSnapshot,
) -> dict[str, Any]:
    """Nội dung file demo. `vector_of`: chữ → vector embedding (chunk và câu hỏi gốc); `inputs`:
    danh tính các file đầu vào (hash, số dòng) để truy được file demo ghép từ lần chấm nào;
    `metadata`: tháng đăng + topic của mỗi bài (ADR-0041, `read_unit_metadata`).

    Thiếu vector, điểm cross-encoder, output Haiku hay metadata của bất kỳ đoạn / bài nào →
    `DemoFileError`: file thiếu một ô thì trang xếp hạng / lọc sai mà không ai thấy."""
    missing_meta = [unit.id for unit in units if unit.id not in metadata.units]
    if missing_meta:
        raise DemoFileError(f"thiếu tháng đăng / topic của bài {', '.join(missing_meta)}")
    by_id = {unit.id: unit for unit in units}
    passage_index: dict[tuple[str, str], int] = {}
    passages: list[dict[str, Any]] = []
    first_chunk: list[Chunk] = []
    ways: dict[str, list[dict[str, Any]]] = {}
    for way, chunks in by_way.items():
        records: list[dict[str, Any]] = []
        for chunk in chunks:
            key = (chunk.unit_id, chunk.text)
            if key not in passage_index:
                passage_index[key] = len(passages)
                first_chunk.append(chunk)
                passages.append({"unit": chunk.unit_id, "text": chunk.text})
            text = by_id[chunk.unit_id].full_text
            records.append(
                {
                    "id": chunk.id,
                    "unit": chunk.unit_id,
                    "start": utf16_offset(text, chunk.start),
                    "end": utf16_offset(text, chunk.end),
                    "passage": passage_index[key],
                }
            )
        ways[way.value] = records
    for passage, chunk in zip(passages, first_chunk, strict=True):
        passage |= _context_of(outputs, by_id[chunk.unit_id].full_text, chunk)

    def vectors(texts: Sequence[str]) -> NDArray[np.float64]:
        missing = sum(1 for text in texts if text not in vector_of)
        if missing:
            raise DemoFileError(f"thiếu vector của {missing} chữ — chạy lệnh embed")
        return _unit_matrix([vector_of[text] for text in texts])

    passage_vectors = vectors([p["text"] for p in passages])
    question_vectors = vectors([q.text for q in questions])
    # vector thô đã dùng (đoạn rồi câu hỏi): không lưu vector, chỉ lưu dấu vết để truy lần embed
    used_vectors = np.asarray(
        [vector_of[p["text"]] for p in passages] + [vector_of[q.text] for q in questions],
        dtype=np.float64,
    )
    cosine = {
        way: _upper_triangle(
            passage_vectors[[r["passage"] for r in records]]
            @ passage_vectors[[r["passage"] for r in records]].T
        )
        for way, records in ways.items()
    }

    question_records: list[dict[str, Any]] = []
    ties: dict[str, dict[str, Any]] = {
        kind: {"passages": 0, "by_way": dict.fromkeys(ways, 0)}
        for kind in ("dense", "cross_encoder")
    }
    for row, question in enumerate(questions):
        transform = outputs.get(transform_id(question))
        if transform is None:
            raise DemoFileError(f"câu {question.number}: thiếu câu hỏi biến đổi")
        ids = [rerank_id(question, p["text"]) for p in passages]
        if any(pair_id not in cross_encoder_logits for pair_id in ids):
            raise DemoFileError(f"câu {question.number}: thiếu điểm cross-encoder")
        if any(pair_id not in outputs for pair_id in ids):
            raise DemoFileError(f"câu {question.number}: thiếu điểm Haiku")
        for pair_id, passage in zip(ids, passages, strict=True):
            # ADR-0037 D8: câu trích lên trang phải là chuỗi con nguyên văn của đoạn
            if outputs[pair_id]["quote"] not in passage["text"]:
                raise DemoFileError(f"{pair_id}: câu trích không nguyên văn trong đoạn")
        dense = [float(v) for v in passage_vectors @ question_vectors[row]]
        logits = [float(cross_encoder_logits[pair_id]) for pair_id in ids]
        for kind, raw in (("dense", dense), ("cross_encoder", logits)):
            # trên mọi đoạn của câu hỏi, và trong từng cách chia (trang xếp hạng theo cách chia)
            ties[kind]["passages"] += rounding_ties(raw)
            for way_name, records in ways.items():
                ties[kind]["by_way"][way_name] += rounding_ties(
                    [raw[r["passage"]] for r in records]
                )
        span = question.gold_span
        # mọi bài đáp án của câu có vị trí dùng chung span (questions.py); đổi đơn vị theo từng bài
        gold_spans = {
            unit_id: {
                "start": utf16_offset(by_id[unit_id].full_text, span.start),
                "end": utf16_offset(by_id[unit_id].full_text, span.end),
            }
            for unit_id in question.gold_unit_ids
            if span is not None
        }
        question_records.append(
            {
                "number": question.number,
                "text": question.text,
                "english": question.english,
                "rule": question.rule.value,
                "gold_unit_ids": list(question.gold_unit_ids),
                "gold_spans": gold_spans,
                # Python đánh dấu chunk trúng (ADR-0038 D7); mã chunk theo từng cách chia
                "gold_chunks": {
                    way.value: {
                        unit_id: list(hits)
                        for unit_id, hits in gold_chunk_ids(question, chunks).items()
                    }
                    for way, chunks in by_way.items()
                },
                "transforms": dict(transform),
                "dense": [_score(v) for v in dense],
                "cross_encoder": [_score(v) for v in logits],
                "llm": [_llm_cell(outputs[pair_id]) for pair_id in ids],
            }
        )

    return {
        "format": DEMO_FILE_FORMAT,
        "provenance": {
            **code_provenance(),
            # cặp đoạn cùng câu hỏi thành bằng nhau CHỈ vì làm tròn (điểm thô khác nhau)
            "rounding_ties": ties,
            "embedding_vectors_sha256": hashlib.sha256(used_vectors.tobytes()).hexdigest(),
            "question_texts_sha256": question_texts_sha256(questions),
            "inputs": dict(inputs or {}),
            # topic là ảnh chụp lúc dựng file, có thể lệch với /topics sau lần gom cụm sau
            "topics": {
                "cluster_run_id": metadata.cluster_run_id,
                "cluster_run_at": metadata.cluster_run_at,
            },
        },
        "units": [
            {
                "id": unit.id,
                "text": unit.full_text,
                "sha256": content_hash(unit.full_text),
                "month": metadata.units[unit.id].month,
                "topic": {
                    "id": metadata.units[unit.id].topic_id,
                    "label_en": metadata.units[unit.id].topic_label_en,
                },
                "posts": [
                    {
                        "id": post.post_id,
                        "start": utf16_offset(unit.full_text, post.start),
                        "end": utf16_offset(unit.full_text, post.end),
                    }
                    for post in unit.posts
                ],
            }
            for unit in units
        ],
        "passages": passages,
        "ways": ways,
        "cosine": cosine,
        "questions": question_records,
    }


def _llm_cell(output: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "score": output["score"],
        "quote": output["quote"] or None,
        "quote_en": output["quote_en"] or None,
        "quote_dropped": quote_drop_reason(dict(output)) or None,
    }


def non_gold_kept(demo: Mapping[str, Any]) -> dict[int, int]:
    """Số đoạn Haiku giữ (điểm ≥ mức giữ) mà không trúng đáp án ở cách chia nào, theo câu hỏi.

    Con số trang phải nói khi giữ đáp án chốt trước (ADR-0040 D4); đo 2026-11-08: 43 đoạn."""
    ways = demo["ways"]
    keep = demo["provenance"]["llm_keep_min_score"]
    counts: dict[int, int] = {}
    for question in demo["questions"]:
        gold: set[int] = set()
        for way, hits in question["gold_chunks"].items():
            passage_of = {record["id"]: record["passage"] for record in ways[way]}
            gold |= {passage_of[chunk_id] for ids in hits.values() for chunk_id in ids}
        counts[question["number"]] = sum(
            1
            for index, cell in enumerate(question["llm"])
            if cell["score"] >= keep and index not in gold
        )
    return counts


def encode_demo(demo: Mapping[str, Any]) -> bytes:
    return json.dumps(demo, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def write_demo(
    demo: Mapping[str, Any], path: Path = DEMO_PATH, max_bytes: int = DEMO_FILE_MAX_BYTES
) -> tuple[int, str]:
    """Ghi file nếu dưới ngân sách; trả (số byte, sha256). Vượt → `DemoFileError`, không ghi gì.

    Chốt chặn nằm ở đây, trong code chạy thật: file ở `data/` (gitignored) nên CI không thấy file
    thật (ADR-0037 D3). Ghi qua file tạm rồi đổi tên: chết giữa chừng không để lại file cụt."""
    data = encode_demo(demo)
    if len(data) >= max_bytes:
        raise DemoFileError(f"file demo {len(data)} byte, ngân sách < {max_bytes} (ADR-0037 D3)")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(data)
        # Windows: file đích đang mở ở tiến trình khác → PermissionError; file cũ còn nguyên
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):  # không để lỗi dọn file tạm che lỗi gốc
            temporary.unlink(missing_ok=True)
        raise
    return len(data), hashlib.sha256(data).hexdigest()


def score_counts(demo: Mapping[str, Any]) -> Counter[int]:
    """Phân bố điểm Haiku 0–3 trên mọi cặp câu hỏi × đoạn (để đối chiếu methodology log)."""
    return Counter(cell["score"] for q in demo["questions"] for cell in q["llm"])
