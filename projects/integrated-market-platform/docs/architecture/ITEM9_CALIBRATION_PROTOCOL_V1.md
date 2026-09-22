# Item 9 Calibration Protocol V1

**Document ID:** `ITEM9_CALIBRATION_PROTOCOL_V1`

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`

**Protocol version:** `item9.calibration-protocol/1.0.0`

**Dataset schema:** `item9.calibration-dataset/1.0.0`

**Calibration state:** `NOT_CALIBRATED`

**Item 9 status:** `PARTIAL / NOT_CALIBRATED`

This protocol governs future corpus collection and eventual calibration of the
Paper `BarConservativeSimulator` against lawful 1-minute `BAR_OHLCV_1M`
evidence. It does **not** fit parameters, select a winner, activate FTEP, or
mint a production forecast.

Executable twin:
`src/market_platform_foundation/paper/calibration/item9_calibration_protocol.py`.
Machine-readable dataset header:
`manifests/paper/item9_calibration_dataset_v1.json`.

Parent contracts: [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](PAPER_SIMULATOR_CALIBRATION_CONTRACT.md),
[IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md](IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md),
BUILD 15 `DIRECTION_UP_DOWN_5M_POLICY` (`intelligence/outcomes/policy.py`).

## 1. What Item 9 calibrates

Item 9 eventually calibrates **IMP Paper bar-conservative fill behavior** for
US cash equities on `BAR_OHLCV_1M`, not Path A probability models.

| Axis | Current code truth |
|---|---|
| Simulator | `BarConservativeSimulator` `phase7.bar-conservative/1.1.0` |
| Inputs | PIT-visible completed 1m OHLCV bars; signal `created_time` |
| Output | order state `FILLED` / `REJECTED` / partial; fill at bar **high** (long) or **low** (short); 1/100 participation cap |
| Path A relationship | Shared 5-minute `direction` horizon exists on Path A PRODUCTION identity. Path A **labels** are BUILD 15 `TRADE` prints, not bars. Item 7 owns Path A forecast calibration. |
| Provisional thresholds | All numeric gates `UNSET/BLOCKING` (`paper/calibration/thresholds.py`) |
| Admissible market evidence | Mode B `PROSPECTIVE_BAR_OHLCV_1M` + nested `PROSPECTIVE_OPEND_KLINE` |
| Comparator | Alpaca Paper HTTPS; missing keys `COMPARATOR_NOT_CONFIGURED` |

A simulator `FILLED` result is IMP Execution Simulation Layer evidence. It is
not market truth and is not a Path A label.

## 2. Unit of observation

One row = **one Mode B prospective proof receipt** identified by stable
`experiment_id`.

Required identity fields:

- `observation_id` = `experiment_id`
- `instrument_id` (canonical symbol as collected, e.g. `AAPL`)
- `signal_time_ns` / `signal_established_at_ns`
- `feature_cutoff_ns` = first post-signal bar `available_time` (bar end)
- feature reference (`bar_id` / `normalized_event_id` / payload hash or payload ref)
- feature provenance (provider, source, evidence class, fetch times)
- Path A label slot (value + evidence ids + availability) — may be null
- inclusion/exclusion state
- `runtime_git_sha`, protocol version

Do not mint multiple rows from the same `experiment_id`. Re-polls of the same
Mode B run that persist the same id are duplicates.

## 3. Label contract (Path A 5-minute)

Frozen from BUILD 15, not invented from the 1m path proof.

| Field | Rule |
|---|---|
| Reference / decision time | `signal_time_ns` (information available at or before feature cutoff) |
| Horizon | `PATH_A_HORIZON_NS` = 300_000_000_000 (5 minutes) |
| Target time | `signal_time_ns + 5m` |
| Terminal window | `[target_time, target_time + 60s]` (`target_window_tolerance_ns`) |
| Late-arrival grace | 0 |
| Reference price | P6 P0 on eligible **TRADE** tape at decision time |
| Terminal price | first valid **TRADE** in the terminal window with `available_time <= cutoff` |
| Direction | `sign(p_target / p0 - 1)`; exact zero is `UNLABELABLE` / `ZERO_RETURN` |
| Allowed terminal evidence | `TRADE` only |
| Fallback | none (`fallback_observation_kinds` empty) |
| Missing label | leave row unlabelable; do not impute |
| Session | US cash RTH only |
| Extended hours | excluded |
| Corporate actions | operator `EXCLUDED` with reason; no automatic CA feed in v1 |

**`BAR_OHLCV_1M` is not an approved Path A label source.** Five completed 1m
closes must not be composed into a Path A label under this protocol.

The overlapping signal minute (bar starts before `signal_time`, ends after) is
**feature-eligible** under the existing PIT rule `available_time > signal_time`.
That same bar is **not** a Path A TRADE terminal.

## 4. Item 9 feature / simulator timing

| Instant | Meaning |
|---|---|
| Event start | kline `time_key` / canonical `event_time` (bar open) |
| Event end / availability | `event_time + 60s` = `available_time` |
| Signal | wall clock when Mode B records `signal_time_ns` |
| Feature eligibility | first bar with `available_time > signal_time` |
| Incomplete bars | `bar_end > fetched_at` dropped at normalize; never features |

v1 search space for the fill model is **empty**. The conservative high/low fill
and 1% cap stay fixed. Later work may set the five numeric **gates** after
sample floors; it may not grid-search fill internals after seeing outcomes.

## 5. Evidence classes (do not mix)

| Class | Use |
|---|---|
| `PROSPECTIVE_BAR_OHLCV_1M` + `PROSPECTIVE_OPEND_KLINE` | Only class that may enter the calibration corpus |
| `NOT_PROSPECTIVE_EVIDENCE` / Mode A | Transport/dev only |
| `ADMITTED_HISTORICAL_FIXTURE` | Tests/methodology only |
| Unknown | excluded until classified |

Historical kline must not be inserted into the prospective corpus.

## 6. Persistence

Source of truth: immutable JSON receipts under
`artifacts/ftep-v1-002/item9-prospective-proof-receipts/`.

The calibration dataset is **derived** and must be rebuildable from those
receipts. It is not an opaque CSV. Discovery scans **only** that governed
directory (`*.json`, UTF-8). It must not walk `.local` or unrelated JSONL.

## 7. Inclusion / exclusion

Corpus-admissible only when all hold:

- Mode B prospective evidence class
- US cash RTH at `signal_time_ns`
- completed first post-signal bar
- `raw_provenance_hash` not SHA256 of `[]`
- unique `experiment_id`
- receipt `calibrated=false` and `empirical_active=false`

Empty raw hash (`4f53cda1…` = SHA256(`[]`)) → `PATH_PROOF_ONLY`. The September
17, 2026 AAPL receipt remains a path proof. It is **not** rewritten and is
**not** corpus-admissible until a **future** receipt (new file) carries a
non-empty raw-row hash. Do not backfill hash into the existing file.

## 8. Labelability audit (current empirical basis)

Operator-local receipt (immutable; not copied into this protocol):

`item9-prospective-20260917-rth-aapl` on runtime `aae13fd1…`

| Count | Value |
|---|---|
| Prospective observations | 1 |
| Path A labelable now | 0 |
| Awaiting Path A TRADE horizon/evidence | 1 |
| Invalid | 0 |
| Duplicate | 0 |
| Corpus-admissible | 0 (`PATH_PROOF_ONLY` / empty raw hash) |
| Historical/fixture mixed in | 0 |

Git-tracked receipts under the governed directory: **0** at protocol freeze.

## 9. Temporal split

Chronological 60% / 20% / 20% by `signal_time_ns`:

1. development / training period
2. calibration / selection period
3. untouched evaluation period

No random shuffle. Evaluation ids never enter selection.

## 10. Minimum sample gate

Fitting and `CALIBRATED` remain forbidden while any of these fail:

- included rows `<` BUILD 14 `MINIMUM_CALIBRATION_SAMPLES` (20)
- distinct RTH session dates `< 3`
- evaluation split `<` BUILD 14 `MINIMUM_CLASS_COUNT` (5)
- numeric gates still `UNSET/BLOCKING` for any **execution claim**

Return `INSUFFICIENT_CALIBRATION_EVIDENCE`. Do not invent a smaller N to
enable the next run.

## 11. Metrics (frozen before a larger corpus)

Use existing `paper/calibration/metrics.py` dimensions when a comparator is
paired: fill disagreement, price/slippage error, timing error, partial
completion, reject/cancel disagreement, position/P&L delta, unexplained
divergence, sample honesty. Small N is `INSUFFICIENT_SAMPLE` / `NOT_OBSERVABLE`,
never a 0% vanity score.

Path A directional accuracy, Brier, and specialist logistic metrics are **Item 7**
and are out of scope here.

## 12. Transaction costs / implementability

v1 records cost fields as `NOT_OBSERVABLE` unless both IMP and comparator
report commission and fees. Do not treat the internal `FILLED` dry-run as a
marketable fill. Spread, latency, and slippage vs Alpaca remain comparator
challenges, not ground truth. Position size stays the dry-run quantity (1).
Unfilled / rejected states stay first-class.

## 13. Comparator

Alpaca Paper (`https://paper-api.alpaca.markets`) remains the $0 HTTPS
comparator. It is **optional** for corpus accumulation and path proof. It is a
**hard gate** for any execution-realism / `PASS_FOR_DECLARED_SCOPE` claim.

