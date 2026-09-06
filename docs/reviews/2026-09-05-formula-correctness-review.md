# Formula correctness review — 2026-09-05

| Field | Value |
|---|---|
| Date | 2026-09-05 |
| Scope | Pre-trade quantitative correctness across `projects/integrated-market-platform` and `projects/short-squeeze-project` |
| Companion | [Hardening task plan](2026-09-04-hardening-task-plan.md) Q-series; ledger `projects/integrated-market-platform/docs/research/FORMULA_LEDGER.md` |
| Status | Spec-pinning and fail-closed numerics verified. **No trade authority.** Gates G1–G6 remain closed. No `SUPPORTED` edge. LIVE-001 / P6 Shadow Run 1 / canary / broker wires were not opened. |

This review answers: **does the implemented math match a versioned spec?** It does not answer whether any formula predicts returns.

---

## Verdict

Safety gates are unchanged. The formula campaign pinned 88 ledger rows, renamed risk-neutral Q to an honest log-normal moment approximation, fail-closed options friction without an underlying price, labeled variance estimators, required usable OFI, subtracted fusion friction once, and tagged naive strategy interpretations as `baseline_only`. Path invariants from Phase 3 (canonical opportunity mint, `MARKET_CONTEXT` → `catalyst`, eligibility omit-fail-closed, unadmitted/donor isolation) hold in tests.

Correctness here is **spec match**, not edge. Q-H2 (2026-09-05): O5 signed-flow no longer uses a silent `DEFAULT_SPOT=100.0`. Q-H1-O5 / O2 (same day): O5 greeks also fail closed without positive vol and rate; O2 no longer uses silent `strike × 1.02/0.98`. Q-H1-rate (same day): dealer BSM, O2 surface IV, and O3 Q no longer silently pin `rate=0.05`; missing rate fail-closes (`BSM_VOL_OR_RATE_ASSUMPTION_MISSING` / skip point / `RATE_ASSUMPTION_MISSING`). Q-H1-O10-rate (same day): O10 / R-O6 research snapshots no longer silently pin `rate=0.05`; missing rate fail-closes with `RATE_ASSUMPTION_MISSING` (`delta_hedged_research_v2` / `r_o6_research_v2`). Fusion / GARCH / HAR / ADAM / logistic stay unfitted (Q-H1 open).

---

## What is spec-pinned (`exact_metric`)

47 of 88 ledger rows are `exact_metric` (O10/R-O6 added as `research_baseline`). Notable families:

- Squeeze Decimal returns, gaps, ranges, baselines, z-scores, SI/borrow/DTC, bar acceleration (open→close float, fail-closed to `None`)
- CS-OFI / BVC / CVD / L1 microprice where the arithmetic is fully specified
- Close-to-close realized vol, Parkinson, EWMA λ=0.94 recursion
- BSM price, Newton IV, greeks day-count (365 calendar vs 252 vol where asserted)
- Fusion product formula (gross EV, occurrence weight, liquidity/futures factors) including `UNAVAILABLE` / `LIQUIDITY_BLOCKED` / non-positive EV
- Fast-signal window arithmetic (momentum, sample vol, rvol, spread, depth, CVD)
- Naive last-value: score equals last `bar_close`; empty training → `FCAST_NO_TRAINING_OBSERVATION`

Goldens: `tests/formulas/test_formula_goldens.py`, squeeze `tests/metrics/test_bar_acceleration.py` / `test_returns.py` / `test_statistics.py`, ADAM `tests/calibration/test_adam_formula_golden.py`.

---

## What remains `research_baseline`

23 rows, including O10 delta-hedged path and R-O6 compose (fail-closed without rate):

- Physical P Gaussian with **mean identically 0**; P−Q `directional_edge` is `vs_zero_drift_baseline`
- Q = `risk_neutral_log_normal_moment_approx_v1` (average IVs → log-normal moments). **Not** Breeden–Litzenberger
- FORECAST_MOMENTUM / whale aligned / whale contrarian: interpretations of naive last-value, `baseline_only`
- Squeeze logistic hazard: tagged baseline, unfitted weights

These are honest estimators. They are not promoted champions.

---

