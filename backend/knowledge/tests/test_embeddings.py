import math
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

from knowledge import embeddings
from knowledge.embeddings import FakeEmbedder, SentenceTransformerEmbedder


def test_fake_embedder_is_deterministic_and_normalized():
    embedder = FakeEmbedder(384)

    a = embedder.embed_query("오케이드라이브 가격")
    b = embedder.embed_passages(["오케이드라이브 가격"])[0]

    assert a == b
    assert len(a) == 384
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-6)


def test_get_embedder_uses_configured_backend(settings):
    settings.EMBEDDING_BACKEND = "fake"

    assert isinstance(embeddings.get_embedder(), FakeEmbedder)


def test_unknown_backend_is_rejected(settings):
    settings.EMBEDDING_BACKEND = "nope"

    with pytest.raises(ImproperlyConfigured):
        embeddings.get_embedder()


def test_sentence_transformer_adds_e5_prefixes():
    embedder = SentenceTransformerEmbedder("some-model", 3)
    model = mock.Mock()
    model.encode.return_value = [mock.Mock(tolist=lambda: [1.0, 0.0, 0.0])]
    embedder._model = model

    embedder.embed_query("질문")
    assert model.encode.call_args.args[0] == ["query: 질문"]
    assert model.encode.call_args.kwargs["normalize_embeddings"] is True

    embedder.embed_passages(["문서"])
    assert model.encode.call_args.args[0] == ["passage: 문서"]


def test_dimension_mismatch_fails_with_clear_error():
    fake_model = mock.Mock(spec=["get_embedding_dimension", "encode"])
    fake_model.get_embedding_dimension.return_value = 768
    with mock.patch("sentence_transformers.SentenceTransformer", return_value=fake_model):
        embedder = SentenceTransformerEmbedder("some-model", 384)

        with pytest.raises(ImproperlyConfigured, match="EMBEDDING_DIM=384"):
            embedder.embed_query("x")


def test_encode_failure_raises_embedding_error():
    embedder = SentenceTransformerEmbedder("some-model", 3)
    embedder._model = mock.Mock(encode=mock.Mock(side_effect=RuntimeError("boom")))

    with pytest.raises(embeddings.EmbeddingError):
        embedder.embed_query("x")
