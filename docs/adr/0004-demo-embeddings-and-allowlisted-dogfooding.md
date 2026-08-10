# ADR 0004: Deterministic demo embeddings and allowlisted dogfooding

- Status: Accepted
- Date: 2026-08-10

## Context

Tests and a public demonstration need repeatable embeddings without requiring a model service or distributing private corpus data. Indexing the repository itself demonstrates the complete path, but unrestricted traversal could ingest generated files, credentials, local databases, or machine-specific content.

## Decision

Provide a deterministic normalized hashing embedder as the default for tests and the public demo only. Provide Ollama as an optional environment-selected adapter for semantic embeddings.

Dogfood the indexer against the repository through an explicit allowlist covering Python source, Markdown under `docs`, both READMEs, and `SECURITY.md`.

Reject allowlisted candidates that are symlinks, non-files, over 128 KiB, contain a NUL byte, are invalid UTF-8, or match recognized secret, private-network, or private-path patterns. Parse Python with the standard AST, split Markdown by headings, build a complete shadow SQLite index, check its integrity, flush it, and atomically replace the target.

## Consequences

- Tests and demos are deterministic and require no embedding service.
- The public demo contains only repository content admitted by named patterns.
- The hashing embedder has limited semantic quality and must not be represented as a model-equivalent embedding system.
- Pattern checks reduce accidental disclosure but do not replace review or a dedicated secret scanner.
- A malicious or incorrect contribution under an allowed path can still be indexed.
- Ollama receives complete queries and document chunks and becomes a separate privacy, model-governance, and availability boundary. Remote initial URLs require HTTPS; loopback HTTP remains available for local operation.
- Changing provider, model, or dimensions requires rebuilding the index.

## Alternatives considered

### Bundle a pretrained embedding model

Rejected because it increases artifact size, dependency surface, licensing review, and hardware assumptions for the demo.

### Require Ollama for every run

Rejected because tests would depend on external process state and model availability.

### Recursively index the checkout

Rejected because broad traversal is incompatible with a sanitized public demonstration.

### Treat pattern matching as complete data-loss prevention

Rejected because secret formats and sensitive context are open-ended; human review and independent scanning remain necessary.
