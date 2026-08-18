# Futures Lane — Read-Only Integration

**Status:** `COMPLETE` — fixture-first ES depth lane with optional donor bridge.

This lane connects the governed IMP UI to ES CME futures depth evidence. The primary path uses admitted synthetic fixture `ADMITTED-L2-ES-001` per ADR-DATA-002. An optional read-only bridge to Eric_futuresX (`:8788`) serves live snapshots when the donor bridge is running.

## Prerequisites

- Python 3.11+ for IMP foundation
- Node.js for IMP `ui/` dev server (optional for API-only verification)
- FuturesX venv at `Eric_futuresX-main/futuresX-main/venv` (optional, for bridge)

## Quick start (three terminals)

### Terminal 1 — FuturesX donor bridge (optional)

```powershell
cd Eric_futuresX-main\futuresX-main
.\venv\Scripts\python.exe scripts\bridge_server.py --port 8788
```

Verify: `http://127.0.0.1:8788/health` returns `status: OK` and `symbol: ES`.

### Terminal 2 — IMP UI API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

Verify fixture path:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/workspace/ES/futures | Select-Object available, symbol, contract_month, snapshot_count
```

Verify explore:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/explore/futures | Select-Object available, symbol
```

### Terminal 3 — React frontend

```powershell
cd integrated-market-platform\ui
npm run dev
```

Open `http://127.0.0.1:5173/workspace/ES/futures` to view the futures workspace.

Open `http://127.0.0.1:5173/explore` for the ES futures bridge status card (when donor bridge is running).

## Explain / Inspect

| Ref | Endpoint |
|---|---|
| `explain:futures:ES` | `GET /explain/explain:futures:ES` |
| `inspect:futures:ES` | `GET /inspect/inspect:futures:ES` |

Workspace Explain/Inspect buttons on `/workspace/ES/futures` use these refs. Inspect includes DERIVATION metadata for `futures_lane` signal methods.

## Donor launcher

From the workspace root:

```powershell
.\tools\run_donor_demos.ps1 -Start futures
```

Read-only bridge on `:8788`; does **not** start `live_trader.py`.

## Data paths

| Path | Provenance | Replay admission |
|---|---|---|
| Fixture `es_depth_slice.json` | Synthetic ES L2 (smoke-derived) | Admitted — ADMITTED-L2-ES-001 |
| Donor bridge `:8788` | Live/read-through from FuturesX | **Not** admitted into canonical replay |
| Bundled FuturesX CSV/DB | Git LFS (blocked in zip copy) | Deferred until lawful bytes + ADR update |

## Governance

- ADR-DATA-002 admits bounded synthetic ES fixture only.
- ADR-DATA-001 full ES session bundle remains **deferred**.
- `futures_positioning` whale family carries depth-derived signals only — not CFTC positioning.
- No order execution in IMP; research-only by default.

## Phase 14 acceptance

```powershell
cd integrated-market-platform
python tools/phase14/run_phase14_pipeline.py --output-dir evidence/phase14/build-run
```

## Lane acceptance (end-to-end evidence)

With FuturesX bridge (`:8788`) and IMP UI API (`:8766`) running:

```powershell
cd integrated-market-platform
python tools/integration/futures_lane_acceptance.py --require-donor --require-imp --output evidence/integration/futures-lane-acceptance.json
```

Offline fail-closed checks always run; live projection and HTTP checks run when servers are up.
When the donor bridge is live, workspace `/workspace/ES/futures` should report `provenance: donor_bridge`.

Canonical lane-closure artifact: [`evidence/integration/futures-lane-acceptance.json`](../../evidence/integration/futures-lane-acceptance.json) (`status: PASS` when both servers are live).

## Related modules

| Component | Path |
|---|---|
| Lane patterns | `src/market_platform_foundation/donor_patterns/futures_lane.py` |
| Fixture provider | `src/market_platform_foundation/providers/adapters/fixture_futures.py` |
| Donor bridge client | `src/market_platform_foundation/donor_bridge/futures_client.py` |
| UI workspace | `ui/src/components/futures/` |
| Fixture | `tests/fixtures/providers/futures/es_depth_slice.json` |
