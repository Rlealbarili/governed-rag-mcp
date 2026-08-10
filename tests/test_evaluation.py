from governed_rag_mcp.evaluation import EvalCase, compute_retrieval_metrics


def test_hitrate_and_mrr_are_computed_from_ranked_ids() -> None:
    cases = [
        EvalCase(query="q1", expected_ids=frozenset({"a"})),
        EvalCase(query="q2", expected_ids=frozenset({"z"})),
    ]
    metrics = compute_retrieval_metrics(cases, [["a", "b"], ["x", "z"]], k=2)

    assert metrics.query_count == 2
    assert metrics.hit_rate_at_k == 1.0
    assert metrics.mrr == 0.75
