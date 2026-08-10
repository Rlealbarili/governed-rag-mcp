from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import (
    ClientProfile,
    NRCReason,
    RetrievalMetrics,
    SearchRequest,
    SearchSource,
    Status,
)
from .service import SearchService


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected_ids: frozenset[str]


@dataclass(frozen=True)
class EvaluationQuery:
    query: str
    expected_paths: frozenset[str]
    source: SearchSource = "all"
    project: str | None = None
    profile: ClientProfile | None = None
    expected_status: Status = Status.PASS
    expected_reason: NRCReason | None = None
    expected_skipped_sources: frozenset[str] = frozenset()


def compute_retrieval_metrics(
    cases: Sequence[EvalCase],
    ranked_ids: Sequence[Sequence[str]],
    *,
    k: int,
) -> RetrievalMetrics:
    if not cases or len(cases) != len(ranked_ids) or k < 1:
        raise ValueError("cases, rankings and k must define a non-empty aligned evaluation")
    hits = 0
    reciprocal_rank_sum = 0.0
    for case, ranking in zip(cases, ranked_ids, strict=True):
        first_rank = next(
            (
                rank
                for rank, item_id in enumerate(ranking[:k], start=1)
                if item_id in case.expected_ids
            ),
            None,
        )
        if first_rank is not None:
            hits += 1
            reciprocal_rank_sum += 1.0 / first_rank
    return RetrievalMetrics(
        query_count=len(cases),
        k=k,
        hit_rate_at_k=hits / len(cases),
        mrr=reciprocal_rank_sum / len(cases),
    )


def evaluate_service(
    service: SearchService,
    cases: Sequence[EvaluationQuery],
    *,
    k: int,
    profile: ClientProfile,
) -> dict[str, object]:
    metric_cases: list[EvalCase] = []
    rankings: list[list[str]] = []
    details: list[dict[str, object]] = []
    failed_queries: list[str] = []
    contract_failures: list[str] = []
    for case in cases:
        case_profile = case.profile or profile
        response = service.search(
            SearchRequest(
                query=case.query,
                source=case.source,
                project=case.project,
                confidence="strict",
                limit=k,
            ),
            profile=case_profile,
        )
        ranked_paths = [result.path for result in response.results]
        first_rank = next(
            (
                rank
                for rank, path in enumerate(ranked_paths, start=1)
                if path in case.expected_paths
            ),
            None,
        )
        if case.expected_paths:
            rankings.append(ranked_paths)
            metric_cases.append(EvalCase(query=case.query, expected_ids=case.expected_paths))
            if first_rank is None:
                failed_queries.append(case.query)
        case_failures: list[str] = []
        if response.status is not case.expected_status:
            case_failures.append("status")
        if response.no_relevant_context_reason is not case.expected_reason:
            case_failures.append("reason")
        if not case.expected_skipped_sources.issubset(response.coverage.skipped_by_acl):
            case_failures.append("skipped_by_acl")
        contract_failures.extend(f"{case.query}:{failure}" for failure in case_failures)
        details.append(
            {
                "query": case.query,
                "profile": case_profile.value,
                "status": response.status.value,
                "first_relevant_rank": first_rank,
                "returned_paths": ranked_paths,
                "contract_failures": case_failures,
            }
        )
    if not metric_cases:
        raise ValueError("evaluation requires at least one positive retrieval case")
    metrics = compute_retrieval_metrics(metric_cases, rankings, k=k)
    return {
        "metrics": metrics.model_dump(mode="json"),
        "failed_queries": failed_queries,
        "contract_failures": contract_failures,
        "cases": details,
    }
