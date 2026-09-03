# Options O10 Phase B — Chain History Admission

**Status:** Preparation scaffold — no Phase B datasets admitted  
**Manifest:** [`manifests/options/phase-b-chain-history-admission.json`](../../manifests/options/phase-b-chain-history-admission.json)  
**Harness:** [`src/market_platform_foundation/options/research/harness.py`](../../src/market_platform_foundation/options/research/harness.py)

O10-S5 baseline gates **PASS on Phase A fixtures** (`nvda_bars_slice.json`, `nvda_r_o6_panel_slice.json`, `nvda_options_slice.json`). Phase B re-validation on multi-year chain history is required before distributional or surface ML is authorized.

---

## Phase B data requirements

| Requirement ID | Dataset | Minimum | Priority | Blocks |
|---|---|---|---|---|
| `PHASE_B_CHAIN_SNAPSHOTS` | Single-name full chain snapshots | 3–5 symbols | HIGH | R-O10-SURF OOS, surface ML |
| `PHASE_B_DAILY_CHAIN_HISTORY` | Daily chain history | 2+ years, 1 symbol | HIGH | R-O5/R-O6 OOS walk-forward |
| `PHASE_B_EARNINGS_STRADDLE` | Earnings dates + ATM straddle prices | 1 symbol with events | MEDIUM | R-O7 event-vol extension |

All datasets must carry aligned `event_time` and `available_time`. Walk-forward evaluation uses chronological partitions only; overlapping expirations require purge/embargo per [`OPTIONS_RESEARCH_PLAN.md`](../research/OPTIONS_RESEARCH_PLAN.md) §2.4.

---

## Admission checklist

Complete every item before changing manifest `status` from `PENDING` to `ADMITTED`:

1. **Procurement authorization** — lawful source documented; no live Moomoo capture bytes promoted without ADR review.
2. **Chain snapshots (3–5 symbols)** — full chain per symbol with IV, bid/ask, OI, and underlying; surface QA passes O2/O3 gates on each snapshot.
3. **Daily chain history (≥2 years, ≥1 symbol)** — one continuous daily series with PIT-safe `available_time`; history spans at least 504 trading-day observations for walk-forward policy defaults.
4. **Earnings + straddle panel** — announcement dates with pre-event ATM straddle mid prices for at least one admitted symbol.
5. **Fixture manifests** — each admitted payload gets a fixture admission manifest under `tests/fixtures/providers/options/` with `content_path`, `instrument_id`, and `admitted_fixture_id`.
6. **Manifest slots** — populate `dataset_slots` in the Phase B admission manifest with `requirement_id`, `admitted_fixture_id`, and `content_path` for every requirement.
7. **Harness smoke** — `run_o10_phase_b_walk_forward_harness()` returns `available=True` with non-empty partitions and `pit_status=PASS`.
8. **Gate re-run** — R-O5, R-O6, and R-O10-SURF OOS gates pass on admitted Phase B data (not fixture slices).
9. **Roadmap update** — record Phase B OOS evidence in `OPTIONS_JOINT_LANE_REPORT.md` and cooperative roadmap.

Until step 6–7 pass, the harness **fail-closes** with `reason=PHASE_B_DATA_NOT_ADMITTED` and empty partitions.

---

## Walk-forward partition policy

Defaults are declared in the admission manifest `walk_forward_policy`:

| Field | Default | Purpose |
|---|---|---|
| `min_train_days` | 252 | Minimum in-sample trading days |
| `test_size_days` | 21 | Out-of-sample fold width |
| `embargo_days` | 5 | Gap between train end and test start |
| `purge_overlapping_expirations` | true | Exclude overlapping option lifetimes across fold boundary |
| `event_clustering_aware` | true | Stratify or embargo earnings clusters |

Implementation lives in `build_phase_b_walk_forward_partitions()`; distributional ML is **not** wired until admission completes.

---

## Related documents

- [`OPTIONS_RESEARCH_PLAN.md`](../research/OPTIONS_RESEARCH_PLAN.md) — research milestones and Phase B dataset table
- [`tools/options/run_o10_baseline_gate_validation.py`](../../tools/options/run_o10_baseline_gate_validation.py) — Phase A fixture gate report
