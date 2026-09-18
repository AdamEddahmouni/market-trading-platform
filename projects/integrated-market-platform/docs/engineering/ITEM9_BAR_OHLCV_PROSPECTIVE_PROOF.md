# Item 9 — OpenD BAR_OHLCV_1M prospective proof operator

**Status:** software ready; empirical prospective proof requires US equity RTH.

## CLI

From `projects/integrated-market-platform/` with `PYTHONPATH=src`:

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py readiness
python tools/moomoo/opend_bar_1m_prospective_proof.py display --instrument-id AAPL
python tools/imp.py item9 next-rth-preflight --json
```

### Next-RTH preflight (read-only)

`next-rth-preflight` validates calendar (`America/New_York` / `US_EQUITY_RTH`), loopback
OpenD reachability, governed receipt directory writability, frozen collector authority
(`fed2d9f7…` worktree under repo `.imp-actual-01-phase-d/`), and duplicate prospective
`--poll` processes. It **never** runs Mode B `--poll` and **never** writes a receipt.
Off-hours disposition `NOT_RTH` is software success (exit 0). During RTH with all gates
passing, disposition is `READY_TO_COLLECT` — operator still starts collection manually.

**Off-hours from a non-frozen software worktree:** `calendar.rth_active=false` is still the
expected calendar outcome. Overall disposition may be `WRONG_RUNTIME` (exit 1) because the
frozen-collector SHA gate runs before the not-RTH branch — that is honest, not a calendar
failure. Governed Mode B `--poll` must still be launched from `.imp-actual-01-phase-d` @
`fed2d9f7…`, not from **CURRENT_MAIN**.

### Process probe architecture ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251))

Duplicate `--poll` detection uses OS process command lines. That subprocess I/O lives in
**non-governed** `tools/item9_next_rth_preflight.py` and is injected via
`active_collector_probe` into the governed library. The library alone defaults
`active_collector.process_probe_status` to `NOT_RUN` (unit tests and direct `src/` entry).

| Entry | Process probe |
|-------|----------------|
| `python tools/imp.py item9 next-rth-preflight` | `COMPLETED` (tools wrapper lists processes) |
| `python tools/item9_next_rth_preflight.py` | `COMPLETED` |
| `python tools/item9.py next-rth-preflight` | `COMPLETED` (delegates to tools wrapper) |
| Governed `src/.../item9_next_rth_preflight.main` without injection | `NOT_RUN` (intentional) |

Do not move subprocess handling back into governed `src/`.

After a successful prospective receipt:

```powershell
python tools/item9_corpus_status.py corpus-status --receipt-dir artifacts/ftep-v1-002/item9-prospective-proof-receipts
```

No automatic calibration fitting.

`display` may call loopback OpenD for recent completed 1m bars. Off-hours that
fetch is **diagnostic / transport visibility only** — not prospective evidence
and not RTH empirical proof.

Mode B `--poll` fetches 1m history kline for the **observation session date**
in `America/New_York` (`start=end=YYYY-MM-DD`, `max_count>=1000`). Do not use
the vendor default `start=None, end=None`: SDK docs expand that to
`[today-365d, today]`. **K_1M oldest-first paging is same-API inference** from
proven `K_DAY` oldest-first behavior plus the SDK window — not a live-sampled
1m receipt. Under that inference, an unbounded window can yield a year-old
oldest page; those bars correctly fail `available_time > signal_time` and are
not prospective evidence.

If paging is oldest-first (inferred for `K_1M`), session-day plus `max_count=120` is still wrong:
extended-hours 04:00–05:59 fills the page and every bar is before a 09:34
signal. `max_count>=1000` is required so RTH minutes are not truncated.

Each `request_history_kline` attempt writes fail-closed diagnostics to stderr
(`raw_row_count`, `first_raw_time_key`, `last_raw_time_key`, `vendor_ret`,
`vendor_ret_msg`, `kline_start`/`kline_end`, `max_count_requested`,
`connection_host`/`connection_port`, `request_duration_ms`,
`protocol_error_category`) and attaches the same fields as `kline_fetch` on poll
outcomes, plus `poll_attempt_index` during Mode B `--poll` (one history
`request_history_kline` per poll step — not a transport retry counter). Mode B
`--poll` reuses one loopback OpenD **quote context** for the bounded run
(opens on first fetch, closes in `finally` on success, timeout, or fail-closed
exit). Single-shot `display` and non-poll loads still open/close per call.
Unmatched
`MOOMOO_PROTOCOL_ERROR` maps to `protocol_unclassified`, not a fabricated
exception label. Categories classify transport for logging only — they do **not**
uniquely explain Sep 15 poll #1 (no row-level detail in poll #1 logs) or
hour-2 `MOOMOO_PROTOCOL_ERROR` (separate open hypotheses). Timeout
still reports `PROSPECTIVE_NO_POST_SIGNAL_BAR`; the last fetch stats distinguish
empty vs TZ-dropped vs pre-signal rows. PIT is unchanged.

Follow-up (not in this repair): poll `get_cur_kline` instead of repeated history
pulls where vendor semantics allow. Hour-2 `MOOMOO_PROTOCOL_ERROR` may include frequency
limit, timeout, connect-churn, or other vendor conditions — operator notes about
quota/resume are lore, not receipt-cited facts. `retMsg` is preserved for the
next RTH attempt.

### Mode A — transport / replay (`RETROSPECTIVE_TRANSPORT_PROOF`)

Not prospective evidence. Uses operator-supplied signal and observation times.

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py transport-proof `
  --instrument-id AAPL `
  --source moomoo-opend `
  --signal-time-ns <NS> `
  --observation-time-ns <NS> `
  --receipt-out artifacts/ftep-v1-002/item9-prospective-proof-receipts
