# Contributing to Governed RAG MCP

Contributions should preserve the project's narrow public contract, fail-closed behavior, and explicit operational limits. Prefer small changes with evidence over broad refactors.

## Development setup

Prerequisites are Python 3.11 or newer, an environment that can install `sqlite-vec`, and GNU Make.

```bash
make setup
. .venv/bin/activate
make test
```

Run the public self-indexing path against the repository's allowlisted content:

```bash
make demo
```

The demo must only read files admitted by the repository allowlist. Do not add generated databases, private fixtures, real logs, credentials, machine-specific paths, or external service output to a contribution.

## Change workflow

1. State the behavior or documentation gap and its security impact.
2. For behavior changes, add a failing test before the minimal implementation.
3. Keep validation at system boundaries and preserve immutable result construction.
4. Run the focused test while iterating, then run `make test` before proposing the change.
5. Update public documentation in English and Portuguese when the public contract changes.
6. Review the complete diff for secrets, private paths, generated artifacts, and unrelated edits.

Behavior changes are expected to maintain at least 80% branch-aware coverage for the package. Riskier changes should include unit, integration, and end-to-end coverage at the relevant boundary. Documentation-only changes should still run link, sanitization, and contract checks where available.

## Architectural invariants

Changes to these decisions require an ADR and explicit review:

- the public server is FastMCP over `stdio`;
- the MCP surface contains exactly `search_knowledge`, `list_knowledge_sources`, and `rag_status`, plus `governed-rag://capabilities`;
- the retrieval core remains synchronous unless a measured requirement justifies a runtime change;
- Pydantic models validate externally supplied structured data;
- hybrid retrieval uses FTS5 and `sqlite-vec`, fused by RRF;
- missing or invalid environment profiles cannot expand access;
- strict search with no acceptable context returns `NO_RELEVANT_CONTEXT` and no chunks;
- telemetry remains aggregate-only and excludes query and chunk text;
- the hash embedder remains clearly labeled as deterministic demo infrastructure;
- repository dogfooding reads an explicit allowlist and fails closed on unsafe input.

See [the ADR directory](docs/adr/) before changing these boundaries.

## Testing expectations

Tests should be deterministic, isolated, and use synthetic text. They must not require a running external embedding service unless clearly marked and excluded from the default suite.

Cover at least the following when applicable:

- valid and invalid Pydantic input;
- missing, invalid, authorized, and denied ACL profiles;
- FTS, vector, hybrid, and degraded retrieval paths;
- strict low-confidence blocking and all `NO_RELEVANT_CONTEXT` reasons;
- aggregate telemetry with assertions that text is absent;
- malformed, NUL-containing, oversized, symlinked, or sensitive repository input;
- index replacement and read-only query behavior;
- the exact MCP tool and resource surface.

Avoid assertions that depend on nondeterministic rank ties or an external model's changing output. Evaluation changes should report both hit rate at `k` and mean reciprocal rank against explicit expected paths.

## Security requirements

- Never hardcode or commit secrets. Use environment variables populated by an approved secret manager.
- Validate all data at its trust boundary; do not rely on downstream validation.
- Parameterize SQL and keep FTS operators from being interpreted from caller input.
- Do not put query text, chunk text, credentials, or raw exception details in telemetry.
- Preserve read-only serving access to the index.
- Treat retrieved text as attacker-controlled, even when it came from the repository.
- Do not weaken fail-closed behavior to improve apparent result rates.
- Run the dependency audit included in the development toolchain before release-oriented changes.

Report suspected vulnerabilities according to [SECURITY.md](SECURITY.md), not in a public issue with exploit details.

## Documentation style

Public documentation must be factual, reproducible, and free of organization-specific context. Use synthetic examples and relative repository paths. Explain what a control does and what it does not do.

Keep `README.md` as the primary English document and `README.pt-BR.md` equivalent in scope and technical claims. Update architecture, threat model, capabilities, and limits together when behavior changes.

Do not claim guarantees that depend on an MCP host, gateway, external model, container runtime, or operator policy. Do not describe planned behavior as already implemented.

## Pull request checklist

- [ ] The change is scoped and its rationale is documented.
- [ ] Tests were written first for changed behavior and now pass.
- [ ] Package coverage remains at or above 80%.
- [ ] The exact three-tool and one-resource contract is preserved or explicitly reviewed.
- [ ] Security boundaries and failure modes were considered.
- [ ] English and Portuguese public documentation remain aligned.
- [ ] No secrets, private paths, real data, generated indexes, or unrelated files are present.
- [ ] The final diff and dependency audit were reviewed.
