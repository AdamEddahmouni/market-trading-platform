# NOAA/NWS/CPC Weather Demand and Forecast-Vintage Design

**Status:** APPROVED  
**Date:** 2026-08-20  
**Scope:** Official NOAA-family weather-demand evidence, centered on natural gas

## Purpose

Add a governed `weather` evidence family that answers: what official weather forecast was actually available at decision time T? The package supplies CPC degree-day forecast vintages and realizations, prospective NWS forecasts, deterministic weather-demand context, and PIT-safe integration with FRED, CFTC, and EIA. It does not produce a score, signal, recommendation, or forecast model.

## Source boundary

- NWS API: current and prospective `/points`, point forecast, hourly forecast, raw grid data, station discovery, and latest observations. NWS data is never presented as historical forecast truth.
- CPC: canonical structured source for realized HDD/CDD, archived seven-day NDFD-derived HDD/CDD forecasts, official regions, 2010 population/heating-fuel weights, and 1981-2010 degree-day normals.
- NCEI/NDFD: archive metadata, access health, identity, and bounded format proof only. Raw GRIB2 decoding is deferred.
- CPC 6-10 and 8-14 day outlooks: documented and prospectively characterized. Historical normalization remains deferred unless issue and target-window semantics are cleanly provable.

No credential is required for the core package. NWS uses a deterministic project `User-Agent` with an `IMP_NWS_USER_AGENT` override. `NOAA_CDO_TOKEN` remains optional and absent status does not block the package.

## Canonical contracts

`WeatherForecastObservation` preserves provider/product identity, explicit region and weighting, variable, issue time, source availability, target interval, lead time, value/unit, file metadata, first-observed/retrieval/ingestion clocks, content hash, history/PIT classification, quality, provenance, lifecycle, and `predictive=False`.

`WeatherRealizationObservation` is a separate evidence family with observation/period and availability clocks. A realization never overwrites or masquerades as a forecast.

`WeatherReferenceObservation` is limited to versioned support evidence with an explicit subtype: `CLIMATOLOGY`, `REGION_CROSSWALK`, `WEIGHTING`, or `NWS_GRID_MAPPING`. It is not a catch-all.

`WeatherDemandState` provides bounded NG-oriented blocks: latest compatible forecasts, realized degree days available so far, next-three/seven-day summaries from one forecast vintage, utility-gas and population series kept separate, revision deltas, compatible forecast-vs-normal values, source age/quality, and `predictive=False`.

## Clock and vintage model

Weather owns four distinct clocks:

1. `forecast_issue_time`: source-declared model/product issue.
2. `forecast_available_time`: first defensible public/platform knowledge time.
3. `target_start`/`target_end`: period being forecast.
4. realization `available_time`: when the later outcome can be used.

Forecast visibility depends only on forecast availability, not target time. Realization visibility depends on realization availability. Forecast error becomes available at the later of forecast and realization availability.

A new issue is a new forecast vintage. A changed file for the same issue/product/region/weighting/target is a new knowledge version of that existing vintage. Monday and Tuesday issues are alternatives for the same target, while a correction to Monday remains Monday's vintage. The store retains both distinctions.

Historical CPC `Last-Modified` is retained as archive metadata and, where necessary, an explicitly labeled availability proxy. It is never silently equated with issue time or original publication time. Prospective capture records platform first-observed time and content hash.

## Geography and weighting

Canonical region types remain distinct: `STATE`, `CENSUS_DIVISION`, `CLIMATE_DIVISION`, `CONUS`, and `NWS_POINT`. CPC geography is not silently mapped to EIA storage regions.

CPC raw mappings are preserved verbatim. The observed Vermont-to-Mountain defect is emitted with a source-mapping quality flag. Any future corrected mapping must be a separately versioned transformation with provenance.

Population, utility-gas-customer, and other heating-fuel weighting methods are independent series. Normals are compatible only when variable, region, weighting, and normal version all match. The 1981-2010 normal period and 2010 weight vintage are explicit evidence fields.

## Components

- `contracts.py`, `quality.py`, `regions.py`: provider-neutral domain vocabulary and source-local validation.
- `transport.py`, `live.py`: bounded stdlib HTTP, required NWS User-Agent, retries/cache metadata, and live gate.
- `nws.py`, `cpc.py`, `ndfd.py`: source parsers and bounded source characterization.
- `capture.py`, `normalize.py`: immutable raw metadata, hashes, and canonical observations.
- `store.py`, `pit.py`: append-only correction history, forecast-as-of, realization-as-of, revision, and leak-safe forecast error.
- `derived.py`: deterministic NG demand windows, compatible anomalies, and `WeatherDemandState`.
- `sync.py`, `health.py`: scheduler-neutral incremental operations, prospective capture, independent source health, and capability report.
- `eia/contracts.py`, `eia/cross_asset.py`: additive weather state and weather clock in `EnergyMarketContext`.

## Failure behavior

Unavailable, missing, withheld, uncertain, mapping-changed, archive-gap, incompatible-normal, and decode-unavailable states are explicit quality flags. Unknown never becomes zero or normal weather. Source health is component-level rather than one Boolean.

## Validation design

Offline fixtures are compact official-data-derived slices. Required tests cover parsing, issue-versus-availability, future target visibility, forecast-as-of revisions, same-issue corrections, realization leakage, forecast-error availability, unknown-not-zero, weighting and region separation, normal compatibility/knowledge date, NWS remapping, and the Wednesday/Thursday/Friday FRED+CFTC+EIA+weather timeline.

`weather` is an offline suite in the existing `energy` domain. `live_weather` is opt-in through `IMP_WEATHER_LIVE=1`. Live validation is bounded and semantic: one representative NWS point chain, CPC current/archived products, parser clocks, source health, NDFD metadata/range proof, and no bulk downloads.

Development uses CHANGED after edits, energy DOMAIN at the milestone, weather LIVE once after offline stability, and FULL exactly once at final acceptance. No files are committed or staged.

## Explicit deferrals

Hurricanes, LNG/pipeline flows, power burn, ISO load, raw NDFD decode, shapefile/GIS ingestion, generic forecast engines, weather ensemble modeling, ML, trading logic, and market-consensus interpretation remain outside this package.
