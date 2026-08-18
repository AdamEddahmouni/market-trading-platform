# Short-Squeeze Read-Only Integration Lane

**Status:** `COMPLETE` — read-only donor bridge closed end-to-end for frozen cohort and live scanner projections.

This lane connects the governed IMP UI to the short-squeeze donor screener. Frozen research rows use `FROZEN_DEMO` (or any mode serving `/api/frozen/candidates`). Ephemeral scanner rows use `CLOUD_PROVIDER_MODE` (or any mode serving populated `/api/current/candidates`). No frozen-demo bytes are admitted into canonical replay; the bridge is HTTP read-only only.

## Prerequisites

- Python 3.11+ for IMP foundation and squeeze donor
- Node.js for IMP `ui/` dev server (optional for API-only verification)
- Short-squeeze virtualenv at `short-squeeze-project/short-squeeze-core/.venv`
- **Live scanner path:** provider credentials in process env (`FINVIZ_API_KEY`, `NEWSAPI_KEY`, etc.) or `CLOUD_BOOTSTRAP_SYMBOLS` for SEC-only dev seeding

## Quick start (three terminals)

### Terminal 1 — Squeeze donor server

**Frozen research cohort (13 rows):**

```powershell
cd short-squeeze-project\short-squeeze-core
$env:SQUEEZE_APP_MODE = "FROZEN_DEMO"
.\.venv\Scripts\python.exe -m apps.research_screener --no-browser --port 8787
```

**Live provider scanner (ephemeral current rows):**

```powershell
cd short-squeeze-project\short-squeeze-core
$env:SQUEEZE_APP_MODE = "CLOUD_PROVIDER_MODE"
$env:SEC_ENABLED = "true"
$env:FINVIZ_ENABLED = "true"          # optional — set FINVIZ_API_KEY when enabled
$env:NEWSAPI_ENABLED = "true"         # optional — set NEWSAPI_KEY when enabled
$env:CLOUD_BOOTSTRAP_SYMBOLS = "AVTX,GME,BIYA"   # dev fallback when discovery is empty
.\.venv\Scripts\python.exe start_cloud.py --no-browser --port 8787
```

Or from workspace root:

```powershell
.\tools\run_donor_demos.ps1 -Start squeeze-cloud
```

Verify: `http://127.0.0.1:8787/health` returns `status: OK` and `mode: CLOUD_PROVIDER_MODE` for the live path.
Verify scanner: `http://127.0.0.1:8787/api/current/candidates` returns `row_count > 0` after bootstrap/discovery.

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
donor screener rows as attention items (`explain:squeeze:{symbol}` refs). When the
donor has current scanner candidates, up to three additional ephemeral rows appear
(`explain:squeeze:scanner:{symbol}`). Explain and Inspector resolve through the
same read-only bridge.

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
| GET | `/explore/squeeze/scanner` | Ephemeral provider scanner rows (`CURRENT` mode) |
| GET | `/workspace/{symbol}/squeeze` | Per-symbol squeeze evidence, rules, ignition cards |
| GET | `/workspace/{symbol}/squeeze?data_mode=current` | Per-symbol **current scanner** evidence |
| GET | `/explain/squeeze:{symbol}` | Explanation drawer payload (via `/explain/...`) |
| GET | `/attention` | Includes up to 5 squeeze rows when donor bridge is up |

**Historical squeeze context** (donor-independent): workspace squeeze payloads include
`historical_context` from the Phase 3F n=30 calibration cohort fixture. RESEARCH analytics
includes `squeeze_historical_cohort` panel with outcome/classification distributions.

**Institutional options cross-ref** (replay-aware): when the IMP replay store is loaded and
`ADMITTED-OPTIONS-BIYA-001` is entitled, workspace squeeze payloads replace the frozen-donor
Options ignition card with admitted fixture summaries. BIYA shows this card even when donor
squeeze evidence is unavailable (replay-only boundary).

**Institutional borrow + depth cross-ref** (replay-aware): Borrow shows PARTIAL SEC disclosure
for BIYA when entitled; Depth shows admitted order-book snapshots for NVDA. Other symbols
remain honest UNAVAILABLE when no fixture is entitled.

**Live provider scanner bridge** (read-only): `GET /explore/squeeze/scanner` projects ephemeral
`/api/current/candidates` rows from the donor screener. These are **not** the frozen research
cohort. Workspace detail uses `?data_mode=current` to fetch `/api/current/candidate/{symbol}`.
Requires the donor server running; scanner rows appear after discovery refresh on the donor.

