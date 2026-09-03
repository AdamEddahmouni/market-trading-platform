# NOAA / NWS / CPC Weather Demand and Forecast-Vintage Intelligence

Official NOAA-family weather evidence for energy-demand research, with natural gas as the highest-priority consumer. The package is intended to answer one question safely:

> What weather forecast was actually available at decision time T?

It is not a weather trading signal, a natural-gas demand model, a composite weather score, or a substitute for measured consumption.

## Evidence labels and implementation status

Labels used throughout this document:

- **DOCUMENTED** — stated by an official NOAA, NWS, CPC, or NCEI source.
- **OBSERVED** — verified from a captured fixture or bounded live probe in this repository.
- **INFERRED** — a conservative platform interpretation that must retain its assumptions.
- **UNTESTED** — designed or documented but not yet verified by repository tests or a live probe.

The weather package, compact official-derived fixtures, bounded live probe, capability report, and `EnergyMarketContext` weather join are implemented. Parser/PIT behavior is **OBSERVED** in offline tests, and the bounded current-source characteristics are **OBSERVED** in `evidence/weather/capability-report.json`. Deeper archive statements that were not exhaustively live-enumerated remain **DOCUMENTED** or **INFERRED** as labeled.

## Product role

| Evidence family | What it contributes | Clock that controls visibility |
|---|---|---|
| FRED / ALFRED | Macro conditions and revisions | Macro `available_time` / knowledge interval |
| CFTC COT | Participant positioning | CFTC publication / availability time |
| EIA | Physical inventory and storage | WPSR or WNGSR availability time |
| NOAA / NWS / CPC | Weather-demand conditions, forecasts, and forecast revisions | Weather forecast or realization `available_time` |
| Futures / Order Flow | Price, flow, and liquidity | Market event and receipt clocks |

These sources may disagree. A higher HDD forecast, ample EIA storage, heavily long CFTC positioning, and weak futures price action must remain separate evidence. The platform must not collapse them into a bullish or bearish conclusion.

## Official source matrix

| Source | Canonical role | Access | Status |
|---|---|---|---|
| NWS API | Current point, hourly, raw-grid forecasts and observations | Public HTTPS; descriptive `User-Agent`; no API key | **OBSERVED** |
| CPC degree-day products | Realized HDD/CDD, normals, weighted regional aggregates | Public HTTPS/FTP | Parser **OBSERVED**; current realized data **OBSERVED** |
| CPC seven-day forecast archive | Historical forecast vintages derived from NDFD grids | Public archive organized by issue date | Parser/archive retrieval **OBSERVED** |
| NCEI NDFD archive | Deeper raw gridded forecast-vintage research | Public archive/cloud access | Metadata access **OBSERVED**; decode **DEFERRED** |
| CPC 6–10 and 8–14 day outlooks | Medium-range probabilistic temperature context | Public product pages and archives | **DOCUMENTED/CHARACTERIZED**, canonical ingestion **DEFERRED** |
| NCEI Climate Data Online v2 | Optional station/climate verification | Free token | **DOCUMENTED**, optional and **DEFERRED** |

## Official URLs

### NWS API

- Service documentation: <https://www.weather.gov/documentation/services-web-api>
- OpenAPI schema: <https://api.weather.gov/openapi.json>
- API root: <https://api.weather.gov/>
- Point metadata: `https://api.weather.gov/points/{latitude},{longitude}`
- Forecast: `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast`
- Hourly forecast: `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`
- Raw grid forecast: `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}`
- Latest station observation: `https://api.weather.gov/stations/{stationId}/observations/latest`

### CPC degree days and outlooks

- CPC degree-day landing page: <https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/cdus/degree_days/>
- CPC weighted daily-data tree: <https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/>
- CPC seven-day forecast tree: <https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_forecasts_7day/>
- CPC 6–10 day outlook: <https://www.cpc.ncep.noaa.gov/products/predictions/610day/>
- CPC 8–14 day outlook: <https://www.cpc.ncep.noaa.gov/products/predictions/814day/>

Archive directory and filename discovery must be re-verified by the bounded live probe before code treats a path as a stable production contract. HTML navigation and directory layouts are not schemas.

### NCEI

