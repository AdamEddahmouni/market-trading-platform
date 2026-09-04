# DECISION-RESEARCH-001 — Cross-Spec Audit

**Audit date:** 2026-08-22
**Audited document:** [`docs/superpowers/specs/2026-08-22-decision-research-001-design.md`](../docs/superpowers/specs/2026-08-22-decision-research-001-design.md) (milestone A: governed decision research / strategy synthesis)
**Audited against:**
- [`2026-08-15-phase-6-preregistered-strategy-design.md`](../docs/superpowers/specs/2026-08-15-phase-6-preregistered-strategy-design.md) — Phase 6 preregistered strategy
- [`2026-08-21-mc16-multi-document-llm-synthesis-design.md`](../docs/superpowers/specs/2026-08-21-mc16-multi-document-llm-synthesis-design.md) — MC16 multi-document LLM synthesis
- [`2026-08-21-mc16-mc78-synthesis-enrichment-design.md`](../docs/superpowers/specs/2026-08-21-mc16-mc78-synthesis-enrichment-design.md) — MC16 → MC7/MC8 enrichment

**Code-verification basis:** `src/market_platform_foundation/strategy/{preregistration,strategy_spec,evaluation}.py`, `src/market_platform_foundation/research/decision_research/{pit_gate,experiments,runner}.py`, `evidence/strategy/<hash>/` acceptance dirs.

**Resolution status: ALL FINDINGS APPLIED to the spec (2026-08-22).** The spec is updated and internally consistent; it remains uncommitted pending principal review (per repo convention, design specs are not auto-committed).

---

## 1. Contradictions found (2)

### 1.1 Live-LLM out-of-scope misattribution
- **Finding:** Spec §13 read "Live LLM synthesis runtime (MC16 scope)". MC16 itself bans live LLM ("Runtime never calls live LLM"; "Live LLM runtime in IMP CI" is on MC16's own out-of-scope list). The parenthetical wrongly implied MC16 owns the capability.
- **Fix applied (§13):** "Live LLM synthesis runtime — out of scope in both MC16 and this milestone (fixture-precomputed labels only, matching MC16's 'runtime never calls live LLM'); neural networks or third-party ML."

### 1.2 `verify_preregistration` name collision with Phase 6
- **Finding:** Phase 6 ships `verify_preregistration(preregistration, strategy_spec)` — strategy-identity binding, in-memory, in `strategy/preregistration.py`. The spec defined a *different* `verify_preregistration(card, run)` — card-registry binding, fail-closed on absent hash — in a different module. Same name, two semantics.
- **Fix applied (§5, §14):** renamed to `verify_experiment_card_registration(card, run)`; the sole remaining `verify_preregistration` reference is Phase 6's own, marked "remains unchanged."

---

## 2. Missing handoffs (5 substantive)

### A. StrategySpec ↔ ExperimentCard boundary undefined
- Phase 6 `StrategySpec` is strategy-level (alignment type, hypothesis, evidence requirements on the EQ-1 equity fixture); DEC cards are experiment-level, multi-instrument. The spec never said whether cards reference Phase 6 strategies, whether `SS-BASE` is a Phase 6 strategy, or where Phase 6 `StrategyInterpretation` sits relative to `evaluate_experiment`.
- **Fix applied (§5 "Relationship to Phase 6 preregistration"):** cards reuse Phase 6's hashing / identity-binding / fail-closed pattern but are a distinct contract; `SS-BASE` is a card, not a Phase 6 strategy; Phase 6 `StrategyInterpretation` is not a candidate direction source; no reconciliation required. Cross-referenced from §8.

### B. MC16 → evidence-family mapping unwritten
- DEC vocabulary includes CATALYST and MARKET_CONTEXT; MC16 enriches exactly those lanes via MC7/MC8 — yet the spec never named MC16 as a feature source.
- **Fix applied (§8 "MC16 cluster synthesis is an explicit input"):** `MultiDocumentSynthesisSummary` fields (`theme_agreement_score`, `contradiction_detected`, `consolidated_channels`) are eligible features; feature `available_time_ns` inherits MC16 cluster `available_time` (`max(member.available_time)`), preserving PIT; MC16 `contradiction_detected` enriches (never overrides) the contradiction rule.

### C. Experimental-flag and scalar propagation unspecified
- MC16 stamps every row `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL`; `synthesis_confidence` / `theme_agreement_score` are 0..1 scalars that must remain inputs only.
- **Fix applied (§8 "MC16 flags and scalars propagate safely"):** `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL` and other MC16 flags propagate verbatim into feature `quality_flags`, never dropped; the two scalars are declared-features-only, never converted into direction or any composite score.

### D. MC16 un-cited as prior art for the contradiction doctrine
- MC16 already implements the identical fail-closed doctrine at cluster level (separate `contradicting_document_ids` / `supporting_document_ids`, no neutral default, majority-wins channel exclusion). The spec's MIXED / NO_HYPOTHESIS rule was presented as novel.
- **Fix applied (§8):** the contradiction rule now cites MC16's cluster-level doctrine as the precedent it extends; both milestones share one "no fused score" doctrine.

### E. Fixture dependency for handoff B implicit
- CATALYST features in BOXL-derived examples need MC16 rows; the spec did not name the fixture inputs.
- **Fix applied (§11):** BOXL-derived CATALYST features use the admitted `boxl_multidoc_synthesis_slice.json` / `boxl_synthesis_enrichment_expected.json` rows as inputs, exercising the MC16 handoff end-to-end.

---

## 3. Minor findings also fixed

- **§7 `chronological_split` attribution:** now correctly attributed to the foundation's own `research/decision_research/pit_gate.py` (0.6/0.2/0.2), not Phase 5R/6 machinery.
- **§10 Phase 6 assertion continuity:** new lead-in states the Phase 6 registry (`STRAT-001`, `ABST-001`, `PIT-STRAT-001`, `DET-001`, `SAFE-003`) remains enforced and unchanged; `DEC-*` assertions are additive.
- **§8 Phase 6 UI-exclusion supersession:** Phase 6 scoped research UI out *for Phase 6*; operator-UI surfacing is authorized here (milestone A) and supersedes that Phase-6-scoped exclusion.
- **§5 evidence convention:** card registry dir mirrors the hash-bound acceptance convention of `evidence/strategy/<hash>/`.

---

## 4. Verified accurate (no change needed)

- `SHORT_SQUEEZE_EXPERIMENTS` exists in `research/decision_research/experiments.py`; `evaluate_experiment` retains its fail-closed status mapping.
- `runner.py` emits `execution_authority: NONE` and `auto_strategy_promotion: False` (spec's "already enforced" claim).
- §9's "`run_strategy_evaluation` stays in-memory, unchanged" correctly references Phase 6's `strategy/evaluation.py`.
- PIT semantics align: MC16 `available_time <= prediction_cutoff` ≡ DEC `available_time_ns <= decision_time_ns`.
- "No universal news score" (MC16) ≡ "no % bullish / no composite score" (DEC) — consistent doctrine.
- `DEC-DET-001` correctly avoids colliding with Phase 6's `DET-001` (distinct assertion prefix per repo convention).
- `chronological_split` (0.6/0.2) exists as claimed — attribution was the only issue (see §3).

---

## 5. Residual notes

- The audited spec remains **uncommitted** (`?? docs/superpowers/specs/2026-08-22-decision-research-001-design.md`) as of this audit; the prior turn's "Commit the reviewed spec" follow-up is still available.
- No code changed during this audit — findings are spec-text only. The next implementation entry point is `research/decision_research/cards.py` + `registry.py` (spec §5) with fixed-hash SS-family card fixtures (spec §11).
