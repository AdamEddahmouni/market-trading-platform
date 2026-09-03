# NOAA/NWS/CPC Weather Demand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not stage or commit files.

**Goal:** Build PIT-correct official NOAA/NWS/CPC weather-demand evidence and integrate it additively into natural-gas `EnergyMarketContext`.

**Architecture:** A dedicated `weather` package owns weather-specific clocks, forecast vintages, corrections, realizations, CPC/NWS parsing, deterministic demand state, and source health. The shared bitemporal reference store retains immutable evidence versions; EIA integration consumes a weather state at the same independent decision time.

**Tech Stack:** Python 3 standard library, frozen dataclasses, `urllib`, existing unittest/manifest validation framework, compact JSON/text fixtures.

## Global Constraints

- Official NOAA-family sources only; no paid or mandatory credential.
- Keep issue, availability, target, and realization clocks separate.
- Forecasts, realizations, and bounded versioned weather references remain distinct.
- Preserve raw CPC anomalies and quality flags; never silently repair source evidence.
- No GRIB2 scientific dependency stack.
- Natural gas is the first consumer; no score, signal, ML, or execution change.
- CPC and EIA geographies remain distinct without an explicit versioned crosswalk and weighting.
- New issue equals new vintage; same-issue content correction equals a knowledge version of that vintage.
- Preserve 1981-2010 normals and 2010 weight vintage explicitly.
- Run CHANGED throughout, energy DOMAIN once at the milestone, weather LIVE once, and FULL once at final acceptance.
- Do not stage, commit, push, reset, clean, stash, or alter unrelated dirty work.

---

### Task 1: Canonical contracts, quality, and PIT selectors

**Files:**
- Create: `src/market_platform_foundation/weather/__init__.py`
- Create: `src/market_platform_foundation/weather/contracts.py`
- Create: `src/market_platform_foundation/weather/quality.py`
- Create: `src/market_platform_foundation/weather/pit.py`
- Create: `src/market_platform_foundation/weather/store.py`
- Modify: `src/market_platform_foundation/contracts/reference.py`
- Test: `tests/weather/test_weather_pit.py`

**Interfaces:**
- Produces: `WeatherForecastObservation`, `WeatherRealizationObservation`, `WeatherReferenceObservation`, `WeatherDemandState`, `WeatherStore`, `forecast_as_of(...)`, `forecast_revision(...)`, `realization_as_of(...)`, and `forecast_error_as_of(...)`.
- Reference kinds: `WEATHER_FORECAST`, `WEATHER_REALIZATION`, and `WEATHER_REFERENCE`.

- [ ] Write tests that construct Monday/Tuesday/Wednesday forecasts for one Friday target and assert issue/availability separation, future-target visibility, latest-available selection, same-issue correction versions, and old-vintage auditability.
- [ ] Run `python -m unittest tests.weather.test_weather_pit -v` and confirm failures are caused by the absent weather package.
- [ ] Implement the frozen contracts, explicit enums, quality flags, identity keys, append-only store, and selectors with UTC ISO clock comparisons.
- [ ] Add realization-leak and forecast-error tests: Wednesday sees forecast but not Friday actual/error; post-realization sees both and computes signed error.
- [ ] Run the focused test module and confirm all tests pass.
- [ ] Run `python tools/validate.py changed` and record result plus `full_suite_required`.

### Task 2: CPC parsers, regions, normals, and deterministic features

**Files:**
- Create: `src/market_platform_foundation/weather/cpc.py`
- Create: `src/market_platform_foundation/weather/regions.py`
- Create: `src/market_platform_foundation/weather/normalize.py`
- Create: `src/market_platform_foundation/weather/derived.py`
- Create: `tests/weather/test_cpc_weather.py`
- Create: `tests/fixtures/weather/cpc_forecast_utility_gas_heating.txt`
- Create: `tests/fixtures/weather/cpc_forecast_population_heating.txt`
- Create: `tests/fixtures/weather/cpc_forecast_states_cooling.txt`
- Create: `tests/fixtures/weather/cpc_realized_population_heating.txt`
- Create: `tests/fixtures/weather/cpc_climatology_1981_2010.txt`
- Create: `tests/fixtures/weather/cpc_regions.txt`

