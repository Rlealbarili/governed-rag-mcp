# ADR 0001: FastMCP stdio and a synchronous core

- Status: Accepted
- Date: 2026-08-10

## Context

The server needs a small MCP integration surface for local hosts without adding an HTTP listener, network identity model, or asynchronous persistence layer. SQLite access and the initial embedding adapters are blocking APIs.

## Decision

Use FastMCP for Python with `stdio` transport. Register exactly three synchronous tools:

- `search_knowledge`
- `list_knowledge_sources`
- `rag_status`

Register one resource, `governed-rag://capabilities`, that reports `async_runtime: false` and the exact public contract.

Keep request handling and retrieval in a synchronous service. FastMCP remains the protocol adapter rather than the domain boundary.

## Consequences

- Local MCP hosts can launch the server without opening a port.
- Protocol framing and tool discovery remain delegated to FastMCP.
- The retrieval service is straightforward to test without an event loop.
- Blocking SQLite and Ollama calls occupy the calling thread.
- `stdio` supplies no user identity, network authentication, TLS, rate limiting, or remote lifecycle management.
- Ordinary logs must not be written to stdout because they can corrupt the MCP stream.
- Scaling requires multiple isolated processes or a separately governed gateway, not an undocumented transport change.

## Alternatives considered

### HTTP or Server-Sent Events transport

Rejected for the initial scope because it creates authentication, TLS, routing, quota, and exposure obligations not solved by the retrieval core.

### Async domain service

Deferred until representative benchmarks show a concurrency requirement. Wrapping blocking dependencies in async syntax would not remove the blocking work.

### Additional administrative MCP tools

Rejected to keep index mutation and policy administration outside the caller-facing retrieval surface.
