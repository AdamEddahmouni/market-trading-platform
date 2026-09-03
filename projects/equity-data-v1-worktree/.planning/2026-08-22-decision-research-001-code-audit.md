# DECISION-RESEARCH-001 — Code-Grounded Audit

**Audit date:** 2026-08-22 (follow-up to the spec-text audit in
`2026-08-22-decision-research-audit.md`)
**Method:** Walked every claim the spec
[`2026-08-22-decision-research-001-design.md`](../docs/superpowers/specs/2026-08-22-decision-research-001-design.md)
makes about **existing code** that cards / registry / harness / synthesis will build on. New-contract
claims (cards.py, registry.py, harness.py, synthesis.py) are itemized as as-built checks below, to be
re-verified as they are implemented.
**Scope note:** The earlier audit was spec-text-to-spec-text; this one is spec-claims-to-source. No code or
governed subjects were mutated.

---

## 1. Verified accurate against source (spec claims hold)

| # | Spec claim | Verified in | Notes |
|---|---|---|---|
| V1 | Phase 6 hashing pattern: `canonical_bytes` / `sha256_bytes`, identity-hash binding | `strategy/strategy_spec.py` (`strategy_identity_hash`: hash of body minus the hash field), `strategy/preregistration.py`, helpers in `canonical.py` (`canonical_bytes` = sorted-key compact JSON + `\n`; `sha256_bytes` = uppercase hex). Same helpers already used by `paper/contracts.py` | cards.py/registry.py must import `..canonical` — single hashing dialect, no third variant |
| V2 | `verify_preregistration(preregistration, strategy_spec)` unchanged | `strategy/preregistration.py` — returns `(status, reasons)`, identity + record-hash check | Phase 6's `verify_preregistration` stays untouched; DEC's new `verify_experiment_card_registration` is a distinct name (no collision) |
| V3 | Phase 6 assertion registry `STRAT-001, ABST-001, PIT-STRAT-001, DET-001, SAFE-003` | `phase6_assertions.py` `MANDATORY_IDS` — exact match | `DEC-*` prefix unused in code (only the spec doc) — no prefix collision |
| V4 | Phase 6 `StrategySpec` is strategy-level (alignment_type, hypothesis, evidence_requirements, EQ-1) | `strategy/strategy_spec.py` — confirmed | distinct from card-level, multi-instrument DEC contract; `SS-BASE` is a card, not a Phase 6 strategy |
| V5 | "`run_strategy_evaluation` stays in-memory, unchanged" | `strategy/evaluation.py` — builds prereg, runs `run_walk_forward_evaluation`, returns dict; no order path | `strategy_evaluation_root_hash` is the deterministic root-hash precedent the harness run-records should mirror |
| V6 | Walk-forward substrate exists | `research/evaluation.py::run_walk_forward_evaluation` (Phase 5R) | harness §7 supersedes/extendable; harness must stay in-memory (no provider I/O) |
| V7 | `chronological_split` (0.6 / 0.2 / 0.2) in `pit_gate.py` | `research/decision_research/pit_gate.py` (train_ratio=0.6, validation_ratio=0.2; test = remainder) | single-split case; harness folds generalize it |
| V8 | PIT gate semantics | `pit_gate.py::validate_temporal_example` — feature `available_time_ns <= decision_time_ns`, outcome `outcome_time_ns > decision_time_ns` | exact match to spec §2 / §4 |
| V9 | `SHORT_SQUEEZE_EXPERIMENTS` exists with the §6 six hypotheses | `research/decision_research/experiments.py` — SS-BASE/SS-OF/SS-CAT/SS-MKT/SS-OF-CAT/SS-FV-DISC, labels, added_evidence | matches spec §6 table exactly |
| V10 | `evaluate_experiment` retains fail-closed status vocabulary | `experiments.py` — INSUFFICIENT_DATA / NEEDS_PROSPECTIVE_VALIDATION / INCONCLUSIVE | **thresholds 5 / 20 are hard-coded today and must be replaced** by card `min_sample_oos`; vocabulary retained (see F2) |
| V11 | runner emits `execution_authority: NONE`, `auto_strategy_promotion: False` | `runner.py::run_short_squeeze_family` | spec's "already enforced" claim verified |
| V12 | §9 order chain `OrderTicket → build_user_order_intent → evaluate_risk → BarConservativeSimulator`, gated by `IMP_PAPER_EXECUTION=1` | `paper/contracts.py::build_user_order_intent`; `risk/decision.py::evaluate_risk`; `execution/simulator.py::BarConservativeSimulator`; `operating_modes.py::paper_execution_env_enabled` | no `research_candidate_id` yet (additive per §9) |
| V13 | MC16 cluster-level doctrine | `market_context/synthesis.py::MultiDocumentSynthesisSummary` — separate `supporting_document_ids` / `contradicting_document_ids`, majority event-type/channel with opposite-channel exclusion (majority-wins), no neutral default when <2 eligible | precedent §8 cites |
| V14 | MC16 `available_time = max(member.available_time)` | `synthesize_cluster` — `available_ns = max(available_times)`, then ISO | spec §8 inheritance claim verified upstream |
| V15 | MC16 flags: `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL` (plus `NO_UNIVERSAL_NEWS_SCORE`) | `contracts/market_context.py::ContextQualityFlag` | propagate verbatim into `quality_flags` |
| V16 | MC16 scalars 0..1 (`theme_agreement_score`, `synthesis_confidence`) | `MultiDocumentSynthesisSummary` fields | **can be `None`** (see F4) |
| V17 | MC16 workspace projection consumes row shape | `build_workspace_market_context_payload(...)["multi_document_synthesis_summaries"]` = `synthesis_summary_to_dict` rows (`providers/projections.py` L2730; full key list incl. `available_time`, `quality_flags`, `scoring_method`) | `ui_api/projections.py::explain:synthesis` reads the same keys |
| V18 | Fixture inputs for BOXL handoff | `tests/fixtures/market_context/boxl_multidoc_synthesis_slice.json`, `...expected.json`, `boxl_synthesis_enrichment_expected.json` — all present | spec §11 end-to-end is feasible |

