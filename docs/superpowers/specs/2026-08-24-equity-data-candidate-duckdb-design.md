# Equity Data Phase 2 — Deterministic Candidate DuckDB Design

**Status:** Approved design, pending principal review of this specification

**Date:** 2026-08-24

**Decision owner:** Principal

**Implementation state:** Not started

## 1. Decision

Phase 2 will transform one frozen, inventoried copy of the legacy equity SQLite database into an immutable candidate DuckDB bundle. The build is deterministic within one pinned Windows x86-64 build profile, preserves source anomalies, and records the limits of the legacy evidence without inventing point-in-time, currency, security-type, or historical-universe facts.

The result is deliberately not research-ready. Every Phase 2 artifact is marked `CANDIDATE`, `NOT_EVALUATED`, and `NONE` for artifact class, admission status, and research authority. Phase 3 must establish safe availability, identity and universe policy, quality dispositions, and explicit admission before any row can feed a formula, feature, model, evaluation, or backtest.

This specification narrows Phase 2 of [Equity Data Pipeline Integration — V1 Design and Delivery Plan](2026-08-23-equity-data-pipeline-integration-design.md). Where that parent design assumes facts that the legacy snapshot does not contain, this specification controls Phase 2. It does not weaken the parent design's requirements for an eventually admitted dataset.

## 2. Evidence that constrains the design

The committed V1 inventory describes a mutable source file, not a frozen build input. At audit time it recorded:

- SQLite size: `2,484,719,616` bytes;
- SHA-256: `8670c385ad4b5d8c9917f0633bca74d98f50095065ff507792673536e6f9b8c4`;
- `18,044,890` daily-price rows for `6,570` instruments, spanning `1962-01-02` through `2026-07-27`;
- `13,052` ticker-registry rows, `206,243` dividend rows, and `4,802` split rows;
- `1,881,131` weekly rows, `433,837` monthly rows, `734` current index-membership rows, and `12,847` progress rows.

The audit also established these limitations:

- the legacy database has no acquisition-attempt table and no row-level retrieval timestamp, provider revision, collector version, or `yfinance` version;
- the current collector requests unadjusted OHLC with `auto_adjust=False`, but the database cannot prove that every historical row was collected under that code and configuration;
- the ticker registry is a current observation, not listing history, and contains heuristic ETF flags, mostly null countries, and securities such as units, warrants, rights, preferred shares, tests, and foreign listings;
- currency is absent from price and dividend rows;
- the source includes at least 25 nonpositive-price rows, 22 OHLC-geometry failures, extremely large reverse-split-era prices, extreme dividends, and one duplicate dividend;
- no orphaned instrument references were found in the audited populated tables;
- the database did not have a non-empty WAL at audit time, but it had not been frozen and therefore was not a valid immutable build input.

These observations are audit evidence, not permission to clean or classify rows during Phase 2.

## 3. Scope

Phase 2 includes only:

1. a versioned source-inventory contract for a frozen SQLite copy;
2. an isolated `data_worker` build environment and complete dependency lock;
3. deterministic, read-only streaming from SQLite through bounded Arrow batches into DuckDB;
4. candidate tables for instruments, observed symbols, daily bars, corporate actions, a reference calendar, empty quality flags, and dataset metadata;
5. logical content hashes, a deterministic dataset identity, a transport checksum, a build report, and a canonical manifest;
6. an atomic, immutable candidate-directory publication operation;
7. benchmark and deterministic-rebuild gates;
8. offline worker, collector inventory, repository-boundary, and platform validation tests.

Phase 2 does not include:

- data cleaning, deduplication, capping, rounding, quarantine, rejection, validation, or admission;
- a current/admitted pointer, rollback, or packaging;
- a platform worker protocol, platform API, research service, CLI research commands, features, formulas, model training, evaluation, or backtests;
- a historical universe, security classification, exchange-calendar assignment, currency conversion, dividend normalization, adjusted-price derivation, or corporate-action reconciliation;
- resumed collection or mutation of the legacy source;
- live tests or network access.

## 4. Build boundary and dependency isolation

The builder lives in a separate `data_worker/` Python project. The governed platform core remains CPython 3.11 standard-library-only and must not import DuckDB, PyArrow, pandas, NumPy, or exchange-calendar packages.

The worker uses:

