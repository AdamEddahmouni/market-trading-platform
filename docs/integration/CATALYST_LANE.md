# Catalyst Read-Only Integration Lane

**Status:** `COMPLETE` — read-only donor bridge over internship demo state.

This lane connects the governed IMP UI to the internship news-momentum agent's
seeded `state/*.json` files. No demo bytes are admitted into canonical replay;
the bridge is filesystem read-only only.

## Prerequisites

- Internship demo state seeded:
  ```powershell
  cd internship-project-main\internship-project-main\news_momentum_agent
  python scripts/seed_demo_state.py
  ```
- `state/demo.lock` must exist (blocks live `main.py` scheduler)

## Quick start

### Terminal 1 — IMP UI API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

Verify bridge:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/explore/catalyst | Select-Object available, row_count
Invoke-RestMethod http://127.0.0.1:8766/workspace/BOXL/catalyst | Select-Object available, symbol
```

### Optional — Internship Streamlit dashboard

```powershell
.\tools\run_donor_demos.ps1 -Start internship
```

## API endpoints (IMP)

| Method | Path | Purpose |
|---|---|---|
| GET | `/explore/catalyst` | Demo trade-log + watchlist catalyst rows |
| GET | `/workspace/{symbol}/catalyst` | Per-symbol catalyst evidence cards |
| GET | `/explain/catalyst:{symbol}` | Explanation drawer payload |
| GET | `/attention` | Includes up to 5 catalyst rows when state is seeded |

Donor upstream: `news_momentum_agent/state/trade_log.json`, `watchlist.json`, `health.json`.

## Verification

```bash
cd integrated-market-platform
python -m unittest tests.donor_bridge.test_catalyst_bridge
```

## Governance

- Demo state is **not admitted** into canonical replay (see `docs/DONOR_FIXTURE_MAP.md`).
- `donor_patterns/catalyst_lane.py` provides stdlib gate/evidence helpers for projections.
- Live scheduler, broker adapters, and paper execution remain unauthorized in IMP.

## Phase 15 — fixture-first canonical path

Phase 15 admits `ADMITTED-CATALYST-BOXL-001` into canonical replay:

| Artifact | Path |
|---|---|
| Fixture slice | `tests/fixtures/providers/catalyst/boxl_catalyst_slice.json` |
| Admission manifest | `tests/fixtures/providers/catalyst/admission_manifest.json` |
| Provider adapter | `src/market_platform_foundation/providers/adapters/fixture_catalyst.py` |
| Whale family | `public_catalyst` (entitled on BOXL only) |

The UI API serves `/workspace/BOXL/catalyst` from the fixture provider when entitled. The donor bridge above remains an optional overlay when internship demo state is seeded; fixture path is canonical for replay/PIT.

Verification:

```bash
cd integrated-market-platform
python -m unittest tests.providers.test_catalyst tests.integration.test_catalyst_lane_acceptance -v
python tools/phase15/run_phase15_pipeline.py --output-dir evidence/phase15/build-run
```

## Lane acceptance (end-to-end evidence)

After seeding internship demo state and with IMP UI API (`:8766`) running:

```powershell
cd integrated-market-platform
python tools/integration/catalyst_lane_acceptance.py --require-imp --output evidence/integration/catalyst-lane-acceptance.json
```

Offline fail-closed checks always run; live projection and HTTP checks run when demo state is seeded.
Use `--require-state` to fail when `news_momentum_agent/state/demo.lock` is missing.

Canonical lane-closure artifact: [`evidence/integration/catalyst-lane-acceptance.json`](../../evidence/integration/catalyst-lane-acceptance.json) (`status: PASS` when demo state is seeded and IMP API is live).
