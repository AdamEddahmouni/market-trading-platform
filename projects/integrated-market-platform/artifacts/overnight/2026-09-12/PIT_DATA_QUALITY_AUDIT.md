# PIT and data quality audit

**Lane:** F | **Date:** 2026-09-12  
**Basis:** `pit-infrastructure-audit.json` + ADR-PIT-001 / ADR-RDATA-001

## Strengths

- DECISION-RESEARCH-001: preregistered cards, `pit_gate.py`, harness, offline invariants DEC-PIT-001 etc.
- Runtime: `pit_joins.py`, `bitemporal_store.py` for market joins.
- FTEP: temporal law in `paper_forward_bridge/temporal.py` + protocol SHA binding.
- Canonical hashing: `canonical.py` for replay integrity.

## Gaps

| ID | Issue | Severity | Overnight action |
|---|---|---|---|
| PIT-A-001 | No single PIT export API module | Medium | Spec only |
| PIT-A-002 | Durable evidence store gaps for research runs | High | DEFER (EVIDENCE) |
| PIT-A-003 | stock_data Parquet export sibling to IMP kernel | Low | Document bridge |

## Safe isolated tasks (future Wave B)

1. Add `docs/engineering/PIT_OPERATOR_GUIDE.md` index (no WORK_LOG).
2. Thin read-only `tools/research/pit_inventory.py` listing contract paths (stdlib only).

## Foreground

Manifest freeze, FTEP-V1-001 activation artifacts → **no overnight edits**.
