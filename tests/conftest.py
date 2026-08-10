from pathlib import Path

import pytest

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.indexer import build_index
from governed_rag_mcp.models import DocumentInput


@pytest.fixture
def demo_index(tmp_path: Path) -> tuple[Path, HashingEmbedder]:
    index_path = tmp_path / "knowledge.sqlite"
    embedder = HashingEmbedder(dimensions=64)
    documents = [
        DocumentInput(
            id="decision-circuit-breaker",
            path="acme/decisions/circuit-breaker.md",
            source="decisions",
            project="acme",
            text=(
                "Circuit breaker policy: abort retrieval after the latency budget "
                "and report failure."
            ),
        ),
        DocumentInput(
            id="code-acl",
            path="acme/src/access.py",
            source="code",
            project="acme",
            text="def enforce_acl(profile, source): return source in allowed_sources(profile)",
        ),
        DocumentInput(
            id="config-timeout",
            path="acme/config/runtime.toml",
            source="config",
            project="acme",
            text="retrieval.timeout_seconds: 2.5",
        ),
        DocumentInput(
            id="docs-rollback",
            path="beta/docs/rollback.md",
            source="docs",
            project="beta",
            text=(
                "Rollback restores the previous immutable index snapshot after a failed deployment."
            ),
        ),
    ]
    build_index(index_path, documents, embedder)
    return index_path, embedder