- NDFD product and archive description: <https://www.ncei.noaa.gov/products/weather-climate-models/national-digital-forecast-database>
- NDFD THREDDS archive: <https://www.ncei.noaa.gov/thredds/catalog/model/ndfd.html>
- NOAA NDFD cloud registry: <https://registry.opendata.aws/noaa-ndfd/>
- Climate Data Online API documentation: <https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation>
- CDO web services v2: <https://www.ncdc.noaa.gov/cdo-web/webservices/v2>

## Access and credential model

### NWS

The NWS API requires a descriptive `User-Agent` and currently does not require an API key (**DOCUMENTED**). The intended configuration is:

```text
IMP_NWS_USER_AGENT
```

A deterministic project default may be used if repository policy permits it. Operators may override it. Capability reports, logs, and probes should record whether an override is active, not persist the literal value, because a user-supplied value may contain contact information.

### CPC and NDFD

CPC degree-day files and the NDFD archive are public and require no mandatory secret (**DOCUMENTED**).

### Optional CDO token

NCEI Climate Data Online v2 may use:

```text
NOAA_CDO_TOKEN
```

The token is optional. Its absence must not block NWS, CPC, or NDFD metadata/archive characterization. Report absence as:

```text
CDO_LIVE_VALIDATION=DEFERRED_TOKEN_UNAVAILABLE
```

Never emit the token in URLs, logs, fixtures, evidence, or capability reports.

## NWS current forecast evidence

### Point-to-grid discovery

`/points/{latitude},{longitude}` maps a geographic coordinate to a Weather Forecast Office and grid coordinates (`office`, `gridX`, `gridY`) and supplies canonical endpoint links (**DOCUMENTED**).

NWS warns that point-to-grid mappings can change. The platform may cache the mapping, but the cache must retain:

- latitude and longitude;
- office, grid X, and grid Y;
- source update metadata when present;
- first-observed and retrieved times;
- a revalidation time or age policy;
- prior mappings as versions rather than overwriting them.

Office/grid coordinates are not an eternal spatial identity.

### Forecast products

The NWS point API exposes approximately the next seven days through forecast, hourly forecast, and raw grid products (**DOCUMENTED**). The platform must preserve the periods returned by the provider. It must not manufacture a fixed 168-hour horizon.

The three products serve different purposes:

| Product | Use | Canonical caution |
|---|---|---|
| Forecast | Human-oriented multi-period forecast | Preserve each returned valid period |
| Hourly | Hourly temperature and related fields | Do not assume complete or fixed-length coverage |
| Raw grid | Gridpoint forecast properties and update metadata | Preserve provider units and valid-time intervals |

Current NWS endpoints are current/prospective evidence. They must not reconstruct what NWS said last week or last month. Historical forecast truth requires a CPC/NDFD archive or a prospectively captured NWS snapshot.

### Observations

Observation stations are discovered from NWS point/grid relationships and station endpoints. NWS notes that observations may be delayed by upstream MADIS quality-control processing (**DOCUMENTED**). Preserve separately:

- meteorological `observation_time`;
- provider availability or first-observed evidence;
- platform `retrieved_time` and `ingested_time`.

An observation timestamp is not proof that the observation was publicly knowable at that instant.

## CPC degree-day evidence

### Definition

For an unweighted daily temperature calculation:

```text
daily_mean_temperature = (daily_max_temperature + daily_min_temperature) / 2
HDD65 = max(0, 65°F - daily_mean_temperature)
CDD65 = max(0, daily_mean_temperature - 65°F)
```

Heating degree days approximate weather-driven heating requirements. Cooling degree days approximate weather-driven cooling requirements. They are weather-demand proxies, not measured natural-gas demand, electricity load, or end-use consumption.

The platform must not recompute a CPC weighted HDD/CDD aggregate from one aggregate temperature. CPC's published weighted degree-day product is canonical for that series.

### Realized data

CPC publishes daily realized degree-day data organized by year, region type, and weighting method (**DOCUMENTED**). A canonical realization must preserve:

- variable (`HDD65`, `CDD65`, or temperature where provided);
- period or target date;
- region type and region identifier;
- weighting method;
- value and unit;
- normal/climatology methodology and version when present;
- source filename and source metadata;
- provider/source availability evidence;
- retrieved and ingested times;
- content hash, quality flags, and provenance.

Corrections to realized archives are new versions. They never overwrite previously observed content.

### Weighting methods

Population and utility-gas weighting answer different questions and must remain separate dimensions.

