import pytest
from pydantic import ValidationError

from governed_rag_mcp.models import SearchRequest


def test_search_request_rejects_empty_query_and_out_of_range_limit() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")
    with pytest.raises(ValidationError):
        SearchRequest(query="rollback", limit=21)


def test_search_request_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="rollback", client_profile="auditor")
