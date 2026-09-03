# Equity Data Pipeline Integration — V1 Design and Delivery Plan

**Status:** Proposed for final review

**Date:** 2026-08-23

**Decision owner:** Principal

**Implementation state:** Not started

## 1. Executive decision

Integrate the existing `stock-data` project and the market platform into one Git repository while retaining hard component boundaries. The collector remains a mutable acquisition subsystem, the research platform remains standard-library-only, and a separate local data worker owns DuckDB and all analytical data operations.

Version one will deliver a research-ready, point-in-time-controlled daily dataset for quality-qualified U.S. equities and ETFs. It will preserve the complete discovered symbol registry and all rejected or questionable observations, but only admitted data may be used by default for features, formulas, training, evaluation, or backtests.

The distributable ZIP will contain the platform, pipeline code, one admitted DuckDB snapshot, its manifest, quality report, and checksums. It will not contain the mutable raw SQLite database, candidate builds, provider caches, credentials, or quarantined raw payloads.

This is the best first-version balance of compact storage, query performance, reproducibility, portability, and isolation from the governed platform core.

## 2. V1 goals

1. Preserve and complete the useful daily price and corporate-action data already collected.
2. Produce immutable, content-addressed DuckDB snapshots suitable for reproducible research.
3. Prevent look-ahead, survivorship, symbol-identity, adjustment, and stale-data errors from silently entering research.
4. Expose bounded research operations through the platform API and CLI without adding DuckDB to the platform core.
5. Retain failed and anomalous observations for formula hardening and robustness evaluation.
6. Make refresh, validation, admission, rollback, export, and offline replay deterministic and auditable.
7. Establish an extensible contract for later point-in-time fundamentals, filings, earnings, insiders, options, and supplemental datasets.

## 3. V1 non-goals

- Live trading or broker execution based on the new dataset.
- A new research UI; API and CLI come first.
- Declaring all discovered tables training-safe.
- Reconstructing historical options chains from current option-chain snapshots.
- Treating current index membership, current ticker status, or current fundamentals as historical truth.
- Automatically admitting a candidate merely because collection completed.
- Storing mutable raw acquisition data in Git or the normal distribution ZIP.

## 4. Repository and runtime architecture

The final repository should use this logical layout; exact package moves may be staged to preserve existing imports during migration.

```text
market-trading-platform/
├── platform/                    # Governed standard-library-only platform core
├── pipelines/stock_data/        # Collection, normalization, and mutable raw SQLite
├── data_worker/                 # DuckDB build, validation, query, and artifact jobs
├── data/
│   ├── raw/                     # Mutable local inputs; ignored and never distributed
│   ├── candidate/               # Replaceable builds awaiting admission
│   └── admitted/                # Immutable DuckDB snapshots
├── manifests/                   # Dataset identities, provenance, and admission pointers
├── reports/quality/             # Machine-readable and human-readable validation reports
├── checksums/                   # Snapshot and artifact hashes
└── tools/                       # Root orchestration, validation, migration, and packaging
```

There are three runtime trust zones:

1. **Acquisition pipeline:** may use network access and third-party Python dependencies; writes only mutable raw storage and acquisition logs.
2. **Data worker:** owns DuckDB and data-science dependencies; reads raw inputs, builds candidates, validates them, serves read-only queries, and emits versioned artifacts.
3. **Platform core:** remains CPython 3.11 standard-library-only; communicates with the worker through a narrow local process protocol and never imports DuckDB.

The normal data flow is:

```text
discover/update raw SQLite
  -> build isolated candidate DuckDB
  -> validate and quarantine
  -> generate manifest, report, and hashes
  -> explicit admission
  -> immutable snapshot used by research API/CLI
```

## 5. Storage decisions

### 5.1 Raw acquisition store

SQLite remains the mutable collector database for V1 because the current collection pipeline and approximately 18 million daily rows already use it successfully. It is a staging system, not a research contract.

Before migration or resumed collection, the existing database must be copied or snapshotted read-only and assigned a SHA-256 hash. The original must not be modified during conversion testing.

### 5.2 Admitted research store

DuckDB is the V1 admitted format because it provides compressed columnar storage, fast analytical scans, a single portable file, and direct support for deterministic offline queries. Large tables are physically ordered by stable instrument ID and session date, use bounded numeric types, and avoid repeated strings through normalized dimensions.

One admitted snapshot is one immutable DuckDB file. Admission never edits a prior file in place.

### 5.3 Distribution

The standard ZIP contains:

- repository code and configuration templates;
- one explicitly selected admitted DuckDB snapshot;
- dataset manifest and current-pointer manifest;
- quality report and checksums;
- setup, verification, and run instructions.

