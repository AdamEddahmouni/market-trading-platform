# Short-Squeeze Read-Only Integration Lane

**Status:** `COMPLETE` — read-only donor bridge closed end-to-end.

This lane connects the governed IMP UI to the short-squeeze donor screener in
`FROZEN_DEMO` mode. No frozen-demo bytes are admitted into canonical replay; the
bridge is HTTP read-only only.

## Prerequisites

- Python 3.11+ for IMP foundation and squeeze donor
- Node.js for IMP `ui/` dev server (optional for API-only verification)
- Short-squeeze virtualenv at `short-squeeze-project/short-squeeze-core/.venv`

## Quick start (three terminals)

### Terminal 1 — Squeeze FROZEN_DEMO server

```powershell
cd short-squeeze-project\short-squeeze-core
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe -m apps.research_screener --no-browser --port 8787
```

Verify: `http://127.0.0.1:8787/health` returns `status: OK`.

### Terminal 2 — IMP UI API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

Verify bridge:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/explore/squeeze | Select-Object available, row_count
Invoke-RestMethod http://127.0.0.1:8766/workspace/AVTX/squeeze | Select-Object available, symbol, replay_chart_available
Invoke-RestMethod http://127.0.0.1:8766/workspace/BIYA/squeeze | Select-Object available, symbol, replay_chart_available
```

### Terminal 3 — React frontend

```powershell
cd integrated-market-platform\ui
npm run dev
```

Open `http://127.0.0.1:5173/explore`, click a symbol (e.g. **AVTX**), confirm WORKSPACE loads squeeze
evidence. **BIYA** shows the admitted replay chart only — it is not one of the 13 frozen squeeze cases.
Other frozen symbols show squeeze evidence with an honest UNAVAILABLE replay chart.

### NOW feed integration

When the squeeze server is running, the NOW command center also surfaces up to five
donor screener rows as attention items (`explain:squeeze:{symbol}` refs). Explain and
Inspector resolve through the same read-only bridge.

## Launcher script

From workspace root:

```powershell
.\tools\run_donor_demos.ps1 -Start squeeze
.\tools\run_donor_demos.ps1 -Start status
```

The status command reports donor health and IMP bridge URLs.

## API endpoints (IMP)

| Method | Path | Purpose |
|---|---|---|
| GET | `/explore/squeeze` | Screener table (13 frozen rows) |
| GET | `/workspace/{symbol}/squeeze` | Per-symbol squeeze evidence, rules, ignition cards |
| GET | `/explain/squeeze:{symbol}` | Explanation drawer payload (via `/explain/...`) |
| GET | `/attention` | Includes up to 5 squeeze rows when donor bridge is up |

Donor upstream: `GET /api/frozen/candidates`, `GET /api/frozen/candidate/{symbol}` on `:8787`.

## Tests

```powershell
cd integrated-market-platform
python -m unittest tests.donor_bridge.test_explore_bridge
python -m unittest tests.donor_bridge.test_workspace_squeeze
python -m unittest tests.integration.test_squeeze_lane_acceptance
```

Integration cases skip automatically when the squeeze server is not running.

## Lane acceptance (end-to-end evidence)

With squeeze FROZEN_DEMO (`:8787`) and IMP UI API (`:8766`) running:

```powershell
cd integrated-market-platform
python tools/integration/squeeze_lane_acceptance.py --require-donor --require-imp
```

Offline fail-closed checks always run; live projection and HTTP checks run when servers are up.
Write evidence JSON with `--output evidence/integration/squeeze-lane-acceptance.json`.

```powershell
python tools/integration/squeeze_lane_acceptance.py --output evidence/integration/squeeze-lane-acceptance.json
```

## Donor acceptance (optional)

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/integration_acceptance.py --mode frozen
```

## Capability boundaries

- Read-only research aggregates only — no trade recommendations
- Frozen demo bytes are **not** admitted to canonical replay (`ADMITTED-SHORTSQ-BIYA-BARS-001` remains the only admitted bar fixture)
- **BIYA** has admitted replay bars but is **not** in the 13-symbol frozen squeeze aggregate; workspace shows replay with an honest UNAVAILABLE squeeze panel
- Frozen symbols (e.g. **AVTX**) have squeeze evidence but no admitted replay chart
- Institutional, depth, and options panels remain `UNAVAILABLE`
- Live/paper execution is not authorized

## Related docs

- [DONOR_PATTERN_EXTRACTIONS.md](../research/donors/DONOR_PATTERN_EXTRACTIONS.md)
- [DONOR_FIXTURE_MAP.md](../../../docs/DONOR_FIXTURE_MAP.md)
- [SHORT_SQUEEZE_NOTES.md](../../../SHORT_SQUEEZE_NOTES.md)
