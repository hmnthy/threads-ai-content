"""Cross-encoder của demo RAG: dựng cặp, kiểm file điểm từ WSL2, luật không cắt chữ ngầm.

Bước WSL2 cần torch: test thay `torch` và `sentence_transformers` bằng module giả để kiểm logic
dừng / ghi file mà không tải model. Chữ tự đặt, không chữ bài thật (repo public).
"""

from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.rag_demo import cross_encoder_wsl
from src.rag_demo.chunking import Chunk
from src.rag_demo.cross_encoder import (
    CROSS_ENCODER_MAX_LENGTH,
    CROSS_ENCODER_MODEL,
    CROSS_ENCODER_REVISION,
    CrossEncoderResultError,
    Pair,
    cross_encoder_pairs,
    pairs_file_is_current,
    parse_scores,
    read_scores,
    sigmoid,
    write_pairs,
)
from src.rag_demo.llm_jobs import rerank_id
from src.rag_demo.questions import QUESTIONS

CHUNKS = [
    Chunk(0, "u1", 0, 9, "Đoạn một."),
    Chunk(1, "u1", 10, 18, "Đoạn hai."),
    Chunk(0, "u1", 0, 9, "Đoạn một."),  # cùng chữ ở cách chia khác: chỉ chấm một lần
]


def test_pairs_cover_every_question_times_distinct_text_with_llm_rerank_ids() -> None:
    pairs = cross_encoder_pairs(QUESTIONS[:2], CHUNKS)
    assert len(pairs) == 2 * 2
    assert pairs[0] == Pair(rerank_id(QUESTIONS[0], "Đoạn một."), QUESTIONS[0].text, "Đoạn một.")
    # cùng khoá với LLM rerank → bước đóng file demo ghép được hai cách chấm
    assert {p.id for p in pairs} == {
        rerank_id(q, t) for q in QUESTIONS[:2] for t in ("Đoạn một.", "Đoạn hai.")
    }


def test_write_pairs_refuses_duplicate_ids(tmp_path: Path) -> None:
    pair = Pair("rr-q01-x", "q", "p")
    with pytest.raises(ValueError, match="trùng"):
        write_pairs([pair, pair], tmp_path / "pairs.json")


def _scores_file(tmp_path: Path, pairs_path: Path, **overrides: Any) -> Path:
    import hashlib

    ids = [p["id"] for p in json.loads(pairs_path.read_bytes())["pairs"]]
    payload: dict[str, Any] = {
        "model": CROSS_ENCODER_MODEL,
        "revision": CROSS_ENCODER_REVISION,
        "max_length": CROSS_ENCODER_MAX_LENGTH,
        "pairs_digest": hashlib.sha256(pairs_path.read_bytes()).hexdigest(),
        "longest_pair_tokens": 100,
        "scores": {pair_id: -1.5 for pair_id in ids},
    }
    payload.update(overrides)
    path = tmp_path / "scores.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def pairs_path(tmp_path: Path) -> Path:
    path = tmp_path / "pairs.json"
    write_pairs(cross_encoder_pairs(QUESTIONS[:1], CHUNKS), path)
    return path


