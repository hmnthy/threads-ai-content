"""Cross-encoder rerank của demo RAG — CHỈ chạy trong WSL2 (torch bị Smart App Control chặn trên
Windows, xem `src/pipeline/cluster_wsl.py`). Đọc `data/rag_demo/cross_encoder_pairs.json` do
`python -m scripts.rag_demo_build ce-export` ghi trên Windows.

Chạy trong WSL:
    wsl -d Ubuntu -- bash -c "cd /mnt/c/.../threads-ai-content/.claude/worktrees/<tên> \
        && source ~/threads-clustering-env/bin/activate \
        && python3 -m src.rag_demo.cross_encoder_wsl measure"

`measure` chỉ đếm token của từng cặp (câu hỏi + chunk, gồm token đặc biệt), không chấm, không ghi
file: để biết độ dài tối đa có cắt mất chữ của cặp nào không trước khi chọn.

`score` chấm mọi cặp, ghi `data/rag_demo/cross_encoder_scores.json`:
- điểm thô (logit), không qua sigmoid: thứ hạng như nhau, sigmoid tính lại được khi hiển thị;
- fp32 (mặc định của torch), không fp16: 4.700 cặp chỉ mất vài phút, đổi lấy điểm không lệch vì làm
  tròn nửa chính xác (model card nói fp16 "slight performance degradation");
- dừng trước khi chấm nếu có cặp dài hơn `CROSS_ENCODER_MAX_LENGTH` (không cắt ngầm);
- kiểm lặp lại: chấm lại từng cặp một (không đệm chung lô) `REPEAT_CHECK_PAIRS` cặp rải đều (bước
  cố định, phủ mọi câu hỏi) cộng mọi cặp dài hơn `LONG_PAIR_TOKENS` (nơi phần đệm trong lô khác
  nhiều nhất), ghi độ lệch lớn nhất so với lần chấm theo lô.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from importlib.metadata import version

from src.rag_demo.cross_encoder import (
    CROSS_ENCODER_MAX_LENGTH,
    CROSS_ENCODER_MODEL,
    CROSS_ENCODER_REVISION,
    PAIRS_PATH,
    SCORES_PATH,
)

# Lựa chọn thiết kế: vừa 8 GB VRAM ở 1024 token fp32; không ảnh hưởng điểm (kiểm bằng lần chấm lại)
BATCH_SIZE = 16
# Lựa chọn thiết kế: số cặp chấm lại từng cặp một để đo độ lệch do gom lô. Lấy cách đều nhau trên
# danh sách (xếp theo câu hỏi rồi theo chunk), nên phủ mọi câu hỏi và mọi cách chia; 100 cặp chấm
# lại mất vài giây.
REPEAT_CHECK_PAIRS = 100
# Lựa chọn thiết kế: cặp dài hơn mức này cũng được chấm lại hết (50 cặp ở lần dựng 2026-11-08).
# 512 = mặc định FlagEmbedding, tức đúng các cặp mà mức 512 sẽ cắt; mẫu rải đều gần như không gặp
# chúng vì 20 chunk "không chia" nằm liền nhau ở đầu danh sách chữ của mỗi câu hỏi.
LONG_PAIR_TOKENS = 512


def repeat_check_indices(lengths: list[int]) -> list[int]:
    """Vị trí các cặp chấm lại: bước đều `len // REPEAT_CHECK_PAIRS` (tối đa `REPEAT_CHECK_PAIRS`
    vị trí) cộng mọi cặp dài hơn `LONG_PAIR_TOKENS`, theo thứ tự tăng dần, không trùng."""
    step = max(1, len(lengths) // REPEAT_CHECK_PAIRS)
    spread = range(0, len(lengths), step)[:REPEAT_CHECK_PAIRS]
    long = (i for i, length in enumerate(lengths) if length > LONG_PAIR_TOKENS)
    return sorted({*spread, *long})


# Các mốc chỉ để báo cáo: 512 = ví dụ trong model card, 1024 / 2048 = các bậc kế tiếp
REPORT_THRESHOLDS = (512, 1024, 2048)


def measure() -> None:
    from transformers import AutoConfig, AutoTokenizer

    pairs = json.loads(PAIRS_PATH.read_bytes())["pairs"]
    tokenizer = AutoTokenizer.from_pretrained(CROSS_ENCODER_MODEL, revision=CROSS_ENCODER_REVISION)
    config = AutoConfig.from_pretrained(CROSS_ENCODER_MODEL, revision=CROSS_ENCODER_REVISION)
    by_id = {
        p["id"]: len(tokenizer(p["question"], p["passage"], truncation=False)["input_ids"])
        for p in pairs
    }
    lengths = sorted(by_id.values())
    n = len(lengths)
    print(
        f"cặp: {n} · token min / trung vị / p95 / max = {lengths[0]} / {lengths[n // 2]} / "
        f"{lengths[int(n * 0.95)]} / {lengths[-1]}"
    )
    for threshold in REPORT_THRESHOLDS:
        over_ids = [pair_id for pair_id, length in by_id.items() if length > threshold]
        # mã cặp = rr-qNN-<digest chữ chunk>: phần digest cho biết bao nhiêu chunk khác nhau bị dài
        passages = sorted({pair_id.rsplit("-", 1)[1] for pair_id in over_ids})
        print(
            f"  > {threshold} token: {len(over_ids)} cặp ({len(over_ids) / n:.1%}), "
            f"{len(passages)} chunk khác nhau {passages}"
        )
    print(f"max_position_embeddings của model: {config.max_position_embeddings}")


def score() -> int:
    import numpy as np
    import torch
    from sentence_transformers import CrossEncoder

    raw = PAIRS_PATH.read_bytes()
    pairs = json.loads(raw)["pairs"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CrossEncoder(
        CROSS_ENCODER_MODEL,
        revision=CROSS_ENCODER_REVISION,
        max_length=CROSS_ENCODER_MAX_LENGTH,
        device=device,
    )
    inputs = [(p["question"], p["passage"]) for p in pairs]
    lengths = [len(model.tokenizer(q, p, truncation=False)["input_ids"]) for q, p in inputs]
    longest = max(lengths)
    if longest > CROSS_ENCODER_MAX_LENGTH:
        over = sum(1 for length in lengths if length > CROSS_ENCODER_MAX_LENGTH)
        print(
            f"DỪNG: {over} cặp dài hơn {CROSS_ENCODER_MAX_LENGTH} token (dài nhất {longest}) — "
            "chấm sẽ cắt chữ; hỏi Thy trước khi đổi độ dài",
            file=sys.stderr,
        )
        return 1

    identity = torch.nn.Identity()  # giữ logit thô
    start = time.perf_counter()
    logits = model.predict(inputs, batch_size=BATCH_SIZE, activation_fn=identity)
    seconds = time.perf_counter() - start
    sample = repeat_check_indices(lengths)
    repeat = model.predict([inputs[i] for i in sample], batch_size=1, activation_fn=identity)
    diffs = np.abs(repeat - logits[sample])
    repeat_diff = float(np.max(diffs))
    long_mask = np.array([lengths[i] > LONG_PAIR_TOKENS for i in sample])
    long_diff = float(np.max(diffs[long_mask])) if long_mask.any() else 0.0

    result = {
        "model": CROSS_ENCODER_MODEL,
        "revision": CROSS_ENCODER_REVISION,
        "max_length": CROSS_ENCODER_MAX_LENGTH,
        "pairs_digest": hashlib.sha256(raw).hexdigest(),
        "longest_pair_tokens": longest,
        "device": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
        "dtype": str(next(model.parameters()).dtype),
        "batch_size": BATCH_SIZE,
        "seconds": round(seconds, 1),
        "repeat_check": {
            "pairs": len(sample),
            "long_pairs": int(long_mask.sum()),
            "batch_size": 1,
            "max_abs_diff": repeat_diff,
            "max_abs_diff_long": long_diff,
        },
        # venv WSL nằm ngoài uv.lock: lưu phiên bản để truy được về sau
        "versions": {
            pkg: version(pkg) for pkg in ("torch", "transformers", "sentence-transformers")
        },
        "scores": {p["id"]: float(s) for p, s in zip(pairs, logits, strict=True)},
    }
    SCORES_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(
        f"Đã chấm {len(pairs)} cặp trong {seconds:.1f} s trên {result['device']} "
        f"({result['dtype']}); dài nhất {longest} token; chấm lại từng cặp một {len(sample)} cặp "
        f"(có {int(long_mask.sum())} cặp > {LONG_PAIR_TOKENS} token): lệch tối đa "
        f"{repeat_diff:.2e}, riêng cặp dài {long_diff:.2e} → {SCORES_PATH}"
    )
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if argv[:1] == ["measure"]:
        measure()
        return 0
    if argv[:1] == ["score"]:
        return score()
    print("Cách dùng: python3 -m src.rag_demo.cross_encoder_wsl measure | score", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