- CPython `3.11.15` for the supported build profile;
- Python's standard-library `sqlite3` module for source reads;
- PyArrow for bounded typed batches;
- DuckDB for candidate storage;
- `exchange_calendars` only to materialize the versioned `XNYS_REFERENCE` calendar.

The implementation must commit a complete, hash-locked dependency resolution, including every direct and transitive package and wheel. A build records the lock-file hash and refuses to run when the interpreter, package versions, wheel hashes, operating system, or architecture differ from the declared profile. Selecting exact package artifacts and hashes is an implementation task performed before builder code is accepted; floating or range-based production dependencies are prohibited.

DuckDB's SQLite extension is not used. The build must not auto-install or auto-load extensions. Community and unsigned extensions are disabled. The DuckDB storage compatibility version, block size, row-group size, insertion batch size, thread count, and relevant configuration values are explicit inputs recorded in the manifest.

## 5. Frozen-source prerequisite and inventory 2.0

No real candidate build may read the mutable database at its current path. Before a build, an operator must create a consistent frozen copy in a new immutable source-snapshot directory. The copy procedure must ensure SQLite is closed or use SQLite's supported backup mechanism; copying a live main file while ignoring WAL content is forbidden.

The builder accepts only source inventory format `2.0.0`. The existing V1 inventory remains historical evidence and is rejected as a build authorization document.

Inventory 2.0 contains, at minimum:

- inventory schema version and inventory capture timestamp;
- snapshot method and completion status;
- relative source filename, exact byte size, modification time, and SHA-256;
- SQLite `quick_check` result and schema hash;
- journal mode plus the presence, size, and disposition of `-wal` and `-shm` sidecars;
- every source table, ordered column schema, row count, and source-table content hash;
- source-lineage ID and parent inventory identity;
- the inventory tool code revision and configuration hash.

Host-specific absolute paths are diagnostic only and do not contribute to logical dataset identity. A real build recomputes all authorized source checks before opening SQLite. It then opens only the frozen copy in read-only/query-only mode. `immutable=1` may be used only after the inventory and sidecar checks prove that the copy is a complete immutable snapshot.

## 6. Source-table policy

The manifest enumerates every discovered source table exactly once with one of these dispositions:

- `CONSUMED`;
- `EXCLUDED_BY_POLICY`;
- `ABSENT`;
- `UNSUPPORTED_SCHEMA`.

Each entry includes its source row count and a stable reason code. The initial policy is:

| Source table | Phase 2 disposition | Reason |
| --- | --- | --- |
| `tickers` | `CONSUMED` | observed registry and source identity |
| `daily_prices` | `CONSUMED` | raw daily bars |
| `dividends` | `CONSUMED` | raw provider dividend events |
| `splits` | `CONSUMED` | raw provider split events |
| `weekly_prices` | `EXCLUDED_BY_POLICY` | later derivable from admitted daily bars |
| `monthly_prices` | `EXCLUDED_BY_POLICY` | later derivable from admitted daily bars |
| `index_membership` | `EXCLUDED_BY_POLICY` | current membership is not historical truth |
| `scraping_progress` | `EXCLUDED_BY_POLICY` | mutable operational state, not research data |
| fundamentals and statement tables | `EXCLUDED_BY_POLICY` when present and empty | no point-in-time contract in this dataset |
| supplemental tables | `EXCLUDED_BY_POLICY` when present and empty | no point-in-time contract in this dataset |
| `acquisition_attempts` | `ABSENT` for the legacy snapshot | the audited database predates that schema |

An unexpected table or schema does not disappear silently. It is recorded as `UNSUPPORTED_SCHEMA`, and the build fails before publication until policy is explicitly revised.

## 7. Instrument identity and registry semantics

The source snapshot receives a persistent `source_lineage_id`. Each instrument's stable external identity is UUIDv5 over a versioned namespace and the tuple `(source_lineage_id, raw_ticker_id)`. The raw database file hash is not part of the instrument identity, so later snapshots from the same proven registry lineage retain IDs. A rebuilt registry that reassigns raw ticker IDs must receive a new lineage ID and therefore new instrument IDs.

The Phase 2 instrument record preserves source assertions but does not elevate them to canonical facts:

- `reported_symbol`, `reported_exchange`, `reported_country`, `reported_is_etf`, `reported_first_seen`, `reported_last_updated`, and `reported_active` retain source values;
- `normalized_symbol` is a deterministic lookup aid, not proof of historical equivalence;
- canonical `security_type` is `UNKNOWN`;
- canonical `country_code` and `currency_code` are null unless directly evidenced by the frozen source, which the legacy snapshot does not provide reliably;
- listing, delisting, and symbol-effective dates are null;
- no default research cohort is assigned.

