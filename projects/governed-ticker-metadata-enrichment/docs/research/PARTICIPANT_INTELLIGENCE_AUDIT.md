# Participant / Whale Intelligence — Current State Audit (Deliverable 1)

**Date:** 2026-08-19  
**Status:** Baseline audit before PI1–PI2 implementation  
**Authority:** Complements `SWIM_WITH_THE_WHALES.md`; does not replace Revision 3 whale families

---

## Executive summary

The platform already contains a rigorous **eight-family whale evidence scaffold** (Revision 3 Phases 9–16, all PASS on fixtures). That work is **KEEP** and becomes the **raw ingestion layer** for Participant Intelligence — not a replacement architecture.

Participant Intelligence (PI-series) adds a **higher semantic layer**:

```text
whale ledger envelope (8 families)
  → participant identity (PI1)
  → participant action semantics (PI2)
  → mechanism / skill / copyability (PI3+)
  → cross-lane ParticipantEvidence
```

The mature goal is **not** a large-trade scanner. It is conditional **Swim With the Whales** research.

---

## Existing work classification

| Area | Location | Verdict |
|---|---|---|
| 8-family WhaleLedger + envelopes | `providers/whale_ledger.py`, `providers/envelope.py` | **KEEP** — ingestion substrate |
| EDGAR Form 4/13D/G/13F vocabulary | `donor_patterns/edgar_whale.py` | **EXTEND** → PI action semantics |
| Institutional feature aggregator | `features/institutional.py` | **REFACTOR** — currently neutral/count only; consume PI actions |
| Strategy WHALE_ALIGNED/CONTRARIAN | `strategy/strategy_spec.py`, `strategy/interpretation.py` | **EXTEND** — mechanism-aware abstention |
| Institutional Flow UI (8 tabs) | `ui/src/components/institutional/` | **KEEP** — add Whales semantic view later |
| Cross-lane evidence bus | `cross_lane/evidence.py` | **EXTEND** — PARTICIPANT_INTELLIGENCE lane |
| Order Flow CVD/OFI/metaorder | `order_flow/*` | **KEEP** — Order Flow owns primitives |
| Futures COT positioning | `futures/positioning.py` | **KEEP** — Futures owns semantics |
| Options signed flow | `contracts/options.py`, O5 | **KEEP** — Options owns semantics |
| Short Squeeze causal states | `donor_bridge/*`, SS lane | **KEEP** — consumes ParticipantEvidence |
| Market Context contracts | `contracts/market_context.py` | **KEEP** — Context for intent timing |
| Crypto / prediction participant docs | `ON_CHAIN_INTELLIGENCE.md`, `PREDICTION_MARKET_WHALE_INTELLIGENCE.md` | **RESEARCH_FIRST** |
| Donor Unusual Whales API | `internship-project-main` | **RESEARCH_FIRST** — reimplement as platform adapter |
| `futures_positioning` vs `futures_depth` ledger naming | `whale_ledger.py` | **REFACTOR** — PI consumes both without duplicating COT |
| Universal whale score | — | **REMOVE** from scope (correctly absent) |
| Auto copy-trading execution | doctrine | **REMOVE** from scope (forbidden) |

---

## Pipeline traces (summary)

### Regulatory disclosure (Phase 9)

```text
biya_disclosures.json → FixtureEdgarDisclosureProvider
  → filing_to_disclosure_event() / normalize_edgar_filing()
  → build_disclosure_envelope()
  → WhaleLedger (regulatory_disclosure)
  → [NEW] participant.bridge → ParticipantAction
  → DisclosureWorkspacePanel / InstitutionalFlowWorkspacePanel
```

### Order flow / metaorder (Phase 10, OF11 planned)

```text
nvda_order_flow_slice → order_flow_lane → WhaleLedger (order_flow)
  → Order Flow engines (CVD, OFI) → cross_lane signals
  → [PI6] MetaorderEvidence (infer only; no invented identity)
```

### Options large activity (Phase 11)

```text
BIYA options fixture → options_lane → WhaleLedger (options)
  → Options O5 signed flow (owner) → PI consumes, does not reinterpret
```

### COT / futures positioning

```text
fixture_futures_positioning → futures/positioning.py (F4 owner)
  → FUTURES_POSITIONING_CROWDED_* cross-lane signals
  → PI11 cross-asset participant context (consume only)
```

---

## Gaps vs target Participant Intelligence spec

| Requirement | Prior state | PI milestone |
|---|---|---|
| Canonical participant identity + confidence | Absent | **PI1** (implemented) |
| Canonical ParticipantAction | Absent | **PI2** (implemented) |
| Form 4 transaction semantics (P/S vs grant/exercise) | Partial in `edgar_whale.py` | **PI2** (extended) |
| 13F PIT copyability flags | Implicit lag note only | **PI2** quality flags |
| Mechanism / null-hypothesis engine | Absent | **PI7** |
| Participant skill (walk-forward) | Absent | **PI5** |
| Copyability / entry quality | Absent | **PI9** |
| Metaorder lifecycle | OF11 NOT STARTED | **PI6** + OF11 |
| Cross-lane ParticipantEvidence | Absent | **PI3** / SHARED P3 |
| Activist 13D structured extraction | Event type only | **PI3** |
| Crypto wallet / entity PIT labels | Docs only | **PI14** |
| Dedicated Whales UI semantic panel | 8-family aggregator only | Post-PI3 |

---

## Tests inventory

| Layer | Tests |
|---|---|
| EDGAR ingest | `tests/providers/test_providers.py` |
| Whale families | `tests/providers/test_*.py` (phases 9–16) |
| Donor patterns | `tests/donor_patterns/test_donor_patterns.py` |
| Strategy whale abstention | `tests/phase6/test_strategy.py` |
| Institutional UI | `InstitutionalFlowWorkspacePanel.test.tsx` |
| **Participant contracts** | `tests/contracts/test_participant_contract.py` (new) |

---

## Related documents

- `PARTICIPANT_TARGET_ARCHITECTURE.md`
- `PARTICIPANT_DISCREPANCY_REGISTER.md`
- `PARTICIPANT_DATA_CAPABILITY_GAP_ANALYSIS.md`
- `PARTICIPANT_RESEARCH_PLAN.md`
- `PARTICIPANT_GLOSSARY.md`
- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` (PI-series integrated)
