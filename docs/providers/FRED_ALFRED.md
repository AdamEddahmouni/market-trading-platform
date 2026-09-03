# FRED / ALFRED Macroeconomic Evidence

**Status:** OBSERVED / CAPTURED (not ADMITTED)  
**Source:** Federal Reserve Bank of St. Louis — https://fred.stlouisfed.org/  
**ADR:** ADR-FRED-001

## Purpose

FRED / ALFRED provides **official U.S. macroeconomic and financial regime context** for Market Context (MC11), Futures macro context (F7), and cross-asset synthesis with CFTC COT positioning.

FRED is **not** a trading oracle, low-latency release feed, or macro surprise/consensus source.

## Dual-API Architecture (Mandatory)

| API | Role | Must NOT |
|-----|------|----------|
| **FRED V1 + ALFRED** | Series metadata, observations, vintages, realtime periods, releases, incremental updates, PIT reconstruction | Be replaced by V2 for historical truth |
| **FRED V2** | `/fred/v2/release/observations` — bulk current release histories, reconciliation bootstrap | Substitute for ALFRED historical-as-known queries |

**Classification:** DOCUMENTED (official FRED API documentation)

## Authentication Differences

| API | Auth | Logging hazard |
|-----|------|----------------|
| V1 | `api_key` query parameter | Full credentialed URLs must never be logged |
| V2 | `Authorization: Bearer <key>` | Bearer header must never appear in evidence |

Sanitized log example: `GET /fred/series/observations series_id=CPIAUCSL status=200`

**Classification:** OBSERVED

## REAL-TIME PERIOD SEMANTICS

Official ALFRED documentation defines observation-level real-time periods as a **knowledge interval**, not a release timestamp:

| Field | Official meaning |
|-------|------------------|
| `realtime_start` | First vintage date on which this revision is the **latest** available information |
| `realtime_end` | Last vintage date on which this revision remains the **latest** available information |
| `vintage_date` | Historical as-of date used to query ALFRED |
| `available_time` | Platform canonical first-eligibility time for decisions (derived — see policy below) |

**Critical rule:** `realtime_end` is the **end** of the knowledge interval. It must **never** be treated as first availability.

Current/latest revisions may have an open-ended `realtime_end` (`.` / missing / `#NA` in provider formats).

Date-only ALFRED historical knowledge lacks intraday precision. The platform preserves `availability_precision=DATE_ONLY` and fails conservatively on same-calendar-day intraday queries unless live first-observed or authoritative publication timestamps exist.

**Classification:** DOCUMENTED (ALFRED Download Data Help; FRED API Real-Time Periods)

## PIT / ALFRED Semantics

Multiple clocks are preserved:

| Clock | Meaning |
|-------|---------|
| `observation_date` | Economic reference period (valid time) |
| `scheduled_release_date` | Source calendar expectation (control plane) |
| `knowledge_start_date` / `realtime_start` | Knowledge interval start |
| `knowledge_end_date` / `realtime_end` | Knowledge interval end |
| `source_publication_time` | Authoritative original-source publication timestamp (when supplied) |
| `provider_first_observed_time` | Platform live capture timestamp |
| `available_time` | Canonical decision-knowledge cutoff |
| `availability_precision` | `TIMESTAMP`, `DATE_ONLY`, or `SNAPSHOT` (V2) |
| `observed_time` | First platform observation / retrieval evidence |
| `series_last_updated` | V2 series metadata only — not observation vintage truth |

`macro_as_of(indicator, T)` selects the revision whose **knowledge interval contains** `T`, respecting availability precision. V2 snapshot rows are excluded from historical PIT.

### `available_time` policy table

| Source evidence | Precision | Canonical rule |
|-----------------|-----------|----------------|
| Live first observation | `TIMESTAMP` | `available_time = provider_first_observed_time` |
| Authoritative source publication timestamp | `TIMESTAMP` | retain `source_publication_time`; governed separately from FRED vintage dates |
| ALFRED `realtime_start` only | `DATE_ONLY` | `available_time = knowledge_start_date`; intraday same-day queries fail conservatively |
| `realtime_end` | n/a | knowledge interval **end** only — never first availability |
| V2 `last_updated` | metadata | series change-detection only — never historical observation availability |
| V2 bulk snapshot | `SNAPSHOT` | `available_time = snapshot_observed_time`; current-state evidence only |

V1 `output_type` modes:

- `1` — Observations by Real-Time Period (row-level `realtime_start` / `realtime_end`)
- `2` — Observations by Vintage Date, All Observations (cross-tabulation shape)
- `3` — Observations by Vintage Date, New and Revised Observations Only
- `4` — Observations, Initial Release Only

**Historical PIT unavailable → fail closed (`PIT_UNAVAILABLE`).** V2 current history must never backfill historical decisions.

**Classification:** OBSERVED (live ALFRED proof on GDPC1 2024-Q1 revisions)

Live note: some `output_type=3/4` request shapes return HTTP 400 for specific series/parameter combinations. Capture sanitized error bodies; do not globally label types 3/4 unreliable. Per-vintage `output_type=1` remains the canonical PIT reconstruction path.

