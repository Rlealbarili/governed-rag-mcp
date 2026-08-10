from __future__ import annotations

import json
import time
from pathlib import Path

from .acl import sources_for_request
from .database import connect_readonly
from .embeddings import Embedder
from .errors import EmbeddingError, GovernedRagError
from .fts import build_fts_query
from .fusion import reciprocal_rank_fusion
from .models import (
    ClientProfile,
    ConfidenceLevel,
    Coverage,
    NRCReason,
    ResultScores,
    SearchRequest,
    SearchResponse,
    SearchResult,
    Status,
)
from .observability import MetricsRegistry

VECTOR_OVERFETCH = 100
SOURCE_SLOTS = 5

_FTS_WITHOUT_PROJECT = """select c.*, bm25(chunks_fts) as bm25
    from chunks_fts
    join chunks c on c.id = chunks_fts.id
    where chunks_fts match ? and c.source in (?, ?, ?, ?, ?)
    order by bm25(chunks_fts)
    limit ?"""

_FTS_WITH_PROJECT = """select c.*, bm25(chunks_fts) as bm25
    from chunks_fts
    join chunks c on c.id = chunks_fts.id
    where chunks_fts match ? and c.source in (?, ?, ?, ?, ?) and c.project = ?
    order by bm25(chunks_fts)
    limit ?"""


def _matches_scope(row: dict[str, object], sources: set[str], project: str | None) -> bool:
    return str(row["source"]) in sources and (project is None or row["project"] == project)


