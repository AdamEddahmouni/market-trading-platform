# Item 9 — OpenD BAR_OHLCV_1M prospective proof operator

**Status:** software ready; empirical prospective proof requires US equity RTH.

## CLI

From `projects/integrated-market-platform/` with `PYTHONPATH=src`:

```powershell
python tools/moomoo/opend_bar_1m_prospective_proof.py readiness
python tools/moomoo/opend_bar_1m_prospective_proof.py display --instrument-id AAPL
```

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

Off-hours without `--poll` returns `SOFTWARE_READY_RTH_REQUIRED` without polling OpenD.

## Evidence receipt

- **Contract:** `item9.bar-ohlcv-prospective-proof/1.0.0` (`RECEIPT_CONTRACT_VERSION` in code)
- **Default directory:** `artifacts/ftep-v1-002/item9-prospective-proof-receipts/<experiment_id>.json`
- **Fields:** `experiment_id`, `proof_mode`, `instrument_id`, `signal_time_ns`, `signal_established_at_ns`, `observation_time_ns`, `bar_event_time_ns`, `bar_available_time_ns`, `provider_id`, `bar_source_id`, `raw_provenance_hash`, `bar_provenance`, `first_post_signal_bar`, simulator decision, `orders_placed=false`, `calibrated=false`, `empirical_active=false`, `runtime_git_sha`, `receipt_contract_version`

Item 9 remains **PARTIAL / NOT_CALIBRATED** after receipts; a successful bar fetch is not calibration.

## Related harness

`tools/providers/run_bar_ohlcv_comparator_experiment.py` remains the low-level bounded dry-run JSON emitter.
