# Phase 3 — verified historical adapter (operational plan)

**Status:** Complete — Phase 3 `PASS` published  
**Plan date:** 2026-08-15  
**Scope:** Phase 3 only  
**Design spec:** [Phase 3 design spec](../specs/2026-08-15-phase-3-verified-historical-adapter-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 | `PASS` |
| Phase 3 design spec | `APPROVED` |
| Phase 3 implementation authorization | `EFFECTIVE` |
| Phase 3 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-A1 | Governance activation |
| WP-A2 | `adapters/equity_intraday_jsonl.py` + registry extension |
| WP-A3 | Normalization reports and idempotency proofs |
| WP-A4 | Assertion registry + evaluator for `ADP-*` and `SAFE-*` |
| WP-A5 | Postreview gate + `phase3.pass_publication` |

## 3. Hard constraints

- Read admitted object from collection only (`EXTERNAL_COLLECTION_READ_ONLY`).
- Offline guard and `ADR-OFF-001` remain in force.
- Adapter registry remains a closed offline allowlist.
