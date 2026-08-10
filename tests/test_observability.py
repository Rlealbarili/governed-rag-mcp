from governed_rag_mcp.observability import MetricsRegistry


def test_observability_is_aggregate_only() -> None:
    registry = MetricsRegistry()
    registry.record(
        profile="engineer",
        requested_source="code",
        status="PASS",
        winning_source="code",
        latency_ms=12.5,
    )

    snapshot = registry.snapshot()
    assert snapshot["query_text_recorded"] is False
    assert snapshot["chunk_text_recorded"] is False
    assert snapshot["request_count"] == 1
    assert "query" not in snapshot
    assert "text" not in snapshot
