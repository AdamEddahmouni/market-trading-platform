# Governed Ticker-Metadata Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed, append-only `refresh-ticker-metadata` command that calls only `yfinance.Ticker.get_info()` and records allowlisted noncanonical metadata evidence in an explicitly selected existing SQLite database.

**Architecture:** A focused `src.ticker_metadata` package owns the request contract, provider classification, database preflight/schema, process lock, serialized writer, concurrency/retry circuits, provenance, and bounded reporting. The CLI recognizes the governed command before invoking the legacy create-capable global database initializer. All external effects are injected or isolated so the complete offline suite uses temporary databases and fake providers only.

**Tech Stack:** CPython 3.11, stdlib `sqlite3`, `concurrent.futures`, `threading`, `queue`, `hashlib`, `json`, `importlib.metadata`, existing `yfinance`, existing `FilterSpec`, pytest.

## Global Constraints

- `--database` is mandatory and must resolve to an existing regular SQLite file opened only with URI `mode=rw`.
- No live provider call or operator-database mutation occurs during implementation or offline validation.
- The adapter calls only `yfinance.Ticker(symbol).get_info()` once per call ordinal and retains only the eleven approved keys.
- Existing `tickers`, price, action, fundamental, statement, supplemental, progress, and generic acquisition rows are never updated by this command.
- Metadata attempts and observations are append-only, with exact schema validation and rejecting `UPDATE`/`DELETE` triggers.
- Defaults are four workers, two call starts per second with burst one, three ordinals, and retry delays of two then four seconds without jitter.
- Complete, partial, no-data, invalid-symbol, and schema-drift are terminal; only transient and throttled retry automatically.
- Three consecutive final schema-drift outcomes or five consecutive final throttled outcomes stop new scheduling and yield a stable nonzero CLI status.
- The implementation stops before any live canary, unbounded run, price/action refresh, source freeze, inventory mutation, Phase 2 build, or Phase 3 work.

---

### Task 1: Request contract and response classifier

**Files:**
- Create: `pipelines/stock_data/src/ticker_metadata/__init__.py`
- Create: `pipelines/stock_data/src/ticker_metadata/contract.py`
- Create: `pipelines/stock_data/src/ticker_metadata/models.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_contract.py`

**Interfaces:**
- Produces: `REQUEST_CONTRACT_JSON: str`, `REQUEST_CONTRACT_SHA256: str`, `REQUEST_CONTRACT_VERSION: str`, `ALLOWLIST: tuple[str, ...]`.
- Produces: `classify_response(requested_symbol: str, payload: object) -> ClassifiedResult` and `classify_exception(exc: BaseException) -> ClassifiedResult`.
- Produces: frozen `ClassifiedResult(outcome, reason_code, detail, projected, observed_fields)` and `TickerRef(raw_ticker_id, requested_symbol)` dataclasses.

- [ ] Write tests proving canonical contract JSON/hash stability, all eleven allowlisted keys, trimming/Unicode preservation, control-character and length rejection, boolean/negative market-cap rejection, ignored unknown keys, symbol normalization, identity-envelope outcomes, non-mapping drift, and stable exception mappings.
- [ ] Run `python -m pytest tests/ticker_metadata/test_contract.py -q` and confirm collection fails because `src.ticker_metadata.contract` does not exist.
- [ ] Implement immutable models and a canonical JSON contract with explicit bounds: symbol/quote type/currency 64, exchange forms 128, sector/industry/country 256, and names 512 Unicode code points.
- [ ] Implement projection and outcome classification without retaining the source mapping. Unknown exceptions use outcome `transient`, reason `unknown_exception`, and sanitized exception-class-only detail.
- [ ] Re-run the focused test and then `python tools/validate.py changed`; require both to pass before continuing.

### Task 2: Governed existing-database boundary and process lock

**Files:**
- Create: `pipelines/stock_data/src/ticker_metadata/storage.py`
- Create: `pipelines/stock_data/src/ticker_metadata/locking.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_storage_preflight.py`

**Interfaces:**
- Produces: `resolve_existing_database(value: str | Path) -> Path`.
- Produces: `MetadataStore.preflight(path: Path) -> PreflightSummary`, `MetadataStore.initialize_schema() -> None`, and `MetadataRefreshLock(path: Path)` context manager.
- Consumes: request-contract identifiers from Task 1.

- [ ] Write tests for missing, directory, empty, malformed, read-only, corrupt, wrong-registry, valid-registry, and no-creation behavior; patch the adapter factory to prove every refusal occurs before provider construction.
- [ ] Write a same-process/subprocess lock contention test showing the second lock fails with stable `metadata_refresh_locked` while a different database remains lockable.
- [ ] Run the focused preflight test and confirm failure because the storage/locking APIs are absent.
- [ ] Implement path resolution, 16-byte SQLite-header verification, percent-encoded `file:` URI construction, `sqlite3.connect(..., uri=True)` with `mode=rw`, foreign keys enabled, `PRAGMA quick_check`, `BEGIN IMMEDIATE`/rollback writability check, and exact required `tickers` columns (`id` integer primary key and `ticker` text-like non-null symbol plus filter columns used when selected).
- [ ] Implement a temp-directory lock filename derived only from SHA-256 of the normalized database path, using `msvcrt.locking` on Windows and `fcntl.flock` on POSIX, with OS-release semantics and bounded stable errors.
- [ ] Re-run the focused test and `python tools/validate.py changed`.

