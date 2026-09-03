# EIA Physical Energy Fundamentals

Official U.S. Energy Information Administration (EIA) Open Data API v2 evidence for **Weekly Petroleum Status Report (WPSR)** and **Weekly Natural Gas Storage Report (WNGSR)** physical supply/inventory state.

Labels used in this document:

- **DOCUMENTED** — stated in official EIA documentation
- **OBSERVED** — verified in this repository via fixtures or live probe
- **INFERRED** — reasonable interpretation, not independently proven here
- **UNTESTED** — not covered by automated tests yet

## Why EIA

| Layer | Source | Provides |
|-------|--------|----------|
| Macro | FRED / ALFRED | growth, inflation, rates, USD, liquidity |
| Positioning | CFTC COT | managed money, producers, swap dealers |
| **Physical** | **EIA** | petroleum inventories, production, refinery activity, NG storage |
| Market | Futures / OF | price, flow, liquidity |

EIA evidence is **observational**. No composite energy score, no trade signal, no inventory surprise without a consensus expectations source.

## API v2 (DOCUMENTED)

- Base: `https://api.eia.gov/v2/...`
- Auth: `api_key` query parameter (**never log credentialed URLs**)
- Pagination: `offset` + `length`, JSON row cap **5000** (DOCUMENTED)
- Legacy API v1 is **not** primary; use v2 routes and `/v2/seriesid/{legacy_id}` only when needed

### Primary routes (OBSERVED live 2026-08-20)

| Release | Route | Frequency | Status |
|---------|-------|-----------|--------|
| WPSR weekly supply | `/v2/petroleum/sum/sndw/data` | weekly, four-week-average | **OBSERVED** |
| WNGSR working gas | `/v2/natural-gas/stor/wkly/data` | weekly | **OBSERVED** |

Metadata discovery: query parent route without `/data` (e.g. `/v2/petroleum/sum/sndw`).

Production facet IDs (OBSERVED): `duoarea`, `product`, `process`, `series`.

Data column for numeric values: `value` with companion `units` field (e.g. `MBBL`, `BCF`, `MBBL/D`).

Pagination: `offset` + `length`, max **5000** JSON rows (DOCUMENTED/OBSERVED).

## Credential handling (DOCUMENTED)

- Load `EIA_API_KEY` from ignored `.env` or environment
- Redact `api_key` from logs, exceptions, fixtures, capability reports
- Sanitize EIA response `request.params.api_key` echoes before hashing or persistence

Live gate: `IMP_EIA_LIVE=1` + `EIA_API_KEY`.

## Live characterization (OBSERVED 2026-08-20)

Probe: `python tools/eia/probe.py` with `IMP_EIA_LIVE=1` → `evidence/eia/capability-report.json`.

### Authentication

- EIA API v2 auth succeeds with bounded metadata request (**OBSERVED**)
- Response metadata does **not** echo `api_key` in `request.params` (**OBSERVED**)
- Sanitizer confirmed on all persisted evidence paths (**OBSERVED**)

### Latest production periods (OBSERVED)

| Family | Reference week ending | Scheduled release | API latest period |
|--------|----------------------|-------------------|-------------------|
| WPSR | 2026-08-14 | 2026-08-19 (Wed 10:30 ET) | 2026-08-14 |
| WNGSR | 2026-08-14 | 2026-08-20 (Thu 10:30 ET) | 2026-08-14 |

`period_end` ≠ `available_time`. Official artifact release time is **not directly observed** by the probe; only API retrieval time is recorded.

### Registry corrections applied (OBSERVED)

| Concept | Old series | Production series |
|---------|-----------|-------------------|
| TOTAL_PRODUCT_SUPPLIED | WTTUPUS2 | WRPUPUS2 |
| CRUDE_DAYS_OF_SUPPLY | WD0STUS1 | W_EPC0_VSD_NUS_DAYS |
| LOWER48_WORKING_GAS | NW2_EPG0_SWO_R48_BCF_W | NW2_EPG0_SWO_R48_BCF |
| EAST | NW2_EPG0_SWO_R30_BCF_W | NW2_EPG0_SWO_R31_BCF |
| MIDWEST | NW2_EPG0_SWO_R20_BCF_W | NW2_EPG0_SWO_R32_BCF |
| MOUNTAIN | NW2_EPG0_SWO_R40_BCF_W | NW2_EPG0_SWO_R34_BCF |
| PACIFIC | NW2_EPG0_SWO_R50_BCF_W | NW2_EPG0_SWO_R35_BCF |
| SOUTH_CENTRAL | NW2_EPG0_SWO_R31_BCF_W | NW2_EPG0_SWO_R33_BCF |
| SOUTH_CENTRAL_SALT | NW2_EPG0_SWO_R31_S1_BCF_W | NW2_EPG0_SSO_R33_BCF |
| SOUTH_CENTRAL_NONSALT | NW2_EPG0_SWO_R31_S2_BCF_W | NW2_EPG0_SNO_R33_BCF |

