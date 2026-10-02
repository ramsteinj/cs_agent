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
    """e5 models need "passage: " / "query: " prefixes and normalized output."""

    def __init__(self, model_name, dim):
        self.model_name = model_name
        self.dim = dim
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
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text):
        return self._encode([f"query: {text}"])[0]


_embedders = {}
_embedders_lock = threading.Lock()


def get_embedder():
    """Process-wide embedder for the configured backend (lazy singleton)."""
    key = (settings.EMBEDDING_BACKEND, settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM)
    with _embedders_lock:
        if key not in _embedders:
            backend, model_name, dim = key
            if backend == "fake":
                _embedders[key] = FakeEmbedder(dim)
            elif backend == "sentence_transformers":
                _embedders[key] = SentenceTransformerEmbedder(model_name, dim)
            else:
                raise ImproperlyConfigured(f"Unknown EMBEDDING_BACKEND: {backend}")
        return _embedders[key]


def embed_passages(texts):
    return get_embedder().embed_passages(texts)


def embed_query(text):
    return get_embedder().embed_query(text)


def model_name():
    return get_embedder().model_name