**Interfaces:**
- Produces: `parse_cpc_forecast(...)`, `parse_cpc_realized(...)`, `parse_cpc_climatology(...)`, `parse_cpc_regions(...)`, `build_weather_demand_state(...)`, `forecast_vs_normal(...)`, and bounded next-3/7-day summaries.
- Consumes: Task 1 weather contracts and store.

- [ ] Write parser tests for explicit 00Z issue, independent target columns, total-column exclusion, region types, utility-gas versus population weighting, missing values, and source metadata.
- [ ] Run `python -m unittest tests.weather.test_cpc_weather -v` and confirm expected parser-import failures.
- [ ] Implement pipe-delimited parsers using metadata headers and target dates; do not recompute weighted CPC aggregates.
- [ ] Add tests preserving the raw Vermont mapping plus `SOURCE_REGION_MAPPING_ANOMALY`, and prove CPC state/Census/climate/CONUS/EIA-region identities cannot be conflated.
- [ ] Add normal compatibility and future-normal-knowledge tests using variable, region, weighting, normal period/version, and available-from keys.
- [ ] Implement deterministic revision, next-3/7-day, and forecast-vs-normal features from one selected vintage with `predictive=False`.
- [ ] Run focused tests, then `python tools/validate.py changed`.

### Task 3: NWS current/prospective capture and NDFD archive characterization

**Files:**
- Create: `src/market_platform_foundation/weather/transport.py`
- Create: `src/market_platform_foundation/weather/live.py`
- Create: `src/market_platform_foundation/weather/nws.py`
- Create: `src/market_platform_foundation/weather/ndfd.py`
- Create: `src/market_platform_foundation/weather/capture.py`
- Create: `tests/weather/test_nws_ndfd.py`
- Create: `tests/fixtures/weather/nws_points.json`
- Create: `tests/fixtures/weather/nws_forecast.json`
- Create: `tests/fixtures/weather/nws_hourly.json`
- Create: `tests/fixtures/weather/nws_grid.json`
- Create: `tests/fixtures/weather/nws_observation.json`
- Create: `tests/fixtures/weather/ndfd_catalog.json`

**Interfaces:**
- Produces: `WeatherTransport`, `NwsClient`, point/grid mapping normalization, forecast/grid/observation capture, `characterize_ndfd_metadata(...)`, and sanitized capture envelopes.
- Consumes: Task 1 contracts/quality and Task 2 normalization vocabulary.

- [ ] Write tests for required/configurable User-Agent, bounded retry behavior, returned rather than manufactured horizons, grid interval units, observation/retrieval separation, point remapping, capture hashes, and NDFD `ARCHIVE_AVAILABLE_DECODE_DEFERRED`.
- [ ] Run `python -m unittest tests.weather.test_nws_ndfd -v` and confirm expected failures.
- [ ] Implement stdlib HTTP with a safe default User-Agent, cache metadata, timeouts, conservative pacing, `Retry-After`/bounded backoff, and sanitized errors.
- [ ] Implement NWS response normalization while retaining provider links, update/generation times, actual periods, units, interval valid times, QC data, and mapping revalidation metadata.
- [ ] Implement metadata-only NDFD characterization and bounded GRIB marker recognition without downloading or decoding full objects.
- [ ] Run focused tests, then `python tools/validate.py changed`.

### Task 4: Incremental sync, source health, and prospective capture

**Files:**
- Create: `src/market_platform_foundation/weather/sync.py`
- Create: `src/market_platform_foundation/weather/health.py`
- Create: `tests/weather/test_weather_sync_health.py`

**Interfaces:**
- Produces: `WeatherSync`, checkpoint records, `sync_cpc_degree_days()`, `sync_cpc_degree_day_forecast()`, `sync_nws_current_forecast()`, `capture_forecast_vintage()`, `source_health()`, and `capability_report()`.
- Consumes: Tasks 1-3 transport, parsers, capture, and store.

