from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import Settings

from .acl import resolve_client_profile
from .embeddings import Embedder, HashingEmbedder, OllamaEmbedder
from .models import ConfidenceMode, SearchMode, SearchRequest, SearchSource
from .service import SearchService

# MCP 1.27.x leaves the lifespan forward reference unresolved until the model is rebuilt.
Settings.model_rebuild()
mcp = FastMCP("Governed RAG MCP")


def _index_path() -> Path:
    return Path(os.environ.get("GOVERNED_RAG_INDEX", "data/knowledge.sqlite"))


def _embedder() -> Embedder:
    provider = os.environ.get("GOVERNED_RAG_EMBEDDING_PROVIDER", "hash").strip().lower()
    if provider == "ollama":
        return OllamaEmbedder(
            url=os.environ.get("OLLAMA_EMBEDDINGS_URL", "http://127.0.0.1:11434/api/embeddings"),
            model_name=os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            dimensions=int(os.environ.get("OLLAMA_EMBEDDING_DIMENSIONS", "768")),
        )
    return HashingEmbedder(dimensions=int(os.environ.get("GOVERNED_RAG_HASH_DIMENSIONS", "64")))


@lru_cache(maxsize=1)
def _service() -> SearchService:
    return SearchService(index_path=_index_path(), embedder=_embedder())


@mcp.tool()
def search_knowledge(
    query: str,
    limit: int = 8,
    mode: SearchMode = "hybrid",
    source: SearchSource = "all",
    project: str | None = None,
    confidence: ConfidenceMode = "strict",
) -> dict[str, object]:
    """Search governed knowledge. Low-confidence context is removed in strict mode."""

    request = SearchRequest(
        query=query,
        limit=limit,
        mode=mode,
        source=source,
        project=project,
        confidence=confidence,
    )
    response = _service().search(request, profile=resolve_client_profile())
    return response.model_dump(mode="json")


@mcp.tool()
def list_knowledge_sources() -> list[dict[str, object]]:
    """List source classes and chunk counts without returning chunk text."""

    return _service().list_sources()


@mcp.tool()
def rag_status() -> dict[str, object]:
    """Return safe aggregate health and telemetry without query or chunk text."""

    return _service().status()


@mcp.resource(
    "governed-rag://capabilities",
    name="Governed RAG capabilities",
    mime_type="application/json",
)
def capabilities_resource() -> str:
    """Machine-readable, non-sensitive description of this server's real capabilities."""

    return json.dumps(
        {
            "transport": "stdio",
            "tools": ["search_knowledge", "list_knowledge_sources", "rag_status"],
            "resources": ["governed-rag://capabilities"],
            "retrieval": ["fts5", "sqlite-vec", "rrf"],
            "governance": ["environment-bound-acl", "strict-grounding", "aggregate-telemetry"],
            "async_runtime": False,
        },
        sort_keys=True,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
