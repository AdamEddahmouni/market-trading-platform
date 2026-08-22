# DECISION-RESEARCH-001 — Governed decision research and strategy synthesis (design spec)

**Status:** Design complete — pending principal review
**Spec date:** 2026-08-22
**Scope:** Platformization milestone **A** (decision research / strategy synthesis):
preregistered experiment families with walk-forward out-of-sample evaluation on
PIT-gated decision examples, and research-only strategy synthesis that feeds the
operator UI — **manual orders only, no automatic strategy promotion**.
**Prerequisites:** P3.3 decision-research foundation (`research/decision_research/`),
Phase 5R `PASS`, Phase 6 preregistration `PASS`, SHARED P4 fixture scope, Platformization
P0–P3.3 landed (`main` at `94f4ed7`)

## 1. Purpose

The platform can already observe live markets, run internal paper execution, and
discover candidates. What it cannot yet do is turn lane evidence into **governed,
reproducible research claims**: which combinations of evidence (squeeze state, order
flow, options, market context, participant crowding, discovery) add measurable
out-of-sample value over a baseline — and present the result as a decision-grade
package a human can act on.

This milestone delivers that in three parts:

1. **Preregistered experiment cards** — hypotheses are declared with a hash-bound
   card (features, outcome, inclusion rules, primary metric) **before** any
   evaluation result exists.
2. **Walk-forward OOS harness** — the existing short-squeeze experiment family runs
   on PIT-gated decision examples; reported metrics come **only** from
   out-of-sample folds. Nothing is ever reported as validated without OOS evidence.
3. **Strategy synthesis** — lane evidence is packaged into `DecisionCandidate`
   objects with separate relevance/direction/quality/freshness fields, an
   evidence-cited thesis, and explicit contradiction handling. **There is no
   composite score, no % bullish, and no automatic order creation.** Candidates
   surface in the operator UI; a human may place a manual paper order that records
   the candidate as provenance.

This is Platformization milestone **A** per the [P3.2 roadmap note](../research/PLATFORMIZATION_ROADMAP.md)
("governed combination research, manual orders only") and precedes P4 broker
adapters so that execution-contract work begins only after research evidence
exists.

## 2. Non-negotiable constraints

- **PIT gate:** every decision example must pass `validate_temporal_example` —
  all features `available_time_ns <= decision_time_ns`, outcome
  `outcome_time_ns > decision_time_ns`.
- **Preregistration:** no evaluation result is reportable without a hash-bound,
  registry-recorded experiment card.
- **OOS-only reporting:** primary metrics are computed exclusively on
  out-of-sample folds of the walk-forward harness.
- **No composite score:** synthesis emits separate evidence fields only;
  contradictions produce `MIXED` with no direction hypothesis, never an averaged
  score.
- **Manual orders only:** there is no code path from research output to order
  creation. Research outputs carry `execution_authority: NONE` and
  `auto_strategy_promotion: False` (already enforced by `research/decision_research/runner.py`).
- **No retroactive discovery:** Finviz-derived features require a prospective
  capture; `NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION` is enforced at example
  construction.
- **Fail closed:** insufficient samples yield `INSUFFICIENT_DATA` /
  `NEEDS_PROSPECTIVE_VALIDATION`, never `SUPPORTED`.

## 3. Architecture

```text
admitted fixtures (BIYA / NVDA / BOXL / ES slices)  +  prospective Finviz captures
        ↓
decision example builder (PIT-gated)        research/decision_research/examples.py
        ↓
preregistered experiment cards             research/decision_research/cards.py + registry
        ↓
walk-forward OOS harness                   research/decision_research/harness.py
        ↓
family evaluation (SS first)               research/decision_research/experiments.py (extended)
        ↓
strategy synthesis (DecisionCandidate)     research/decision_research/synthesis.py
        ↓
operator UI (What Matters Now / evidence drawer)  →  manual paper OrderTicket
        ↓
paper ledger fill (candidate_id provenance, optional join)
```

Consumed by the harness: lane evidence snapshots already published by the P3.2
`WorkspaceEvidence` adapters (separate relevance / direction / quality /
freshness per lane), the Phase 5R forecast substrate, and SHARED P4 frictions
(spread + slippage cost model).

## 4. Decision examples

The P3.3 `ResearchExample` model is the base. This milestone formalizes the
feature envelope:

```json
{
  "example_id": "ss-ex-000042",
  "instrument_id": "BIYA",
  "decision_time_ns": 1780000000000000000,
  "features": [
    {
      "evidence_family": "SQUEEZE_STATE",
      "available_time_ns": 1779999990000000000,
      "quality_flags": [],
      "freshness_ms": 10,
      "authority": "IMP_DERIVED",
      "value": {"state": "IGNITION", "fuel_pct": 41.2}
    }
  ],
  "outcome_time_ns": 1780000300000000000,
  "outcome": {
    "positive": true,
    "forward_return_bps": 214.0,
    "horizon_ns": 30000000000,
    "costs_bps": 31.0,
    "cost_model_version": "execution_book_aware_v1"
  }
}
```

Rules:

- `evidence_family` is a controlled vocabulary (SQUEEZE_STATE, ORDER_FLOW_CVD,
  MICROSTRUCTURE, OPTIONS_DEALER, CATALYST, ATTENTION, PARTICIPANT_CROWDING,
  FINVIZ_DISCOVERY, MACRO_CONTEXT).
- Every feature carries `available_time_ns`; the PIT gate rejects any feature
  available after `decision_time_ns`.
- Outcomes are **mark-based forward returns** over a declared horizon, with
  frictions applied from the SHARED P4 / OF9 cost model (`execution_book_aware_v1`).
  No fill is required for an experiment outcome — manual paper fills are an
  optional attribution join, never a prerequisite.
- A Finviz feature requires `capture_present: true` referencing a committed
  prospective capture; otherwise the example is rejected
  (`NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION`).

## 5. Preregistration contract

New `ExperimentCard` model (`research/decision_research/cards.py`), building on
Phase 6 preregistration semantics (`strategy/preregistration.py`):

| Field | Meaning |
|---|---|
| `card_id` | `CARD-<uuid5>` over the card body |
| `experiment_id` | e.g. `SS-OF-CAT` |
| `family` | e.g. `SHORT_SQUEEZE` |
| `hypothesis_label` | `CONFIRMATORY` / `EXPLORATORY` |
| `baseline_id` | required; e.g. `SS-BASE` |
| `added_evidence` | evidence families added over baseline |
| `feature_spec` | per family: required, min freshness, min quality |
| `outcome_spec` | horizon_ns, return basis, cost_model_version |
| `inclusion_criteria` / `exclusion_criteria` | declared, machine-checkable |
| `primary_metric` | one metric, e.g. `oos_precision_delta_vs_baseline` |
| `min_sample_oos` | minimum OOS examples for any SUPPORTED claim |
| `evaluation_window` | fold schema (expanding window), fixed seed-free fold rule |
| `preregistered_at_ns` | registry timestamp |
| `card_hash` | SHA-256 of canonical card bytes |

Registry: `research/decision_research/registry.py` persists cards to
`evidence/research/experiment-cards/` (committed, immutable, mirroring the
hash-bound acceptance convention of `evidence/strategy/<hash>/`) and binds
`card_hash` into every run record.
`verify_experiment_card_registration(card, run)` fails closed when the hash is
absent or unbound.

**Relationship to Phase 6 preregistration:** the card registry builds on the
Phase 6 pattern in `strategy/preregistration.py` — `canonical_bytes` /
`sha256_bytes` hashing, identity-hash binding, and fail-closed verification —
but is a distinct card-level contract. Phase 6 `StrategySpec`
(`strategy/strategy_spec.py`) is strategy-level (alignment type, hypothesis,
evidence requirements on the EQ-1 equity fixture), and its
`verify_preregistration(preregistration, strategy_spec)` remains unchanged.
`baseline_id: SS-BASE` refers to the canonical squeeze-baseline **card** in this
registry, not to a Phase 6 strategy. Phase 6 `StrategyInterpretation` outputs
are not a candidate direction source (see §8); no reconciliation between Phase 6
strategies and DEC cards is required.

## 6. Experiment families

`SHORT_SQUEEZE` is the first family (existing `SHORT_SQUEEZE_EXPERIMENTS` in
`experiments.py`, now bound to cards):

| Experiment | Label | Added evidence over SS-BASE |
|---|---|---|
| SS-BASE | CONFIRMATORY | (canonical squeeze baseline) |
| SS-OF | CONFIRMATORY | ORDER_FLOW_CVD |
| SS-CAT | CONFIRMATORY | CATALYST |
| SS-MKT | CONFIRMATORY | MARKET_CONTEXT |
| SS-OF-CAT | EXPLORATORY | ORDER_FLOW_CVD + CATALYST |
| SS-FV-DISC | EXPLORATORY | FINVIZ_DISCOVERY |

