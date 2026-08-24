# Equity Data V1 Acquisition Foundation — Session Handoff

**Handoff date:** 2026-08-24

**Repository:** `C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform`

**Validated feature worktree:** `C:\Users\adame\Desktop\market-trading-platform\equity-data-v1-worktree`

**Feature branch:** `feat/equity-data-v1`

**Validated implementation baseline:** `9da57e129245b456e462b7a5056e98048e5e9ccb`

**Base/main HEAD at handoff:** `60250919e65c6a4f88d947d787791e6475b3a6b2`

The handoff itself is committed on the feature branch after the validated
implementation baseline. Resolve the branch's current moving HEAD with
`git rev-parse HEAD`; do not hard-code the documentation commit as an
implementation boundary.

## 1. Read this first

The completed milestone is the **V1 acquisition foundation**, not the entire
end-state called V1 in the broader integration design.

The collector has been imported into the monorepo, the source database has been
inventoried read-only, hidden collection limits have been removed, acquisition
attempts are auditable, and daily price/corporate-action refreshes are resumable.
The branch is fully validated and ready for integration.

The following are **not implemented yet**:

- deterministic candidate DuckDB construction;
- canonical point-in-time research schemas;
- validation, quarantine, and explicit admission;
- immutable admitted snapshots and atomic current pointers;
- the isolated data-worker protocol and platform client;
- research API/CLI services backed by the admitted data;
- code-plus-data packaging and redistribution enforcement.

Therefore, the current SQLite database remains mutable acquisition staging. It
must not be treated as authoritative input for training, evaluation, formulas,
features, backtests, or trading decisions.

## 2. Original objective and settled decisions

The original objective was to determine whether the material in
`C:\Users\adame\Desktop\stock-data` could be used for training, evaluation,
enhancement, or formula hardening, finish the useful data collection, and
integrate the pipeline into the market-trading platform as one eventual Git
repository and distributable ZIP.

The settled first-version decisions are:

1. Use one monorepo while preserving hard runtime and dependency boundaries.
2. Keep the imported collector as a nested project at
   `pipelines/stock_data/`.
3. Keep SQLite as mutable acquisition staging because the existing data and
   collector already use it.
4. Use an immutable, compressed DuckDB file as the admitted analytical format.
5. Keep DuckDB and other data-science dependencies out of the governed,
   standard-library-only platform core.
6. Put DuckDB work in a separate local data worker, eventually communicating
   with the platform through bounded newline-delimited JSON over standard
   input/output.
7. Deliver daily U.S. equity/ETF bars and corporate actions first.
8. Preserve the full discovered symbol registry and rejected/quarantined
   observations, but admit only quality-qualified data by default.
9. Use API and CLI integration before building a new research UI.
10. Require point-in-time controls, immutable dataset identity, provenance,
    quality gates, walk-forward evaluation, and explicit admission before any
    research-safety claim.
11. Do not distribute provider data merely because it was accessible. Packaging
    must require an affirmative redistribution allowlist; otherwise ship code
    only and provide local build instructions.
12. Do not keep asking the principal routine implementation questions. Choose
    conservative, reproducible defaults and present milestone plans for review
    before implementation.

## 3. Provider clarification

The imported stock-data collector and the platform's FINRA/Finviz components
are separate concerns:

| Component | Current role | Credential state | Relevance to this milestone |
|---|---|---|---|
| Yahoo Finance through `yfinance` | Daily prices, dividends, and splits in the nested collector | Managed by the collector/library path | Primary price/action acquisition source in the implemented refresh |
| FINRA | Platform regulatory/short-intelligence data | Credential loader already exists and uses `FINRA_CLIENT_ID` and `FINRA_CLIENT_SECRET` | Not the source of the imported daily-price dataset |
| Finviz | Read-only discovery/observational platform provider | Separate Finviz credential lifecycle | Not the source of the imported daily-price dataset |

The prior platform baseline failure was not missing FINRA authentication. It
was a test-scoping defect in a Finviz lifecycle test: the test imported
`load_finra_credentials` into a local name, patched the module attribute, and
then called the unpatched local reference. Commit `9da57e1` changed the test to
call through the patched FINRA module namespace. No production FINRA or Finviz
code changed.

## 4. Current source-data inventory

The read-only inventory is committed at
`reports/equity_data/raw-stock-data-inventory.json`.

