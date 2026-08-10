import asyncio
import json

from governed_rag_mcp.embeddings import OllamaEmbedder
from governed_rag_mcp.server import _embedder, capabilities_resource, mcp


def test_mcp_surface_has_three_tools_and_one_resource() -> None:
    tools = asyncio.run(mcp.list_tools())
    resources = asyncio.run(mcp.list_resources())

    assert sorted(tool.name for tool in tools) == [
        "list_knowledge_sources",
        "rag_status",
        "search_knowledge",
    ]
    assert [str(resource.uri) for resource in resources] == ["governed-rag://capabilities"]


def test_capabilities_resource_is_machine_readable_and_honest() -> None:
    payload = json.loads(capabilities_resource())
    assert payload["transport"] == "stdio"
    assert payload["retrieval"] == ["fts5", "sqlite-vec", "rrf"]
    assert payload["async_runtime"] is False


def test_ollama_provider_uses_environment_contract(monkeypatch: object) -> None:
    monkeypatch.setenv("GOVERNED_RAG_EMBEDDING_PROVIDER", "ollama")  # type: ignore[attr-defined]
    monkeypatch.setenv("OLLAMA_EMBEDDINGS_URL", "http://127.0.0.1:11434/api/embeddings")  # type: ignore[attr-defined]
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "example-embed")  # type: ignore[attr-defined]
    monkeypatch.setenv("OLLAMA_EMBEDDING_DIMENSIONS", "384")  # type: ignore[attr-defined]

    embedder = _embedder()

    assert isinstance(embedder, OllamaEmbedder)
    assert embedder.url == "http://127.0.0.1:11434/api/embeddings"
    assert embedder.model_name == "example-embed"
    assert embedder.dimensions == 384