### Task 3: Exact append-only metadata schema and atomic writes

**Files:**
- Modify: `pipelines/stock_data/src/ticker_metadata/storage.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_storage_schema.py`

**Interfaces:**
- Produces: `MetadataStore.record_attempt(attempt: AttemptRecord, observation: ObservationRecord | None) -> WriteReceipt`.
- Produces: `MetadataStore.latest_outcomes(contract_hash: str) -> dict[int, str]`, `select_tickers(filter_spec, limit, retry_errored, contract_hash) -> Selection`.
- Consumes: frozen `AttemptRecord`, `ObservationRecord`, `WriteReceipt`, and `Selection` models.

- [ ] Write tests asserting exact columns/types/not-null/defaults, foreign keys, indexes, unique observation attempt ID, four immutability triggers, idempotent initialization, one-table-only refusal, incompatible object refusal, and exact definition revalidation.
- [ ] Write atomicity tests that force observation insertion failure and prove neither row commits; prove complete/partial requires one observation and every other outcome rejects observations.
- [ ] Snapshot every pre-existing fixture table as ordered typed rows before a write and prove only the two metadata tables change.
- [ ] Run the focused schema test and confirm it fails on missing behavior.
- [ ] Add canonical `CREATE TABLE`, `CREATE INDEX`, and `CREATE TRIGGER` statements; compare `PRAGMA table_info`, `foreign_key_list`, index metadata, and normalized trigger definitions before accepting an existing schema.
- [ ] Implement one short `BEGIN IMMEDIATE` transaction per attempt/observation pair, canonical sorted JSON field lists, foreign-key checks, cardinality invariants, deterministic ID ordering, raw-ID selection order before limit, resume rules, and filter predicates without adding the legacy active-only condition.
- [ ] Re-run the focused test and `python tools/validate.py changed`.

### Task 4: Single-method yfinance adapter and sanitized provenance

**Files:**
- Create: `pipelines/stock_data/src/ticker_metadata/provider.py`
- Create: `pipelines/stock_data/src/ticker_metadata/provenance.py`
- Modify: `pipelines/stock_data/src/acquisition.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_provider.py`

**Interfaces:**
- Produces: `YFinanceMetadataAdapter.call(symbol: str, ordinal: int) -> ProviderCallResult`.
- Produces: `collect_provenance(repository_root: Path) -> CollectorProvenance`.
- Produces: strengthened `safe_error_detail()` removing query strings, profile paths, secrets, authorization/cookies, controls, and text beyond 500 characters.

- [ ] Write tests with a sentinel ticker exposing forbidden properties/methods and assert only constructor plus `get_info()` is touched once per call.
- [ ] Test every exception class/message outcome, UTC start/completion timestamps, observed-field inventory, no raw payload retention, yfinance/Python version capture, Git clean/dirty capture, and conservative redaction.
- [ ] Run the provider test and confirm the missing adapter failure.
- [ ] Implement a late-imported default factory calling `yf.Ticker(symbol).get_info()` exactly once, passing the returned object directly into Task 1 classification and discarding it afterward.
- [ ] Implement bounded provenance through `git rev-parse HEAD`, `git status --porcelain`, `sys.version`, and `importlib.metadata.version`, with stable `unknown` fallbacks and no command output persisted beyond the declared fields.
- [ ] Re-run the provider test and `python tools/validate.py changed`.

### Task 5: Global limiter, serialized writer, retries, and circuits

**Files:**
- Create: `pipelines/stock_data/src/ticker_metadata/runner.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_runner.py`

**Interfaces:**
- Produces: `StartRateLimiter(rate_per_second=2.0, burst_capacity=1, monotonic, sleep).wait()`.
- Produces: `MetadataRunner(store, adapter, provenance, clock, workers=4).run(selection) -> RunReport`.
- Consumes: `MetadataStore.record_attempt`, Task 1 contract/models, and Task 4 adapter/provenance.

- [ ] Write fake-clock tests proving starts are globally separated by at least 0.5 seconds, initial burst is one, retry sleeps are exactly `[2.0, 4.0]`, call ordinals reset across invocations, and only transient/throttled retry.
- [ ] Write concurrency tests measuring at most four simultaneous provider calls and exactly one serialized SQLite writer operation at a time.
- [ ] Write circuit tests proving three consecutive final schema drifts and five consecutive final throttles stop new scheduling, intervening outcomes reset only their matching counters, already-started work commits, and circuit reports are stable/non-successful.
- [ ] Write interrupted-run/resume tests proving committed interactions remain selectable according to latest outcome and absent commits safely retry.
- [ ] Run the runner test and confirm missing runner APIs.
- [ ] Implement a lock-protected token-start limiter, four-worker bounded submission window, dedicated queue-backed writer thread with per-write acknowledgement, retry loop, and circuit-aware scheduler that stops replenishing the window after a trip.
- [ ] Aggregate only counters/timestamps/field presence into a frozen `RunReport`; never retain row-level provider values in the report.
- [ ] Re-run the runner test and `python tools/validate.py changed`.

