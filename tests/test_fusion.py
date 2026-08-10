from governed_rag_mcp.fusion import reciprocal_rank_fusion


def test_rrf_is_deterministic_and_preserves_raw_branch_scores() -> None:
    fused = reciprocal_rank_fusion(
        vector_rows=[{"id": "b", "distance": 0.20}, {"id": "a", "distance": 0.30}],
        fts_rows=[{"id": "a", "bm25": -8.0}, {"id": "c", "bm25": -4.0}],
        limit=3,
    )

    assert [row["id"] for row in fused] == ["a", "b", "c"]
    assert fused[0]["scores"]["vector_distance"] == 0.30
    assert fused[0]["scores"]["fts_bm25"] == -8.0
    assert fused[0]["scores"]["rrf"] == (1 / 62) + (1 / 61)
