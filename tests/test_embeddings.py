from __future__ import annotations

import pytest

from governed_rag_mcp.embeddings import OllamaEmbedder
from governed_rag_mcp.errors import EmbeddingError


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/embeddings.json",
        "ftp://example.test/embeddings",
        "http://example.test/api/embeddings",
        "https://" + "user" + ":" + "password" + "@example.test/api/embeddings",
    ],
)
def test_ollama_embedder_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(EmbeddingError):
        OllamaEmbedder(url=url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/api/embeddings",
        "http://localhost:11434/api/embeddings",
        "https://embeddings.example.test/api/embeddings",
    ],
)
def test_ollama_embedder_accepts_loopback_http_or_remote_https(url: str) -> None:
    assert OllamaEmbedder(url=url).url == url
