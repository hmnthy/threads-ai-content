from __future__ import annotations

import hashlib
from typing import Any

import pytest

from src.nlp import topics as topics_module
from src.nlp.topics import (
    HDBSCAN_MIN_CLUSTER_SIZE,
    UMAP_N_COMPONENTS,
    TopicLabelResult,
    _extract_json_object,
    label_cluster_with_claude,
)


def test_hdbscan_min_cluster_size_is_reasonable_for_small_dataset() -> None:
    # 140 content units, ~2 post/ngày -> hypothesis ban đầu, CHƯA calibrate (xem
    # docstring của module). Chỉ kiểm tra sanity (>=2, không phải giá trị tuỳ tiện).
    assert HDBSCAN_MIN_CLUSTER_SIZE >= 2
    assert UMAP_N_COMPONENTS == 3


def test_extract_json_object_from_clean_json() -> None:
    text = '{"label": "Alternance search", "description": "desc"}'
    assert _extract_json_object(text) == text


def test_extract_json_object_strips_surrounding_text() -> None:
    text = 'Here is the result:\n{"label": "X", "description": "Y"}\nThanks!'
    assert _extract_json_object(text) == '{"label": "X", "description": "Y"}'


def test_extract_json_object_raises_when_no_json_found() -> None:
    with pytest.raises(ValueError, match="No JSON object found"):
        _extract_json_object("no json here")


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, content: list[_FakeTextBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def create(self, **kwargs: Any) -> _FakeResponse:
        return self._response


class _FakeAnthropicClient:
    """Duck-types the subset of the Anthropic SDK client `label_cluster_with_claude`
    uses — avoids spending a real API call in the test suite."""

    def __init__(self, response: _FakeResponse) -> None:
        self.messages = _FakeMessages(response)


def test_label_cluster_with_claude_parses_json_response() -> None:
    fake_response = _FakeResponse(
        [
            _FakeTextBlock(
                '{"label": "Alternance stories", "description": "Posts about alternance."}'
            )
        ]
    )
    fake_client = _FakeAnthropicClient(fake_response)

    result = label_cluster_with_claude(["post 1", "post 2"], client=fake_client)  # type: ignore[arg-type]

    assert result == TopicLabelResult(
        label_en="Alternance stories", description_en="Posts about alternance."
    )


@pytest.mark.slow  # UMAP + HDBSCAN thật, ~20s trên Windows
def test_cluster_embeddings_on_toy_data() -> None:
    # BLOCKED trên máy chạy agent này (2026-08-31): umap-learn/hdbscan phụ thuộc
    # scipy.linalg._flapack ở tầng import, bị Smart App Control chặn (chẩn đoán
    # 2026-09-02, xem docs/decisions/legacy-log.md). Skip thay vì fail cứng.
    # pytest 9.1+ only auto-skips on ModuleNotFoundError by default — this failure is
    # a plain ImportError (DLL load failure), so exc_type must be passed explicitly.
    numpy = pytest.importorskip("numpy")
    pytest.importorskip(
        "hdbscan",
        reason="blocked by Smart App Control on this machine — see docs/decisions/legacy-log.md",
        exc_type=ImportError,
    )
    pytest.importorskip(
        "umap",
        reason="blocked by Smart App Control on this machine — see docs/decisions/legacy-log.md",
        exc_type=ImportError,
    )
    from src.nlp.topics import cluster_embeddings

    rng = numpy.random.default_rng(0)
    embeddings = numpy.vstack([rng.normal(0, 0.1, (10, 8)), rng.normal(5, 0.1, (10, 8))])

    result = cluster_embeddings(embeddings)

    assert result.labels.shape[0] == 20
    assert result.umap_coords.shape == (20, 3)


class _RecordingMessages:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.kwargs = kwargs
        return _FakeResponse([_FakeTextBlock('{"label": "X", "description": "Y."}')])


class _RecordingClient:
    def __init__(self) -> None:
        self.messages = _RecordingMessages()


def test_label_prompt_v2_rules_are_sent_and_versioned() -> None:
    """Prompt v2 (ADR-0018, Thy duyệt 2026-10-04). Sửa prompt → tăng LABEL_PROMPT_VERSION để
    các topic đặt bằng bản cũ được đặt tên lại; test này nhắc việc đó."""
    client = _RecordingClient()
    label_cluster_with_claude(["post"], client=client)  # type: ignore[arg-type]
    prompt = client.messages.kwargs["messages"][0]["content"]
    assert "Title Case, at most 5 words" in prompt
    assert "Mention Vietnamese identity" in prompt and "ONLY if most sample posts" in prompt
    assert "'Abroad' or 'Expat Life'" in prompt
    assert client.messages.kwargs["model"] == topics_module.CLUSTER_LABELING_MODEL
    # Khoá TOÀN VĂN prompt theo phiên bản: sửa bất kỳ chữ nào → test đỏ → tăng
    # LABEL_PROMPT_VERSION (topic đặt bằng bản cũ được đặt tên lại) rồi thêm hash mới vào đây
    prompt_hashes = {2: "ed7eceddc783642e39eeeb0b5a88b3b389ab89762bd61004f298f24f380ee51d"}
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert prompt_hashes.get(topics_module.LABEL_PROMPT_VERSION) == digest
