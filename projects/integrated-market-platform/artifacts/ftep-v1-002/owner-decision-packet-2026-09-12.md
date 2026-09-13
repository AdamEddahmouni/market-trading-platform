# FTEP-V1-002 owner decision packet (pre-freeze)

| Field | Value |
| --- | --- |
| **Campaign** | `FTEP-V1-002` / US-equity-news-catalyst |
| **Manifest status** | `PENDING_OWNER_DECISIONS` (proposed, **not frozen**) |
| **Incremental cost** | $0 (Moomoo US equity L1 + Finviz Elite owner subscription) |
| **Parallel campaign** | `FTEP-V1-001` frozen — do not mutate |

## Authority-resolved (no separate owner action)

| ID | Resolution | Evidence |
| --- | --- | --- |
| **OD-1** | Option A — news-strategy arms on US equity lane | `ACTIVATION_MANIFEST.json` → `authority_resolutions.OD-1` |
| **OD-3** | US equity RTH calendar | `calendar_scope: US_EQUITY_RTH`, `authority_resolutions.OD-3_calendar_interpretation` |

## Unresolved owner decisions (4)

1. **OD-2** — Approve preregistered US equity symbol universe (proposed: SPY, AAPL, MSFT, NVDA, AMZN).
2. **OD-6** — Confirm phased **SIGNAL_ONLY** first segment for V1-002 (no execution segment without separate authorization).
3. **OD-11** — Authorize manifest **freeze** pathway for V1-002 (not granted in this increment).
4. **OD-PAPER-ACCOUNT** — Select internal-simulation Paper account before any empirical session.

## Operator follow-up (not owner decisions)

- **Finviz Elite live probe:** `LOCAL_PROBE_REQUIRED` — run `python tools/finviz/probe.py` when credentials are configured (`artifacts/ftep-v1-002/finviz-local-probe-status-2026-09-12.json`).
- **Campaign bind (G-A6):** After OD-11 freeze, promote Moomoo `US_EQUITY_L1` to `CAMPAIGN_BOUND` per activation gates.

## Verification

```powershell
cd projects/integrated-market-platform
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
python -m unittest tests.intelligence.test_ftep_v1_002_campaign -q
```