| Property | Recorded value |
|---|---:|
| Source path | `C:\Users\adame\Desktop\stock-data\database\market_data.db` |
| Size | 2,484,719,616 bytes |
| Recorded modification time (ns) | 1,785,225,946,137,277,700 |
| SHA-256 | `8670c385ad4b5d8c9917f0633bca74d98f50095065ff507792673536e6f9b8c4` |
| SQLite `PRAGMA quick_check` | `ok` |
| Daily-price rows | 18,044,890 |
| Instruments with daily prices | 6,570 |
| Daily minimum date | 1962-01-02 |
| Daily maximum date | 2026-07-27 |
| Ticker registry rows | 13,052 |
| Dividend rows | 206,243 |
| Split rows | 4,802 |
| Current index-membership rows | 734 |
| Weekly rows, non-authoritative | 1,881,131 |
| Monthly rows, non-authoritative | 433,837 |

The annual/quarterly statement tables, `fundamentals`, and
`supplemental_data` were empty in this inventory.

The inventory implementation:

- opens SQLite using `mode=ro`;
- runs `PRAGMA quick_check`;
- counts every user table and records daily bounds;
- hashes the database with SHA-256;
- verifies that size and modification time do not change during the scan;
- raises `RAW_DATABASE_CHANGED_DURING_INVENTORY` if the source moves during
  inventory.

Important limitation: the committed inventory proves the source was stable
during that scan. It is not itself a separately frozen database copy. Before a
candidate build, quiesce writers and create a consistent out-of-Git snapshot of
the SQLite database, including any relevant WAL/SHM state, then inventory that
exact frozen copy. Do not silently reuse the old hash if the mutable source has
changed.

## 5. What was implemented

### 5.1 Monorepo boundary

Only the collector's code, documentation, tests, and scripts were imported.
The source `.git`, raw database, generated data, virtual environments, caches,
credentials, and logs were excluded.

The nested project requires CPython 3.11+ and owns third-party dependencies such
as yfinance, pandas, NumPy, SQLAlchemy, requests, PyArrow, and Rich. A boundary
test rejects imports of these packages from `src/market_platform_foundation`.

Ignored nested outputs include:

```text
pipelines/stock_data/database/
pipelines/stock_data/data/
pipelines/stock_data/.venv*/
pipelines/stock_data/.pytest_cache/
pipelines/stock_data/htmlcov/
pipelines/stock_data/*.log
pipelines/stock_data/*.egg-info/
```

### 5.2 Read-only inventory

`pipelines/stock_data/src/inventory.py` provides:

```text
build_inventory(database_path, chunk_size=8_388_608)
write_inventory(database_path, output_path)
python -m src.inventory --database PATH --output PATH
```

### 5.3 Explicit V1 acquisition sequence

`PipelineRunConfig` defaults to:

```text
limit=None
retry_errored=False
aggregate=False
```

The fixed V1 sequence is:

```text
discover -> prices/actions -> current index snapshot -> validate
```

There are no hidden production ticker caps. A bounded run requires an explicit
positional limit or `--limit`. V1 does not generate weekly/monthly aggregates.
The legacy `all` and dashboard paths also receive one explicit limit rather
than injecting former 100/50-item defaults.

### 5.4 Acquisition evidence

The collector defines these stable attempt outcomes:

```text
complete
transient
throttled
invalid_symbol
no_data
partial_response
schema_drift
```

Every incremental attempt is appended to the `acquisition_attempts` SQLite
table. Existing attempt evidence is never overwritten. The database layer
provides single-ticker and one-query per-stage latest-attempt lookups.

Persisted exception details redact common authorization, cookie, API key,
token, secret, client-secret, and password assignments and are truncated to a
bounded length.

### 5.5 Incremental price/action refresh

For an instrument with existing history, refresh requests a seven-calendar-day
overlap and uses an exclusive provider end date. For a new instrument it
requests full history. The overlap exists so provider corrections can replace
previously stored prices, dividends, and splits.

The refresh path:

- loads latest daily dates with one grouped SQLite query;
- uses bounded concurrency;
- stores prices, dividends, and splits;
- replaces observations in the requested overlap range;
- preserves existing rows when a request is throttled or fails;
- treats a missing provider `Adj Close` column as nullable rather than a crash;
- retries transient/throttled outcomes with bounded backoff;
- skips terminal invalid-symbol, no-data, and schema-drift outcomes until the
  operator explicitly passes `--retry-errored`;
- records requested and observed ranges for every attempt;
- never updates the weekly or monthly tables.

## 6. Operator commands

Run collector commands from the validated worktree unless the branch has
already been merged.