## What remains `heuristic_unconstrained`

18 rows. Constants are **pinned, not calibrated**:

- Fusion liquidity 1.05 / 0.85 plus fragility/fill/slippage haircuts (named module constants; drift-guarded vs ledger)
- GARCH(1,1) ω=1e-6, α=0.05, β=0.90
- HAR-RV 0.3 / 0.4 / 0.3 on 5 / 22 / 66
- ADAM pressure/ignition weights and linear maps
- Squeeze logistic weights (0.8, 0.5, 0.3)

O5 no longer silently uses `DEFAULT_VOL=0.35` / `DEFAULT_RATE=0.05` after spot is known. O2 no longer silently uses `strike × 1.02/0.98`. Dealer / O2 / O3 no longer silently use `rate=0.05`: dealer and O5 greeks require a positive resolved rate (`BSM_VOL_OR_RATE_ASSUMPTION_MISSING`); O2 skips the surface point; O3 sets `available=False` with `RATE_ASSUMPTION_MISSING`. O10 / R-O6 no longer silently use `rate=0.05` (Q-H1-O10-rate closed). Tape fixtures stamp `rate` 0.04. Those rate leftovers are Q-H1-rate / Q-H1-O10-rate (closed). Q-H1 remains the unfitted fusion/GARCH/HAR/ADAM/logistic pins only.

ADAM ignition still does **not** share a return definition with squeeze Decimal close-to-close returns.

---

## Path invariants (Phase 3, verified)

- Canonical opportunity: `StrategyMatch` → `bridge.py` → `OpportunityEngine`; duplicate identity conflicts on persist
- Lane map: discovery ≠ workspace kebab ≠ `LaneId`; `MARKET_CONTEXT` → workspace `catalyst`
- Execution-intent runtime omitting `strategy_eligibility` is ineligible; research scanners do not mint `OrderReadyV1`
- Unadmitted captures rejected at training, promotion, and OrderReady; donor execution modules unreachable from platform adapters

---

## Gates G1–G6 (still closed)

Unchanged from the [2026-09-04 hardening review](2026-09-04-hardening-review.md):

| Gate | Status |
|---|---|
| G1 Forward validation campaign (P6 Shadow Run 1 / EVIDENCE-01C) | Closed / deferred |
| G2 Champion promoted on forward evidence (`SUPPORTED`) | Closed — none |
| G3 Live canary executed | Closed / not executed |
| G4 Production live broker transport | Closed / absent |
| G5 Real-provider observational shakedown | Closed / deferred |
| G6 ES-session acceptance | Closed / blocked on lawful ES bytes |

G7 attribution parity was already made a fail-closed invariant (task P0-4). That still grants **no** execution authority.

---

## Verification this review used

Python 3.13 (`py -3.13`). Python 3.10 cannot import `StrEnum` / `datetime.UTC`.

| Command | Result |
|---|---|
| Targeted formula + Phase 3 pytest | 63 passed |
| Broader pytest (`tests/formulas`, `options`, `cross_lane`, `order_flow`, `phase6`, `distribution`, `intelligence`, `platform`, `validation/test_validation_manifest.py`) | 1881 passed, 27 skipped |
| `py -3.13 tools/imp.py validate domain options` | 545 passed, 11 skipped |
| `py -3.13 tools/imp.py validate domain order-flow` | 525 passed, 11 skipped |
| Squeeze metrics + ADAM (`PYTHONPATH=src`) | 49 passed |
| UI `npx vitest run …/laneRegistry.test.ts` | 9 passed |
| `py -3.13 tools/imp.py validate changed` from the **monorepo snapshot** | 21 passed (mandatory invariants only). Git paths are `projects/integrated-market-platform/…`, so suite `source_globs` do not match; this is **not** a full `validate.py` |

**Not run:** `imp.py validate full` (thousands of tests; last recorded full offline receipt on 2026-09-04 was 3487 passed). Full squeeze suite (environmental IB / freeze / git-baseline failures known from P1-8). Live-gated suites.

Campaign-only breakage fixed: unclassified `tests/formulas` blocked `validate.py` until the `formulas` suite was added to `tools/validation_manifest.json` (offline suite count 59 → 60).
