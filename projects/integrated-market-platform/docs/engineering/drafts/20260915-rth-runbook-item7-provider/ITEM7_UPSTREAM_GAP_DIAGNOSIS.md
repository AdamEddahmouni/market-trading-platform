# ITEM 7 UPSTREAM GAP — 2026-09-15 RTH (diagnosis only)

**Not Item 7 completion.** Zero governed rows is empty-corpus evidence, not
software success of the gate. Frozen RTH runtime `.rth-operator-20260915` SHA
`7aade60bf8041df5ebf9f0ac856d5d8802845c8d` was not modified. Live and
enrichment worker were not enabled. No forecasts, outcomes, quotes, or
probabilities were manufactured. Settlement was not forced.

**Provenance:** refined copy of notes on `diagnosis/item7-upstream-20260915`
(`docs/engineering/ITEM7_UPSTREAM_GAP_DIAGNOSIS_20260915.md`). That branch was
not rewritten. Stage labels below use the requested classification vocabulary.

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

`CAPTURE_CONTEXT_ABSENT` (PR #196 sidecar not on today's runtime) is an
evidence-class limitation. It is **not** today's Item 7 completion blocker and
must not be "fixed" by fabricating rows.

## Exact missing production chain

Collector is a **reader**, not a producer. Required generating loop:

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

**First failing production stage on this runtime:** there is no
collector-readable governed persistence of *any* stage. Join diagnostics are
empty because there are no outcomes to miss a forecast for.

Prior-day (2026-09-14) OpenD capture, **not** on today's `IMP_STATE_DIR`,
already proved the next lawful-input break even when envelopes exist:

- 3540 raw envelopes, 1770 tape-eligible, **0 grid**
- 885 `US_EQUITY_L1` all dropped `NOT_TAPE_ELIGIBLE_QUOTE_MISSING_VALID_BID_ASK`
- 0 forecast bindings → 0 ledger → settlement not invoked
- `materialize_opend_capture_jsonl` does not synthesize forecasts; empty
  `forecast_bindings` is contract-correct

Today's Opportunity path independently confirms no live generating loop:
`LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, ranked items `[]`,
`opportunity_operator_acks=0`. Do not treat that as an Item 7 collector bug.

## Stage classification

Labels (exactly one primary per stage):

| Label | Meaning here |
|---|---|
| `IMPLEMENTED` | Library **and** operational path exist; today's empty result is honest |
| `SOFTWARE_ONLY` | Library/CLI exists; not the live generating loop |
| `NOT WIRED` | Pieces exist but are not connected on the production path |
| `NOT IMPLEMENTED` | Missing software (no production writer / no mint) |
| `WAITING FOR EMPIRICAL DATA` | Software can consume lawful inputs that were not present |

| Stage | Classification | Evidence |
|---|---|---|
| Collector / PIT / floors / diagnose / collect | `IMPLEMENTED` | Status `ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY`; 0 rows; empty `missing_edges` |
| Lawful quote / BBO | `SOFTWARE_ONLY` + `NOT WIRED` | OpenD L1 hop; `item7_bbo_snapshot.py` (`SNAPSHOT_BBO`, never from `last_price`). BBO probe not recorded this session. `SNAPSHOT_BBO` is diagnostic, not admitted to grid. No governed capture JSONL under `IMP_STATE_DIR`. |
| Grid candidate | `SOFTWARE_ONLY` + `NOT WIRED` | `is_grid_point_candidate` requires tape-eligible **and** valid bid/ask. Last_price-only `US_EQUITY_L1` cannot grid. Must not synthesize BBO. |
| SnapshotV1 + `momentum_simple` + `net_signed_share` | `NOT WIRED` | Snapshot builders exist. Ingress `put_snapshot` is SEC/congressional, not a Path A quote loop. Collector load: 0 snapshots, 0 signals. |
| Pre-existing PRODUCTION `ForecastV1` | `SOFTWARE_ONLY` + `WAITING FOR EMPIRICAL DATA` | `emit_production_forecast` / hop producer exist; hop is **load-only**. CONTROL/RESEARCH rejected. No `path-a/forecasts`. Emitter forbids quote-print mint. |
| Ledger bind (`candidate_id` → `forecast_id`) | `SOFTWARE_ONLY` + `NOT WIRED` | `PredictionLedgerService.register_forecast`; capture bridge only if bindings already exist. Paper runtime uses `COUNTERFACTUAL` in-memory. 0 ledger rows. |
| Maturity (5m Path A horizon) | `SOFTWARE_ONLY` + `WAITING FOR EMPIRICAL DATA` | `inspect_settlement` exists. No pending rows. Forcing settlement is forbidden and would be empty-op. |
| Settlement `OutcomeV1` LONG/SHORT | `SOFTWARE_ONLY` + `WAITING FOR EMPIRICAL DATA` | Labels only from settled outcomes. JSONL scan: 0 settled envelopes. |
| Persist `intelligence_records.jsonl` (production writer) | `NOT IMPLEMENTED` | No production writer outside tests. Collector loaders look only at known JSONL / `path-a/forecasts` aliases. SQLite holds FTEP/opportunity tables, not ForecastV1/OutcomeV1. Mongo unused. |
| Evidence validator / #196 sidecar | `SOFTWARE_ONLY` | Validator must not mint rows. `CAPTURE_CONTEXT_ABSENT` expected. |
| `training_build` / hop-consumable PRODUCTION JSON | `SOFTWARE_ONLY` + `WAITING FOR EMPIRICAL DATA` | Floors unmet. Not `PRODUCTION_FORECAST_ARTIFACT_READY`. |
| Live Opportunity Engine / Paper Path A loop | `NOT WIRED` | `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`. Prerequisite of Item 7 rows, not a collector bug. |

There is **no production writer** of `intelligence_records.jsonl` outside tests.
Collector loaders look only for:

- `intelligence/intelligence_records.jsonl`
- `intelligence_records.jsonl`
- `path-a/intelligence_records.jsonl`
- `path-a/forecasts`, `path-a/production/forecasts`, `forecasts/path-a`

## What cannot be fixed without live governed ForecastV1 / quote evidence

- Zero `governed_candidate_rows` / `pit_valid_governed_rows`
- Grid from last_price-only L1 (doctrine: no derived BBO)
- First PRODUCTION `ForecastV1` (chicken-egg: readiness/producer need a governed
  training manifest; collector needs pre-existing PRODUCTION forecasts joined
  to settled outcomes)
- Ledger rows without an already-present `forecast_id`
- Settled `LONG`/`SHORT` without matured forecasts + later lawful quotes
- `ITEM7_GOVERNED_ROW_CAPTURED`, `GOVERNED_PATH_A_TRAINING_CORPUS_READY`,
  `PRODUCTION_FORECAST_ARTIFACT_READY`, `ITEM7_COMPLETE`

A later PR may **wire persistence and BBO-grid**. It cannot lawfully mint the
first probability.

## Ordered work package (software wiring only; no fake rows)

**After** live OE loop, Item 9 bar receipt software, launcher/SPA routing, and
staleness — not a Sept 16 campaign, and not this docs-only lane.

1. **Prerequisite (not this package):** a live Opportunity Engine / Paper Path A
   loop that can resolve a pre-existing PRODUCTION forecast
   (`FORECAST_UNAVAILABLE` and `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` are
   upstream of Item 7 rows).
2. Operator-local append-only `intelligence_records.jsonl` (or equivalent under
   `IMP_STATE_DIR`) written by the Path A / capture-ledger path for `forecast`,
   `snapshot`, `signal`, `outcome`, `prediction_ledger_entry` — the shapes
   `corpus_persistence.py` already loads. (`NOT IMPLEMENTED` today.)
3. Admit **vendor** bid/ask (`SNAPSHOT_BBO` or L1 envelopes that already carry
   valid bid/ask) into `is_grid_point_candidate`. Do **not** fill bid/ask from
   `last_price`. Do **not** redefine `US_EQUITY_L1` as SNAPSHOT_BBO.
4. Wire SnapshotV1 + Path A `momentum_simple` + `net_signed_share` from those
   grid quotes (today `NOT WIRED`).
5. Once a **pre-existing** PRODUCTION `ForecastV1` is in the repository: bind
   `OCLC-*` candidate_id → `forecast_id`, register ledger, wait 5m, settle from
   a later lawful quote. No forced settlement; no quote-synthetic labels.
6. Optional attach of PR #196 `evidence_capture_context_v1` as SOFTWARE /
   PROSPECTIVE sidecar. Sidecar must not upgrade empty/fixture evidence.
7. Collector stays a reader. Do not lower floors. Do not claim Item 7 complete.

**Out of scope:** manufacturing ForecastV1/probabilities/outcomes; enabling
Live; turning on enrichment worker; treating `CAPTURE_CONTEXT_ABSENT` as the
row blocker; new providers.