## Release Dates vs FRED Availability

Official release calendars do **not** guarantee when FRED serves updated values. Prefer first successful observation / provider evidence for live `available_time`.

**Classification:** DOCUMENTED

**Classification:** OBSERVED (live probe 2026-08-20)

Production V2 responses nest observations under `series[]` (not a flat top-level list). The client flattens these blocks while preserving `series_id`, `last_updated`, and `copyright_id`.

## V2 Release Observations

- Endpoint: `/fred/v2/release/observations`
- Max `limit`: 500,000 (default)
- Cursor pagination when `has_more=true`
- Preserve `last_updated` per series as **series metadata**
- Preserve `copyright_id`
- Missing value `"."` → UNKNOWN (never zero)
- V2 values are numeric strings — preserve raw reproducibility
- `last_updated` = timestamp when the **series** was last updated in FRED (partial-release detection aid)
- `last_updated` ≠ observation-level historical vintage availability

### Mixed-release hazard

During coordinated release updates, a single fetch may contain a mix of already-updated and not-yet-updated series. The platform detects `MIXED_RELEASE_UPDATE`, backs off, and re-fetches the complete release. It does not silently publish an inconsistent snapshot.

**Heuristic (INFERRED → audited live):** Production CPI release (id 10) showed `STABLE` mixed-update state on 2026-08-20; differing `last_updated` alone does not trigger mixed detection.

## V1/V2 Reconciliation

For current values, V1 and V2 must agree on series ID, observation date, and raw value for the **same** observation date (not merely the latest row in a bulk page). Mismatch → `V1_V2_RECONCILIATION_MISMATCH` (no silent winner).

**Classification:** OBSERVED (live CPILFESL 2026-07-01 matched)

## Tier 1 Macro Registry

Bounded registry (43 indicators) maps canonical concepts (e.g. `US_CORE_CPI`) to FRED series IDs. Live audit 2026-08-20: 41 VERIFIED_LIVE, 2 RIGHTS_REVIEW (ICE spreads).

**Classification:** OBSERVED

## Derived Features (UNVALIDATED)

| Feature | Layer |
|---------|-------|
| Raw levels | RAW |
| Parsed floats | NORMALIZED |
| US_2S10S, US_3M10Y, revision deltas | DETERMINISTIC_DERIVED |

All derived inputs must satisfy PIT: selected revision knowledge interval must contain `decision_time` for every component.

## CFTC Interoperability

`CrossAssetRegimeContext` joins:

- `MacroRegimeState` (FRED knowledge intervals / `available_time`)
- `InstitutionalPositioningState` (CFTC, `publication_time`)

Independent source clocks — no arbitrary FRED-before-COT ordering.

**Classification:** OBSERVED (live ES TFF + macro, 2026-08-20)

## Quality Flags

Includes: `SOURCE_UNAVAILABLE`, `AUTH_FAILED`, `MIXED_RELEASE_UPDATE`, `V1_V2_RECONCILIATION_MISMATCH`, `PIT_UNAVAILABLE`, `PIT_UNCERTAIN`, `MISSING_VALUE`, `COPYRIGHT_RESTRICTED`, `CURSOR_LOOP`, `PARTIAL_RELEASE_RETRIEVAL`.

## Sync Operations

```python
from market_platform_foundation.fred import FredSync, transport_from_env

v1, v2 = transport_from_env()
sync = FredSync(v1=v1, v2=v2)
sync.sync_series("DFF")
sync.sync_release_v2(10)
sync.reconcile_release(10, "CPILFESL")
```

## Security

- `FRED_API_KEY` in ignored local `.env` only
- Credential audit scans `FRED_API_KEY` and `api_key=` patterns
- No credentialed URLs or Bearer headers in fixtures/evidence

## Live Testing

```bash
# .env: FRED_API_KEY=...
IMP_FRED_LIVE=1 python -m unittest discover -s tests/live_fred -v
IMP_FRED_LIVE=1 python tools/fred/probe.py  # live when IMP_FRED_LIVE=1 and key present
```

Normal CI: no internet, no key required.

## Evidence migration note

Prior FRED evidence generated before the PIT semantics correction may have used `available_time = realtime_end` or V2 `last_updated` as historical availability. Those artifacts remain in the tree for auditability but are **superseded** by corrected code paths and regenerated `evidence/fred/capability-report.json` after live validation. Do not treat pre-correction snapshots as canonical PIT proof.

## Limitations

- Not a low-latency macro event feed
- Release calendar ≠ guaranteed FRED availability
- Macro revisions require ALFRED/vintage semantics
- Cross-frequency lag (monthly CPI vs daily yields)
- V2 current history ≠ historical truth
- Date-only ALFRED knowledge lacks intraday precision
- Third-party FRED series (e.g. ICE BofA spreads) may restrict redistribution — internal research only
- NBER recession / retrospective indicators deferred (lookahead hazard)

## Classification Legend

- **DOCUMENTED** — official FRED/ALFRED documentation
- **OBSERVED** — live probe or fixture characterization
- **INFERRED** — platform heuristic (e.g. mixed-release detection)
- **UNTESTED** — declared but not exercised in CI
