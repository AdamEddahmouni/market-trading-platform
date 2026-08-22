# DECISION-RESEARCH-001 — Milestone A Implementation Plan

## Goal

Implement governed decision research and strategy synthesis (Platformization milestone **A**) per the committed design spec
[`2026-08-22-decision-research-001-design.md`](../docs/superpowers/specs/2026-08-22-decision-research-001-design.md)
(commit `ada1a2e`). Deliver preregistered SS-family experiment cards, a deterministic walk-forward OOS harness, and
research-only strategy synthesis — **manual orders only, no automatic strategy promotion, no P4 work**.

## Scope guardrails (from spec §2, §13)

- Offline only: no provider I/O, no live LLM, no network. Determinism under network denial (`DEC-DET-001`).
- No code path from `research/` to order creation (`DEC-MAN-001`); `execution_authority: NONE` everywhere.
- No composite score / no % bullish / no universal news score (`DEC-SYN-001`).
- Fixture-first on admitted BIYA / NVDA / BOXL / ES slices; no retroactive Finviz reconstruction (`DEC-FV-001`).
- Phase 6 preregistration and its assertion registry (`STRAT-001`, `ABST-001`, `PIT-STRAT-001`, `DET-001`, `SAFE-003`)
  remain unchanged; `DEC-*` assertions are additive.

## Current state (verified 2026-08-22)

- `src/market_platform_foundation/research/decision_research/` contains only `{models, pit_gate, experiments, runner, __init__}.py`.
- `models.py`: `ResearchExample`, `ResearchHypothesis`, `ResearchResultStatus` (SUPPORTED / NOT_SUPPORTED / INCONCLUSIVE /
  INSUFFICIENT_DATA / NEEDS_PROSPECTIVE_VALIDATION), `HypothesisLabel` (CONFIRMATORY / EXPLORATORY), `EvaluationResult`.
- `pit_gate.py`: `validate_temporal_example`, `reject_historical_finviz_screen_without_capture`, `chronological_split` (0.6/0.2).
- `experiments.py`: `SHORT_SQUEEZE_EXPERIMENTS` (6 hypotheses SS-BASE … SS-FV-DISC) + `evaluate_experiment` (thresholds 5 / 20; INCONCLUSIVE fallback, no OOS yet).
- `runner.py`: `run_short_squeeze_family` already emits `execution_authority: NONE`, `auto_strategy_promotion: False`.
- `paper/contracts.py`: `build_user_order_intent` — **no `research_candidate_id`** parameter yet.
- P3.2 `WorkspaceEvidence` envelope exists (`build_workspace_evidence_payload`; backend lane adapters with separate
  relevance / direction / quality / freshness); `WorkspaceEvidenceLaneSchema` in `ui/src/api/schemas.ts`.
- Missing modules to build: `examples.py`, `cards.py`, `registry.py`, `harness.py`, `synthesis.py`.

## Settled Task 6 definitions (2026-08-22, fixture-grounded)

These fix the card fields **before** Task 3 writes fixed-hash fixtures, so the registry hashes are final.
Grounding measured from admitted fixtures: BIYA intraday bars = 2838 (1-min, 2026-07-16 → 21); NVDA
order-flow slice = 11 events; BOXL catalyst slice = 5 events; BIYA disclosures = 8 events.

### primary_metric definitions (deterministic, stdlib-only, reuse current `metrics.precision` semantics)

- **Hit** = example with `outcome.positive == true` (mark-based forward-return sign over the declared horizon,
  after `execution_book_aware_v1` frictions). `oos_precision(S) = hits(S) / |S|` over PIT-valid,
  inclusion-admitted OOS examples.
- **SS-BASE (reference):** `primary_metric = "oos_positive_base_rate"` = `oos_precision(all admitted OOS
  examples)`. Never `SUPPORTED` (delta vs itself = 0); anchors the delta. Add a degenerate-baseline guard test:
  SS-BASE must never report `SUPPORTED`.
