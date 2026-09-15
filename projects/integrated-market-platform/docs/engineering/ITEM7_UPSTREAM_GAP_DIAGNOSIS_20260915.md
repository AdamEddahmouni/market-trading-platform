# ITEM 7 UPSTREAM GAP — 2026-09-15 RTH (diagnosis only)

**Not Item 7 completion.** Zero governed rows is empty-corpus evidence, not software
success of the gate. Frozen RTH runtime
`.rth-operator-20260915` SHA `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` was not
modified. Live and enrichment worker were not enabled. No forecasts, outcomes,
quotes, or probabilities were manufactured. Settlement was not forced.

Branch: `diagnosis/item7-upstream-20260915` (notes only; no merge/push).

## Observed Lane C collector result (valid empty corpus)

Cutoff `training_cutoff_ns=1789479245806950100` (`2026-09-15T09:34:05-04:00`).
Collector persistence root was canonical
`projects/integrated-market-platform/.local` (not the frozen worktree `.local`).

| Field | Value |
| --- | ---: |
| collector exit | 0 |
| status | `ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY` |
| `market_rth_open` | true at collect |
| `governed_candidate_rows` | 0 |
| `pit_valid_governed_rows` | 0 |
| `fixture_only_rows` | 0 |
| forecasts / outcomes / snapshots / signals / ledger | 0 / 0 / 0 / 0 / 0 |
| `missing_edges` | `{}` (empty join, not a failed join of existing rows) |
| blockers | `NO_GOVERNED_PATH_A_TRAINING_CORPUS`, `RTH_OR_FUTURE_OUTCOMES_REQUIRED` |
| production status | `PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS` |
| load note | no governed intelligence JSONL or forecast directories |

Artifacts:
`C:\Users\adame\Desktop\market-trading-platform\.rth-operator-20260915\projects\integrated-market-platform\.local\rth-session-20260915\lane-c-item7\`

`CAPTURE_CONTEXT_ABSENT` (PR #196 sidecar not on today's runtime) is an evidence-class
limitation. It is **not** today's Item 7 completion blocker and must not be "fixed"
by fabricating rows.

## Exact missing production chain

Required generating loop (collector is a **reader**, not a producer):

```text
lawful quote/BBO evidence
  → grid candidate (capability QUOTE + valid bid/ask)
  → SnapshotV1 + momentum_simple + net_signed_share SignalV1
  → pre-existing PRODUCTION ForecastV1 (not CONTROL, not RESEARCH, Path A 5m identity)
  → PredictionLedgerEntryV1 (bind candidate_id → existing forecast_id)
  → maturity (PATH_A_HORIZON_NS = 300_000_000_000 = 5 minutes)
  → OutcomeV1 SETTLED with realized LONG/SHORT
  → persist Forecast/Snapshot/Signal/Outcome/Ledger where the collector can load them
  → PIT-valid governed row → floors (specialist 8/2, calibration 20/5) → attestation
  → training_build → hop-consumable PRODUCTION JSON
```

**First failing production stage on this runtime:** there is no collector-readable
governed persistence of *any* stage. Join diagnostics are empty because there are
no outcomes to miss a forecast for.

Prior-day (2026-09-14) OpenD capture, **not** on today's `IMP_STATE_DIR`, already
proved the next lawful-input break even when envelopes exist:

- 3540 raw envelopes, 1770 tape-eligible, **0 grid**
- 885 `US_EQUITY_L1` all dropped `NOT_TAPE_ELIGIBLE_QUOTE_MISSING_VALID_BID_ASK`
- 0 forecast bindings → 0 ledger → settlement not invoked
- `materialize_opend_capture_jsonl` does not synthesize forecasts; empty
  `forecast_bindings` is contract-correct

Today's Opportunity path independently confirms no live generating loop:
`LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, ranked items `[]`,
`opportunity_operator_acks=0`. Do not treat that as an Item 7 collector bug.

## Software vs no lawful inputs (this runtime)