### Create the collector environment

```powershell
cd C:\Users\adame\Desktop\market-trading-platform\equity-data-v1-worktree\pipelines\stock_data
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
```

### Inventory a frozen raw copy

```powershell
.venv\Scripts\python.exe -m src.inventory --database <frozen-raw.sqlite3> --output <inventory.json>
```

### Bounded development run

```powershell
.venv\Scripts\python.exe -m src.pipeline v1 --limit 25
```

### Unbounded V1 acquisition run

```powershell
.venv\Scripts\python.exe -m src.pipeline v1
```

### Incremental refresh through an inclusive date

```powershell
.venv\Scripts\python.exe -m src.pipeline refresh-prices --through 2026-08-24
```

Add `--limit N` for a bounded refresh. Use `--retry-errored` only after
reviewing the terminal symbol/provider condition.

### Collector tests

```powershell
.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp\handoff
```

The explicit base temp avoids the Windows sandbox permission issue previously
seen at `C:\Users\adame\AppData\Local\Temp\pytest-of-adame`.

### Platform validation

Use the platform virtual environment and CPython 3.11:

```powershell
cd C:\Users\adame\Desktop\market-trading-platform\equity-data-v1-worktree
$env:PYTHONPATH='src'
C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform\.venv\Scripts\python.exe tools\validate.py changed
C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform\.venv\Scripts\python.exe tools\validate.py full
```

Follow `AGENTS.md`: run `changed` after edits, the applicable domain selector at
a domain milestone, and `full` once at the final checkpoint. Do not run live
provider tests unless that specific live boundary was changed and explicitly
authorized.

## 7. Validation evidence at handoff

The final validated code state produced:

| Check | Result |
|---|---:|
| Exact FINRA mock regression | 1 passed |
| Full Finviz offline suite | 43 passed |
| Collector suite | 149 passed |
| Platform changed selector | 64 passed, 0 failures/errors |
| Platform full selector | 1,776 passed, 9 skipped, 0 failures/errors |
| Full runtime | 736.192 seconds |
| `git diff --check` | clean for the implementation diff |
| `git merge-tree --write-tree main HEAD` | exit 0, no commit-tree conflicts |
| Feature/main dirty-path overlap | none at handoff |

The collector's first audit invocation produced 140 passes and 9 setup errors
because pytest could not access the sandbox's default user temp directory. The
same suite passed all 149 tests when rerun with `--basetemp` inside the writable
collector workspace. This was an execution-environment issue, not a code
failure.

## 8. Git state and commits

The feature branch has not been merged into `main`.

Acquisition implementation commits after `main`, oldest first:

```text
90d2de96a45727326e8bd6846801bab82b01edc0  build(data): import isolated stock collector
552c598b5b107fd6f30c9885020e1d0977f50539  feat(data): inventory immutable raw database
d09d0d3f8127795a215314cd5a3c46fbae6d4778  fix(data): remove hidden collection limits
d605c5c4606fc7e3fd57f8bc905ef5487d61dde8  feat(data): record classified acquisition attempts
5998e575328839149ba4bf8037fb6909a59a98e2  feat(data): add resumable incremental price refresh
49d4ca5ae24005e450392fb02da0de258961be46  docs(data): add acquisition operations guide
9da57e129245b456e462b7a5056e98048e5e9ccb  test(finra): fix credential loader mock binding
```

The integration design and acquisition implementation plan are already on
`main`:

```text
2c9c6cf  docs(data): add equity pipeline integration design
6025091  docs(data): add acquisition implementation plan
```

### Existing uncommitted state that must be preserved

At handoff, the feature worktree contains these unrelated modified files:

```text
evidence/ui1/assistant-audit/conversations.json
evidence/ui1/assistant-audit/messages.json
```

At handoff, the main worktree contains:

```text
M  .env.example
M  evidence/ui1/assistant-audit/conversations.json
M  evidence/ui1/assistant-audit/messages.json
?? docs/providers/IBKR_OBSERVATIONAL.md
?? docs/superpowers/decisions/2026-08-23-adr-live-002-ibkr-gateway-observational.json
```

These changes belong to the user or another workflow. Do not reset, discard,
overwrite, stage, or commit them as part of equity-data work. Re-audit both
worktrees because their state may have changed after this handoff.

Git on this machine may reject the feature worktree as unsafe under the sandbox
owner. Use a command-scoped option rather than modifying global configuration:

```powershell
git -c safe.directory=C:/Users/adame/Desktop/market-trading-platform/equity-data-v1-worktree status
```