| Weighting | Interpretation | Restriction |
|---|---|---|
| Population | Degree-day exposure weighted by population | Do not relabel as natural-gas demand |
| Utility gas / heating-fuel customers | Heating exposure weighted toward gas-heating customers | Still a proxy, not measured consumption |
| Unweighted or source-specific | Source-defined geographic aggregation | Never merge silently with weighted products |

Unknown weighting is not a default weighting and not zero. It must fail closed or retain an explicit `UNKNOWN` classification with a quality flag.

### Regions

CPC products may cover:

- states;
- climate divisions;
- Census divisions;
- CONUS.

These taxonomies remain explicit. A state, CPC climate division, and Census division with similar names are not interchangeable.

EIA natural-gas storage regions are a separate taxonomy. Any CPC-to-EIA mapping must live in an explicit, versioned mapping table with documented aggregation assumptions. Raw CPC observations retain their original region identity even when a derived EIA-region view is produced.

## CPC archived seven-day forecasts

CPC publishes raw seven-day heating/cooling degree-day forecasts derived from NDFD grids and organizes historical products by forecast issue date (**DOCUMENTED**). High-value products include, subject to live filename verification:

- `StatesCONUS.Heating`;
- `StatesCONUS.Cooling`;
- `Population.Heating`;
- `Population.Cooling`;
- `UtilityGas.Heating`;
- `ClimateDivisions.Heating`;
- `ClimateDivisions.Cooling`.

A forecast file may identify its product, issue date/cycle, region/weighting semantics, seven target dates, and a total. Parse the seven targets as individual forecast observations. The total is a deterministic aggregation supplied for convenience; it is not an eighth independent observation.

The archive is the primary historical forecast-vintage source for structured energy weather. The current NWS API must not substitute for missing historical files.

## Forecast clock model

Weather requires four distinct clocks:

| Clock | Meaning |
|---|---|
| `forecast_issue_time` | When the source says the forecast product was generated/issued |
| `forecast_available_time` | Earliest defensible time the source file/product was publicly observable to the platform |
| `target_start` / `target_end` | The period the forecast describes |
| `realization_available_time` | When the later observed outcome became eligible for use |

Example:

```text
issue_time       = Monday 00:00 UTC
available_time   = Monday 15:00 UTC
target_time      = Friday
realization_time = after Friday's observed product is published
```

A Monday morning decision must not see the file if it was first defensibly observable Monday afternoon. A Friday target does not defer the forecast's knowledge time until Friday. Conversely, Friday's realized outcome must not be available to the Monday decision.

### Availability evidence hierarchy

The canonical policy should prefer:

1. authoritative public distribution timestamp, when the source supplies one;
2. defensible archive/file metadata, preserved with its precision and limitations;
3. prospective platform first-observed timestamp;
4. conservative date-only archive evidence with `PIT_UNCERTAIN`.

Do not set `forecast_available_time = forecast_issue_time` without evidence. Do not treat file modification metadata as exact public distribution time unless the source documents that semantic. Preserve `source_file_last_modified`, `provider_first_observed_time`, and `retrieved_time` separately.

## Forecast vintages, corrections, and PIT selection

For the same target, Monday, Tuesday, and Wednesday issues are distinct forecast vintages:

```text
forecast_vintage_1 ─┐
forecast_vintage_2 ─┼─> revision trajectory ─> realization ─> forecast error
forecast_vintage_3 ─┘
```

`forecast_as_of(target, decision_time)` may select only a compatible forecast whose `forecast_available_time <= decision_time`. The selected forecast is the latest eligible issued vintage under deterministic tie-breaking.

A later forecast issue does not mutate the earlier forecast. Both remain auditable. A provider correction to the same issued file is different: preserve both content hashes/source versions and close only the prior correction's knowledge interval.

Forecast revision comparisons require compatible:

- variable and unit;
- source product semantics;
- region type and identifier;
- weighting method;
- target interval;
- climatology version when an anomaly is compared.

Revision is a forecast change, not a market surprise.

## Realizations and forecast error

Forecasts and realizations are separate observation families. A realization never overwrites a forecast.

`forecast_error = realization - forecast` is deterministic derived evidence and may exist only when:

- the selected forecast was available at the intended forecast decision time;
- the compatible realization is available at the evaluation decision time;
- variable, unit, region, weighting, and target period are compatible.

Before realization availability, forecast error is unknown, not zero. Backtests must use a second, later evaluation cutoff for forecast-error analysis.

## Climatology and normals