### Task 6: Governed CLI dispatch and bounded terminal report

**Files:**
- Modify: `pipelines/stock_data/src/cli_args.py`
- Modify: `pipelines/stock_data/src/pipeline.py`
- Create: `pipelines/stock_data/src/ticker_metadata/cli.py`
- Test: `pipelines/stock_data/tests/ticker_metadata/test_cli.py`

**Interfaces:**
- Produces: `run_refresh_ticker_metadata(database, filter_spec, limit, retry_errored) -> int`.
- Modifies: `pipeline.main() -> int | None`, with `raise SystemExit(main())` at module execution so circuit/preflight failures are observable by the shell.

- [ ] Write parser/dispatch tests proving `--database` is mandatory only for metadata refresh, named/positional limits resolve once, existing filter flags are recorded, invalid/non-positive limits fail, and legacy commands retain existing behavior.
- [ ] Patch `init_database`, legacy scraper entry points, and provider factory to prove metadata dispatch never invokes the global create-capable initializer or fundamentals paths.
- [ ] Write stdout/stderr tests for bounded preflight/run summaries, all required counters/config fields, no row values, sanitized failures, and stable nonzero codes for preflight, lock, schema, and circuit failures.
- [ ] Run the CLI test and confirm expected failures.
- [ ] Add `--database` to centralized parsing, detect the governed command before legacy initialization, acquire the path-keyed lock before selection, preflight/initialize/select/run/report in order, and map stable domain failures to fixed exit codes.
- [ ] Add command documentation without changing any legacy default database behavior.
- [ ] Re-run CLI and existing pipeline-limit/refresh tests, then `python tools/validate.py changed`.

### Task 7: Boundary, immutability, and offline-network regression coverage

**Files:**
- Modify: `pipelines/stock_data/tests/test_monorepo_boundary.py`
- Create: `pipelines/stock_data/tests/ticker_metadata/test_boundaries.py`
- Modify: `pipelines/stock_data/README.md`
- Modify: `pipelines/stock_data/docs/SCHEMA.md`

**Interfaces:**
- Verifies the complete command boundary rather than adding production APIs.

- [ ] Add an AST-based source boundary test allowing only `get_info` in `provider.py` and rejecting imports from `src.scrapers.fundamentals` or calls to legacy projection mutators anywhere in the new package.
- [ ] Add a subprocess CLI test under a network-denial fixture proving missing/incompatible databases fail before any socket attempt and a fake adapter completes without network.
- [ ] Add database-content hashing/typed-row snapshots around a representative run to prove every protected table is byte-semantically unchanged.
- [ ] Run the boundary tests and confirm they fail before the documentation/source boundary is complete.
- [ ] Document command syntax, noncanonical evidence semantics, resume/retry behavior, live-canary gate, schema, and explicit prohibition on using the legacy default database.
- [ ] Re-run boundary tests and `python tools/validate.py changed`.

### Task 8: Collector and repository validation checkpoint

**Files:**
- Modify only files required by failures reproduced with a new failing regression test.

**Interfaces:**
- No new interfaces; validates Tasks 1-7 as one offline milestone.

- [ ] Run the complete collector suite from `pipelines/stock_data` with an isolated temporary base and CPython 3.11: `python -m pytest tests -q`.
- [ ] Run the applicable repository domain checkpoint selected from `tools/validation_manifest.json`; if the collector has no declared domain owner, run its direct boundary tests plus platform `changed` and record that ownership gap rather than editing the governed manifest without approval.
- [ ] Run `python tools/validate.py changed --explain`, inspect `full_suite_required`, selected suites, and omitted domains, then run it without `--explain` if needed for a clean final result artifact.
- [ ] Re-read every design acceptance item and verify it against tests/source; add a failing regression test before correcting any gap.

### Task 9: Final offline verification and handoff

**Files:**
- No planned source edits.

**Interfaces:**
- Produces verification evidence only; does not call a provider or mutate an operator database.

- [ ] Run the focused metadata tests again from a clean process.
- [ ] Run `python tools/validate.py full` exactly once at the final major checkpoint and confirm zero offline failures/errors.
- [ ] Run `git diff --check`, inspect `git status --short`, and review the complete diff for raw payload storage, credential leakage, accidental legacy initialization, mutable metadata SQL, hidden caps, or Phase 2/3 scope creep.
- [ ] Report the exact commands/results and explicitly state that live canary, unbounded acquisition, price/action refresh, frozen copy, and inventory remain unexecuted operator-gated steps.
