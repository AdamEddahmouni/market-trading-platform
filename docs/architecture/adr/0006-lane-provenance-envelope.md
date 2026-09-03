# ADR-0006: Lane-Specific Data Provenance Envelope

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-01 |

## Context

TD-002: Lane UI surfaces reused generic handoff timestamps or session `as_of` for freshness display. Paper decision `source_time` was solved separately; lane payloads lacked a consistent contract.

## Decision

1. Workspace and paper portfolio API responses attach `lane_provenance`:
   - `lane_id` — lane identifier
   - `source_time` — epoch ns when available from lane payload (optional)
   - `source_kind` — `lane_payload` | `context_as_of` | `unknown`
   - `retrieved_at` — server wall time when response was built (epoch ns)
2. Frontend uses `laneProvenance.ts` for extract/format/stale — no per-component timestamp logic.
3. Paper lane drafts prefer `lane_provenance.source_time` over handoff time when `source_kind !== unknown`.
4. `retrieved_at` is never shown as data freshness.

## Consequences

- Lane panels show honest freshness labels.
- Legacy payloads without envelope degrade via client fallback without fabricating precision.
- Handoff time remains valid only when lane source time is genuinely unavailable.

## References

- `src/market_platform_foundation/ui_api/lane_provenance.py`
- `ui/src/components/workspace-module-shared/laneProvenance.ts`
- TD-002 closure (2026-09-01 operational hardening)