`symbol_history` contains the observed source symbol tied to the instrument but leaves effective bounds unknown. It must not turn registry observation times into listing dates or fabricate ticker-change history.

If the physical benchmark chooses a numeric surrogate for joins, that value is candidate-local and never replaces the stable UUID in manifests or external contracts.

## 8. Candidate logical schema

Exact DuckDB physical encodings are frozen only after the benchmark gate, but these logical contracts are fixed.

### 8.1 `instruments`

One row per consumed raw ticker ID, including the stable instrument UUID, source lineage and row ID, preserved registry fields, nullable canonical fields, and provenance basis.

### 8.2 `symbol_history`

One observed-symbol row per legacy ticker row unless the source contains distinct evidence. Effective-from and effective-to remain null, and the basis is `LEGACY_REGISTRY_OBSERVATION`.

### 8.3 `daily_bars`

One row per source `daily_prices` row. It retains source row ID, instrument identity, session date, unadjusted OHLC, provider adjusted close, volume, source provenance, and the availability fields in section 9. Phase 2 derives no split-adjusted or total-return series.

No source bar is removed or rewritten because it has a nonpositive value, invalid geometry, extreme magnitude, unusual return, zero volume, duplicate logical key, or calendar mismatch.

### 8.4 `corporate_actions`

One row per source dividend or split row. The record preserves source row ID and event type. Dividends use `provider_amount`; splits use `provider_ratio`. `currency_code` is null, and Phase 2 makes no USD assertion, conversion, reconciliation, deduplication, or predictive-event claim.

### 8.5 `trading_sessions`

A version-pinned `XNYS_REFERENCE` calendar over the daily-bar date range plus the configured boundary buffer. It contains expected session open, close, early-close, and status values. It is reference data only: Phase 2 does not assign XNYS to every instrument or reject source dates that do not match it.

### 8.6 `quality_flags`

The table and stable schema exist but contain zero rows in Phase 2. Source anomalies remain in their source tables. Phase 3 owns rule execution and dispositions, preventing a construction step from being mislabeled as validation.

### 8.7 `dataset_metadata`

Contains the logical dataset ID, schema version, build profile, source snapshot and lineage identities, builder revision, dependency-lock hash, configuration hash, logical table row counts and hashes, source-table dispositions, artifact class, admission status, research authority, and the explicit legacy limitations.

It does not contain the DuckDB file's own checksum, the manifest checksum, an admission timestamp, or any field that creates a hash cycle.

## 9. Time and availability semantics

The build keeps four different concepts separate:

1. `session_date` is the market date represented by a daily bar.
2. `source_observed_at` is the frozen snapshot's observation timestamp. For the legacy snapshot this is a dataset-level timestamp and therefore may be identical across all rows and instruments. It is not claimed to be the time each value was originally collected.
3. `market_available_at` is a modeled market-time lower bound. For a raw daily bar only, it is the pinned reference-session close plus a declared ingestion delay. It varies by session date. It is null for legacy corporate actions because their announcement/publication time is unknown.
4. `available_at` is the research-admission boundary. It remains null for every legacy Phase 2 observation.

Every row also has an `availability_basis`. Legacy rows use `UNRESOLVED_LEGACY_SNAPSHOT`; modeled bar times separately record the calendar version and delay policy. No query may substitute `source_observed_at` or `market_available_at` for null `available_at`.

This means availability fields do affect downstream calculations by design: null `available_at` causes fail-closed exclusion. Phase 2 itself performs no calculations, formulas, model fitting, or backtests.

Phase 3 must either establish an approved conservative availability rule with evidence or reject the affected observations. Until then, the candidate has no research authority.

## 10. Provenance and legacy assertions

Provenance strength is explicit rather than implied:

- source provider and collection configuration are `PIPELINE_DECLARED` where supported by the merged collector code and documentation;
- row-level retrieval time, collector version, provider-library version, provider revision, and response identity are `UNKNOWN_LEGACY`;
- `auto_adjust=False` is recorded as the current pipeline declaration, not proof about every stored row;
- source table and source row ID are retained for traceability;
- the frozen snapshot time is labeled `source_observed_at`, never `collected_at` or `retrieved_at`.

