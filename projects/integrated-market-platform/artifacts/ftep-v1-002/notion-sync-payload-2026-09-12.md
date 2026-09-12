# Notion sync payload — FTEP-V1-002 pivot (2026-09-12)

## Summary

Engineering pivot to **FTEP-V1-002** (`US-equity-news-catalyst`) on a **$0 incremental** provider stack (Moomoo US equity L1 + Finviz Elite news). **FTEP-V1-001** remains **frozen** with fingerprint `69C36BA…` and is classified **FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT** for prospective ES market evidence.

## Owner decisions required (4)

**Authority-resolved (engineering, not frozen):** OD-1 (news-strategy Option A on US equity lane), OD-3 (US_EQUITY_RTH).

1. **OD-2** — Approve preregistered US equity symbol universe (proposed: SPY, AAPL, MSFT, NVDA, AMZN).
2. **OD-6** — Confirm phased SIGNAL_ONLY first segment for V1-002 (no execution segment without separate authorization).
3. **OD-11** — Authorize manifest freeze pathway for V1-002 (not granted in this increment).
4. **OD-PAPER-ACCOUNT** — Select internal simulation Paper account before any empirical session (not authorized here).

**Operator (not owner):** Finviz Elite `LOCAL_PROBE_REQUIRED` — see `artifacts/ftep-v1-002/finviz-local-probe-status-2026-09-12.json`; stale verified evidence remains `2026-08-22`.

## Commands (verification)

```powershell
cd projects/integrated-market-platform
$env:PYTHONPATH = "src"
python -m unittest tests.intelligence.test_ftep_v1_002_campaign -q
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

## Artifacts

- `artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json` (PROPOSED)
- `artifacts/ftep-v1-002/reconciliation-matrix-2026-09-12.json`
- `artifacts/ftep-v1-002/us-equity-provider-stack-selection.json`
