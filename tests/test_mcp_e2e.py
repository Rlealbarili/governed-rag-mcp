from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.repository_ingest import build_repository_index


def test_stdio_server_searches_its_own_repository(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    index = tmp_path / "self.sqlite"
    build_repository_index(repository_root, index, HashingEmbedder(dimensions=64))

    async def exercise_server() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "governed_rag_mcp.server"],
            cwd=repository_root,
            env={
                **os.environ,
                "GOVERNED_RAG_CLIENT_PROFILE": "engineer",
                "GOVERNED_RAG_INDEX": str(index),
                "GOVERNED_RAG_EMBEDDING_PROVIDER": "hash",
                "GOVERNED_RAG_HASH_DIMENSIONS": "64",
            },
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            response = await session.call_tool(
                "search_knowledge",
                {
                    "query": "reciprocal rank fusion vector FTS branch scores",
                    "source": "code",
                    "confidence": "strict",
                    "limit": 5,
                },
            )

        assert sorted(tool.name for tool in tools.tools) == [
            "list_knowledge_sources",
            "rag_status",
            "search_knowledge",
        ]
        assert [str(resource.uri) for resource in resources.resources] == [
            "governed-rag://capabilities"
        ]
        assert response.isError is False
        assert response.structuredContent is not None
        assert response.structuredContent["status"] == "PASS"
        assert response.structuredContent["results"][0]["path"] == (
            "src/governed_rag_mcp/fusion.py"
        )

    asyncio.run(exercise_server())