def test_read_scores_accepts_a_matching_file(tmp_path: Path, pairs_path: Path) -> None:
    scores = read_scores(pairs_path, _scores_file(tmp_path, pairs_path))
    assert len(scores) == 2
    assert set(scores.values()) == {-1.5}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"pairs_digest": "0" * 64}, "file cặp khác"),
        ({"model": "BAAI/bge-reranker-v2-gemma"}, "model"),
        ({"revision": "main"}, "revision"),
        ({"max_length": 512}, "max_length"),
        ({"longest_pair_tokens": CROSS_ENCODER_MAX_LENGTH + 1}, "cắt chữ"),
        ({"longest_pair_tokens": "790"}, "thiếu độ dài"),
        ({"longest_pair_tokens": None}, "thiếu độ dài"),
        ({"scores": {}}, "thiếu 2 cặp"),
    ],
)
def test_read_scores_refuses_a_file_that_does_not_match(
    tmp_path: Path, pairs_path: Path, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(CrossEncoderResultError, match=message):
        read_scores(pairs_path, _scores_file(tmp_path, pairs_path, **overrides))


def test_read_scores_refuses_an_extra_pair(tmp_path: Path, pairs_path: Path) -> None:
    ids = [p["id"] for p in json.loads(pairs_path.read_bytes())["pairs"]]
    scores = dict.fromkeys(ids, 0.5) | {"rr-q99-0000000000000000": 0.5}
    with pytest.raises(CrossEncoderResultError, match="thiếu 0 cặp, thừa 1 cặp"):
        read_scores(pairs_path, _scores_file(tmp_path, pairs_path, scores=scores))


def test_read_scores_refuses_missing_length_field(tmp_path: Path, pairs_path: Path) -> None:
    """File cũ không ghi độ dài cặp dài nhất thì không chứng minh được là không cắt chữ."""
    path = _scores_file(tmp_path, pairs_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["longest_pair_tokens"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CrossEncoderResultError, match="cắt chữ"):
        read_scores(pairs_path, path)


@pytest.mark.parametrize("bad", [True, "1.0", None])
def test_read_scores_refuses_non_numeric_score(
    tmp_path: Path, pairs_path: Path, bad: object
) -> None:
    ids = [p["id"] for p in json.loads(pairs_path.read_bytes())["pairs"]]
    scores = {ids[0]: bad, ids[1]: 0.5}
    with pytest.raises(CrossEncoderResultError, match="không hữu hạn"):
        read_scores(pairs_path, _scores_file(tmp_path, pairs_path, scores=scores))


def test_read_scores_refuses_infinite_score(tmp_path: Path, pairs_path: Path) -> None:
    # json.dumps ghi `Infinity`, json.loads đọc lại thành float('inf')
    ids = [p["id"] for p in json.loads(pairs_path.read_bytes())["pairs"]]
    path = _scores_file(tmp_path, pairs_path, scores={ids[0]: math.inf, ids[1]: 0.5})
    with pytest.raises(CrossEncoderResultError, match="không hữu hạn"):
        read_scores(pairs_path, path)


def test_sigmoid_matches_the_model_card_example_and_is_stable() -> None:
    # model card bge-reranker-v2-m3: logit -8.1875 → 0.000278…, 5.26171875 → 0.99484…
    assert sigmoid(-8.1875) == pytest.approx(0.00027803096387751553, rel=1e-6)
    assert sigmoid(5.26171875) == pytest.approx(0.9948403768236574, rel=1e-9)
    assert sigmoid(-1000.0) == 0.0
    assert sigmoid(1000.0) == 1.0


# --- bước WSL2 với torch / sentence_transformers giả ---


class _FakeTokenizer:
    def __call__(self, question: str, passage: str, truncation: bool) -> dict[str, list[int]]:
        assert truncation is False  # phải đếm độ dài THẬT, không phải độ dài sau khi cắt
        return {"input_ids": [0] * (len(question) + len(passage))}


class _FakeCrossEncoder:
    instances: list[_FakeCrossEncoder] = []

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name, self.kwargs = name, kwargs
        self.tokenizer = _FakeTokenizer()
        self.predict_calls: list[int] = []
        _FakeCrossEncoder.instances.append(self)

    def predict(self, inputs: list[tuple[str, str]], batch_size: int, activation_fn: Any) -> Any:
        self.predict_calls.append(batch_size)
        return np.array([float(len(p)) for _, p in inputs])

    def parameters(self) -> Any:
        return iter([types.SimpleNamespace(dtype="torch.float32")])


@pytest.fixture
def fake_wsl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
    torch.nn = types.SimpleNamespace(Identity=lambda: "identity")  # type: ignore[attr-defined]
    st = types.ModuleType("sentence_transformers")
    st.CrossEncoder = _FakeCrossEncoder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", st)
    monkeypatch.setattr(cross_encoder_wsl, "version", lambda _: "0.0")
    _FakeCrossEncoder.instances.clear()
    pairs_path, scores_path = tmp_path / "pairs.json", tmp_path / "scores.json"
    monkeypatch.setattr(cross_encoder_wsl, "PAIRS_PATH", pairs_path)
    monkeypatch.setattr(cross_encoder_wsl, "SCORES_PATH", scores_path)
    return tmp_path


def test_wsl_score_writes_each_score_under_its_own_pair_id(fake_wsl: Path) -> None:
    # độ dài khác nhau → điểm giả (= độ dài chunk) khác nhau: ghép sai id thì assert đỏ
    texts = ["Một.", "Đoạn dài hơn.", "Ba"]
    chunks = [Chunk(i, "u1", 0, len(t), t) for i, t in enumerate(texts)]
    write_pairs(cross_encoder_pairs(QUESTIONS[:2], chunks), fake_wsl / "pairs.json")
    assert cross_encoder_wsl.score() == 0
    model = _FakeCrossEncoder.instances[0]
    assert model.kwargs["revision"] == CROSS_ENCODER_REVISION
    assert model.kwargs["max_length"] == CROSS_ENCODER_MAX_LENGTH
    assert model.predict_calls == [cross_encoder_wsl.BATCH_SIZE, 1]  # lô chính + kiểm lặp lại
    scores = read_scores(fake_wsl / "pairs.json", fake_wsl / "scores.json")
    assert scores == {rerank_id(q, t): float(len(t)) for q in QUESTIONS[:2] for t in texts}
    written = json.loads((fake_wsl / "scores.json").read_text(encoding="utf-8"))
    assert written["repeat_check"]["max_abs_diff"] == 0.0
    assert written["repeat_check"]["pairs"] == 6


class _DriftingCrossEncoder(_FakeCrossEncoder):
    """Chấm từng cặp một (batch_size=1) lệch +0,5 đúng ở chunk `DRIFT`: giả lập độ lệch do gom
    lô."""

    DRIFT = "z" * 600  # > 512 token với tokenizer giả (1 ký tự = 1 token)

    def predict(self, inputs: list[tuple[str, str]], batch_size: int, activation_fn: Any) -> Any:
        values = super().predict(inputs, batch_size, activation_fn)
        if batch_size == 1:
            values = values + np.array([0.5 if p == self.DRIFT else 0.0 for _, p in inputs])
        return values


def test_wsl_repeat_check_compares_the_same_pairs_and_reports_long_ones(
    fake_wsl: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 10 câu × 20 chữ = 200 cặp → bước 2: mẫu rải đều là các vị trí chẵn; chunk DRIFT ở vị trí lẻ
    # (1 trong mỗi câu) nên chỉ được chấm lại nhờ luật "mọi cặp dài". So sai vị trí (vd `[:n]`
    # thay cho `[sample]`) thì hiệu của các chữ khác độ dài khác 0.
    texts = [f"{'w' * (i + 1)}" for i in range(20)]
    texts[1] = _DriftingCrossEncoder.DRIFT
    chunks = [Chunk(i, "u1", 0, len(t), t) for i, t in enumerate(texts)]
    write_pairs(cross_encoder_pairs(QUESTIONS, chunks), fake_wsl / "pairs.json")
    monkeypatch.setattr(sys.modules["sentence_transformers"], "CrossEncoder", _DriftingCrossEncoder)
    assert cross_encoder_wsl.score() == 0
    check = json.loads((fake_wsl / "scores.json").read_text(encoding="utf-8"))["repeat_check"]
    assert (check["pairs"], check["long_pairs"]) == (110, 10)
    assert check["max_abs_diff"] == pytest.approx(0.5)
    assert check["max_abs_diff_long"] == pytest.approx(0.5)


def test_wsl_score_stops_before_scoring_when_a_pair_is_too_long(
    fake_wsl: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    long_text = "x" * CROSS_ENCODER_MAX_LENGTH  # câu hỏi + chunk > độ dài tối đa
    write_pairs(
        cross_encoder_pairs(QUESTIONS[:1], [Chunk(0, "u1", 0, 1, long_text)]),
        fake_wsl / "pairs.json",
    )
    assert cross_encoder_wsl.score() == 1
    assert _FakeCrossEncoder.instances[0].predict_calls == []
    assert not (fake_wsl / "scores.json").exists()
    assert "DỪNG" in capsys.readouterr().err


def test_repeat_check_spreads_over_every_question_and_adds_every_long_pair() -> None:
    short = [100] * 4700
    indices = cross_encoder_wsl.repeat_check_indices(short)
    assert len(indices) == cross_encoder_wsl.REPEAT_CHECK_PAIRS
    # 4.700 cặp = 10 câu × 470 chunk, xếp theo câu hỏi: mỗi câu có đúng 10 cặp được chấm lại
    assert all(sum(1 for i in indices if i // 470 == q) == 10 for q in range(10))
    # 5 chunk dài ở vị trí 1–5 của mỗi câu (mẫu rải đều chỉ gặp vị trí 0): đều được thêm vào
    lengths = [600 if i % 470 in range(1, 6) else 100 for i in range(4700)]
    with_long = cross_encoder_wsl.repeat_check_indices(lengths)
    assert len(with_long) == 100 + 50
    assert {i for i, n in enumerate(lengths) if n > 512} <= set(with_long)
    assert with_long == sorted(set(with_long))
    assert cross_encoder_wsl.repeat_check_indices([1] * 5) == [0, 1, 2, 3, 4]


def test_wsl_measure_counts_untruncated_lengths(
    fake_wsl: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = types.SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda *_, **__: _FakeTokenizer()
    )
    transformers.AutoConfig = types.SimpleNamespace(  # type: ignore[attr-defined]
        from_pretrained=lambda *_, **__: types.SimpleNamespace(max_position_embeddings=8194)
    )
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    chunks = [Chunk(0, "u1", 0, 1, "y" * 600), Chunk(1, "u1", 1, 2, "ngắn")]
    write_pairs(cross_encoder_pairs(QUESTIONS[:1], chunks), fake_wsl / "pairs.json")
    cross_encoder_wsl.measure()
    out = capsys.readouterr().out
    assert "cặp: 2" in out
    assert (
        "> 512 token: 1 cặp" in out
    )  # câu hỏi + 600 ký tự > 512 với tokenizer giả 1 ký tự = 1 token
    assert "> 1024 token: 0 cặp" in out
    assert "8194" in out


def test_wsl_main_rejects_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cross_encoder_wsl.main(["nope"]) == 2
    assert "measure | score" in capsys.readouterr().err


def test_pairs_file_is_current_only_for_exactly_the_pairs_written(tmp_path: Path) -> None:
    """`read_scores` chỉ so file điểm với file cặp; phép này so file cặp với code hiện tại."""
    pairs = [Pair("a", "câu hỏi", "đoạn một"), Pair("b", "câu hỏi", "đoạn hai")]
    path = tmp_path / "pairs.json"
    write_pairs(pairs, path)
    assert pairs_file_is_current(pairs, path)
    assert not pairs_file_is_current([pairs[0], Pair("b", "câu hỏi", "đoạn hai sửa")], path)
    assert not pairs_file_is_current(pairs[:1], path)


@pytest.mark.parametrize("scores", [b"[]", b'{"scores": []}', b"null"])
def test_scores_file_of_the_wrong_shape_is_a_clear_error(scores: bytes) -> None:
    with pytest.raises(CrossEncoderResultError, match="không phải object"):
        parse_scores(b'{"pairs": []}', scores)
