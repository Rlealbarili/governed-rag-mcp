from __future__ import annotations

import re

from .errors import GovernedRagError


def build_fts_query(query: str) -> str:
    """Convert all user terms to quoted literals so FTS operators cannot execute."""

    terms = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    if not terms:
        raise GovernedRagError("invalid_query", "The query contains no searchable terms.")
    return " ".join(f'"{term}"' for term in terms)
