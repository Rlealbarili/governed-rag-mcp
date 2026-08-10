# ADR 0002: FTS5 and sqlite-vec retrieval fused with RRF

- Status: Accepted
- Date: 2026-08-10

## Context

Lexical search is precise for identifiers and exact terminology, while vector search can recover less literal similarity. Their scores have different meanings and scales, so directly averaging BM25 and vector distance would require corpus-specific calibration.

## Decision

Store canonical chunks in SQLite, lexical terms in an FTS5 virtual table, and fixed-dimension vectors in a `sqlite-vec` virtual table.

Support `fts`, `vector`, and `hybrid` modes. In hybrid mode, merge ranked branch results through Reciprocal Rank Fusion using `k0=60`:

```text
score(document) = sum(1 / (60 + rank_in_branch))
```

Use chunk ID as the deterministic tie-breaker. Preserve branch rank, BM25, vector distance, and fused score in each result.

Classify branch agreement as high confidence, an FTS result or vector distance at most `0.65` as medium confidence, and weaker vector-only evidence as low confidence.

## Consequences

- Hybrid ordering does not require normalizing incomparable branch scores.
- Exact and semantic evidence remain inspectable in the response.
- The design remains local and uses one database artifact.
- RRF rank discards score magnitude beyond ordering.
- Confidence thresholds are heuristics and require evaluation against each target corpus.
- Vector retrieval overfetches 100 neighbors before source and project filtering, which can reduce recall for sparse scopes.
- Query embeddings must match the model and dimensions used at index build time.

## Alternatives considered

### FTS-only retrieval

Retained as a mode but not the only strategy because paraphrases and vocabulary mismatch can reduce recall.

### Vector-only retrieval

Retained as a mode but not the default because identifiers and exact phrases are often better served by lexical search.

### Weighted score averaging

Rejected because BM25 and vector distance require calibration and can drift with corpus and model changes.

### Learned reranker

Deferred because it adds model governance, latency, evaluation, and data-disclosure boundaries beyond this reference implementation.
