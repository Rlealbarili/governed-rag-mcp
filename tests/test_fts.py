from governed_rag_mcp.fts import build_fts_query


def test_fts_operators_are_quoted_as_literals() -> None:
    assert build_fts_query('token OR password* "quoted"') == '"token" "OR" "password" "quoted"'