- **Evidence-augmented cards (SS-OF / SS-CAT / SS-MKT / SS-OF-CAT / SS-FV-DISC):** `primary_metric =
  "oos_precision_delta_vs_baseline"` = `oos_precision(card's evidence-bearing OOS subset) −
  oos_positive_base_rate`, where the card's OOS subset = OOS examples whose features include every
  `feature_spec.required` family for that card (i.e. contain the added evidence). Empty subset →
  `INSUFFICIENT_DATA`.
- **SUPPORTED condition:** `hypothesis_label == CONFIRMATORY` AND `|OOS subset| >= min_sample_oos` AND
  `delta >= primary_metric_threshold` (per-card, default +0.05) AND `delta > 0`. EXPLORATORY cards with edge →
  `NOT_SUPPORTED` (preregistered rule: exploratory findings are never `SUPPORTED`). `n_oos == 0` / gate failure
  → `INSUFFICIENT_DATA`; `0 < n_oos < min_sample_oos` → `NEEDS_PROSPECTIVE_VALIDATION`.
- **Scope note:** experiment precision counts realized outcomes, not lane direction hypotheses; lane direction
  is Task 7 (synthesis) only. This avoids a second prediction contract.

### min_sample_oos (per-card, fixed at registry write; fixture-grounded)

| Card | min_sample_oos | primary_metric | primary_metric_threshold | Expected on current fixtures |
|---|---|---|---|---|
| SS-BASE | 150 | oos_positive_base_rate | — | INCONCLUSIVE (baseline anchor; never SUPPORTED) |
| SS-OF | 30 | oos_precision_delta_vs_baseline | +0.05 | NEEDS_PROSPECTIVE_VALIDATION (slice = 11) |
| SS-CAT | 30 | oos_precision_delta_vs_baseline | +0.05 | NEEDS_PROSPECTIVE_VALIDATION (slice = 5) |
| SS-MKT | 45 | oos_precision_delta_vs_baseline | +0.05 | NEEDS_PROSPECTIVE_VALIDATION (small slice) |
| SS-OF-CAT | 30 | oos_precision_delta_vs_baseline | +0.05 | NEEDS_PROSPECTIVE_VALIDATION (intersection smaller) |
| SS-FV-DISC | 30 | oos_precision_delta_vs_baseline | +0.05 | NEEDS_PROSPECTIVE_VALIDATION (no retroactive Finviz; needs prospective capture) |

### Consequences / guardrails

- Only SS-BASE reaches SUPPORTED-eligible OOS size on the admitted fixtures; all augmentation cards
  deterministically resolve `NEEDS_PROSPECTIVE_VALIDATION` / `INSUFFICIENT_DATA`. That is the milestone's
  intended output — sparse donor slices cannot validate a lane; the gate report records coverage gaps and P4
  stays deferred. No threshold is tuned to force SUPPORTED; values are declared independent of observed metrics
  (preregistration).
- **Fold scheme (harness §7):** expanding window; OOS block = `max(50, ceil(0.15 × ordered))` per fold, 4 folds,
  folds position-derived (no RNG), `example_id` tie-break. SS-BASE total OOS ≈ 4 × ~0.15 × ~2700 ≈ 1600 ≥ 150.
- Provided the two new **additive card fields** `min_sample_oos`, `primary_metric`, `primary_metric_threshold`
  are hashed into the card body, Task 3 fixtures are final and immutable after the first registry write; a
  changed threshold is a **new card**, never a mutation of an existing one. (Spec §5 table should gain a
  `primary_metric_threshold` row on next edit — pending principal review.)

### Empirical fold-scheme verification (2026-08-22, run against the real fixtures)

Method: load 2838 BIYA 1-min bars (2026-07-16 → 21); one example per bar, usable `N = bars − horizon`;
`positive = close[i+H] > close[i]` (raw mark; frictions applied by the builder); expanding window with
`B = max(50, ceil(0.15·N))`, 4 sequential OOS blocks over `[N − 4B, N)`, train = `[0, block_start)`.