It excludes raw SQLite, candidates, caches, credentials, logs containing provider responses, and any source material whose license does not permit redistribution. A code-only ZIP remains available when data redistribution rights are unclear.

## 6. Canonical admitted schema

V1 uses the following logical tables. Physical types and indexes are finalized during implementation benchmarking.

### `instruments`

- stable `instrument_id` independent of current symbol;
- current display symbol and normalized symbol;
- exchange/MIC where known;
- security type and ETF indicator;
- currency and country;
- known listing and delisting bounds;
- active status as an observed attribute, not historical membership truth;
- source and retrieval metadata.

### `symbol_history`

- `instrument_id`;
- source symbol;
- normalized symbol;
- effective-from and effective-to when known;
- confidence and provenance.

Unknown historical mappings remain unknown. V1 must not fabricate effective dates from the current registry.

### `daily_bars`

- `instrument_id` and `session_date` as the logical key;
- unadjusted open, high, low, close, and volume;
- provider adjusted close when present;
- derived split-adjustment and total-return factors only when their construction is fully reproducible;
- source, retrieval timestamp, and `available_at`;
- row-level quality status.

Raw and adjusted views are separate named operations. The default backtest price convention must be declared by the caller and recorded in the run manifest.

### `corporate_actions`

- split or dividend type;
- ex-date, record date, payment date, and announcement/publication time where known;
- value or ratio and currency;
- source, retrieval timestamp, and `available_at`;
- reconciliation status.

An ex-date without a trustworthy publication time can adjust historical series but cannot be exposed as a predictive event feature before its safe availability boundary.

### `trading_sessions`

- calendar and session date;
- expected open and close timestamps;
- holiday, early-close, and session status.

### `quality_flags`

- dataset, instrument, session, or source scope;
- stable rule code and severity;
- observed value and threshold;
- disposition: admitted, quarantined, or rejected;
- explanatory details and validation version.

### `dataset_metadata`

- dataset ID and schema version;
- source and collector versions;
- build and validation versions;
- minimum and maximum session dates;
- retrieval window;
- table row counts and content hashes;
- parent raw snapshot identity;
- admission policy and timestamp.

## 7. Point-in-time and research-safety rules

1. `session_date` means the market session represented by a daily bar.
2. `available_at` means the earliest time the platform may use that observation.
3. Daily bars are available only after the exchange close plus the configured ingestion delay, never at the beginning of their own session.
4. All experiment queries apply `available_at <= decision_time` in addition to session-date filtering.
5. Current index membership and the current active-security registry are not valid historical universes.
6. V1 universe construction uses known listing bounds and observed data availability, with an explicit limitation when delisting or symbol-history evidence is incomplete.
7. Training, preprocessing, normalization, imputation, and feature selection are fit inside each walk-forward training fold.
8. Every research result binds the exact dataset ID, universe policy, price convention, feature/formula version, fold boundaries, and code revision.
9. Offline replay performs no network calls and resolves no unpinned `current` dataset pointer.

## 8. Acquisition-completion plan

### 8.1 Stabilize before collecting

- Freeze and hash the current raw database.
- Reconcile schema migrations and document every existing table.
- Replace test-sized stage limits with explicit `--limit` development options; production defaults must cover the selected universe.
- Make stage progress granular by instrument, dataset type, date range, attempt, and terminal disposition.

### 8.2 Repair retry and incremental semantics

Collection outcomes are classified as:

- transient provider/network failure: exponential backoff and bounded retry;
- throttling: provider-aware cooldown and resume checkpoint;
- invalid or changed symbol: identity-review queue;
- legitimate no-data security: terminal status with evidence and recheck policy;
- partial response: retain valid range, record missing range, and retry only the gap;
- parser/schema drift: halt the affected source adapter and quarantine its payload.

Completed ranges are never downloaded again unless the operator requests reconciliation or a source correction policy requires it.

### 8.3 Finish the V1 source domain

The first completion target is daily prices and corporate actions for the qualified U.S. equity/ETF universe. The full 13,052-symbol registry is retained, while research admission initially requires a supported security classification, sufficient history, acceptable staleness, and passing market-data checks.

Existing weekly and monthly tables are not admitted. They are regenerated on demand from admitted daily bars using declared session-period conventions.

### 8.4 Refresh model

- The admitted snapshot remains frozen during collection.
- A daily refresh updates raw SQLite incrementally.
- The worker builds a new candidate with a new identity.
- Validation compares the candidate with the preceding admitted snapshot.
- Only an explicit admission command promotes it and updates the current pointer.
- Rollback changes the pointer to a prior immutable snapshot; it does not rewrite data.

## 9. Quality and admission policy

### 9.1 Hard structural gates

