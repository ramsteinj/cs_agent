import importlib
import logging
from unittest import mock

from knowledge import embeddings


def test_skipped_for_fake_backend(settings):
    settings.EMBEDDING_BACKEND = "fake"

    assert embeddings.preload_in_background() is None


def test_can_be_disabled(settings):
    settings.EMBEDDING_BACKEND = "sentence_transformers"
    settings.EMBEDDING_PRELOAD = False

    assert embeddings.preload_in_background() is None


def test_loads_and_warms_the_model_in_a_background_thread(settings, caplog):
    settings.EMBEDDING_BACKEND = "sentence_transformers"
    settings.EMBEDDING_PRELOAD = True
    embedder = mock.Mock(model_name="intfloat/multilingual-e5-small")
    caplog.set_level(logging.INFO, logger="knowledge.embeddings")

    with mock.patch.object(embeddings, "get_embedder", return_value=embedder):
        thread = embeddings.preload_in_background()
        thread.join(timeout=5)

    assert thread.daemon is True
    embedder.embed_query.assert_called_once_with("warm-up")
    assert "Embedding model intfloat/multilingual-e5-small preloaded" in caplog.text


def test_failure_only_logs_a_warning(settings, caplog):
    settings.EMBEDDING_BACKEND = "sentence_transformers"
    settings.EMBEDDING_PRELOAD = True

    with mock.patch.object(embeddings, "get_embedder", side_effect=RuntimeError("no db yet")):
        embeddings.preload_in_background().join(timeout=5)

    assert "preload failed; it will load on first use" in caplog.text


def test_wsgi_and_asgi_entry_points_start_the_preload():
    import config.asgi
    import config.wsgi

    for module in (config.wsgi, config.asgi):
        with mock.patch("knowledge.embeddings.preload_in_background") as preload:
            importlib.reload(module)
        preload.assert_called_once_with()