- [ ] Write failing tests for bounded overlap, missing/recent issue checks, content-hash correction handling, platform first-observed clocks, unknown-not-zero, independent component health, archive gaps, and deferred CDO/NDFD decode.
- [ ] Implement scheduler-neutral sync operations with no embedded cadence and no full-archive scan.
- [ ] Implement separate NWS, CPC realized, CPC forecast/archive, climatology, NDFD, medium-range, and integration health fields.
- [ ] Run focused tests, then `python tools/validate.py changed`.

### Task 5: FRED+CFTC+EIA+weather EnergyMarketContext

**Files:**
- Modify: `src/market_platform_foundation/eia/contracts.py`
- Modify: `src/market_platform_foundation/eia/cross_asset.py`
- Modify: `src/market_platform_foundation/eia/__init__.py`
- Create: `tests/weather/test_energy_weather_context.py`
- Create: `tests/fixtures/weather/energy_weather_timeline.json`

**Interfaces:**
- Extends: `EnergyMarketContext.weather_demand_state`, `weather_available_time`, and `staleness['weather']` with backward-compatible defaults.
- Extends: `build_energy_market_context(..., weather_store: WeatherStore | None = None)`.

- [ ] Write failing NG-context tests for Monday weather, Wednesday revision, Thursday-after-WNGSR, and Friday-after-COT, proving all four sources retain independent availability clocks.
- [ ] Add tests that contradictory storage/positioning/weather evidence remains separate and produces no composite score or direction.
- [ ] Implement additive context fields and build `WeatherDemandState` at the same decision time.
- [ ] Run `python -m unittest tests.weather.test_energy_weather_context -v`, all weather tests, then `python tools/validate.py changed`.
- [ ] Run `python tools/validate.py domain energy` and record exact counts/runtime.

### Task 6: Live suite, validation ownership, provider probe, and documentation

**Files:**
- Create: `tests/live_weather/test_live_weather.py`
- Create: `tools/weather/probe.py`
- Modify: `tools/validation_manifest.json`
- Modify: `tools/validate.py`
- Modify: `.env.example`
- Modify: `docs/engineering/VALIDATION_ARCHITECTURE.md`
- Create: `docs/providers/NOAA_NWS_CPC_WEATHER.md`
- Create: `evidence/weather/capability-report.json`

**Interfaces:**
- Adds: offline `weather` suite in domain `energy`, live provider `weather`, and child gate `IMP_WEATHER_LIVE`.
- Probe writes a sanitized, credential-free capability report.

- [ ] Write manifest/validation tests proving weather ownership, live isolation, and offline network denial.
- [ ] Register `weather` and `live_weather`; add weather gate mapping without changing unrelated provider gates.
- [ ] Implement bounded live tests for one NWS point chain, CPC realized/forecast archive semantics, NDFD metadata/range proof, parser clocks, and component health. Avoid fixed 14/168-period assumptions and bulk downloads.
- [ ] Implement the provider probe and capability report; document source labels, clocks, weighting, regions, PIT limitations, and explicit deferrals.
- [ ] Run `python tools/validate.py changed` and retain the expected `full_suite_required=true` result from manifest/shared-contract changes.
- [ ] Run all offline weather tests and record exact tests/skips/failures/runtime.
- [ ] Run `python tools/validate.py live weather` exactly once and record exact outcomes/current characterization.

### Task 7: Final acceptance and dirty-tree audit

**Files:**
- Verify all files above; do not create unrelated changes.

**Interfaces:**
- Produces the acceptance evidence needed for final sections A-AD.

- [ ] Re-read the approved design and acceptance checklist; verify each claim against code, fixtures, reports, or current official-source evidence.
- [ ] Run `python tools/validate.py full` exactly once and record configured/discovered suites, tests, passes, skips, failures, errors, and wall time.
- [ ] Run `git status --short`, `git diff --stat`, and targeted diffs; separate weather-created, weather-modified, and pre-existing dirty untouched files.
- [ ] Confirm nothing is staged or committed and HEAD remains `7d286de34be6dcc051e7cf31c726a5d1cd5bf4bb` unless repository reality changed externally.
- [ ] Produce the required A-AD final report and end with exactly `READY_FOR_NEXT_SOURCE` only if all correctness gates pass; otherwise end with `WEATHER_CORRECTNESS_BLOCKER_REMAINS`.