Donor upstream: `GET /api/frozen/candidates`, `GET /api/frozen/candidate/{symbol}` on `:8787`.
Live scanner: `GET /api/current/candidates`, `GET /api/current/candidate/{symbol}`.

## Tests

```powershell
cd integrated-market-platform
python -m unittest tests.donor_bridge.test_explore_bridge
python -m unittest tests.donor_bridge.test_workspace_squeeze
python -m unittest tests.donor_bridge.test_institutional_ignition
python -m unittest tests.donor_bridge.test_live_squeeze_bridge
python -m unittest tests.integration.test_squeeze_lane_acceptance
```

```powershell
cd integrated-market-platform\ui
npm run test -- squeeze
```

UI coverage includes schema parsing (`squeezeWorkspace.test.ts`), `StateTransitionBlock` transition-log rendering, and `SqueezeWorkspacePanel` availability/actions tests.

Integration cases skip automatically when the squeeze server is not running.

## Lane acceptance (end-to-end evidence)

With squeeze donor (`:8787`) and IMP UI API (`:8766`) running:

**Frozen cohort (FROZEN_DEMO):**

```powershell
cd integrated-market-platform
python tools/integration/squeeze_lane_acceptance.py --require-donor --require-imp
```

**Live scanner (CLOUD_PROVIDER_MODE with current rows):**

```powershell
python tools/integration/squeeze_lane_acceptance.py --require-donor --require-imp --require-scanner-rows --output evidence/integration/squeeze-lane-acceptance.json
```

Offline fail-closed checks always run; live projection and HTTP checks run when servers are up.
Write evidence JSON with `--output evidence/integration/squeeze-lane-acceptance.json`.

Canonical lane-closure artifact: [`evidence/integration/squeeze-lane-acceptance.json`](../../evidence/integration/squeeze-lane-acceptance.json) (`status: PASS` when both servers are live; `scanner_row_count > 0` when run with `--require-scanner-rows`).

**Live scanner soak (stability over multiple polls):**

```powershell
python tools/integration/squeeze_cloud_soak.py --iterations 3 --interval-seconds 5 --trigger-refresh --output evidence/integration/squeeze-cloud-soak.json
```

Soak artifact: [`evidence/integration/squeeze-cloud-soak.json`](../../evidence/integration/squeeze-cloud-soak.json).
SEC-only cloud deployments may keep Adam classifications `UNEVALUABLE` without Finviz/IBKR keys.

**Local provider soak (Finviz/NewsAPI from `.private/providers.env`):**

```powershell
cd ..\tools
.\run_donor_demos.ps1 -Start squeeze-cloud-providers
# then from integrated-market-platform:
python tools/integration/squeeze_cloud_soak.py --trigger-refresh --require-evaluable --output evidence/integration/squeeze-cloud-providers-soak.json
```

`start_cloud.py --load-local-providers` preloads private credentials into `os.environ` for
local `CLOUD_PROVIDER_MODE` without shipping secrets to container platforms.

## Donor acceptance (optional)

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/integration_acceptance.py --mode frozen
```

## Capability boundaries

- Read-only research aggregates only — no trade recommendations
- Frozen demo bytes are **not** admitted to canonical replay (`ADMITTED-SHORTSQ-BIYA-BARS-001` remains the only admitted bar fixture)
- **BIYA** has admitted replay bars but is **not** in the 13-symbol frozen squeeze aggregate; workspace shows replay with an honest UNAVAILABLE squeeze panel and an **ADMITTED** Options ignition card when Phase 11 fixture is entitled
- Frozen symbols (e.g. **AVTX**) have squeeze evidence but no admitted replay chart; Options card stays unavailable unless a symbol-specific options fixture is entitled
- Borrow and depth institutional panels remain `UNAVAILABLE` in this lane
- Live/paper execution is not authorized

## Related docs

- [DONOR_PATTERN_EXTRACTIONS.md](../research/donors/DONOR_PATTERN_EXTRACTIONS.md)
- [DONOR_FIXTURE_MAP.md](../../../docs/DONOR_FIXTURE_MAP.md)
- [SHORT_SQUEEZE_NOTES.md](../../../SHORT_SQUEEZE_NOTES.md)
