from pathlib import Path

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.models import ClientProfile, NRCReason, SearchRequest, Status
from governed_rag_mcp.service import SearchService


def test_hybrid_search_returns_grounded_untrusted_chunk(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, embedder = demo_index
    service = SearchService(index_path=index_path, embedder=embedder)

    response = service.search(
        SearchRequest(
            query="circuit breaker latency budget", source="decisions", confidence="strict"
        ),
        profile=ClientProfile.ENGINEER,
    )

    assert response.status is Status.PASS
    assert response.results[0].id == "decision-circuit-breaker"
    assert response.results[0].text_is_untrusted_context is True
    assert response.results[0].scores.fts_rank == 1
    assert response.results[0].scores.vector_rank is not None


def test_acl_denial_happens_before_config_search(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, embedder = demo_index
    service = SearchService(index_path=index_path, embedder=embedder)

    response = service.search(
        SearchRequest(query="timeout", source="config", confidence="strict"),
        profile=ClientProfile.ENGINEER,
    )

    assert response.status is Status.NO_RELEVANT_CONTEXT
    assert response.no_relevant_context_reason is NRCReason.ACL_DENIED
    assert response.results == []
    assert response.coverage.queried_sources == []
    assert response.coverage.skipped_by_acl == ["config"]


def test_source_all_never_includes_sensitive_config(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, embedder = demo_index
    service = SearchService(index_path=index_path, embedder=embedder)

    response = service.search(
        SearchRequest(query="timeout rollback", source="all"),
        profile=ClientProfile.AUDITOR,
    )

    assert "config" not in response.coverage.queried_sources
    assert all(result.source != "config" for result in response.results)


def test_strict_mode_says_why_it_has_no_relevant_context(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, embedder = demo_index
    service = SearchService(index_path=index_path, embedder=embedder)

    response = service.search(
        SearchRequest(query="medieval pottery kiln glaze", source="all", confidence="strict"),
        profile=ClientProfile.AUDITOR,
    )

    assert response.status is Status.NO_RELEVANT_CONTEXT
    assert response.no_relevant_context_reason in {
        NRCReason.NO_RESULTS,
        NRCReason.STRICT_BLOCKED_LOW,
    }
    assert response.results == []


def test_vector_dimension_mismatch_fails_as_a_governed_plane_error(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, _ = demo_index
    service = SearchService(index_path=index_path, embedder=HashingEmbedder(dimensions=32))

    response = service.search(
        SearchRequest(query="circuit breaker", source="decisions", mode="vector"),
        profile=ClientProfile.ENGINEER,
    )

    assert response.status is Status.NO_RELEVANT_CONTEXT
    assert response.no_relevant_context_reason is NRCReason.PLANE_FAILED
    assert response.coverage.failed_sources == ["decisions"]


def test_hybrid_dimension_mismatch_degrades_to_fts(
    demo_index: tuple[Path, HashingEmbedder],
) -> None:
    index_path, _ = demo_index
    service = SearchService(index_path=index_path, embedder=HashingEmbedder(dimensions=32))

    response = service.search(
        SearchRequest(
            query="circuit breaker latency budget",
            source="decisions",
            mode="hybrid",
            confidence="strict",
        ),
        profile=ClientProfile.ENGINEER,
    )

    assert response.status is Status.PASS
    assert response.results[0].id == "decision-circuit-breaker"
    assert response.coverage.degraded is True
    assert response.coverage.degraded_reason == "embedding_contract_mismatch"