Forecast-versus-normal and realized-versus-normal calculations require a compatible, versioned CPC normal or climatology baseline. Preserve:

- baseline name and source product;
- normal period, such as the source-defined climatological years;
- weighting method;
- region taxonomy and identifier;
- variable and unit;
- source version or file identity;
- first defensible availability time.

Do not apply today's normal retrospectively if that normal was not available at the historical decision time. Do not compare a utility-gas-weighted forecast with a population-weighted normal. Incompatible or future baselines produce no anomaly and a blocking quality flag.

CPC climatology methodology and baseline age must be reported as limitations; a normal is a reference baseline, not a forecast.

## Deterministic derived features

Allowed non-predictive features include:

- `next_3d_hdd`, `next_7d_hdd`;
- `next_3d_cdd`, `next_7d_cdd`;
- `utility_gas_hdd_7d`;
- `forecast_hdd_revision_24h`, `forecast_cdd_revision_24h`;
- `forecast_vs_normal`;
- `realized_hdd_to_date`, `realized_cdd_to_date`;
- `forecast_error`;
- `lead_day` or `lead_hours`.

All must carry `predictive=False`. Forbidden names/semantics include `weather_score`, `bullish_weather_score`, `gas_demand_score`, `temperature_signal`, or any buy/sell conclusion.

## NDFD archive

NCEI archives the National Digital Forecast Database, providing a deeper route to raw historical forecast grids (**DOCUMENTED**). Approved source research identifies NDFD history beginning in June 2004, with roughly the most recent decade online and cloud access from April 2020; exact coverage and gaps must be verified by the bounded probe before being labeled **OBSERVED**.

This package should characterize:

- archive period and directory structure;
- product and element availability;
- issue/reference/valid-time metadata;
- bounded catalog continuity;
- feasible selective retrieval;
- the decoding dependencies required for GRIB products.

Raw NDFD decoding is **DEFERRED/UNTESTED** unless it can be implemented without a heavy new dependency and without large downloads. Do not add a GRIB stack merely to claim archive support. Live validation must be limited to metadata, a catalog listing, or one tiny/selective product when practical.

## CPC 6–10 and 8–14 day outlooks

CPC issues 6–10 and 8–14 day temperature outlooks as medium-range probabilistic products (**DOCUMENTED**). These are not deterministic daily temperatures or HDD/CDD forecasts.

Characterization must preserve:

- issue/publication time and source availability evidence;
- target date range;
- probability category or anomaly tendency exactly as published;
- region/grid semantics;
- archive and machine-readable format availability;
- revision/version identity.

Canonical ingestion remains **UNTESTED** and should be deferred if the available representation cannot preserve machine-readable values, issue vintages, and decision-time availability cleanly. A category such as above-normal temperature must not be converted into invented HDD/CDD values or a directional gas signal.

## Prospective capture

Current NWS forecasts and current CPC files support scheduler-friendly prospective capture (**OBSERVED in fixture tests and the bounded live probe**):

1. discover or revalidate the source identity;
2. fetch with bounded retry/backoff and a declared `User-Agent`;
3. record retrieval and first-observed clocks;
4. hash sanitized raw content;
5. parse provider-specific issue and target semantics;
6. append new content/version only when identity or hash changes;
7. retain a checkpoint that is explicitly not completeness proof.

Prospective capture supports future PIT research. It does not reconstruct uncaptured historical NWS forecasts.

## EnergyMarketContext integration

The intended non-predictive context contains four independent evidence states:

```text
MacroRegimeState                 FRED / ALFRED clock
InstitutionalPositioningState    CFTC publication clock
EnergyFundamentalsState          EIA WPSR / WNGSR clock
WeatherDemandState               NOAA/NWS/CPC weather clock
```

For natural gas, `WeatherDemandState` should expose compatible, decision-time-visible weather evidence such as utility-gas-weighted HDD, population-weighted HDD/CDD, forecast revisions, and normal anomalies. It must retain weighting and region taxonomies and must not infer consumption.

`EnergyMarketContext` should add a separate `weather_available_time` and `staleness["weather"]`. It must not reuse EIA storage availability, CFTC publication time, a forecast target date, or a macro knowledge time as the weather clock.

An acceptance timeline should prove independently:

- a weather file issued Monday but distributed later Monday;
- WPSR visibility on Wednesday;
- WNGSR visibility on Thursday;
- CFTC visibility on Friday;
- a later realization that cannot leak into any earlier decision.