def _database_float(value: object, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise GovernedRagError("index_contract_invalid", f"invalid numeric field: {field}")
    return float(value)


def _database_int(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise GovernedRagError("index_contract_invalid", f"invalid integer field: {field}")
    return value


def _confidence(scores: dict[str, object]) -> ConfidenceLevel:
    has_fts = scores.get("fts_rank") is not None
    has_vector = scores.get("vector_rank") is not None
    if has_fts and has_vector:
        return "high"
    distance = scores.get("vector_distance")
    if has_fts or (distance is not None and _database_float(distance, "distance") <= 0.65):
        return "medium"
    return "low"


class SearchService:
    def __init__(
        self,
        *,
        index_path: Path,
        embedder: Embedder,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.index_path = index_path
        self.embedder = embedder
        self.metrics = metrics or MetricsRegistry()

    def _fts_search(self, request: SearchRequest, sources: list[str]) -> list[dict[str, object]]:
        fts_query = build_fts_query(request.query)
        if len(sources) > SOURCE_SLOTS:
            raise GovernedRagError("source_contract_invalid", "source contract invalid")
        padded_sources = [*sources, *(["__denied__"] * (SOURCE_SLOTS - len(sources)))]
        parameters: list[object] = [fts_query, *padded_sources]
        if request.project:
            parameters.append(request.project)
        parameters.append(request.limit * 4)
        statement = _FTS_WITH_PROJECT if request.project else _FTS_WITHOUT_PROJECT
        with connect_readonly(self.index_path) as connection:
            rows = connection.execute(statement, parameters).fetchall()
        return [{**dict(row), "bm25": _database_float(row["bm25"], "bm25")} for row in rows]

    def _vector_search(self, request: SearchRequest, sources: list[str]) -> list[dict[str, object]]:
        with connect_readonly(self.index_path, vector=True) as connection:
            metadata = {
                str(row["key"]): str(row["value"])
                for row in connection.execute(
                    "select key, value from metadata where key in (?, ?)",
                    ("embedding_model", "embedding_dimensions"),
                ).fetchall()
            }
            if metadata != {
                "embedding_model": self.embedder.model_name,
                "embedding_dimensions": str(self.embedder.dimensions),
            }:
                raise EmbeddingError("embedding_contract_mismatch")
            embedding = self.embedder.embed(request.query)
            rows = connection.execute(
                """select c.*, v.distance as distance
                   from chunks_vec v
                   join chunks c on c.id = v.id
                   where v.embedding match ? and k = ?
                   order by v.distance""",
                (json.dumps(embedding, separators=(",", ":")), VECTOR_OVERFETCH),
            ).fetchall()
        filtered = [
            dict(row) for row in rows if _matches_scope(dict(row), set(sources), request.project)
        ]
        return [
            {**row, "distance": _database_float(row["distance"], "distance")}
            for row in filtered[: request.limit * 4]
        ]

    def _to_result(self, row: dict[str, object]) -> SearchResult:
        raw_scores = row["scores"]
        assert isinstance(raw_scores, dict)
        return SearchResult(
            id=str(row["id"]),
            path=str(row["path"]),
            source=str(row["source"]),
            project=str(row["project"]),
            start_line=_database_int(row["start_line"], "start_line"),
            end_line=_database_int(row["end_line"], "end_line"),
            text=str(row["text"]),
            confidence_level=_confidence(raw_scores),
            scores=ResultScores.model_validate(raw_scores),
        )

    def _record(
        self,
        request: SearchRequest,
        profile: ClientProfile,
        response: SearchResponse,
        started: float,
    ) -> None:
        winner = response.results[0].source if response.results else "none"
        self.metrics.record(
            profile=profile.value,
            requested_source=request.source,
            status=response.status.value,
            winning_source=winner,
            latency_ms=(time.monotonic() - started) * 1000,
        )

    def search(self, request: SearchRequest, *, profile: ClientProfile) -> SearchResponse:
        started = time.monotonic()
        sources, skipped = sources_for_request(profile, request.source)
        coverage = Coverage(
            requested_source=request.source,
            queried_sources=sources,
            skipped_by_acl=skipped,
        )
        if not sources:
            response = SearchResponse(
                status=Status.NO_RELEVANT_CONTEXT,
                results=[],
                coverage=coverage,
                no_relevant_context_reason=NRCReason.ACL_DENIED,
            )
            self._record(request, profile, response, started)
            return response

        fts_rows: list[dict[str, object]] = []
        vector_rows: list[dict[str, object]] = []
        try:
            if request.mode in {"hybrid", "fts"}:
                fts_rows = self._fts_search(request, sources)
            if request.mode in {"hybrid", "vector"}:
                vector_rows = self._vector_search(request, sources)
        except EmbeddingError as exc:
            if request.mode == "vector":
                coverage.failed_sources = sources
                response = SearchResponse(
                    status=Status.NO_RELEVANT_CONTEXT,
                    results=[],
                    coverage=coverage,
                    no_relevant_context_reason=NRCReason.PLANE_FAILED,
                )
                self._record(request, profile, response, started)
                return response
            coverage.degraded = True
            coverage.degraded_reason = exc.code
        except GovernedRagError:
            raise

        fused = reciprocal_rank_fusion(
            vector_rows=vector_rows,
            fts_rows=fts_rows,
            limit=request.limit,
        )
        candidates = [self._to_result(row) for row in fused]
        strict_blocked = False
        if request.confidence == "strict":
            strict_blocked = bool(candidates)
            candidates = [result for result in candidates if result.confidence_level != "low"]

        if not candidates:
            reason = NRCReason.STRICT_BLOCKED_LOW if strict_blocked else NRCReason.NO_RESULTS
            response = SearchResponse(
                status=Status.NO_RELEVANT_CONTEXT,
                results=[],
                coverage=coverage,
                no_relevant_context_reason=reason,
            )
        else:
            distances = [
                r.scores.vector_distance for r in candidates if r.scores.vector_distance is not None
            ]
            bm25 = [r.scores.fts_bm25 for r in candidates if r.scores.fts_bm25 is not None]
            response = SearchResponse(
                status=Status.PASS,
                results=candidates,
                coverage=coverage,
                relevance={
                    "top_vector_distance": min(distances) if distances else None,
                    "top_fts_bm25": min(bm25) if bm25 else None,
                    "top_rrf": max(r.scores.rrf for r in candidates),
                },
            )
        self._record(request, profile, response, started)
        return response

    def list_sources(self) -> list[dict[str, object]]:
        with connect_readonly(self.index_path) as connection:
            rows = connection.execute(
                "select source, count(*) as chunks from chunks group by source order by source"
            ).fetchall()
        return [{"source": str(row["source"]), "chunks": int(row["chunks"])} for row in rows]

    def status(self) -> dict[str, object]:
        with connect_readonly(self.index_path) as connection:
            integrity = connection.execute("pragma integrity_check").fetchone()[0]
            chunks = int(connection.execute("select count(*) from chunks").fetchone()[0])
        return {
            "status": "PASS" if integrity == "ok" else "HOLD",
            "integrity": integrity,
            "chunks": chunks,
            "sources": self.list_sources(),
            "telemetry": self.metrics.snapshot(),
        }
