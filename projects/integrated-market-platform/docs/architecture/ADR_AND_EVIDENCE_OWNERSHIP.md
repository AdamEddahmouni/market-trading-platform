# ADR and Evidence Ownership

Status: `CURRENT` (2026-09-07) — records the WS07 reconciliation ownership
decision (IMP Reconciliation Program v2, files `17-deletion-consolidation-plan.md`
and `14-open-decisions.md` under `docs/audits/imp-reconciliation/`).

This document fixes ownership for architecture decisions and runtime evidence
types. It does **not** merge, move, or rewrite any artifact; it is an ownership
statement only.

## Canonical ADR home

- **Canonical ADR home: `docs/architecture/`** (markdown). New architecture
  decision records are written here.
- Structured JSON under `docs/superpowers/decisions/` remains as
  machine-readable mirrors where useful; it is not a competing ADR home.
- `ADR-DONOR-001` and `ADR-GRIDIQ-001` live under
  `docs/superpowers/decisions/` (not `docs/research/donors/`). They are
  historical donor-governance records, marked SUPERSEDED, and are not ADR
  homes. GridIQ / DS-340W are **not** IMP donors; independent `storage/*`
  **ADAPT** implementations do not take authorization from ADR-GRIDIQ-001.
  Current identity authority:
  [Donor Authority Supersession Notice](../superpowers/governance/2026-09-07-donor-authority-supersession-notice.md).
- Do not create new competing ADR homes.

Consolidation of the historical three-home duplication is tracked by the
reconciliation backlog; this document fixes ownership now without moving
files.

## Evidence type ownership

Each runtime evidence type keeps its owning domain in G0; no types are merged.

| Evidence type | Owning module | Scope | Disposition |
|---|---|---|---|
| Participant evidence | `src/market_platform_foundation/participant/` | Participant/crowding/derivatives observations | Owned by the participant lane; unchanged |
| `NormalizedLaneEvidence` | `src/market_platform_foundation/cross_lane/evidence.py` | Normalized cross-lane model/lane evidence envelopes | Owned by the cross-lane lane; unchanged |
| `EvidenceV1` | `src/market_platform_foundation/intelligence/contracts/evidence.py` | Intelligence evidence envelopes | Owned by the intelligence domain; unchanged |

A future evidence-homes consolidation (reconciliation backlog BL-0012 / Stream
B) may define a single canonical evidence vocabulary; it must not be executed
as part of G0 and must not break existing envelope contracts.