The manifest contains both value and evidence basis so a consumer cannot confuse a declared configuration with measured row provenance.

## 11. Deterministic transformation and logical hashing

SQLite is read in stable source-primary-key order. The builder uses one thread and fixed-size bounded Arrow batches. Every target table has a declared insertion order, column order, and null ordering. The same ordering is used for logical hashing and DuckDB insertion.

Logical row hashes use a versioned typed binary codec, not JSON serialization:

- table and codec domain separators precede every hash;
- columns appear in the canonical schema order;
- each value has an explicit null/present marker and type tag;
- signed integers use fixed-width little-endian two's-complement encoding;
- floating values use their exact IEEE-754 binary64 payload, preserving signed zero and rejecting unsupported non-finite source encodings rather than silently normalizing them;
- text uses its exact UTF-8 byte sequence with an unsigned length prefix;
- dates and timestamps use fixed-width integer epoch representations with declared units and UTC rules;
- UUIDs use their 16 canonical bytes.

Table hashes are streaming hashes over ordered encoded rows and include row counts. The logical dataset ID is a domain-separated SHA-256 over canonical table hashes plus the source snapshot identity, source lineage ID, candidate schema version, builder code revision, dependency-lock hash, build-profile identity, and canonical configuration hash.

The DuckDB file SHA-256 is a transport checksum only. It is written outside the database after the file is closed and is not an input to the dataset ID. Manifest and checksum files likewise avoid self-reference.

## 12. DuckDB byte reproducibility

Byte-identical DuckDB output is required only within the supported pinned profile:

- Windows x86-64 build identity;
- CPython `3.11.15`;
- exact locked DuckDB, PyArrow, calendar, and transitive dependencies;
- fixed DuckDB storage compatibility version and block size;
- fixed row-group size, Arrow batch size, table creation order, row insertion order, and thread count;
- extension autoload, autoinstall, community repositories, and unsigned extensions disabled;
- identical source inventory, builder revision, schema, and configuration.

Cross-platform byte identity is not claimed. Any supported profile change produces a different build-profile identity and therefore a different dataset ID.

A release-mode build creates two independent candidates from the same frozen source and compares logical table hashes, dataset IDs, DuckDB file hashes, row counts, and schemas. Any mismatch fails publication and retains bounded diagnostics.

## 13. Benchmark checkpoint

Before a full conversion, the implementation builds a deterministic, ignored representative sample containing a fixed instrument selection plus every known anomaly class. It benchmarks two physical join layouts:

1. native UUID instrument foreign keys;
2. candidate-local integer join keys with the stable UUID retained in `instruments`.

The proposed UUID/instrument-date layout advances only if, on the declared reference machine:

- projected full DuckDB size is no larger than the frozen SQLite source;
- peak resident memory is at most 4 GiB;
- a single-instrument 10-year bar query has warm p95 latency at most 250 ms;
- a 1,000-instrument one-year panel query has warm p95 latency at most 2 seconds;
- a full-history cross-sectional aggregate has warm p95 latency at most 10 seconds.

Each query runs once to warm storage and ten measured times. The report records hardware, cold timing, all measured timings, SQL, result row counts and hashes, file size, peak memory, and `PRAGMA storage_info` output including compression. If UUID misses any gate and the integer layout passes, the physical schema uses integer joins while preserving UUID as the external identity. If neither layout passes, full construction stops for design review.

Benchmark samples, databases, and timing output are ignored local artifacts; the bounded canonical benchmark report is committed as acceptance evidence when implementation occurs.

## 14. Bundle layout and atomic publication

One candidate is published as a whole immutable directory:

```text
data/candidate/<dataset-id>/
├── equity-candidate.duckdb
├── manifest.json
├── build-report.json
└── SHA256SUMS
```

The builder writes to a uniquely named sibling temporary directory, closes and fsyncs files, verifies both deterministic builds, verifies all hashes and metadata, and atomically renames the completed directory to `<dataset-id>`. It never overwrites an existing dataset directory. A pre-existing directory is accepted only after every expected byte and hash is verified; otherwise the build fails closed.

Before starting, disk preflight reserves space for the frozen source, the first temporary build, the deterministic comparison build, the published final footprint, reports, and a 20 percent safety margin. Publication is not attempted when the conservative bound is unavailable.

