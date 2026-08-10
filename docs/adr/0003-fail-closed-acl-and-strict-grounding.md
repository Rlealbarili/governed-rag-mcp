# ADR 0003: Environment-bound ACL and strict grounding

- Status: Accepted
- Date: 2026-08-10

## Context

An MCP tool argument is caller-controlled and therefore cannot establish the caller's own privilege. Retrieval also needs a stable absence contract so weak or unauthorized context is not mistaken for a useful answer.

## Decision

Bind the source-access profile through `GOVERNED_RAG_CLIENT_PROFILE`. The request schema does not expose a profile argument. Missing, empty, and unknown values resolve to `restricted`, which cannot expand access.

Authorize source classes as follows:

| Profile | Sources |
| --- | --- |
| `restricted` | `docs`, `decisions` |
| `engineer` | `code`, `docs`, `decisions` |
| `auditor` | `code`, `docs`, `decisions`, `config`, `memory` |

Exclude `config` from implicit `source=all`, including for `auditor`.

Make `strict` the public tool default. Remove low-confidence candidates in strict mode. Whenever no authorized, available, and sufficiently relevant context remains, return exactly `NO_RELEVANT_CONTEXT`, an empty result list, coverage, and a structured reason.

## Consequences

- Callers cannot self-assign a more privileged profile in tool input.
- Invalid deployment configuration falls back to the least privileged defined profile.
- Unauthorized requests and weak retrieval cannot return chunks under a success-like status.
- Consumers must handle absence and coverage as normal protocol outcomes.
- One process has one trust profile; mixed-trust callers need separate processes and external identity binding.
- `restricted` is least privilege, not deny-all: it allows documentation and decisions.
- Aggregate source and status tools are not filtered by profile and can reveal names and counts.
- Confidence remains retrieval evidence, not a truth claim.

## Alternatives considered

### Caller-supplied role

Rejected because an unverified argument is not an identity or authorization credential.

### Unknown profile means auditor or engineer

Rejected because configuration mistakes would expand access.

### Return low-confidence chunks with warnings

Rejected for strict mode because downstream consumers can ignore warnings while still using the text.

### Empty successful response without a reason

Rejected because it conflates ACL denial, infrastructure failure, strict filtering, and genuine no-match outcomes.
