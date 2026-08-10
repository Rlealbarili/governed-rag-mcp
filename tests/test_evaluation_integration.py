from pathlib import Path

from governed_rag_mcp.embeddings import HashingEmbedder
from governed_rag_mcp.evaluation import EvaluationQuery, evaluate_service
from governed_rag_mcp.models import ClientProfile, NRCReason, Status
from governed_rag_mcp.repository_ingest import build_repository_index
from governed_rag_mcp.service import SearchService


def test_self_index_evaluation_reports_hitrate_and_mrr(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    embedder = HashingEmbedder(dimensions=64)
    index = tmp_path / "self.sqlite"
    build_repository_index(root, index, embedder)
    service = SearchService(index_path=index, embedder=embedder)
    cases = [
        EvaluationQuery(
            query="reciprocal rank fusion vector FTS scores",
            expected_paths=frozenset({"src/governed_rag_mcp/fusion.py"}),
            source="code",
        ),
        EvaluationQuery(
            query="average_latency_ms by_winning_source query_text_recorded chunk_text_recorded",
            expected_paths=frozenset({"src/governed_rag_mcp/observability.py"}),
            source="code",
        ),
        EvaluationQuery(
            query="reciprocal rank fusion implementation",
            expected_paths=frozenset(),
            source="code",
            profile=ClientProfile.RESTRICTED,
            expected_status=Status.NO_RELEVANT_CONTEXT,
            expected_reason=NRCReason.ACL_DENIED,
            expected_skipped_sources=frozenset({"code"}),
        ),
    ]

    report = evaluate_service(service, cases, k=5, profile=ClientProfile.ENGINEER)

    assert report["metrics"]["hit_rate_at_k"] == 1.0
    assert report["metrics"]["mrr"] >= 0.5
    assert report["failed_queries"] == []
    assert report["contract_failures"] == []