| Stage | Software present (library/CLI) | Lawful inputs on 2026-09-15 frozen runtime |
| --- | --- | --- |
| Lawful quote / BBO | OpenD L1 hop; `tools/moomoo/item7_bbo_snapshot.py` (`SNAPSHOT_BBO`, never derived from `last_price`); capture JSONL schema | **No** governed capture JSONL under `IMP_STATE_DIR`. BBO probe not recorded this session. Prior L1 captures lacked valid bid/ask. `SNAPSHOT_BBO` is diagnostic, not wired into grid. |
| Grid candidate | `is_grid_point_candidate` (`opend_capture_ledger.py`): alias `US_EQUITY_L1`→`QUOTE`, requires tape-eligible **and** valid bid/ask | **0**. L1 last_price-only envelopes cannot become grid. Must not synthesize BBO. |
| Snapshot + Path A features | Snapshot builder; `momentum-calculator` / `cvd-calculator`; ingress `put_snapshot` is SEC/congressional, not Path A quote loop | **0** snapshots, **0** signals in collector load. Ingress does not emit Path A `momentum_simple` + `net_signed_share` from today's quotes. |
| Pre-existing PRODUCTION `ForecastV1` | `emit_production_forecast` (needs fitted specialist); `produce_paper_demo_forecast` (needs contributor **and** calibration; persist only `EMITTED_CALIBRATED`); hop **load-only** | **0**. No `path-a/forecasts` (or aliases) under persistence root. Hop JSON persist is not `intelligence_records.jsonl`. CONTROL/RESEARCH rejected by collector. |
| Ledger candidate | `PredictionLedgerService.register_forecast`; capture bridge only if `forecast_bindings[candidate_id]` already exists in repository | **0**. Paper runtime uses `COUNTERFACTUAL` and in-memory repo. Capture bridge uses `ACTUAL_LIVE` only with bindings. |
| Maturity | Path A horizon 5m; `OutcomeSettlementService.inspect_settlement` | No pending rows. Forcing settlement is forbidden and would be empty-op. |
| Settlement | `OutcomeSettlementService`; labels only from settled `OutcomeV1` `LONG`/`SHORT` | **0** outcomes. JSONL scan: 0 settled envelopes. |
| Collector / PIT / floors | `corpus_collector.py`, `corpus_persistence.py`, `corpus_join_diagnostics.py`, `item7_corpus_collector.py` | Software-ready; empty corpus honestly reported. |
| Evidence validator | `item7_corpus_evidence_validator.py` on frozen SHA (PR #199 class); `--context` sidecar is PR #196 | Optional. `CAPTURE_CONTEXT_ABSENT` expected. Does not mint rows. |
| Calibration / PRODUCTION JSON | `training_build.py`, `item7_production_readiness.py` | Blocked on governed corpus. Floors unmet. Not hop-consumable. |

There is **no production writer** of `intelligence_records.jsonl` outside tests.
Collector loaders look only for:

- `intelligence/intelligence_records.jsonl`
- `intelligence_records.jsonl`
- `path-a/intelligence_records.jsonl`
- `path-a/forecasts`, `path-a/production/forecasts`, `forecasts/path-a`

Mongo (`IMP_MONGODB_URI`) was not used. SQLite `imp-state.sqlite3` holds FTEP /
opportunity tables, not ForecastV1/OutcomeV1.

## What cannot be fixed without live governed ForecastV1 / quote evidence

- Zero `governed_candidate_rows` / `pit_valid_governed_rows`
- Grid from last_price-only L1 (doctrine: no derived BBO)
- First PRODUCTION `ForecastV1` (emitter forbids quote-print mint; hop producer
  abstains without calibration artifact; calibration artifact requires corpus
  floors; CONTROL is excluded from Path A corpus)
- Ledger rows without an already-present `forecast_id`
- Settled `LONG`/`SHORT` labels without matured forecasts + later lawful quotes
- `ITEM7_GOVERNED_ROW_CAPTURED`, `GOVERNED_PATH_A_TRAINING_CORPUS_READY`,
  `PRODUCTION_FORECAST_ARTIFACT_READY`, `ITEM7_COMPLETE`

Chicken-egg (by design, not a collector bug): readiness/producer need a governed
training manifest; the collector needs pre-existing PRODUCTION forecasts joined
to settled outcomes. A later PR may **wire persistence and BBO-grid**, but it
cannot lawfully mint the first probability.

## Minimal later PR (priority 7)

**After** live OE loop, Item 9, launcher, staleness, and routing — not today.

**In scope (software wiring only; no fabricated corpus):**

1. Operator-local append-only `intelligence_records.jsonl` (or equivalent under
   `IMP_STATE_DIR`) written by the Path A / capture-ledger path for
   `forecast`, `snapshot`, `signal`, `outcome`, `prediction_ledger_entry` —
   the shapes `corpus_persistence.py` already loads.
2. Admit **vendor** bid/ask (`SNAPSHOT_BBO` or L1 envelopes that already carry
   valid bid/ask) into `is_grid_point_candidate`. Do **not** fill bid/ask from
   `last_price`. Do **not** redefine `US_EQUITY_L1` as SNAPSHOT_BBO.
3. Once a **pre-existing** PRODUCTION `ForecastV1` is in the repository: bind
   `OCLC-*` candidate_id → `forecast_id`, register ledger, wait 5m, settle from
   a later lawful quote. No forced settlement; no quote-synthetic labels.
4. Optional attach of PR #196 `evidence_capture_context_v1` as SOFTWARE /
   PROSPECTIVE sidecar. Sidecar must not upgrade empty/fixture evidence.

**Out of scope for that PR:** manufacturing ForecastV1/probabilities/outcomes;
lowering floors; claiming Item 7 complete; enabling Live; turning on enrichment
worker; treating `CAPTURE_CONTEXT_ABSENT` as the row blocker.

**Prerequisite (not this PR):** a live Opportunity Engine / Paper Path A loop
that can resolve a pre-existing PRODUCTION forecast (`FORECAST_UNAVAILABLE` and
`LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` are upstream of Item 7 rows).