### Known documentation status drift

The integration design header still says `Status: Proposed for final review`
and `Implementation state: Not started`. The acquisition implementation plan
also retains unchecked task boxes. Those fields were not updated while the
tasks were executed. Do not interpret them as evidence that the acquisition
foundation must be repeated. Use the commit range, current source, inventory,
and validation evidence in this handoff as the implementation record. The
unimplemented broader-design phases remain explicitly listed in sections 1 and
10 of this handoff.

## 9. Research-safety classification

### Potentially useful after admission

- daily OHLCV bars;
- provider adjusted close as a separately identified field;
- dividends and splits;
- broad instrument-registry evidence;
- invalid/no-data/throttled/schema-drift observations for pipeline and formula
  robustness testing.

### Not safe by default today

- raw mutable SQLite tables;
- current index membership as historical universe membership;
- current active/inactive ticker status as historical truth;
- weekly/monthly tables already stored in SQLite;
- fundamentals, statements, earnings, insiders, analyst data, supplemental
  snapshots, and options without separate point-in-time contracts;
- any observation without a defensible `available_at` boundary;
- any provider data for redistribution without affirmative rights.

The weekly/monthly series should eventually be regenerated from admitted daily
bars under an explicit trading-session period convention.

## 10. Recommended continuation sequence

### Step 1 — Re-establish and preserve Git state

1. Read `AGENTS.md`.
2. Inspect both main and feature worktree status.
3. Confirm `feat/equity-data-v1` contains the validated implementation baseline
   and this handoff, and inspect any newer descendant commits.
4. Re-run a merge simulation against the current `main`.
5. Preserve all unrelated dirty files.
6. Integrate the validated V1 branch before starting Phase 2, or create the
   Phase 2 branch from `feat/equity-data-v1` if integration is intentionally
   deferred. Do not silently build Phase 2 from old `main`.

Because local merge, push/PR, keeping the branch, and discard are materially
different repository actions, use the repository's branch-finishing workflow
and obtain the principal's selection before performing one.

### Step 2 — Plan Phase 2: deterministic candidate DuckDB

The next implementation milestone should be narrowly scoped to **candidate
construction**, not admission, worker integration, or research APIs.

Before writing implementation code:

1. Audit existing platform dataset-manifest, provenance, bitemporal, quality,
   quarantine, and content-addressing contracts for patterns that can be reused
   without importing third-party packages into the platform core.
2. Inspect the raw SQLite schema and frozen snapshot only through read-only
   access.
3. Benchmark representative DuckDB physical types, sort order, compression,
   file size, and queries before freezing the physical schema.
4. Write a task-level Phase 2 implementation plan for review.
5. Use TDD and keep candidate-building tests offline and deterministic.

Recommended new boundary:

```text
data_worker/                  DuckDB-owned isolated project/runtime
data/raw/                     ignored frozen inputs or references
data/candidate/               ignored replaceable candidate files
data/admitted/                ignored immutable admitted files
manifests/                    tracked dataset/provenance identities where safe
reports/quality/              tracked bounded reports where safe
checksums/                    tracked hashes where safe
```

Do not finalize this exact placement until existing repository conventions and
ignore rules have been audited. Preserve the architectural boundary even if
the physical paths are adapted.

### Step 3 — Candidate schema and transformation contract

The broader approved design calls for these logical tables:

```text
instruments
symbol_history
daily_bars
corporate_actions
trading_sessions
quality_flags
dataset_metadata
```

Minimum Phase 2 rules:

- assign a stable instrument identity independent of current display symbol;
- retain original source symbols and provenance;
- do not fabricate historical symbol effective dates;
- distinguish `session_date`, retrieval time, and safe `available_at`;
- keep raw OHLC and provider adjusted close semantically separate;
- do not derive adjustment/total-return factors unless construction is fully
  reproducible and tested;
- represent dividends and splits as corporate actions with source and timing
  evidence;
- use deterministic ordering and canonical serialization for manifests;
- bind every candidate to the frozen raw SHA-256 and exact code revision;
- write candidates to a temporary path and publish the finished candidate
  atomically;
- never edit a candidate or admitted file in place;
- do not update an admitted/current pointer during Phase 2.

Candidate output should include:

- one candidate DuckDB file;
- schema/build version;
- source inventory identity;
- table counts and date bounds;
- content hashes/checksums;
- deterministic build manifest;
- bounded build report;
- benchmark evidence for physical layout decisions.

