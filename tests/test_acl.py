from governed_rag_mcp.acl import allowed_sources, resolve_client_profile, sources_for_request
from governed_rag_mcp.models import ClientProfile


def test_invalid_or_missing_profile_fails_closed() -> None:
    assert resolve_client_profile(None) is ClientProfile.RESTRICTED
    assert resolve_client_profile("root-admin") is ClientProfile.RESTRICTED


def test_config_is_auditor_only_and_never_implicit_in_all() -> None:
    assert "config" in allowed_sources(ClientProfile.AUDITOR)
    assert "config" not in allowed_sources(ClientProfile.ENGINEER)
    assert "config" not in allowed_sources(ClientProfile.RESTRICTED)


def test_source_all_reports_implicit_sources_skipped_by_acl() -> None:
    queried, skipped = sources_for_request(ClientProfile.RESTRICTED, "all")

    assert queried == ["decisions", "docs"]
    assert skipped == ["code", "memory"]