- schema and required columns match the declared version;
- logical keys are unique;
- foreign keys resolve;
- dates and timestamps are parseable and bounded;
- no null required OHLCV values;
- no future sessions relative to the build cutoff;
- manifest row counts and hashes reproduce.

Any failure blocks admission.

### 9.2 Market-logic gates

- prices are strictly positive;
- high is not below open, low, or close;
- low is not above open, high, or close;
- volume is non-negative;
- sessions belong to the declared calendar;
- gaps, zero-volume clusters, and stale endings are measured;
- extreme raw and adjusted returns are tested separately.

Invalid rows are quarantined. A security is rejected when remaining valid coverage falls below policy.

### 9.3 Corporate-action gates

- split factors reconcile with price discontinuities within a configured tolerance;
- dividends use consistent units and currency;
- adjusted-close behavior is internally consistent;
- raw OHLC is never silently combined with adjusted close;
- unexplained discontinuities receive a flag and cannot enter the default adjusted series.

### 9.4 Coverage gates

The default V1 research cohort requires:

- a supported U.S. equity or ETF classification;
- at least 252 valid sessions;
- an acceptable latest-session lag for securities believed active;
- a bounded missing-session rate after calendar and listing-bound adjustments;
- no unresolved identity collision.

Short-history securities remain queryable through an explicitly named cohort but are excluded from default model training.

### 9.5 Drift gates

Each candidate is compared with the previous admitted snapshot for:

- instrument and row-count changes;
- earliest and latest dates;
- additions, removals, and sudden coverage loss;
- return and volume distribution shifts;
- corporate-action count changes;
- quarantine and rejection-rate changes.

Large changes require explicit operator acknowledgment even if row-level rules pass.

### 9.6 Dispositions

- **Admitted:** safe under the declared V1 policy.
- **Quarantined:** preserved for inspection and formula-hardening tests, excluded from default research.
- **Rejected:** structurally unusable or unsupported for the candidate; rejection reason remains in metadata.

There is no ambiguous default `admitted_with_warnings` class. Non-blocking flags may accompany admitted data, but the policy must explicitly declare them safe.

## 10. Data-worker contract

The platform launches the worker as a local child process with a pinned admitted dataset path. Communication uses newline-delimited JSON over standard input/output. Logs go to standard error so protocol output remains machine-readable.

Every request contains:

- protocol version;
- request ID;
- operation name;
- dataset ID or exact path;
- bounded parameters;
- decision-time or cutoff when the operation is point-in-time-sensitive.

Every response contains:

- matching request ID;
- success or stable error code;
- dataset ID actually used;
- result metadata;
- bounded inline result or versioned artifact reference.

V1 operations are:

- `catalog` and `coverage`;
- `resolve_instrument`;
- `daily_bars` with explicit raw/adjusted convention;
- `universe_at` with declared policy limitations;
- `walk_forward_folds`;
- `evaluate_formula`;
- `extract_backtest_dataset`;
- `quality_report` and `provenance`;
- `health` and `protocol_version`.

Requests have row, byte, and time limits. Large outputs are written as content-addressed artifacts and returned by reference. The worker opens admitted databases read-only and refuses mutable candidates unless invoked in an explicit administrative mode.

## 11. Platform integration

The platform receives:

1. a standard-library worker client with strict request/response models;
2. an admitted-dataset registry and resolver;
3. research services for coverage, bars, universes, folds, formula evaluation, and backtest extraction;
4. CLI commands that expose those services;
5. run-manifest binding so every experiment records its dataset and research contract;
6. offline replay tests proving that pinned research does not access the network or the mutable raw store.

Recommended initial CLI surface:

```text
platform data list
platform data inspect <dataset-id>
platform data quality <dataset-id>
platform data bars <symbol> --from ... --to ... --price-convention ...
platform research folds --dataset ... --spec ...
platform research evaluate-formula --dataset ... --formula ... --folds ...
platform backtest prepare --dataset ... --strategy-spec ...
```

The CLI defaults to refusing an unpinned dataset for reproducible research commands. An interactive inspection command may use the current pointer but must display the resolved immutable ID.

## 12. Failure handling and operations

- A failed collector run resumes from checkpoints and cannot affect the admitted snapshot.
- A failed candidate build is deleted or replaced safely because candidates are non-authoritative.
- A failed validation leaves a full report and does not update admission pointers.
- An admission operation verifies file and manifest hashes immediately before promotion.
- Pointer updates are atomic.
- Worker crashes return a stable platform error with sanitized standard-error context; callers do not receive partial results as successful responses.
- Unsupported schema or protocol versions fail closed.
- Prior admitted snapshots remain available until an explicit retention policy archives them.
- Raw payloads and logs are sanitized to prevent secrets, cookies, or tokens from entering artifacts.