```

Fixture transport proof (offline):

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py transport-proof `
  --source admitted-fixture `
  --instrument-id BIYA `
  --signal-time-ns <NS> `
  --observation-time-ns <NS>
```

### Mode B — prospective (`PROSPECTIVE_BAR_OHLCV_1M`)

Records `signal_time_ns` at run start. Refuses `--signal-time-ns`. During RTH:

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py prospective `
  --instrument-id AAPL `
  --poll `
  --receipt-out artifacts/ftep-v1-002/item9-prospective-proof-receipts
```

Without `--poll`: off-hours → `SOFTWARE_READY_RTH_REQUIRED` (exit 3, no OpenD
poll). During RTH → `POLL_REQUIRED` (exit 4) — re-run with `--poll`.

Optional stable receipt id: `--experiment-id <id>` (passed through to the JSON receipt).

## Evidence receipt

- **Contract:** `item9.bar-ohlcv-prospective-proof/1.1.0` (`RECEIPT_CONTRACT_VERSION` in code)
- **Default directory:** `artifacts/ftep-v1-002/item9-prospective-proof-receipts/<experiment_id>.json`
- **Fields:** `experiment_id`, `proof_mode`, `instrument_id`, `signal_time_ns`, `signal_established_at_ns`, `observation_time_ns`, `bar_id`, `bar_start_ns`, `bar_end_ns`, `bar_event_time_ns`, `bar_available_time_ns`, `provider_id`, `bar_source_id`, `raw_provenance_hash`, `bar_provenance`, `first_post_signal_bar`, `first_post_signal_proof`, `simulator_output`, `item9_status`, simulator decision, `orders_placed=false`, `calibrated=false`, `empirical_active=false`, `runtime_git_sha`, `receipt_contract_version`

### Comparator bridge (no Paper orders)

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py comparator-bridge `
  --receipt-path artifacts/ftep-v1-002/item9-prospective-proof-receipts/<experiment_id>.json
```

Replay bounded dry-run from receipt times (no retrospective override):

```powershell
python tools/providers/run_bar_ohlcv_comparator_experiment.py `
  --from-receipt artifacts/ftep-v1-002/item9-prospective-proof-receipts/<experiment_id>.json
```

Item 9 remains **PARTIAL / NOT_CALIBRATED** after receipts; a successful bar fetch is not calibration.
Governed future calibration follows [ITEM9_CALIBRATION_PROTOCOL_V1.md](../architecture/ITEM9_CALIBRATION_PROTOCOL_V1.md).
Mode B receipts must hash fetched kline rows (`BarLoadResult.raw_rows`). Empty
`raw_provenance_hash` (SHA256 of `[]`) is path-proof only and is not corpus-admissible.
Do not rewrite already-persisted receipts.

## Related harness

`tools/providers/run_bar_ohlcv_comparator_experiment.py` remains the low-level bounded dry-run JSON emitter.
