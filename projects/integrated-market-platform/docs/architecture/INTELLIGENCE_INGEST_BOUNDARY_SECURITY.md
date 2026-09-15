# Intelligence ingest boundary security (Lane G)

**Status:** Active — analysis-only enrichment; no execution authority  
**Schema ID:** `intelligence/ingest/agent_enrichment/1.0.0`

## Scope

HTTP and payload guards for `/intelligence/ingest/enrichment` before external agent automation expands. This plane cannot submit or cancel orders, mutate positions/risk/strategy state, change credentials, or alter `MODE_AUTHORITY`.

## Authentication posture

| Mode | Ingest behavior |
|------|-----------------|
| `LOOPBACK_TRUST` (default) | Implicit local ADMIN; suitable for single-user loopback workstations only |
| `ENFORCED` | Session required; capability `intelligence.ingest.write` (OPERATOR/ADMIN) |

Set `IMP_INTELLIGENCE_INGEST_REQUIRE_ENFORCED=true` to reject ingest while `LOOPBACK_TRUST` remains active (fail closed for hosted/tunneled APIs).

## Payload limits (fail closed)

| Guard | Limit |
|-------|-------|
| HTTP body | 65 536 bytes (`Content-Length` checked before read) |
| `source_refs` | 32 entries |
| `raw_reference` / URL-like fields | `http`/`https` only; no `file:` or local paths; max 2048 chars |
| `claim_body` text | 16 384 chars aggregate |
| `contradiction_refs` | 64 entries |
| `metadata` / nested JSON | depth ≤ 8, ≤ 64 top-level keys |
| `provenance` | required `ingest_plane` / `source` / `worker_id`; no secret-like keys |

Implementation: `intelligence/ingest/boundary.py`.

## Agent identity

- `agent_id` must match `[a-zA-Z][a-zA-Z0-9._-]{0,127}`.
- `bot_role` must align with `claim_type` (prevents role impersonation).
- Forbidden mutation vocabulary is scanned recursively in `intelligence/ingest/runtime.py`.

## Outbound workers (Lane A)

Typed hooks in `intelligence/ingest/outbound_policy.py` (HTTPS-only targets, secret header denial, timeout/retry env). Lane A owns the worker dispatch loop; this module is policy-only.

## Tests

- `tests/intelligence/test_agent_enrichment_ingest_enforced_http.py` — `INTELLIGENCE_BOUNDARY_SECURITY_HARDENED` acceptance (ENFORCED HTTP)
- `tests/intelligence/test_agent_enrichment_ingest_boundary.py` — payload and outbound policy unit guards

## References

- [GROK_INTELLIGENCE_INGEST_API.md](GROK_INTELLIGENCE_INGEST_API.md)
- [OPERATOR_AUTH_ONBOARDING.md](../engineering/OPERATOR_AUTH_ONBOARDING.md)
- [MODE_AUTHORITY.md](MODE_AUTHORITY.md)