## 2. Findings / discrepancies to act on

### F1. Phantom path `evidence/strategy/<hash>/` (§5)
- `evidence/strategy/` **does not exist**. The real hash-bound acceptance-dir convention is
  `evidence/phase6/<hash>/` (and `evidence/phase0/<hash>/`, `evidence/phase5r/…`). `evidence/phase6/B042…/`
  contains `strategy-determinism-report.json`, `strategy-evaluation-report.json`, `assertion-*.json`.
- The spec §5 sentence "mirroring the hash-bound acceptance convention of `evidence/strategy/<hash>/`"
  cites a path that only exists in the spec (and was repeated in the prior text-audit's verification basis).
- **Action:** ►**APPLIED 2026-08-22** — spec §5 now cites `evidence/phase6/<hash>/` and notes
  `evidence/strategy/` is not a repository path. Pending principal review like all spec edits. `evidence/research/`
  itself does not exist yet — new, no conflicts.

### F2. Current `evaluate_experiment` thresholds are hard-coded and will be replaced
- Today `n < 5 → INSUFFICIENT_DATA`, `n < 20 → NEEDS_PROSPECTIVE_VALIDATION`, else `INCONCLUSIVE`.
- §6 replaces these with card-driven `min_sample_oos` and adds `SUPPORTED` / `NOT_SUPPORTED`. This is an
  explicit, spec-authorized behavior change, **but** the existing `tests/research/test_decision_research_p33.py`
  asserts current behavior — Task 6 must update or extend those assertions, and milestone A should not break
  P3.3's fail-closed statuses. Verify the p33 test expectations before editing `experiments.py`.

### F3. §4 evidence_family controlled vocabulary vs available labelled directions
- Families **MICROSTRUCTURE**, **OPTIONS_DEALER**, **ATTENTION**, **PARTICIPANT_CROWDING** have no direct 1:1
  workspace lane envelope named the same. Implicit mappings only:
  MICROSTRUCTURE → ORDER_FLOW lane (OF8 `latest_microstructure_forecast` / details); OPTIONS_DEALER → OPTIONS lane
  (dealer snapshot details); ATTENTION → MARKET_CONTEXT attention summaries;PARTICIPANT_CROWDING → WHALE_INSIDER participant actions. Several carry `direction: UNKNOWN` (no coercion —
  fine per spec, but example-builder `feature_spec` must declare a mapping table or leave those families
  declared-only until lane adapters expose labelled directions).
- **Action:** ►**APPLIED 2026-08-22** — spec §4 now carries the full mapping table and a **declared-only** rule:
  `OPTIONS_DEALER`, `ATTENTION`, `PARTICIPANT_CROWDING`, and `FINVIZ_DISCOVERY` are declared-only until an
  adapter produces a labelled direction backed by real fixture data; missing features never coerce.

### F4. MC16 scalars can be `None` — synthesis must fail closed
- `theme_agreement_score` is `None` when <2 eligible docs; `synthesis_confidence` (`SynthesisFixtureLabel`) is
  nullable. Spec §8 already forbids coercion; source confirms the None paths exist. Treat as missing feature →
  `INSUFFICIENT`, never default.

### F5. `preregistered_at_ns` (int ns) vs Phase 6 `registered_at` (ISO string)
- Phase 6 preregistration uses ISO `registered_at`; DEC cards and the fixture model use epoch-ns ints
  (`decision_time_ns`). `iso_to_epoch_ns` in `normalization/equity_bars.py` (used by MC16) is the conversion
  helper to standardize on. Two time representations will coexist by design — document the boundary in cards.py.

### F6. `research_candidate_id` is additive but hash-affecting
- `build_user_order_intent` computes `intent_id = sha256_bytes(canonical_bytes(body))` over the full body.
  Adding an optional `research_candidate_id` is additive when absent (existing intents unchanged), but present
  intents get new hashes — fine, but must be updated in `normalize_execution_intent`'s copied-key list too, or
  provenance will be dropped on normalize. Task 8 must handle both.

## 3. As-built checks (re-verify as each milestone component lands)

| Component | Check |
|---|---|
| `cards.py` | `CARD-<uuid5>` deterministic across runs/machines; `card_hash` recompute identity; `from_dict` rejects body/hash mismatch (`CARD_HASH_MISMATCH`); added_evidence ordering canonicalized |
| `registry.py` | idempotent register; `evidence/research/experiment-cards/<hash>.json` layout mirrors `evidence/phase6/<hash>/` conventions (report JSONs, committed); `verify_experiment_card_registration(card, run)` fail-closed on absent/unbound hash (raise ValueError, matching `load_json_strict`/phrase5r registry style) |
| `harness.py` | fold determinism with `example_id` tie-break; no provider import; run-record hash stability under network denial (`DEC-DET-001`); OOS-only metric extraction (`DEC-OOS-001`) |
| `examples.py` | `costs_bps` from `latest_execution_forecast.expected_slippage_absolute / mid * 10000` (+ adverse-selection adder), stamped `execution_book_aware_v1`; `forward_return_bps` basis pinned against store bar `close` |
| `synthesis.py` | direction mapping POSITIVE/NEGATIVE/NEUTRAL/MIXED/UNKNOWN → LONG/SHORT/NEUTRAL/NO_HYPOTHESIS; MC16 enrich-not-override; flags propagate verbatim; no composite score |
| `paper/contracts.py` Task 8 | optional `research_candidate_id` on intent + `normalize_execution_intent`; unknown-id fail closed; import-boundary test research→paper |

## 4. Residual (unchanged from plan)
- Baseline-precision definition (`oos_precision_delta_vs_baseline`) and per-card `min_sample_oos` must be settled
  **before** generating fixed-hash cards (Task 3), because card hashes are immutable once committed.
- A verified evaluation-side `build_walk_forward` vs `run_walk_forward_evaluation` reuse boundary should be
  confirmed in Task 5 (harness generalizes `chronological_split`; Phase 5R helper stays in-memory).

**Overall:** spec's code-facing claims are accurate (18/18 verified). Two action items for spec text (F1 path fix;
F3 mapping table or declared-only note) and two implementation cautions (F2 p33 test update; F6
normalize_execution_intent) before/while building.