| Horizon | Usable N | OOS block B | Initial train | Total OOS | Base rate |
|---|---|---:|---:|---:|---:|
| 5 min | 2833 | 425 | 1133 | 1700 | 0.467 |
| 15 min | 2823 | 424 | 1127 | 1696 | 0.486 |
| **30 min (recommended)** | 2808 | 422 | 1120 | 1688 | 0.500 |
| 60 min | 2778 | 417 | 1110 | 1668 | 0.521 |

- **SS-BASE:** total OOS ≈ 1688–1700 across all horizons, far above `min_sample_oos: 150` → reachable; base rate
  ≈ 0.47–0.52 (not degenerate; no empty-train fold). Assumption: SQUEEZE_STATE features are available on usable
  BIYA bars (the squeeze engine runs over these bars).
- **Recommended `outcome_spec` default horizon = 30 min** → `horizon_ns = 1_800_000_000_000` (per-card override
  allowed; chosen over the spec's illustrative 30 s sample).

**Donor-slice caps bound every augmentation card** (measured 2026-08-22):

| Card (added evidence) | Donor | Donor size | Max possible OOS | Verdict |
|---|---|---|---|---|
| SS-OF | NVDA order-flow | 8 bars, all 2026-07-21 | ≤ 8 | NEEDS_PROSPECTIVE_VALIDATION |
| SS-CAT | BOXL catalyst | 5 events (07-15/18/21/22) | ≤ 5 | NEEDS_PROSPECTIVE_VALIDATION |
| SS-MKT | BOXL market-context + MC16 | 3 golden summaries | ≤ 3 | NEEDS_PROSPECTIVE_VALIDATION |
| SS-OF-CAT | ORDER_FLOW_CVD ∩ CATALYST | disjoint symbols/dates | 0 | INSUFFICIENT_DATA |
| SS-FV-DISC | Finviz prospective | none in fixture scope | 0 | NEEDS_PROSPECTIVE_VALIDATION (DEC-FV-001 gate) |

- **Structural finding:** SS-OF-CAT is not exercisable end-to-end on the current fixture scope — no decision
  timestamp carries both NVDA order-flow and BOXL catalyst evidence (different symbols and dates). It stays
  preregistered (hash-bound card) and deterministically returns `INSUFFICIENT_DATA`; no threshold tuning can or
  should change that. Real co-temporal cross-lane data (or prospective captures) is required to move the
  augmentation cards past their current verdicts.
- **Expected gate report on current fixtures:** SS-BASE `INCONCLUSIVE` (baseline anchor), SS-OF / SS-CAT /
  SS-MKT / SS-FV-DISC `NEEDS_PROSPECTIVE_VALIDATION`, SS-OF-CAT `INSUFFICIENT_DATA`, aggregate PASS.

### Evidence-family → source mapping (finalized 2026-08-22, for the example builder)

Row counts measured from the admitted fixtures; the builder must fail closed on any family not listed as
buildable (declared-only families produce **no** example features, never coerced).

| evidence_family | Source (admission) | Measured rows | available_time_ns | value fields | authority | quality_flags | Direction today | Builder outcome |
|---|---|---|---|---|---|---|---|---|
| `SQUEEZE_STATE` | BIYA bars 2838 + squeeze engine (via `build_workspace_squeeze_payload`) | ~2808 usable | bar/state time `<= decision_time_ns` | `{state, fuel_pct, ignition_state, evidence_coverage}` | `IMP_DERIVED` | PASS/STALE/UNKNOWN | POSITIVE / NEUTRAL (ignition) | SS-BASE: one example per usable BIYA bar → OOS ≈ 1700 ✓ |
| `ORDER_FLOW_CVD` | NVDA order-flow bars (07-21) via `build_workspace_order_flow_payload` | **8** | OF bar `event_time` | `{session_cvd, cvd_slope, aggressive_buy/sell_volume}` | `IMP_DERIVED` (ledger) | PASS/DEGRADED/UNKNOWN-AGGRESSOR | POS/NEG/NEUTRAL/UNKNOWN (`_cvd_direction`) | SS-OF: OOS `<= 8` → `NEEDS_PROSPECTIVE_VALIDATION` |
| `MICROSTRUCTURE` | NVDA L2 depth `ADMITTED-L2-NVDA-001`, OF9 exec forecast | **6** snapshots / 6 forecasts (07-21) | depth `event_time` | `direction_bias, continuation/reversal, expected_slippage_spread_fraction, fill probs` | `IMP_DERIVED` | BOOK_STATE_INVALID etc. | forecast bias only (not a lane label) | **Costs only** for SS-OF outcomes; not built as an SS feature → declared-only |
| `CATALYST` | BOXL catalyst slice (`boxl_catalyst_slice.json`) + MC16 rows | **5** events (07-15/18/21/22); **3** MC16 summaries | catalyst `event_time` / MC16 `available_time` (max member) | `lean/classification, news_score, theme_agreement_score, contradiction_detected, consolidated_channels` | `MODEL_OUTPUT` / `IMPLIED` | `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL`, `NO_UNIVERSAL_NEWS_SCORE` | POS/NEG/NEUTRAL via lean (MC16 enrich-not-override) | SS-CAT: OOS `<= 5` → `NEEDS_PROSPECTIVE_VALIDATION` |
| `MACRO_CONTEXT` | BOXL market-context + MC16 golden `boxl_multidoc_synthesis_expected.json` | **3** summaries | MC16 `available_time` | `regime_label, theme_agreement_score, consolidated_channels` | `MODEL_OUTPUT` | `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL` (+ `NO_UNIVERSAL_NEWS_SCORE`) | POS/NEG/NEUTRAL via regime | SS-MKT: OOS `<= 3` → `NEEDS_PROSPECTIVE_VALIDATION` |
| `FINVIZ_DISCOVERY` | none (prospective captures only) | 0 | — | requires `capture_present: true` | — | — | research-context only | SS-FV-DISC always `NEEDS_PROSPECTIVE_VALIDATION` (`DEC-FV-001`) |
| `OPTIONS_DEALER` / `ATTENTION` / `PARTICIPANT_CROWDING` | — (no labelled adapter on this scope) | 0 | — | — | — | — | not labelled | **declared-only** — never built into examples |

**Vocabulary reconciliation (needed before Task 4):** the SS cards' `added_evidence` uses `MARKET_CONTEXT`
(existing `experiments.py`) but the §4 controlled vocabulary lists `MACRO_CONTEXT`. Resolution: the builder
normalizes card `added_evidence = MARKET_CONTEXT` to canonical `evidence_family = MACRO_CONTEXT` (same
P3.2 MARKET_CONTEXT lane source), and the §4 vocab table line is interpreted accordingly. All other card
`added_evidence` values are exact §4 family names.

**Builder construction rule (from §4 declared-only rule):** an example is admitted for a card only if every
family in `feature_spec.required` for that card has a buildable source **and** a labelled direction or a value
field defined above; otherwise fail closed at example construction (no example emitted for that card at that
decision time). This is what makes SS-OF-CAT deterministically empty (ORDER_FLOW_CVD and CATALYST never
co-occur — NVDA OF bars are 07-21 only, BOXL catalyst spans 07-15/18/21/22).

## Task list (test-first; each task ends with its module's tests passing and `python tools/validate.py changed`)

### Task 1 — `cards.py`: ExperimentCard model + canonical hashing

- [ ] Add `ExperimentCard` dataclass (slots) mirroring spec §5 fields: `card_id`, `experiment_id`, `family`,
      `hypothesis_label`, `baseline_id`, `added_evidence`, `feature_spec`, `outcome_spec`, `inclusion_criteria`,
      `exclusion_criteria`, `primary_metric`, `min_sample_oos`, `evaluation_window` (fold schema: expanding/rolling),
      `preregistered_at_ns`, `card_hash`.
- [ ] Reuse the Phase 6 hashing pattern (`canonical_bytes` / `sha256_bytes` from `..canonical` — same helpers
      `paper/contracts.py` already imports): `card_hash = sha256_bytes(canonical_bytes(card_body))` over the
      hash-relevant body (all fields except `card_id` / `card_hash`, mirroring identity-hash binding in
      `strategy/preregistration.py`).
- [ ] `card_id = "CARD-" + uuid5(NAMESPACE, canonical_card_id_bytes)` — deterministic across runs and machines.
- [ ] `to_dict` / `from_dict`; `from_dict` recomputes `card_hash` and rejects a hash mismatch at construction
      (`CARD_HASH_MISMATCH`).
- [ ] Tests (`tests/research/test_decision_research_cards.py`): canonical bytes stability, hash recompute identity,
      card_id determinism, from_dict rejects altered body, added_evidence ordering canonicalized.

### Task 2 — `registry.py`: hash-bound card registry

- [ ] `ExperimentCardRegistry` persisted under `evidence/research/experiment-cards/<card_hash>.json` (committed,
      immutable — mirrors the real hash-bound acceptance-dir convention `evidence/phase6/<hash>/`;
      `evidence/strategy/` does **not** exist — see code-audit finding F1).
- [ ] `register(card)` — idempotent; refuses on body/hash mismatch; refuses mutation of an existing identical hash with
      different bytes.
- [ ] `load(hash)`, `list_cards()`, `get(experiment_id)`.
- [ ] `verify_experiment_card_registration(card, run)` — fails closed when `card_hash` absent from registry or not bound
      to the run record (`DEC-PRE-001`).
- [ ] Tests: register + reload round-trip, idempotency, fail-closed verification, unregistered-card run reject
      (adversarial), exported registry dir is byte-stable.

### Task 3 — Fixed-hash SS-family card fixtures

- [ ] `tests/fixtures/research/experiment_cards.json` with the 6 spec §6 cards (`SS-BASE`, `SS-OF`, `SS-CAT`, `SS-MKT`,
      `SS-OF-CAT`, `SS-FV-DISC`) at **fixed committed hashes**, using the settled `min_sample_oos` / `primary_metric` /
      `primary_metric_threshold` from the "Settled Task 6 definitions" block above.
- [ ] A deterministic small builder module under `tools/research/` (or a test helper) that emits the fixture JSON;
      tests assert the committed fixture matches the builder output byte-for-byte.
- [ ] `min_sample_oos` / `evaluation_window` / `primary_metric` / `primary_metric_threshold` per card (SS-BASE uses
      `oos_positive_base_rate`; all augmentation cards use `oos_precision_delta_vs_baseline` — see settled
      definitions); each card's `added_evidence` matches the spec §6 table.

### Task 4 — `examples.py`: PIT-gated decision-example builder + fixture

- [ ] `build_decision_examples(...)` producing `ResearchExample`-shaped rows from the admitted BIYA / NVDA / BOXL slices,
      with mark-based forward returns over a declared `horizon_ns` and `execution_book_aware_v1` frictions
      (SHARED P4 / OF9 cost model). No fill required.
      - Friction source (pinned 2026-08-22): `build_workspace_order_book_payload(...)["latest_execution_forecast"]`
        (builder `_execution_forecast_from_event` in `providers/projections.py`; producer
        `order_flow/execution_forecast.py::compute_execution_forecast`, `EXECUTION_METHOD="execution_book_aware_v1"`).
        No `costs_bps` producer exists yet — milestone A adds a small deterministic conversion:
        `costs_bps = round(expected_slippage_absolute / decision_mid * 10000, basis)`, plus optional
        adverse-selection adder from `adverse_selection_risk`, stamped `cost_model_version: execution_book_aware_v1`.
        `forward_return_bps = raw_mark_bps - costs_bps`.
- [ ] CATALYST-family features in BOXL-derived examples read the admitted MC16 rows (confirmed present) at
      `tests/fixtures/market_context/boxl_multidoc_synthesis_slice.json`,
      `tests/fixtures/market_context/boxl_multidoc_synthesis_expected.json`,
      `tests/fixtures/market_context/boxl_synthesis_enrichment_expected.json` (MC16 handoff, spec §4/§11).
      Feature `available_time_ns` = `iso_to_epoch_ns(summary.available_time)` — MC16 already sets
      `available_time = max(member.available_time)` over active members.
- [ ] Every emitted example must pass `validate_temporal_example`; enforce
      `reject_historical_finviz_screen_without_capture` for FINVIZ features (`DEC-FV-001`).
- [ ] Implement the spec §4 family→source mapping table; `OPTIONS_DEALER`, `ATTENTION`, `PARTICIPANT_CROWDING`,
      and `FINVIZ_DISCOVERY` remain declared-only (no labelled adapter → fail closed at example construction,
      never coerced).
- [ ] `tests/fixtures/research/ss_family_examples.json` — deterministic from fixtures (no RNG).
- [ ] Tests: builder provenance determinism, all examples PIT-valid, adversarial fixture rejection cases
      (feature-after-decision, outcome-before-decision, retroactive Finviz without capture).

### Task 5 — `harness.py`: walk-forward OOS harness

- [ ] Deterministic folds: order examples by `decision_time_ns` with `example_id` tiebreak; folds derived from position —
      no RNG. Default **expanding window**; optional rolling per card `evaluation_window`. Single-split case delegates to
      existing `chronological_split` (0.6/0.2).
- [ ] PIT gate re-applied per fold; no cross-fold leakage (spec §7).
- [ ] Run record → `evidence/research/runs/<run_id>.json`: family, fold boundaries, per-experiment **OOS-only** metrics,
      `incremental_vs_baseline`, bound `card_hash` list, `execution_authority: NONE`, `auto_strategy_promotion: False`.
- [ ] Harness imports no provider path, performs no I/O beyond admitted fixtures (`DEC-DET-001`).
- [ ] Tests: fold determinism (identical run hashes on repeat, `DEC-DET-001`), expanding vs rolling fold construction,
      OOS-only metric extraction (`DEC-OOS-001`), adversarial fold-boundary leak attempt rejected.

### Task 6 — Bind `experiments.py` to cards; OOS-only evaluation

- [ ] `evaluate_experiment(card, oos_examples)` **requires a bound, registry-verified card** — raises fail-closed without one.
- [ ] Status mapping per spec §6 + settled definitions: `n_oos < min_sample_oos` → `NEEDS_PROSPECTIVE_VALIDATION`;
      `n_oos == 0` or gate failure → `INSUFFICIENT_DATA`; confirmatory OOS edge `>= primary_metric_threshold` →
      `SUPPORTED`; otherwise `INCONCLUSIVE` / `NOT_SUPPORTED` per preregistered rule (`DEC-INC-001`). Emit the card's
      `primary_metric` value (delta or base rate) in `metrics`; add the degenerate-baseline guard test (SS-BASE never
      `SUPPORTED`).
- [ ] Keep `SHORT_SQUEEZE_EXPERIMENTS` as the declared family source; `SHORT_SQUEEZE_EXPERIMENTS` now yields cards.
- [ ] Tests: status boundary coverage (insufficient / prospective / supported / inconclusive), OOS-only metric assertion,
      unregistered-card run fails closed (adversarial), thresholds driven by card `min_sample_oos`.

### Task 7 — `synthesis.py`: DecisionCandidate + build_decision_candidate

- [ ] `DecisionCandidate` dataclass per spec §8: `candidate_id` (`CAND-<uuid5>`), `instrument_id`, `generated_at_ns`,
      `direction_hypothesis` (LONG/SHORT/NEUTRAL/NO_HYPOTHESIS), `thesis` (display-only narrative with evidence citations),
      `supporting_evidence` / `contradicting_evidence` (separate lists with per-piece quality + freshness), `evidence_mix`
      (ALIGNED/MIXED/INSUFFICIENT), `research_only: True`, `execution_authority: "NONE"`.
- [ ] `build_decision_candidate(instrument, prediction_cutoff, lane_evidence)` consumes P3.2 `WorkspaceEvidence` lane
      envelopes (relevance / direction / quality / freshness) and MC16 `MultiDocumentSynthesisSummary` fields for
      CATALYST / MARKET_CONTEXT lanes. Never recomputes lane scores. Phase 6 `StrategyInterpretation` is **not** a
      direction source.
      - Pinned lane-envelope (2026-08-22): each lane row is `_lane_base(...)` in `ui_api/workspace_evidence.py`:
        `instrument, lane, evidence_type, as_of, available_time, quality, relevance, direction, confidence,
        probability, expected_value, summary, freshness_label, reason_codes, sources, details, explain_ref,
        missing_evidence, research_only`. `direction` vocabulary is `POSITIVE | NEGATIVE | NEUTRAL | MIXED | UNKNOWN`;
        map POSITIVE→LONG, NEGATIVE→SHORT, NEUTRAL→NEUTRAL, UNKNOWN→(no direction), MIXED→contradiction.
        Payload root adds `what_matters_now`, `evidence_mix_summary`, `research_context_execution_authority: "NONE"`.
      - Pinned MC16 row (2026-08-22): `build_workspace_market_context_payload(...)["multi_document_synthesis_summaries"]`
        is a list of `synthesis_summary_to_dict(item)` full rows — `synthesis_id, cluster_id, entity_id,
        thematic_summary, theme_agreement_score, contradiction_detected, consolidated_channels,
        supporting_document_ids, contradicting_document_ids, revision_superseded_ids, synthesis_confidence,
        model_version, quality_flags, available_time, publication_state, scoring_method`.
- [ ] Contradiction between lanes → `evidence_mix = MIXED`, `direction_hypothesis = NO_HYPOTHESIS` (no averaging, no
      vote, no % bullish — extends MC16 doctrine). Missing lanes → `INSUFFICIENT` / `NOT_CONFIGURED`, never coerced.
- [ ] MC16 quality flags (e.g. `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL`) propagate verbatim into feature `quality_flags`;
      `synthesis_confidence` / `theme_agreement_score` remain declared-features-only (never a direction source).
      `available_time_ns` inherits cluster `available_time` (`max(member.available_time)`) preserving the PIT gate.
- [ ] `to_dict`. Tests (`tests/research/test_decision_research_synthesis.py`): no composite score present (`DEC-SYN-001`),
      aligned → ALIGNED/LONG|SHORT, contradiction → MIXED/NO_HYPOTHESIS, missing lane → INSUFFICIENT, MC16 flag
      propagation, MC16 `contradiction_detected` enriches but never overrides.

### Task 8 — Paper intent provenance: optional `research_candidate_id` (`DEC-MAN-001`)

- [ ] Add optional `research_candidate_id` parameter to `build_user_order_intent` in `paper/contracts.py`,
      recorded on the intent body and into the ledger as additive provenance (no automation).
- [ ] Unknown / unregistered candidate ids fail closed at intent build.
- [ ] Add a static import-boundary test proving `research/` has no import path to order creation
      (`DEC-MAN-001`: `research` package never imports `paper` order builders).
- [ ] Tests: provenance recorded on manual paper order, unknown candidate id rejected, boundary import check.

### Task 9 — `tests/research/test_decision_research_001.py`: DEC-* assertion + adversarial suite

- [ ] Assertion coverage for every `DEC-*` id: `DEC-PIT-001`, `DEC-PRE-001`, `DEC-OOS-001`, `DEC-DET-001`,
      `DEC-SYN-001`, `DEC-MAN-001`, `DEC-FV-001`, `DEC-INC-001`.
- [ ] All spec §11 adversarial cases: feature-after-decision leakage, outcome-before-decision, retroactive Finviz without
      capture, unregistered-card run, contradiction between lanes, insufficient-sample family, OOS-fold boundary leak.
- [ ] End-to-end: fixtures → examples → cards → harness → OOS evaluation → synthesis → gate report.

### Task 10 — Gate tool

- [ ] `tools/research/run_decision_research_gate_validation.py`: loads cards + fixtures, runs the harness, asserts all
      `DEC-*`, writes `evidence/research/decision-research-gate-report.json`; aggregate PASS.
- [ ] Wire into the `research` manifest domain so it runs under `python tools/validate.py domain research`.

### Task 11 — Docs / roadmap sync + completion review

- [ ] Mark milestone A complete on `docs/research/PLATFORMIZATION_ROADMAP.md` and
      `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md` (add DECISION-RESEARCH-001 to "Latest cooperative
      milestones"); update README status row.
- [ ] Confirm **no P4 implementation began**; future families (`ORDER_FLOW`, `OPTIONS_VRP`, `MC_SURPRISE`,
      `PARTICIPANT_CROWDING`) remain declared-only with cards created in the registry only before future implementation.
- [ ] Final `python tools/validate.py full` (offline) checkpoint; reconcile against `reports/pre-land-full.json`.

## Validation cadence

| Point | Command |
|---|---|
| After each task | `python tools/validate.py changed` |
| After Task 9/10 | `python tools/validate.py domain research` |
| Final checkpoint | `python tools/validate.py full` (offline only) |

## Decisions made

| Decision | Rationale |
|---|---|
| Build cards/registry first (spec entry point) | Registry binding is a hard prerequisite for every later task (`DEC-PRE-001`) |
| Reuse `canonical_bytes` / `sha256_bytes`/`strategy/preregistration.py` hashing | Matches spec §5 and avoids a third hashing dialect |
| `CARD-<uuid5>` / `CAND-<uuid5>` over canonical body bytes | Deterministic across machines, matches spec §5/§8 |
| Keep `evaluate_experiment`'s fail-closed status vocabulary | Already shipped in `models.py` / existing tests; spec §6 statuses reuse it |
| `research_candidate_id` is additive-only, fail-closed on unknown | Satisfies `DEC-MAN-001` provenance without any research→order path |
| `costs_bps` friction derives from OF9 `latest_execution_forecast` (expected_slippage + adverse-selection), not a new model | Reuses the landed `execution_book_aware_v1` contract; deterministic and fixture-first |
| No committed plan until principal approval | Per repo convention, specs/plans land via explicit review |

## Open items / risks — RESOLVED (2026-08-22 code probe)

- ~~Cost-model interface~~ → `execution_book_aware_v1` is the OF9 method id (`EXECUTION_METHOD`). For fixture scope,
  consume `latest_execution_forecast` from `build_workspace_order_book_payload` (`_execution_forecast_from_event`); a
  tiny new deterministic `costs_bps`/`forward_return_bps` conversion is required (no existing producer).
- ~~WorkspaceEvidence lane fields~~ → pinned `_lane_base` envelope above (Task 7); note `direction` vocabulary is
  POSITIVE/NEGATIVE/NEUTRAL/MIXED/UNKNOWN, mapped to LONG/SHORT/NEUTRAL/NO_HYPOTHESIS in synthesis.
- ~~MC16 fixture paths~~ → confirmed present under `tests/fixtures/market_context/`; workspace rows are
  `synthesis_summary_to_dict` shapes with `available_time` = max(member) already enforced by MC16.

## Residual risks

- ~~Baseline-precision / `min_sample_oos` definition~~ → **SETTLED 2026-08-22** (see "Settled Task 6 definitions"):
  `oos_precision_delta_vs_baseline` = evidence-subset precision minus baseline `oos_positive_base_rate`;
  SS-BASE anchors with the absolute rate; per-card `min_sample_oos` (30–150) and `primary_metric_threshold` (+0.05)
  declared independent of observed metrics; Task 3 fixtures are final.
- `forward_return_bps` basis (percent vs bps vs minor units) must match `_bar_time_iso`/`close` string parsing in
  `ui_api/projections.py` — pin the bar `close` unit in the example builder (Task 4) before writing fixtures.

## Completion definition (spec §14)

Done when: (1) cards + registry exist with hash binding and fail-closed verification; (2) harness produces deterministic
OOS metrics for the SS family with OOS-only reporting; (3) `build_decision_candidate` yields `DecisionCandidate` with no
composite score, MIXED/NO_HYPOTHESIS on contradiction, `execution_authority: NONE`; (4) `research_candidate_id`
provenance is wired with no automation path; (5) all `DEC-*` assertions + adversarial fixtures pass and the gate tool
reports aggregate PASS; (6) both roadmaps mark milestone A complete; no P4 implementation begun.