Future families are declared but not implemented: `ORDER_FLOW` (microstructure
forecast vs next mid), `OPTIONS_VRP` (vol risk premium), `MC_SURPRISE`
(surprise vs baseline sentiment), `PARTICIPANT_CROWDING`. Each future family
gets cards in the same registry before any implementation work.

`evaluate_experiment` retains its fail-closed status mapping but now evaluates
**only on OOS folds** and refuses to run without a bound card:

```text
n_oos < min_sample_oos                    -> NEEDS_PROSPECTIVE_VALIDATION
n_oos == 0 (or gate failure)              -> INSUFFICIENT_DATA
confirmatory, OOS edge >= threshold       -> SUPPORTED
otherwise                                 -> INCONCLUSIVE / NOT_SUPPORTED (per preregistered rule)
```

## 7. Walk-forward OOS harness

New `research/decision_research/harness.py`:

- **Deterministic folds:** examples are ordered by `decision_time_ns` (ties broken
  by `example_id`), and folds are derived from position — no RNG. Default schema
  is **expanding window** (train grows, OOS block moves forward), configurable to
  rolling window via the card `evaluation_window`. The foundation's existing
  `chronological_split` (0.6 / 0.2 / 0.2, in
  `research/decision_research/pit_gate.py`) remains available as the single-split
  case; harness folds generalize it.
- **No training leakage:** fold boundaries are fixed by timestamps; a feature in
  a later fold is never visible to an earlier fold decision, and the PIT gate is
  re-applied per fold.
- **Determinism under network denial:** the harness imports no provider path and
  performs no I/O beyond admitted fixtures; identical inputs produce identical
  run records and hashes (mirrors Phase 6 `DET-001`).
- **Run record:** `evidence/research/runs/<run_id>.json` with family, fold
  boundaries, per-experiment OOS metrics, `incremental_vs_baseline`, bound card
  hashes, and `execution_authority: NONE`.

## 8. Strategy synthesis

New `research/decision_research/synthesis.py`:

```text
build_decision_candidate(instrument, prediction_cutoff, lane_evidence) -> DecisionCandidate
```

`DecisionCandidate` fields:

| Field | Semantics |
|---|---|
| `candidate_id` | `CAND-<uuid5>` |
| `instrument_id`, `generated_at_ns` | identity |
| `direction_hypothesis` | `LONG` / `SHORT` / `NEUTRAL` / `NO_HYPOTHESIS` |
| `thesis` | evidence-cited narrative (display only) |
| `supporting_evidence` / `contradicting_evidence` | separate lists, per-piece quality + freshness |
| `evidence_mix` | `ALIGNED` / `MIXED` / `INSUFFICIENT` |
| `research_only` | always `true` |
| `execution_authority` | always `NONE` |

Rules:

- Synthesis consumes **P3.2 `WorkspaceEvidence` lane envelopes** (already separate
  relevance / direction / quality / freshness) — it never recomputes lane scores.
  Direction hypotheses come from lane envelopes only; Phase 6
  `StrategyInterpretation` signals are not a direction source.
- **MC16 cluster synthesis is an explicit input:** for CATALYST- and
  MARKET_CONTEXT-family features, `MultiDocumentSynthesisSummary` fields
  (`theme_agreement_score`, `contradiction_detected`, `consolidated_channels`)
  from the MC16 workspace projection are eligible features. The feature's
  `available_time_ns` inherits the MC16 cluster `available_time`
  (`max(member.available_time)`), preserving the PIT gate. MC16
  `contradiction_detected` enriches the contradiction rule below — it never
  overrides it.
- **MC16 flags and scalars propagate safely:** `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL`
  and any other MC16 quality flag propagate verbatim into the feature
  `quality_flags` of MC16-derived evidence; they are never dropped in synthesis.
  `synthesis_confidence` and `theme_agreement_score` are admissible as declared
  features only and are never converted into a direction hypothesis or any
  composite score.
- Any contradiction between lanes → `evidence_mix = MIXED`,
  `direction_hypothesis = NO_HYPOTHESIS`. No averaging, no vote, no % bullish.
  This extends the MC16 cluster-level doctrine (separate contradicting /
  supporting document ids, no neutral default, majority-wins exclusion) to
  candidates.
- Missing lanes → `INSUFFICIENT` / `NOT_CONFIGURED`, never coerced to neutral.
- Candidates are surfaced through the existing What Matters Now / evidence drawer;
  a candidate is research context only. Phase 6 scoped research UI out for its
  own milestone; operator-UI surfacing is authorized here (milestone A) and
  supersedes that Phase-6-scoped exclusion.