`COMPARATOR_NOT_CONFIGURED` does not block this protocol freeze. Paid Live
Alpaca is `LIVE_FORBIDDEN`. Tradier stays unused. No other free provider is
promoted as a substitute fill comparator in v1.

Compared objects: IMP simulated fill vs Alpaca Paper fill semantics (fill /
no-fill, price, timing), never “market bars equal truth.”

## 14. FTEP and production

Calibration completion does **not** imply `EMPIRICAL_ACTIVE` or
`PRODUCTION_FORECAST_ARTIFACT_READY`. Those are independent gates.

Promotion sequence:

1. enough corpus-admissible receipts (sample gate)
2. this protocol remains frozen
3. calibration **evaluation** run (no post-hoc search expansion)
4. untouched evaluation split
5. calibration artifact for the declared simulator scope
6. FTEP campaign freeze / forward-test if a campaign uses that execution claim
7. production forecast eligibility remains Item 7

## 15. Software prerequisites

| Issue | Severity | Required-before | v1 action |
|---|---|---|---|
| Raw provenance hash SHA256(`[]`) on Mode B poll | High for corpus trust | Corpus admission (not path-proof validity) | Hash `BarLoadResult.raw_rows` on future receipts. Do not edit 2026-09-17. |
| OpenD connect-churn (open/close quote context) | Medium operational | Prefer before dense multi-hour collection | Separate increment; persistent context + tests |
| Non-UTF-8 `.local` JSONL | Item 7 scanner; Item 9 if discovery is unbounded | Item 9 dataset discovery | Scan only governed receipt `*.json`; reject invalid UTF-8 as `INVALID` |

