# Equity Data Acquisition Operations

This guide covers the V1 acquisition foundation under `pipelines/stock_data`.
The collector writes mutable SQLite staging data and acquisition evidence. It
does not produce research-admitted data by itself.

## Authority boundary

- Raw SQLite is mutable acquisition staging, not a training, evaluation,
  backtest, feature, or formula authority.
- Acquisition completion does not equal research admission. Only a separately
  validated and explicitly admitted immutable DuckDB snapshot may be used by
  platform research workflows by default.
- Current index membership and current active-symbol status are observations at
  collection time, not historical universe truth.
- Existing `weekly_prices` and `monthly_prices` tables are non-authoritative.
  V1 research periods will be regenerated from admitted daily bars under a
  declared session-calendar convention.
- Fundamentals, statements, supplemental snapshots, options, earnings, and
  insiders do not yet have complete point-in-time contracts and are not
  training-safe in V1.

## Environment

From the monorepo root:

```powershell
cd pipelines/stock_data
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
```

The collector requires CPython 3.11 or newer. Its third-party dependencies stay
inside `pipelines/stock_data/.venv`; the governed platform core remains
standard-library-only.

## Preserve and inventory raw data

Before any resumed collection, migration, or conversion test, make a filesystem
or volume snapshot of the raw database and keep the original out of the write
path. Then inventory the frozen copy:

```powershell
.venv\Scripts\python.exe -m src.inventory --database <raw.sqlite3> --output <inventory.json>
```

The command opens SQLite in read-only mode, runs `PRAGMA quick_check`, records
table counts and daily-price bounds, hashes the database with SHA-256, and fails
if its size or modification time changes during the scan. The current source
inventory is stored at `reports/equity_data/raw-stock-data-inventory.json`.

SQLite WAL and SHM files are part of the live staging state. Quiesce writers and
snapshot the database consistently before relying on a hash for migration or
candidate-build provenance.

## Collection workflows

Bounded development collection:

```powershell
.venv\Scripts\python.exe -m src.pipeline v1 --limit 25
```

Unbounded V1 collection:

```powershell
.venv\Scripts\python.exe -m src.pipeline v1
```

The V1 sequence is fixed: ticker discovery, daily prices and corporate actions,
current index snapshot capture, then validation. It does not generate weekly or
monthly aggregates. “Unbounded” means no hidden ticker cap; resumability rules
may still skip work already classified by the collector.

Incremental daily refresh through an inclusive date:

```powershell
.venv\Scripts\python.exe -m src.pipeline refresh-prices --through 2026-08-23
```

Use `--limit N` or the legacy positional limit for a bounded refresh. Existing
series request a seven-calendar-day overlap and an exclusive provider end date;
new series request full history. Overlap rows and actions are replaced for the
observed range so corrections can be incorporated. Incremental refresh never
updates weekly or monthly tables.

## Outcomes and retry behavior

Every incremental attempt is appended to `acquisition_attempts`; prior attempt
rows are not overwritten.

| Outcome | Meaning | Default refresh behavior |
|---|---|---|
| `complete` | Non-empty response stored | Eligible on the next scheduled refresh |
| `transient` | Temporary transport or unclassified provider failure | Retried with bounded backoff |
| `throttled` | HTTP 429 or rate-limit response | Retried with bounded backoff |
| `invalid_symbol` | Delisted, invalid, or missing-timezone symbol | Skipped until `--retry-errored` |
| `no_data` | Provider returned no rows | Skipped until `--retry-errored` |
| `partial_response` | Response was structurally incomplete | Reserved for explicit partial-response checks; retry-eligible |
| `schema_drift` | Expected columns or provider schema changed | Skipped until `--retry-errored` and investigation |

Use an explicit terminal retry only after the underlying symbol or provider
condition has been reviewed:

```powershell
.venv\Scripts\python.exe -m src.pipeline refresh-prices --through 2026-08-23 --retry-errored
```

Persisted exception details redact common authorization, cookie, token, key,
secret, and password assignments. Credentials, cookies, request headers, and
raw provider payloads must never be committed or included in a distribution.

## Offline validation

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The suite uses fake provider clients and temporary SQLite databases. It must not
make network requests.

From the monorepo root, validate the platform boundary as well:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
```

## Provenance and redistribution

Provider access does not imply permission to redistribute collected data. Each
source needs a provenance record covering provider, retrieval method, collection
time, transformations, and known use and redistribution constraints. Packaging
may include an admitted data snapshot only when an affirmative redistribution
allowlist permits it; otherwise produce a code-only ZIP with local build
instructions. This control is not legal advice.

The next integration milestone builds, validates, and explicitly admits an
immutable DuckDB candidate, then exposes it to the platform through the isolated
data-worker process. Until that milestone is complete, this collector remains
acquisition staging only.
