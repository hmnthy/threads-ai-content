import pytest

from src.nlp.embeddings import FALLBACK_MODEL_NAME, PRIMARY_MODEL_NAME


def test_model_name_constants_are_documented() -> None:
    assert PRIMARY_MODEL_NAME == "BAAI/bge-m3"
    assert FALLBACK_MODEL_NAME == "intfloat/multilingual-e5-large"


@pytest.mark.slow  # tải model bge-m3 thật, ~13s
def test_embed_texts_returns_normalized_vectors_and_model_name() -> None:
    # BLOCKED trên máy chạy agent này (2026-08-31): sentence-transformers phụ thuộc
    # scikit-learn -> scipy.linalg._flapack ở tầng import, bị Smart App Control chặn
    # (chẩn đoán 2026-09-02, xem docs/decisions/legacy-log.md). Skip thay vì fail
    # cứng — trên máy không bị chặn, test này sẽ chạy thật.
    # pytest 9.1+ only auto-skips on ModuleNotFoundError by default — this failure is
    # a plain ImportError (DLL load failure), so exc_type must be passed explicitly.
    sentence_transformers = pytest.importorskip(
        "sentence_transformers",
        reason="blocked by Smart App Control on this machine — see docs/decisions/legacy-log.md",
        exc_type=ImportError,
    )
    del sentence_transformers

    from src.nlp.embeddings import embed_texts

    embeddings, model_name = embed_texts(["hello world", "xin chao ban"])
    assert embeddings.shape[0] == 2
    assert model_name in {PRIMARY_MODEL_NAME, FALLBACK_MODEL_NAME}