The manifest is canonical UTF-8 JSON with sorted keys and newline termination. `SHA256SUMS` covers the closed DuckDB, manifest, and build report but not itself. The bounded build report contains counts, timings, resource high-water marks, source dispositions, warnings, and reproducibility comparisons; it contains no raw rows or secrets.

## 15. Fail-closed consumer boundary

Phase 2 tests establish a boundary before later worker integration exists:

- a candidate declares `artifact_class=CANDIDATE`;
- it declares `admission_status=NOT_EVALUATED`;
- it declares `research_authority=NONE`;
- there is no `current` pointer;
- any future non-administrative worker mode must reject a candidate path or these metadata values;
- platform core tests prove it has no DuckDB/PyArrow/calendar imports and cannot discover the mutable raw path through a research API.

The candidate may be opened only by explicit administrative inspection and Phase 3 validation tooling.

## 16. Validation strategy

All Phase 2 tests are offline and use small deterministic fixtures. No live provider tests run.

Worker tests cover:

- inventory 2.0 acceptance and rejection, sidecars, source mutation, schema drift, and read-only enforcement;
- source-table disposition completeness;
- instrument UUID stability within a lineage and change across reassigned lineages;
- exact preservation of anomalous floats, duplicates, source row IDs, and null canonical facts;
- availability semantics and fail-closed null `available_at`;
- typed hash codec edge cases and hash-cycle absence;
- fixed ordering and bounded batches;
- disabled extension behavior;
- atomic directory publication, collision refusal, interrupted-build recovery, and disk preflight;
- two-build logical and byte reproducibility within the pinned profile.

Collector tests cover inventory 2.0 generation from a frozen fixture and ensure the mutable acquisition database is never treated as a candidate.

Repository-boundary tests ensure worker dependencies do not enter the platform lock or import graph. Platform `changed` validation runs after edits, the applicable offline domain suite runs at milestones, and platform `full` runs at the final checkpoint. A `full_suite_required=true` result is honored. No validation step admits the candidate.

## 17. Phase 2 acceptance criteria

Phase 2 is complete only when all of the following are demonstrated:

1. The real build input is a newly frozen copy with a passing inventory 2.0, not the current mutable file or V1 inventory.
2. The source file and sidecar state are reverified before a read-only open, and source bytes remain unchanged after the build.
3. Every discovered source table has one explicit disposition and reconciled row count.
4. Every consumed source row appears exactly once in the corresponding candidate table; anomalies and duplicates are preserved byte-semantically.
5. Instrument UUIDs follow the lineage contract and no registry timestamp is represented as listing history.
6. Canonical security type, currency, country, historical membership, and listing bounds remain unknown where evidence is absent.
7. `source_observed_at`, `market_available_at`, and `available_at` have the distinct semantics in section 9; all legacy `available_at` values are null.
8. The reference calendar is versioned and is not asserted as every instrument's venue calendar.
9. The candidate carries no quality dispositions, admission, current pointer, or research authority.
10. Logical hashes and dataset identity reproduce, with no file-hash or manifest-hash cycle.
11. Two builds under the pinned profile produce identical DuckDB bytes and bundle content.
12. The selected physical schema passes the benchmark checkpoint and records storage compression.
13. Publication is atomic, immutable, collision-safe, and covered by disk preflight.
14. Worker dependencies remain isolated from the platform core.
15. Worker, collector, boundary, platform changed/domain, and final full offline validation pass.

## 18. Explicit handoff to Phase 3

Phase 3 owns all decisions that can grant or deny research use:

- resolve or conservatively reject legacy availability;
- establish supported instrument types, exchange/calendar mapping, currency, symbol history, and universe policy;
- execute structural, market-logic, corporate-action, coverage, and drift rules;
- preserve flags and assign admitted, quarantined, or rejected dispositions;
- reconcile duplicates and anomalous observations without erasing raw candidate evidence;
- create an immutable admitted artifact, explicit admission record, current pointer, and rollback behavior.

Until Phase 3 satisfies those gates, Phase 2 output must remain unusable by formulas, engines, and backtests.

## 19. Review and implementation gate

Principal approval of this specification authorizes a task-level implementation plan for Phase 2 only. It does not authorize a real candidate build until a frozen source copy, inventory 2.0, dependency lock, disk preflight, and benchmark checkpoint are present. Any change that assigns a non-null legacy `available_at`, elevates legacy source assertions to canonical facts, removes anomalous rows, weakens deterministic identity, or grants research authority requires renewed design review.
