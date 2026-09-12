# Notion sync payload — FTEP-V1-002 pivot (2026-09-12)

## Summary

**FTEP-V1-002** (`US-equity-news-catalyst`) is **FROZEN** on $0 incremental stack (Moomoo US equity L1 + Finviz Elite news). Owner authorized **Phase 1 SIGNAL_ONLY** (`signal-only-authorization-receipt-2026-09-12.json`); first session deferred — **US_EQUITY_RTH closed** (2026-09-12 weekend). Branch `work/ftep-v1-002-us-equity-news` @ **`4f6f05e`** (pushed); PR **#29**. With `IMP_PERSIST_STATE=1`, `campaign-readiness FTEP-V1-002` → **READY**. **FTEP-V1-001** unchanged / blocked on ES entitlement.

## Owner decisions (closed for V1-002 freeze)

OD-1, OD-2 (AAPL, MSFT, NVDA, AMZN, META; SPY benchmark-only), OD-3, OD-6 (PHASE_1_SIGNAL_ONLY), OD-11 (pathway A bind/freeze/preflight), OD-PAPER-ACCOUNT (canonical internal simulation Paper).

**Operator (not owner):** Finviz Elite `LOCAL_PROBE_REQUIRED` — see `artifacts/ftep-v1-002/finviz-local-probe-status-2026-09-12.json`; stale verified evidence remains `2026-08-22`.

## Commands (verification)

```powershell
cd projects/integrated-market-platform
$env:PYTHONPATH = "src"
python -m unittest tests.intelligence.test_ftep_v1_002_campaign -q
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

## Artifacts

- `artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json` (**FROZEN**)
- `artifacts/ftep-v1-002/reconciliation-matrix-2026-09-12.json`
- `artifacts/ftep-v1-002/us-equity-provider-stack-selection.json`
