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