## 13. Provenance, licensing, and redistribution

Every source requires a machine-readable source record covering provider, endpoint or dataset, retrieval method, collection time, transformation chain, and known usage/redistribution constraints.

Provider access does not automatically imply permission to redistribute collected data. The packager therefore checks an allowlist before including an admitted snapshot. If rights are unknown or restricted, it emits a code-only ZIP plus instructions to build a local snapshot. This is a packaging control, not legal advice.

## 14. Later data domains

These are subsequent dataset contracts, not additional tables casually added to the daily dataset:

1. **Fundamentals and financial statements:** sourced with filing/publication timestamps, restatement lineage, units, periods, and accession identity.
2. **SEC filings, earnings, and insiders:** event time, public availability, corrections, and issuer identity are mandatory.
3. **Options:** collected prospectively on a schedule or obtained from a licensed historical provider; current chains cannot reconstruct history.
4. **Analyst and supplemental snapshots:** prospective-only until historically timestamped evidence exists.
5. **Historical membership and delistings:** acquired as a dedicated identity/universe dataset to reduce survivorship limitations.

Each domain gets its own schema, candidate, quality policy, manifest, and admission decision while reusing the worker and platform contracts.

## 15. Delivery sequence

### Phase 0 — Preserve and characterize

- snapshot and hash the existing raw database;
- export a reproducible inventory and baseline quality report;
- record source/license metadata and the current known limitations;
- add an architectural decision record for the monorepo boundary and DuckDB worker.

### Phase 1 — Make acquisition resumable and complete

- repair stage limits, status semantics, retry classes, and incremental ranges;
- normalize instrument/security classifications;
- resume daily-price and corporate-action collection for the selected universe;
- add collector unit and failure-recovery tests.

### Phase 2 — Build candidate DuckDB

- implement canonical schema and deterministic SQLite-to-DuckDB transformation;
- derive calendar-aware coverage and safe availability timestamps;
- produce candidate manifests, hashes, and build reports;
- benchmark size and representative queries before freezing physical types.

### Phase 3 — Validate and admit

- implement structural, market, corporate-action, coverage, and drift gates;
- materialize quarantine metadata and formula-hardening cohorts;
- implement explicit admission, atomic current-pointer update, and rollback;
- prove deterministic rebuild identity from the frozen raw snapshot.

### Phase 4 — Integrate the worker

- implement and version the JSON-lines protocol;
- add the read-only DuckDB worker and bounded artifact handling;
- add the standard-library platform client, dataset registry, and error mapping;
- verify platform dependency rules remain intact.

### Phase 5 — Expose research workflows

- implement catalog, bars, point-in-time universe, fold, formula, and extraction services;
- expose the selected CLI commands;
- bind dataset identity and research parameters to experiment manifests;
- add offline replay and walk-forward leakage tests.

### Phase 6 — Package and accept

- implement allowlist-aware code-only and code-plus-admitted-data packaging;
- verify a clean-machine ZIP setup and checksum validation;
- run platform changed/domain/full validation as appropriate;
- publish operating, refresh, admission, rollback, and troubleshooting documentation.

No later phase begins until its preceding data contract and acceptance evidence pass, but implementation tasks within a phase may be parallelized when they do not share mutable files.

## 16. V1 acceptance criteria

V1 is complete only when all of the following are demonstrated:

1. The original raw database is preserved with a recorded hash.
2. Daily updates resume without redownloading completed history and classify failures deterministically.
3. Candidate builds are reproducible from a pinned raw snapshot and code revision.
4. The admitted dataset contains no duplicate keys, orphan references, invalid required OHLC geometry, nonpositive required prices, or future sessions.
5. Every admitted observation has source, retrieval, session, and safe availability metadata.
6. Corporate-action and price conventions cannot be mixed implicitly.
7. Quarantined anomalies are excluded by default but available through an explicit formula-hardening cohort.
8. Every research run records immutable dataset identity, universe policy, price convention, cutoff, folds, feature/formula version, and code revision.
9. Pinned offline replay succeeds with network access disabled.
10. The platform core remains compliant with its standard-library-only boundary.
11. A prior admitted dataset can be restored through an atomic pointer rollback.
12. A clean distribution ZIP verifies checksums and runs the documented inspection and sample research commands.
13. Packaging refuses to include data without an affirmative redistribution policy.
14. Existing platform validation remains green, with new domain tests covering the integration.

## 17. Principal review gate

This document is the single design review before implementation. Approval authorizes creation of the task-level implementation plan and subsequent implementation in the stated phase order. Any later change that weakens admission, point-in-time, provenance, dependency, or redistribution controls requires a new principal decision; ordinary file placement and internal implementation details do not.