### Step 4 — Phase 3 after candidate construction is proven

Only after deterministic candidate construction passes should the next session
implement validation and admission:

- structural key/schema/foreign-key/date/hash gates;
- OHLC geometry, positive-price, nonnegative-volume, session-calendar, gap,
  staleness, and extreme-return checks;
- dividend/split/adjusted-close reconciliation;
- default cohort coverage rules, initially including at least 252 valid
  sessions and no unresolved identity collision;
- candidate-versus-prior-snapshot drift checks;
- explicit admitted/quarantined/rejected dispositions;
- formula-hardening cohorts that are excluded from default research;
- explicit admission with pre-promotion hash verification;
- atomic current-pointer updates and rollback.

No `admitted_with_warnings` ambiguity should be introduced. Nonblocking flags
must be explicitly permitted by policy.

### Step 5 — Later phases

After admission is proven:

1. Implement the versioned JSON-lines data worker and bounded read-only DuckDB
   operations.
2. Add a standard-library platform client and dataset registry.
3. Expose catalog, coverage, instrument resolution, bars, point-in-time
   universes, walk-forward folds, formula evaluation, and backtest extraction.
4. Bind dataset ID, universe policy, price convention, cutoff, fold boundaries,
   formula/feature version, and code revision to every research run.
5. Prove pinned offline replay never uses the network, mutable raw database, or
   an unpinned current pointer.
6. Package code-only by default and include admitted data only through an
   affirmative redistribution allowlist.
7. Validate a clean-machine ZIP, checksums, inspection command, sample research
   workflow, and rollback procedure.

## 11. Stop conditions and non-negotiable boundaries

Stop and report rather than silently proceeding if:

- the source raw hash differs and no new frozen-snapshot identity was approved;
- SQLite changes during inventory/build;
- symbol identity cannot be resolved without inventing history;
- a provider schema drift is detected;
- a candidate build is nondeterministic;
- a required observation lacks a defensible availability boundary;
- a change would add DuckDB/pandas/NumPy/SQLAlchemy/yfinance to the platform
  core;
- admission gates fail;
- packaging rights are unknown;
- unrelated dirty worktree files overlap the intended change;
- platform full validation fails.

Never expose raw SQLite, candidates, current membership, or current ticker
status as point-in-time research truth merely to make the integration easier.

## 12. Primary references

Read these before continuing:

1. `AGENTS.md` — validation and local-runtime rules.
2. `docs/data/EQUITY_DATA_V1_HANDOFF.md` — this handoff.
3. `docs/superpowers/specs/2026-08-23-equity-data-pipeline-integration-design.md`
   — approved end-state architecture and acceptance criteria.
4. `docs/superpowers/plans/2026-08-23-equity-data-acquisition-foundation.md`
   — implemented acquisition-foundation task plan.
5. `docs/data/EQUITY_DATA_ACQUISITION.md` — operator guide and authority
   boundary.
6. `pipelines/stock_data/README.md` — nested collector commands and dependency
   scope.
7. `reports/equity_data/raw-stock-data-inventory.json` — recorded raw source
   identity.

## 13. Fresh-session bootstrap prompt

Use the following as the first instruction in a new session:

```text
Continue the equity-data integration past the validated V1 acquisition
foundation. Start in
C:\Users\adame\Desktop\market-trading-platform\equity-data-v1-worktree on
branch feat/equity-data-v1. Read AGENTS.md and
docs/data/EQUITY_DATA_V1_HANDOFF.md completely, then read the integration design,
acquisition plan, operations guide, and raw inventory referenced by the handoff.

First audit current main/feature Git state and preserve all unrelated dirty
files. The validated implementation baseline was 9da57e1 and main was 6025091;
the handoff documentation was committed afterward, so resolve the current
feature HEAD and inspect descendants rather than treating 9da57e1 as the moving
branch tip. Do not merge, discard, push, or create a PR without the required
branch-integration choice.

The next milestone is a deterministic, isolated SQLite-to-candidate-DuckDB
builder with manifest, provenance, checksums, build report, and benchmark-backed
physical schema. Do not implement validation/admission, the worker protocol,
research APIs, or packaging in the same milestone. Do not use raw SQLite as
research authority, do not add third-party dependencies to the platform core,
and do not mutate the source database.

Choose conservative first-version defaults without asking routine questions.
Present the complete Phase 2 implementation plan for review before coding. Use
test-driven development, offline tests, and the AGENTS.md validation ladder.
```
