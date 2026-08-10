# Security Policy

Governed RAG MCP is a local `stdio` server and reference implementation. Its controls reduce retrieval and publication risk, but they do not replace deployment identity, process isolation, filesystem permissions, dependency governance, or downstream prompt-injection defenses.

## Reporting a vulnerability

Use the repository hosting platform's private vulnerability-reporting feature. Do not include exploit details, secrets, private indexes, or sensitive logs in a public issue.

If private reporting is unavailable, open a minimal public issue asking the maintainers to establish a private channel. Include no reproduction details until a private channel exists.

A useful private report contains:

- affected version or commit;
- affected component and deployment assumptions;
- minimal reproduction using synthetic data;
- observed and expected behavior;
- impact and required caller privileges;
- proposed mitigation, if known.

Reports are assessed on evidence and impact. No fixed remediation timeline is promised because scope and release capacity vary.

## Supported code

Security fixes target the current maintained branch. Historical commits, forks, modified containers, third-party MCP gateways, external embedding services, and operator-built indexes are outside the project's direct control.

## Security boundaries

### MCP transport

The server uses FastMCP over stdin and stdout. It does not listen on a network socket and does not provide network authentication, TLS, sessions, or rate limiting. The process launcher is responsible for deciding who may start or communicate with the process.

### Access profile

`GOVERNED_RAG_CLIENT_PROFILE` binds one source-access profile to the process environment. Missing or invalid values resolve to `restricted`. The tool caller cannot select a profile in a search request.

This is fail-closed with respect to privilege expansion, not deny-all behavior: `restricted` still permits `docs` and `decisions`. Run separate processes for callers with different trust levels. Protect the process environment from caller modification.

### Index

Search opens the SQLite index in read-only and query-only mode. `rag_status` runs SQLite's integrity check. Offline index construction creates a complete shadow database, flushes it, and atomically replaces the target.

These controls detect some corruption and avoid partial in-place updates. They do not authenticate index origin, encrypt data, enforce retention, or prevent a privileged local actor from replacing the index. Set filesystem ownership and permissions outside the application.

### Retrieved text

Every search result marks text as untrusted context. The server retrieves chunks; it does not evaluate instructions inside them, generate an answer, or authorize downstream actions. MCP hosts must keep retrieved instructions separate from trusted policy and must independently authorize tools.

### Embeddings

The deterministic hashing embedder is for tests and the public demo only. The optional Ollama adapter sends full input text to its configured endpoint. Its initial URL must use HTTPS, except that HTTP is accepted for `localhost` and loopback IP literals; embedded credentials, query strings, and fragments are rejected. Operators must still assess endpoint identity, DNS, redirects, transport, logs, retention, tenancy, model provenance, and availability before enabling it.

### Telemetry

Telemetry contains aggregate counters and average latency only. Query text and chunk text are not recorded by the registry. `rag_status` exposes aggregate profile, source, status, and winning-source counters, which may still reveal coarse activity patterns.

## Secure deployment checklist

- Pin and review Python and container dependencies; run the dependency audit before release.
- Build indexes from reviewed, allowlisted inputs and keep generated databases out of source control.
- Use a dedicated unprivileged operating-system account or container identity.
- Make the index and application code read-only to the serving process where practical.
- Set `GOVERNED_RAG_CLIENT_PROFILE` explicitly even though invalid input falls back to `restricted`.
- Use separate server processes for separate trust domains.
- Keep MCP protocol output on stdout and route operational logs to stderr.
- Restrict access to the optional Ollama endpoint and account for full-text disclosure to it.
- Rebuild the index after changing embedding provider, model, or dimensions.
- Put authentication, authorization, quotas, timeouts, and TLS at any gateway that exposes the process remotely.
- Review aggregate status access if source names or counts are sensitive.
- Back up and rotate indexes according to the data owner's retention policy.

## Secret handling

Never commit credentials, tokens, private keys, real user data, private paths, or generated knowledge databases. Load required secrets from environment variables supplied by an approved secret manager. The repository self-indexer rejects several recognized secret, network, and private-path patterns, but those checks are defense in depth rather than a complete scanner.

## Known residual risks

- Source-class ACLs do not provide row-level, tenant-level, or field-level authorization.
- A compromised launcher or process environment can choose a more privileged profile.
- Aggregate inventory is not filtered by profile.
- Malicious but allowlisted text can contain prompt injection.
- A locally replaced index can contain false or malicious content while still passing SQLite integrity checks.
- Hash collisions and limited semantics reduce demo retrieval quality.
- Configured external embedding endpoints can observe text and become an availability dependency; DNS resolution and redirected destinations are not separately pinned by the adapter.
- Synchronous search can be resource-constrained by expensive local queries; no built-in quota exists.

See [the threat model](docs/threat-model.md) for the detailed trust-boundary analysis.
