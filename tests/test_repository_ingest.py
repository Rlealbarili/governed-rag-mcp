from pathlib import Path

import pytest

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.models import ClientProfile, SearchRequest, Status
from governed_rag_mcp.repository_ingest import (
    UnsafeRepositoryError,
    build_repository_index,
    collect_repository_documents,
)
from governed_rag_mcp.service import SearchService


def test_repository_collection_is_allowlist_only(tmp_path: Path) -> None:
    (tmp_path / "src/pkg").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "private").mkdir()
    (tmp_path / "src/pkg/fusion.py").write_text(
        "def reciprocal_rank_fusion():\n    return 'rrf'\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/architecture.md").write_text("# Architecture\nFail-closed retrieval.\n")
    (tmp_path / "tests/test_fusion.py").write_text(
        "def test_reciprocal_rank_fusion():\n    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "private/customer.md").write_text("must never be indexed")

    documents = collect_repository_documents(tmp_path)
    paths = {document.path for document in documents}

    assert "src/pkg/fusion.py" in paths
    assert "docs/architecture.md" in paths
    assert "tests/test_fusion.py" not in paths
    assert "private/customer.md" not in paths


def test_repository_build_aborts_on_named_secret_without_echoing_value(tmp_path: Path) -> None:
    (tmp_path / "src/pkg").mkdir(parents=True)
    synthetic = "sk-" + "proj-" + ("A" * 24)
    (tmp_path / "src/pkg/settings.py").write_text(f'TOKEN = "{synthetic}"\n', encoding="utf-8")

    with pytest.raises(UnsafeRepositoryError) as exc_info:
        collect_repository_documents(tmp_path)

    assert exc_info.value.reason == "named_secret"
    assert synthetic not in str(exc_info.value)


def test_public_repository_can_answer_questions_about_its_own_rrf(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    index_path = tmp_path / "self.sqlite"
    embedder = HashingEmbedder(dimensions=64)

    report = build_repository_index(repository_root, index_path, embedder)
    service = SearchService(index_path=index_path, embedder=embedder)
    response = service.search(
        SearchRequest(
            query="reciprocal rank fusion vector FTS branch scores",
            source="code",
            confidence="strict",
            limit=5,
        ),
        profile=ClientProfile.ENGINEER,
    )

    assert report["rejected_files"] == []
    assert response.status is Status.PASS
    assert any(result.path == "src/governed_rag_mcp/fusion.py" for result in response.results)


def test_python_chunker_preserves_module_preamble(tmp_path: Path) -> None:
    package = tmp_path / "src/example"
    package.mkdir(parents=True)
    (package / "settings.py").write_text(
        "import os\n\n"
        "DEFAULT_TIMEOUT_SECONDS = 3\n\n"
        "def timeout():\n"
        "    return DEFAULT_TIMEOUT_SECONDS\n",
        encoding="utf-8",
    )

    documents = collect_repository_documents(tmp_path)

    module_chunks = [
        document
        for document in documents
        if document.path == "src/example/settings.py" and document.start_line == 1
    ]
    assert len(module_chunks) == 1
    assert "import os" in module_chunks[0].text
    assert "DEFAULT_TIMEOUT_SECONDS = 3" in module_chunks[0].text
    assert "def timeout" not in module_chunks[0].text


def test_repository_collection_rejects_intermediate_symlink_escape(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    outside = tmp_path / "outside/package"
    repository.mkdir()
    outside.mkdir(parents=True)
    (outside / "leak.py").write_text("CUSTOMER_DATA = 'must stay outside'\n", encoding="utf-8")
    (repository / "src").symlink_to(outside.parent, target_is_directory=True)

    with pytest.raises(UnsafeRepositoryError) as exc_info:
        collect_repository_documents(repository)

    assert exc_info.value.reason == "outside_repository"
    assert "CUSTOMER_DATA" not in str(exc_info.value)
