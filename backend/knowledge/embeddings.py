"""Single entry point for embeddings (CLAUDE.md, specs/05-rag-pipeline.md §2.3).

Backends:
- "sentence_transformers": local multilingual e5 model, loaded once per process.
- "fake": deterministic bag-of-words hashing vectors for tests (no model download).
"""

import hashlib
import logging
import math
import re
import threading
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """The embedding model could not be loaded or failed to encode."""


class FakeEmbedder:
    """Same text -> same vector; texts sharing words -> similar vectors."""

    def __init__(self, dim):
        self.dim = dim
        self.model_name = "fake"

    def _encode(self, text):
        vector = [0.0] * self.dim
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_passages(self, texts):
        return [self._encode(t) for t in texts]

    def embed_query(self, text):
        return self._encode(text)


class SentenceTransformerEmbedder:
    """Normalized sentence-transformers embeddings.

    e5 models (name contains "e5") need "passage: " / "query: " prefixes; others don't.
    """

    def __init__(self, model_name, dim):
        self.model_name = model_name
        self.dim = dim
        self.uses_e5_prefixes = "e5" in model_name.lower()
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._load()
        return self._model

    def _load(self):
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s", self.model_name)
            model = SentenceTransformer(self.model_name, device="cpu")
        except Exception as exc:
            raise EmbeddingError(f"Failed to load embedding model {self.model_name}") from exc
        # Renamed in sentence-transformers 6; keep the old name for 3.x-5.x.
        get_dim = getattr(model, "get_embedding_dimension", None)
        actual = get_dim() if get_dim else model.get_sentence_embedding_dimension()
        if actual != self.dim:
            raise ImproperlyConfigured(
                f"EMBEDDING_DIM={self.dim} but {self.model_name} produces {actual}-dim vectors. "
                "Set EMBEDDING_DIM accordingly and create a migration for KnowledgeChunk.embedding."
            )
        return model

    def _encode(self, texts):
        model = self._get_model()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        except Exception as exc:
            raise EmbeddingError("Embedding encode failed") from exc
        return [v.tolist() for v in vectors]

    def embed_passages(self, texts):
        prefix = "passage: " if self.uses_e5_prefixes else ""
        return self._encode([f"{prefix}{t}" for t in texts])

    def embed_query(self, text):
        prefix = "query: " if self.uses_e5_prefixes else ""
        return self._encode([f"{prefix}{text}"])[0]

    def load(self):
        """Load now (used to validate a new model before saving the setting)."""
        self._get_model()


# Only the current model stays in memory; switching models drops the previous one.
_current = {"key": None, "embedder": None}
_embedders_lock = threading.Lock()


def configured_model_name():
    from settings_app.models import SystemSetting

    return SystemSetting.load().embedding_model


def get_embedder(model_name=None):
    """Process-wide embedder for the configured backend and DB model (lazy)."""
    backend, dim = settings.EMBEDDING_BACKEND, settings.EMBEDDING_DIM
    if backend == "fake":
        model_name = "fake"
    elif backend == "sentence_transformers":
        model_name = model_name or configured_model_name()
    else:
        raise ImproperlyConfigured(f"Unknown EMBEDDING_BACKEND: {backend}")
    key = (backend, model_name, dim)
    with _embedders_lock:
        if _current["key"] != key:
            embedder = (
                FakeEmbedder(dim)
                if backend == "fake"
                else SentenceTransformerEmbedder(model_name, dim)
            )
            _current.update(key=key, embedder=embedder)
        return _current["embedder"]


def embed_passages(texts, model_name=None):
    return get_embedder(model_name).embed_passages(texts)


def embed_query(text):
    return get_embedder().embed_query(text)


def model_name():
    return get_embedder().model_name


def preload_in_background():
    """Start loading the configured model in a daemon thread (called by wsgi/asgi).

    Requests that arrive while it loads wait for the same model instead of loading a
    second copy. Returns the thread, or None when preloading is off or not needed.
    """
    if settings.EMBEDDING_BACKEND == "fake" or not settings.EMBEDDING_PRELOAD:
        return None
    thread = threading.Thread(target=_preload, name="embedding-preload", daemon=True)
    thread.start()
    return thread


def _preload():
    from django.db import connection

    started = time.monotonic()
    try:
        embedder = get_embedder()
        embedder.embed_query("warm-up")  # the first encode is slow too
        logger.info(
            "Embedding model %s preloaded in %.1fs", embedder.model_name, time.monotonic() - started
        )
    except Exception:
        logger.warning("Embedding model preload failed; it will load on first use", exc_info=True)
    finally:
        connection.close()  # this thread's DB connection (reading the model name)
