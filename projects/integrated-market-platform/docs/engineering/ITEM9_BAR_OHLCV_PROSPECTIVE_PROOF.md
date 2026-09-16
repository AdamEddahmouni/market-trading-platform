# Item 9 — OpenD BAR_OHLCV_1M prospective proof operator

**Status:** software ready; empirical prospective proof requires US equity RTH.

## CLI

From `projects/integrated-market-platform/` with `PYTHONPATH=src`:

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py readiness
python tools/moomoo/opend_bar_1m_prospective_proof.py display --instrument-id AAPL
```

`display` may call loopback OpenD for recent completed 1m bars. Off-hours that
fetch is **diagnostic / transport visibility only** — not prospective evidence
and not RTH empirical proof.

Mode B `--poll` fetches 1m history kline for the **observation session date**
in `America/New_York` (`start=end=YYYY-MM-DD`, `max_count>=1000`). Do not use
the vendor default `start=None, end=None`: that expands to `[today-365d, today]`
and returns the **oldest** page (a year old). Those bars correctly fail
`available_time > signal_time` and are not prospective evidence.

If paging is oldest-first, session-day plus `max_count=120` is still wrong:
extended-hours 04:00–05:59 fills the page and every bar is before a 09:34
signal. `max_count>=1000` is required so RTH minutes are not truncated.

Each `request_history_kline` attempt writes fail-closed diagnostics to stderr
(`raw_row_count`, `first_raw_time_key`, `last_raw_time_key`, `vendor_ret`,
`vendor_ret_msg`, `kline_start`/`kline_end`, `max_count_requested`,
`connection_host`/`connection_port`, `request_duration_ms`,
`request_retry_index`, `protocol_error_category`) and attaches the same fields
as `kline_fetch` on poll outcomes, plus `poll_attempt_index` during Mode B
`--poll`. Categories classify transport for logging only — they do **not**
uniquely explain Sep 15 poll #1 or hour-2 `MOOMOO_PROTOCOL_ERROR`. Timeout
still reports `PROSPECTIVE_NO_POST_SIGNAL_BAR`; the last fetch stats distinguish
empty vs TZ-dropped vs pre-signal rows. PIT is unchanged.

Follow-up (not in this repair): reuse one quote context and poll `get_cur_kline`
to cut 5s connect-churn. Hour-2 `MOOMOO_PROTOCOL_ERROR` is not unique-security
`historyKLQuota` (resume completed 358 more cycles); remaining hypotheses are
timeout / frequency limit / connect-churn. `retMsg` is now preserved.

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

## Related harness

`tools/providers/run_bar_ohlcv_comparator_experiment.py` remains the low-level bounded dry-run JSON emitter.
