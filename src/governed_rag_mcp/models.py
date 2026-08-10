from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SearchMode = Literal["hybrid", "vector", "fts"]
SearchSource = Literal["all", "code", "docs", "decisions", "config", "memory"]
DocumentSource = Literal["code", "docs", "decisions", "config", "memory"]
ConfidenceMode = Literal["normal", "strict"]
ConfidenceLevel = Literal["high", "medium", "low"]


class ClientProfile(str, Enum):
    AUDITOR = "auditor"
    ENGINEER = "engineer"
    RESTRICTED = "restricted"


class Status(str, Enum):
    PASS = "PASS"  # noqa: S105 - protocol status, not a credential.
    NO_RELEVANT_CONTEXT = "NO_RELEVANT_CONTEXT"


class NRCReason(str, Enum):
    ACL_DENIED = "acl_denied"
    PLANE_FAILED = "plane_failed"
    STRICT_BLOCKED_LOW = "strict_blocked_low"
    NO_RESULTS = "no_results"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    mode: SearchMode = "hybrid"
    source: SearchSource = "all"
    project: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9.-]+$"
    )
    confidence: ConfidenceMode = "normal"

    @field_validator("query")
    @classmethod
    def query_must_have_visible_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must contain visible text")
        return normalized


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    path: str = Field(min_length=1, max_length=500)
    source: DocumentSource
    project: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9.-]+$")
    text: str = Field(min_length=1, max_length=100_000)
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=1, ge=1)


class ResultScores(BaseModel):
    rrf: float
    vector_rank: int | None = None
    vector_distance: float | None = None
    fts_rank: int | None = None
    fts_bm25: float | None = None


class SearchResult(BaseModel):
    id: str
    path: str
    source: str
    project: str
    start_line: int
    end_line: int
    text: str
    text_is_untrusted_context: bool = True
    confidence_level: ConfidenceLevel
    scores: ResultScores


class Coverage(BaseModel):
    requested_source: str
    queried_sources: list[str] = Field(default_factory=list)
    skipped_by_acl: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None


class SearchResponse(BaseModel):
    status: Status
    results: list[SearchResult]
    coverage: Coverage
    no_relevant_context_reason: NRCReason | None = None
    relevance: dict[str, float | int | None] = Field(default_factory=dict)


class RetrievalMetrics(BaseModel):
    query_count: int
    k: int
    hit_rate_at_k: float
    mrr: float