## 16. Item 7

Item 7 remains independent (`ITEM7_PENDING_NATURAL_EVIDENCE` / PARTIAL). This
protocol does not settle Path A, mint TRADE, or merge PR #222.

## 17. Validation readiness companions (software; not calibration)

Protocol version remains **`item9.calibration-protocol/1.0.0`**. Companion
schemas bind to it without opening a fittable `1.1.0`:

| Companion | Schema / CLI |
|---|---|
| Shared vocabulary | `item9_validation_readiness_contract.py` |
| Readiness snapshot | `item9.validation-readiness-snapshot/1.0.0` · `python tools/imp.py item9 readiness-snapshot` |
| Calibration preflight | `CALIBRATION_PREFLIGHT_READY` / `BLOCKED` · `python tools/imp.py item9 calibration-preflight` |
| Methodology freeze | `item9.calibration-methodology-freeze/1.0.0` · `manifests/paper/item9_calibration_methodology_freeze_v1.json` |
| NOT_OBSERVED gaps | `manifests/paper/item9_not_observed_intervals_v1.json` (Sep 21 ≈10:43–13:09 ET; Sep 18 epoch `121031`) |
| Paper acceptance | [ITEM9_PAPER_VALIDATION_ACCEPTANCE_V1.md](ITEM9_PAPER_VALIDATION_ACCEPTANCE_V1.md) |

Invariants for the readiness path:

- `fitting_allowed=false`; `ITEM9_CALIBRATION_RUN=FORBIDDEN`; Live **OFF**
- Search complexity remains **0** (protocol freeze recorded; not retuned from corpus)
- `AUTHORIZATION_ABSENT` does **not** block `CALIBRATION_PREFLIGHT_READY`; it blocks execution
- Ready verdict may set `readiness_state=ITEM9_CALIBRATION_READY_AWAITING_AUTHORIZATION` without changing `item9_status=PARTIAL_NOT_CALIBRATED` or `calibrated`
- Strategy IDs on historical Mode B bar receipts are `NOT_APPLICABLE`
- `EVALUATION_ONLY` is a lifecycle role on an admissible row, not a second exclusion
- Missing Paper lineage links stay `NOT_OBSERVED`; do not invent floors or promote `PATH_PROOF_ONLY`

### Post-merge measured proof on `1cd63fe9` (2026-09-22)

Read-only on merge [#376](https://github.com/AdamEddahmouni/market-trading-platform/pull/376) /
`1cd63fe98411c339e80537af7d6170b4ebdf71b8` against the frozen collector receipt
dir (receipts **not** mutated):

- Counts: **432** admissible / **1** `PATH_PROOF_ONLY` / **87** eval / **3** RTH dates
- `preflight_verdict=CALIBRATION_PREFLIGHT_READY`
- Measured `readiness_state=ITEM9_CALIBRATION_READY_AWAITING_AUTHORIZATION` (software token; **not** independent certification)
- `fitting_allowed=false`; `item9_calibration_run=FORBIDDEN`; `calibrated=false`
- ABSENT-auth execute harness → `verdict=CALIBRATION_EXECUTION_REFUSED` /
  `reason=AUTHORIZATION_REQUIRED_BEFORE_CORPUS_READ` / `corpus_read_attempted=false`

Calibration was **not** executed. Fitting remains unauthorized. Paper is **not**
validated. Full30 is **not** complete. Live is **not** authorized.
