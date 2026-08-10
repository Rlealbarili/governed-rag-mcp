from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from .errors import EmbeddingError


class Embedder(Protocol):
    @property
    def dimensions(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, text: str) -> list[float]: ...


def normalize_embedding(values: list[float], expected_dimensions: int) -> list[float]:
    if len(values) != expected_dimensions or any(not math.isfinite(value) for value in values):
        raise EmbeddingError("embedding_invalid")
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingError("embedding_invalid")
    return [value / norm for value in values]


@dataclass(frozen=True)
class HashingEmbedder:
    """Deterministic dependency-free embedder for tests and the public self-indexing demo."""

    dimensions: int = 64
    model_name: str = "demo-hashing-v1"

    def embed(self, text: str) -> list[float]:
        if self.dimensions < 8:
            raise EmbeddingError("embedding_invalid")
        vector = [0.0] * self.dimensions
        terms = re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)
        if not terms:
            raise EmbeddingError("embedding_invalid")
        for term in terms:
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return normalize_embedding(vector, self.dimensions)


@dataclass(frozen=True)
class OllamaEmbedder:
    url: str = "http://127.0.0.1:11434/api/embeddings"
    model_name: str = "nomic-embed-text"
    dimensions: int = 768
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError as exc:
            raise EmbeddingError("embedding_endpoint_invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and hostname not in {"127.0.0.1", "::1", "localhost"})
        ):
            raise EmbeddingError("embedding_endpoint_invalid")

    def embed(self, text: str) -> list[float]:
        payload = json.dumps(
            {"model": self.model_name, "prompt": text, "keep_alive": "5m"}
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - URL is validated in __post_init__.
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - URL is validated in __post_init__.
                request, timeout=self.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - requires external service
            raise EmbeddingError() from exc
        raw = body.get("embedding")
        if not isinstance(raw, list):
            raise EmbeddingError("embedding_invalid")
        try:
            values = [float(value) for value in raw]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("embedding_invalid") from exc
        return normalize_embedding(values, self.dimensions)