### Live diagnostic samples (OBSERVED, no interpretation)

| Concept | Period | Value | Unit |
|---------|--------|-------|------|
| COMMERCIAL_CRUDE_STOCKS | 2026-08-14 | 428,815 | Thousand Barrels |
| SPR_CRUDE_STOCKS | 2026-08-14 | 293,426 | Thousand Barrels |
| CUSHING_CRUDE_STOCKS | 2026-08-14 | 7,826 | Thousand Barrels |
| LOWER48_WORKING_GAS | 2026-08-14 | 3,169 | Billion Cubic Feet |

Commercial and SPR remain separate series; no default summing.

## Release semantics (DOCUMENTED/OBSERVED)

### WPSR

- Reference week ends **Friday**
- Normal publication: **Wednesday 10:30 a.m. Eastern**
- Holiday-adjusted exceptions preserved in `eia/release_schedule.py`
- `period_end` ≠ `available_time`

### WNGSR

- Reference storage week ends Friday (report period)
- Normal publication: **Thursday 10:30 a.m. Eastern**
- Holiday exceptions (e.g. Thanksgiving week Wednesday noon) preserved explicitly

## PIT / versioning (DOCUMENTED/OBSERVED)

| History class | Meaning | Classification |
|---------------|---------|----------------|
| `CURRENT_API_HISTORY` | Today's mutable API history — may include revisions | **CURRENT_HISTORY_ONLY** |
| `LIVE_RELEASE_CAPTURE` | Prospective first-observation capture at release | **PROSPECTIVE_VERSIONED_PIT** |
| `ARCHIVED_RELEASE_SNAPSHOT` | Official previous-issue artifact | **PARTIAL_ARCHIVE** |

WPSR/WNGSR official previous-issue PDF/XLS archives exist on eia.gov but do not provide machine-readable original-release timestamps for all historical points. Full historical vintage reconstruction is **not** feasible from current API alone.

**Forbidden:** backdating current API values to original release timestamps.

When original vintage unavailable: `HISTORICAL_VINTAGE_UNAVAILABLE` / `PIT_UNCERTAIN`.

Corrections close prior bitemporal `known_to` and append new version (OBSERVED in tests).

## Physical semantics (DOCUMENTED)

- **Commercial crude ≠ SPR** — separate registry entries, no default summing
- **Cushing** — first-class region, distinct from PADD 2 and U.S. total
- **Stock vs flow** — `EnergyMetricClass`: STOCK, FLOW_RATE, UTILIZATION, RATIO, BALANCE_CHANGE
- **Units explicit** — thousand barrels vs thousand barrels/day never mixed
- **Product supplied** — named `product_supplied`; not `consumer_demand`
- **Weekly production** — estimate; re-benchmarking possible
- **Working gas** — stock balance; weekly change is balance change (may include reclassifications)

## Registry

Bounded concepts in `eia/registry.py` — petroleum (commercial crude, Cushing, SPR, gasoline, distillate, production, refinery, imports/exports, product supplied, PADD2) and natural gas (Lower 48 + regional salt/nonsalt).

Each entry maps: canonical id → route, series facet, unit, metric class, PIT confidence.

## Cross-source integration (OBSERVED)

`EnergyMarketContext` joins:

- `MacroRegimeState` (FRED)
- `InstitutionalPositioningState` (CFTC)
- `EnergyFundamentalsState` (EIA)

Independent clocks enforced: WPSR Wednesday, WNGSR Thursday, CFTC Friday (test: `cftc_eia_independent_clocks.json`).

## Operations

```text
sync_eia_petroleum()
sync_eia_natural_gas_storage()
sync_wpsr_release()
sync_wngsr_release()
sync_energy_fundamentals()
```

Incremental sync retrieves recent weeks + overlap; no full-history warehouse in this package.

## Testing

- Offline: `tests/eia/` — no API key required
- Live: `tests/live_eia/` — skipped unless `IMP_EIA_LIVE=1`
- Probe: `python tools/eia/probe.py` → `evidence/eia/capability-report.json`

## Known limitations

- API availability may lag official WPSR/WNGSR file publication (**OBSERVED** — artifact channel not probed)
- Current API history ≠ guaranteed original release vintage (**OBSERVED**)
- Official report release time ≠ API first observation time (**OBSERVED** — only retrieval time recorded)
- No analyst inventory consensus → no `inventory_surprise`
- WPSR methodology changes over decades (see EIA WPSR notes)
- Regional coverage intentionally bounded
- WNGSR weekly change may reflect reclassifications, not only physical injection/withdrawal (**DOCUMENTED**)

## ADR

Reuses observational public-source ADR boundary (`adr-live-001`). No separate EIA ADR required unless governance requests one.
