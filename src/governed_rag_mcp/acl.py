from __future__ import annotations

import os

from .models import ClientProfile

CLIENT_PROFILE_ENV = "GOVERNED_RAG_CLIENT_PROFILE"

_ALLOWED_SOURCES: dict[ClientProfile, frozenset[str]] = {
    ClientProfile.AUDITOR: frozenset({"code", "docs", "decisions", "config", "memory"}),
    ClientProfile.ENGINEER: frozenset({"code", "docs", "decisions"}),
    ClientProfile.RESTRICTED: frozenset({"docs", "decisions"}),
}

# Sensitive configuration must always be explicitly requested, even by an auditor.
IMPLICIT_ALL_SOURCES = frozenset({"code", "docs", "decisions", "memory"})


def resolve_client_profile(value: str | None = None) -> ClientProfile:
    raw = value if value is not None else os.environ.get(CLIENT_PROFILE_ENV)
    try:
        return ClientProfile(str(raw or "").strip().lower())
    except ValueError:
        return ClientProfile.RESTRICTED


def allowed_sources(profile: ClientProfile) -> frozenset[str]:
    return _ALLOWED_SOURCES.get(profile, _ALLOWED_SOURCES[ClientProfile.RESTRICTED])


def sources_for_request(
    profile: ClientProfile, requested_source: str
) -> tuple[list[str], list[str]]:
    allowed = allowed_sources(profile)
    if requested_source == "all":
        return (
            sorted(allowed & IMPLICIT_ALL_SOURCES),
            sorted(IMPLICIT_ALL_SOURCES - allowed),
        )
    if requested_source not in allowed:
        return [], [requested_source]
    return [requested_source], []