## 5. Spec revision cross-check (post-2026-08-22 edits)

Reference snapshot so reviewers can diff pre/post-review versions of the design spec. Both hashes are over
**LF bytes** (the spec file is LF-only on disk — `131E5E…` equals both the raw and normalized value), so they are
directly comparable.

| Version | Identity | SHA-256 (LF bytes) |
|---|---|---|
| **Pre-review** | committed `ada1a2e` (2026-08-22 16:25), git object `7ea4ac2…` | `C37FFB488FB15ABE64AF1B384ECCB898E6E3DDBC8793CCD0D1CF0DC150C03579` |
| **Post-edit** | working tree after §4 mapping table + §5 path fix (F3, F1) | `131E5EFD009B1A4FFF57C251C3C9C59DFF63E1506D7587B7FD76CA9486A4A905` |

- **Authoritative diff:** `git diff ada1a2e -- docs/superpowers/specs/2026-08-22-decision-research-001-design.md`.
- **Verified convention:** the repository's real hash-bound acceptance-dir for strategy evidence is
  `evidence/phase6/<hash>/` (e.g. `evidence/phase6/B0424C196D7BA6A3398DFDC56C58E9844153B8DA72D8DA4FE79A15AAB7344009/`
  holds `strategy-determinism-report.json`, `strategy-evaluation-report.json`, `assertion-*.json`).
  `evidence/strategy/` does **not** exist at `ada1a2e` or in the working tree.
- **Governed state:** `manifests/phase0/canonical-authority.json` is unmodified (on-disk sha256
  `6CDA4148DBDBC82167F990EE6CC160CAE7C7BC452A65DD9E5878EEA70C7AC399`) and still binds Foundation Revision-3
  hash `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`. The design spec is **not** a governed
  hash-bound artifact, so no governed hash changed; only the spec's own content identity moved.
- **Supersession rule:** once the principal approves and the post-edit spec is committed, the new git blob hash
  supersedes `131E5E…`; the pre/post `git diff` and this table remain the review trail.