## 9. Manual-order-only path

- Hard invariant `DEC-MAN-001`: no import path from `research/` to order creation.
  The paper order entry remains the operator `OrderTicket` →
  `build_user_order_intent` → `evaluate_risk` → `BarConservativeSimulator`
  (Platformization P1), gated by `IMP_PAPER_EXECUTION=1`.
- `run_strategy_evaluation` stays in-memory (no orders), unchanged.
- **Provenance (optional, additive):** the paper intent contract gains an
  optional `research_candidate_id` field. When an operator manually submits a
  paper order from a candidate, the ledger records the reference, enabling
  fill-based attribution joins without any automation. Unknown candidate ids fail
  closed at intent build.

## 10. Assertions

All `DEC-*` assertions below are additive; the Phase 6 assertion registry
(`STRAT-001`, `ABST-001`, `PIT-STRAT-001`, `DET-001`, `SAFE-003`) remains
enforced and unchanged.

| ID | Predicate |
|---|---|
| `DEC-PIT-001` | Every example in every run passes `validate_temporal_example` |
| `DEC-PRE-001` | No evaluation result exists without a registry-bound `card_hash` |
| `DEC-OOS-001` | Reported primary metrics come only from OOS folds |
| `DEC-DET-001` | Repeat runs produce identical run-record hashes under network denial |
| `DEC-SYN-001` | Synthesis output has no composite score; contradictions → `MIXED`/`NO_HYPOTHESIS` |
| `DEC-MAN-001` | No automatic order creation path from research output; `execution_authority: NONE` |
| `DEC-FV-001` | Finviz features rejected without prospective capture |
| `DEC-INC-001` | Insufficient samples fail closed (`INSUFFICIENT_DATA` / `NEEDS_PROSPECTIVE_VALIDATION`) |

## 11. Fixtures and adversarial cases

- `tests/fixtures/research/ss_family_examples.json` — decision examples derived
  deterministically from admitted BIYA/NVDA/BOXL slices with mark-based outcomes
  and applied frictions. CATALYST-family features in BOXL-derived examples use
  the admitted `boxl_multidoc_synthesis_slice.json` /
  `boxl_synthesis_enrichment_expected.json` rows as inputs, exercising the MC16
  handoff end-to-end.
- `tests/fixtures/research/experiment_cards.json` — preregistered SS-family cards
  at fixed hashes.
- Adversarial fixtures: feature-after-decision leakage, outcome-before-decision,
  retroactive Finviz feature without capture, unregistered card run,
  contradiction between lanes, insufficient-sample family, OOS-fold boundary
  leak attempt.
- `tests/research/test_decision_research_001.py` — assertion + adversarial suite.

## 12. Tooling and gate

- `tools/research/run_decision_research_gate_validation.py` — loads cards and
  fixtures, runs the harness, asserts `DEC-*`, writes
  `evidence/research/decision-research-gate-report.json`.
- Validation cadence: `python tools/validate.py changed` after edits; gate tool
  at milestone; `python tools/validate.py full` at the final checkpoint. The
  `research` manifest suite (`tests/research`) already owns the new modules via
  `src/market_platform_foundation/research/decision_research/**`.

## 13. Out of scope

- Automatic strategy promotion, any order automation, or live execution
  (Platformization P4 / `LIVE-001`).
- Broker/paper adapters, idempotency, reconciliation (P4).
- Live LLM synthesis runtime — out of scope in both MC16 and this milestone
  (fixture-precomputed labels only, matching MC16's "runtime never calls live
  LLM"); neural networks or third-party ML.
- Composite scores, universal news scores, or % bullish anywhere in the UI.
- ES live session, crypto, prediction markets, live social APIs.
- Retroactive Finviz reconstruction under any circumstances.

## 14. Completion definition

DECISION-RESEARCH-001 is complete when:

- Experiment cards + registry exist with hash binding and
  `verify_experiment_card_registration` fail-closed behavior;
- the walk-forward harness produces deterministic OOS metrics for the SS family
  on admitted-fixture examples, with metrics reported only from OOS folds;
- `build_decision_candidate` produces `DecisionCandidate` with no composite
  score, `MIXED`/`NO_HYPOTHESIS` on contradiction, and `execution_authority: NONE`;
- optional `research_candidate_id` provenance is wired through the paper intent
  without any automation path;
- assertions `DEC-*` and all adversarial fixtures pass; the gate tool reports
  aggregate PASS;
- the master cooperative roadmap and platformization roadmap are updated to mark
  milestone A complete; no P4 implementation has begun.