This integration is **OBSERVED in fixture tests** with separate macro, weather, WNGSR, and CFTC clocks.

## Source health

Health must be reported independently rather than collapsed into one NOAA status:

- NWS points discovery;
- NWS forecast;
- NWS hourly forecast;
- NWS raw grid forecast;
- NWS observations;
- CPC realized degree days;
- CPC current seven-day forecast;
- CPC forecast archive;
- CPC normals/climatology;
- NDFD archive metadata/catalog;
- CPC medium-range products;
- `EnergyMarketContext` interoperability.

Each component should report reachability, latest observed product/period where meaningful, schema/parser state, last successful observation, availability precision, and quality flags. HTTP 200 alone is not a health proof.

Expected fail-closed quality conditions include source unavailable, archive gap, schema change, unknown region, unknown weighting, unit mismatch, forecast not yet available, realization not yet available, availability uncertain, incompatible normal, future-normal leakage, stale grid mapping, and NDFD decode deferred.

## Testing and validation

Implemented offline coverage uses small immutable fixtures for:

- NWS points, forecast, hourly, grid, and observations parsers;
- CPC realized and seven-day forecast text formats;
- issue-versus-availability exclusion;
- target-versus-knowledge separation;
- three forecast vintages for one target;
- same-issue source correction/versioning;
- realization leakage and delayed forecast error;
- population versus utility-gas weighting;
- state, Census division, climate division, CONUS, and EIA-region separation;
- total-row exclusion;
- climatology compatibility and future leakage;
- unknown-not-zero behavior;
- four-source `EnergyMarketContext` timeline.

Planned commands:

```text
python tools/validate.py changed
python tools/validate.py domain energy
python tools/validate.py live weather
python tools/validate.py full
```

Live weather tests must be opt-in and bounded. They should prove User-Agent acceptance, point/grid discovery, real forecast content and clocks, CPC realized/forecast parsing, archive access, source health, and sanitized capability reporting. They must not bulk-download NDFD data or assert brittle exact latest dates.

Planned probe and report paths:

```text
tools/weather/probe.py
evidence/weather/capability-report.json
```

The files are implemented. Offline weather tests, energy-domain validation, and the bounded live-weather suite are **OBSERVED**; the final FULL checkpoint remains the authoritative package acceptance gate.

## Security, cost, and operational boundary

- No mandatory paid API is required.
- No mandatory new secret is required.
- NWS User-Agent configuration is metadata, but a user override may contain private contact information and should not be persisted verbatim.
- Optional CDO credentials must be redacted.
- No broker, order, signal, strategy, risk, position-sizing, paper-execution, or live-execution behavior belongs in this package.
- Capability evidence must contain no private paths, credentials, or personal identifiers.

## Limitations

- Forecast issue time may precede defensible public availability; historical availability may be date-only or uncertain.
- Archive directories can contain gaps, corrections, format drift, or files whose modification time is not original distribution time.
- Degree days are weather-demand proxies, not measured natural-gas or electricity demand.
- CPC weighted products cannot be reconstructed faithfully from one aggregate temperature.
- CPC and EIA region taxonomies are different and require explicit mapping.
- Realized archives may be corrected after initial publication.
- CPC climatology baselines age and may change methodology.
- The current NWS API is not a historical forecast archive.
- NWS point-to-grid mappings can change.
- NWS observations may be delayed by MADIS quality control.
- Raw NDFD coverage and decode feasibility remain to be verified; heavy GRIB decode is deferred.
- Medium-range outlooks express probabilities/categories, not deterministic HDD/CDD.
- No LNG flow, pipeline flow, power-burn, ISO load, hurricane-disruption, rig-count, or refinery-outage intelligence is included.
- No market weather consensus source is included; forecast revision is not market surprise.
- No weather, demand, forecast-correction, or trading model is trained or validated.

## Acceptance boundary

The provider package is not complete merely because current data can be downloaded. Acceptance requires fixture and live evidence that:

```text
FORECAST ISSUE
    -> SOURCE AVAILABILITY
    -> DECISION CAN KNOW FORECAST
    -> FORECAST TARGET OCCURS
    -> REALIZATION BECOMES AVAILABLE
    -> FORECAST ERROR BECOMES ELIGIBLE
```

The regressions and bounded live probe have passed. Final package acceptance additionally requires the single offline FULL checkpoint documented by the repository validation policy.
