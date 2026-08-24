# Governed Ticker-Metadata Enrichment Design

**Status:** Approved direction, pending principal review of this specification

**Date:** 2026-08-24

**Decision owner:** Principal

**Implementation state:** Not started

## 1. Decision

The equity collector will gain one narrowly bounded metadata-acquisition command before the Phase 2 candidate build. It will call only `yfinance.Ticker.get_info()`, retain only an explicit allowlist of ticker identity and classification fields, and write append-only attempts and observations into the operator-selected existing SQLite database.

The command will not invoke the legacy fundamentals scraper, write financial statements, overwrite the current `tickers` projection, or grant research authority. Its output is acquisition evidence for later Phase 2 preservation and Phase 3 adjudication, not canonical instrument truth.

The implementation milestone ends after metadata collection, conservative price/corporate-action refresh through the approved cutoff, source freeze, and inventory. It does not implement the Phase 2 DuckDB builder and does not begin Phase 3.

## 2. Audit evidence and constraints

The read-only audit on 2026-08-24 established the following baseline for `C:\Users\adame\Desktop\stock-data\database\market_data.db`:

- SHA-256 `8670c385ad4b5d8c9917f0633bca74d98f50095065ff507792673536e6f9b8c4` over a `2,484,719,616`-byte SQLite file;
- `PRAGMA quick_check` returned `ok`, journal mode was WAL, the WAL sidecar was empty, and the SHM sidecar existed;
- `13,052` ticker rows, of which sector was absent for `12,048`, industry for `12,048`, country for `11,906`, and market cap for `12,144`;
- `18,044,890` daily-price rows for `6,570` instruments through `2026-07-27`, plus `206,243` dividends and `4,802` splits;
- no `acquisition_attempts` table and empty fundamentals, statement, and supplemental tables.

The current integrated CLI has no mutating `--database` boundary. Its configured default points beneath `pipelines/stock_data`, where no production database exists; using that default would create a new ignored database instead of enriching the audited source. The existing fundamentals scraper is also unsuitable: one ticker can trigger multiple provider methods, it writes statements and fundamentals, and it overwrites fields on `tickers`.

These facts require an explicit database target, a new provider adapter, and storage isolated from the legacy projection.

## 3. Scope and non-goals

This milestone includes:

1. an explicit existing-database preflight and fail-closed connection path;
2. schema and append-only enforcement for ticker-metadata attempts and observations;
3. one `get_info()` adapter with an allowlisted projection and strict validation;
4. bounded retries, global rate limiting, concurrency limits, circuit breakers, resume semantics, and stable outcome classification;
5. sanitized run reporting and coverage summaries;
6. offline unit, integration, boundary, and CLI tests;
7. a live canary followed by an operator-approved unbounded run;
8. conservative daily-price and corporate-action refresh through the approved cutoff;
9. a new frozen source copy and inventory after all acquisition is complete.

This milestone excludes:

- legacy fundamentals, financial statements, analyst data, recommendations, earnings estimates, options, holders, news, or supplemental scraping;
- storage of the full `get_info()` payload or unknown provider fields;
- updates to any existing `tickers` value, including company name, exchange, sector, industry, country, market cap, ETF flag, active state, or timestamps;
- canonical security type, currency, country, MIC, listing history, delisting history, symbol-effective history, or universe membership;
- candidate DuckDB construction, quality disposition, admission, research APIs, formulas, models, backtests, or Phase 3 work.

## 4. Command and database boundary

The new command is:

```text
python -m src.pipeline refresh-ticker-metadata \
  --database <existing-market_data.db> \
  [existing ticker-filter options] \
  [--limit N] \
  [--retry-errored]
```

`--database` is mandatory for this command. The path is resolved before any SQLite connection and must:

- exist as a regular file;
- have a valid SQLite header;
- open with SQLite `mode=rw`, never a create-capable mode;
- pass `PRAGMA quick_check`;
- contain the expected `tickers` primary key, symbol column, and required registry schema;
- have an exact compatible metadata schema if either metadata table already exists.

The command prints the resolved path and a bounded preflight summary before provider work. A missing, empty, malformed, read-only, incompatible, or newly creatable target fails before network access. There is no fallback to `config.DATABASE_PATH`.

Before selection, the process acquires an exclusive OS-level metadata-refresh lock keyed to the resolved database path. A second metadata-refresh process for the same database fails before network access. The lock contains no credentials or provider data, is released by the operating system on process exit, and is not treated as database evidence. This preserves the process-wide rate limit and prevents two invocations from selecting and calling the same ticker concurrently.

The default selection is every row in `tickers`, including rows whose current `active` projection is false. Existing filter options operate on the pre-run `tickers` projection and are recorded in the run report. Selection is ordered by raw ticker ID before `--limit` is applied, making canaries and resumes stable for an unchanged registry.

## 5. Provider boundary and allowlisted projection

The adapter constructs `yfinance.Ticker(requested_symbol)` and invokes only `get_info()` once per call ordinal. It must not access `.info` as a separate operation and must not invoke any history, action, statement, analyst, holder, news, options, or calendar method.

The only retained values are:

| Logical field | Accepted provider key | Accepted value |
| --- | --- | --- |
| provider symbol | `symbol` | non-empty string matching the requested symbol under the versioned symbol-normalization rule |
| short name | `shortName` | non-empty bounded string or null |
| long name | `longName` | non-empty bounded string or null |
| exchange code | `exchange` | non-empty bounded string or null |
| exchange name | `fullExchangeName` | non-empty bounded string or null |
| quote type | `quoteType` | non-empty bounded string or null |
| currency | `currency` | non-empty bounded string or null |
| sector | `sector` | non-empty bounded string or null |
| industry | `industry` | non-empty bounded string or null |
| country | `country` | non-empty bounded string or null |
| market cap | `marketCap` | integer greater than or equal to zero, excluding booleans, or null |

Strings are trimmed, Unicode is preserved, control characters are rejected, and implementation-defined length bounds are part of the versioned request contract. Unknown keys are ignored and never stored. The adapter does not retain the response mapping, cookies, URLs, descriptions, officers, addresses, phone numbers, or provider diagnostics.

The request-contract document is canonical JSON and is hashed with SHA-256. It binds the adapter schema version, provider and method, allowlisted keys, validators, symbol-normalization rule, identity-envelope rule, and outcome-classification version. Each attempt and observation records both the contract version and hash.

## 6. Outcome contract

The command reuses the stable acquisition outcome vocabulary:

- `complete`: the response is a mapping, every observed allowlisted value is valid, the provider symbol is present and matches, quote type is present, at least one name is present, and at least one exchange form is present;
- `partial_response`: the response contains at least one valid useful allowlisted value but does not satisfy the complete identity envelope;
- `no_data`: the response is an empty mapping or contains none of the useful allowlisted values;
- `invalid_symbol`: the provider explicitly reports an invalid, delisted, or unknown symbol through a recognized exception/message contract;
- `schema_drift`: the top-level response is not a mapping, an observed allowlisted field has an invalid type/value, or a present provider symbol does not match the requested symbol;
- `throttled`: a recognized rate-limit response or exception occurs;
- `transient`: a timeout, connection interruption, temporary provider failure, or other recognized retryable transport failure occurs.

Unknown exceptions fail closed as `transient` with a sanitized exception class and stable reason code; they do not store arbitrary exception representations. Complete classification does not require optional sector, industry, country, currency, or market cap, so their absence remains visible in coverage rather than being mislabeled as acquisition failure.

## 7. Append-only storage contract

### 7.1 `ticker_metadata_attempts`

One row represents one provider interaction that returned or surfaced an exception to the adapter:

- monotonically assigned `attempt_id` primary key;
- opaque invocation `run_id`, generated once per command invocation;
- `raw_ticker_id` foreign key and `requested_symbol` captured from the selected registry row;
- provider identifier and method;
- canonical request-contract JSON, version, and SHA-256;
- retry ordinal, UTC start time, and UTC completion time;
- sorted canonical JSON lists of requested allowlisted fields and fields observed in the response;
- outcome and stable reason code;
- nullable sanitized detail;
- collector Git revision and dirty-worktree boolean;
- Python version, provider-library name, and provider-library version.

The table contains no raw response, response fragment, URL, cookie, header, token, traceback, or secret. A hard process termination between a provider interaction and its SQLite commit can leave that interaction unrecorded; the design makes no false claim of crash-proof external call accounting. The next invocation safely retries because no terminal attempt exists.

### 7.2 `ticker_metadata_observations`

Complete and partial outcomes produce exactly one linked observation containing:

- monotonically assigned `observation_id` primary key and unique `attempt_id` foreign key;
- invocation `run_id` copied from the linked attempt;
- `raw_ticker_id`, requested symbol, provider, method, request-contract version and hash;
- canonical request-contract JSON;
- provider observation time, defined as the successful call completion time;
- one nullable typed column for each allowlisted field;
- a sorted canonical JSON list of present projected fields;
- collector revision and dirty-worktree boolean, Python version, and provider-library name/version.

Failed, throttled, transient, invalid-symbol, no-data, and schema-drift outcomes do not produce observations.

### 7.3 Immutability and transaction rules

Both tables have database triggers that reject every `UPDATE` and `DELETE`. Schema initialization is idempotent but validates the exact table, index, foreign-key, and trigger definitions; a conflicting pre-existing object fails closed.

After each completed provider interaction, the attempt insert and any linked observation insert occur in one short SQLite transaction. A complete or partial attempt cannot commit without its observation, and an observation cannot exist without its attempt. Existing acquisition, ticker, price, action, fundamental, statement, supplemental, and progress rows are never updated by this command.

Provider calls and retry waits occur outside SQLite transactions. The four provider workers submit completed classified results to one serialized writer boundary, so the process uses one write transaction at a time and does not depend on concurrent writes through a shared SQLite connection.

Indexes support `(raw_ticker_id, request_contract_sha256, attempt_id)`, outcome summaries, and the observation-to-attempt relationship. Operational IDs and insertion order are provenance, not canonical instrument identity.

## 8. Resume, retry, rate, and circuit behavior

The defaults are fixed and visible in the run report:

- four worker threads;
- one process-wide limiter allowing at most two provider-call starts per second, with burst capacity one;
- at most three call ordinals per ticker in one invocation;
- fixed exponential retry delays of two and four seconds after retryable outcomes;
- no retry jitter and no hidden provider-call concurrency.

The limiter governs adapter call starts, not the provider library's undocumented internal HTTP request count.

Within an invocation, only `transient` and `throttled` outcomes retry automatically. `complete`, `partial_response`, `no_data`, `invalid_symbol`, and `schema_drift` are terminal for that ticker in that invocation.

For the same request-contract hash, the normal resume policy is:

- skip a ticker whose latest terminal outcome is `complete`, `partial_response`, `no_data`, `invalid_symbol`, or `schema_drift`;
- select a ticker with no attempt;
- select a ticker whose latest outcome is `transient` or `throttled`, starting a new invocation with call ordinal one.

`--retry-errored` additionally selects tickers whose latest terminal outcome is `partial_response`, `no_data`, `invalid_symbol`, or `schema_drift`; it does not re-fetch `complete` outcomes. A changed request-contract hash creates a new acquisition contract and therefore a new selectable population without deleting old evidence.

The run stops scheduling new tickers after either circuit condition:

1. three consecutive terminal `schema_drift` ticker outcomes; or
2. five consecutive tickers whose final outcome after bounded retries is `throttled`.

Any intervening different terminal outcome resets the corresponding consecutive counter. Already-running calls may finish and commit. The command then exits nonzero with a stable circuit reason, preserving all committed evidence for resume.

## 9. Security, diagnostics, and reporting

All details pass through conservative redaction before persistence or display. The sanitizer removes authorization material, cookies, query strings, API keys, tokens, passwords, filesystem user profiles, and control characters; it then applies a strict maximum length. Persisted diagnostics use stable reason codes plus minimal bounded context.

The command emits a bounded terminal report with:

- database path, contract hash, collector revision, provider version, selected ticker count, and effective runtime limits;
- calls, retries, skipped tickers, committed attempts, and committed observations;
- outcome counts and circuit status;
- field-presence counts and missing counts for every allowlisted field;
- elapsed time and earliest/latest observation timestamps.

The report contains no row-level provider values. A machine-readable report may be written only to an explicitly selected ignored/evidence path; adding a persistent report option is an implementation-plan decision, not required for the live run.

## 10. Testing and validation

Implementation follows test-driven development. Offline tests use fake provider adapters and temporary SQLite databases; no unit or integration test accesses the network or the operator database.

Required tests cover:

- mandatory explicit database path, `mode=rw`, missing/empty/wrong-schema refusal, `quick_check`, exclusive same-database invocation locking, and no accidental database creation;
- exact schema initialization, incompatible-schema refusal, foreign keys, indexes, immutability triggers, and transaction rollback;
- proof that every pre-existing table remains byte-semantically unchanged in fixture databases;
- the allowlist, ignored unknown keys, string and market-cap validators, identity envelope, symbol mismatch, and all outcome mappings;
- absence of raw payloads and secrets from persisted/displayed diagnostics;
- one adapter method call per ordinal and prohibition of legacy fundamentals methods;
- retry delays through an injected clock, global limiter behavior through a fake monotonic clock, four-worker bound, and both circuits;
- stable selection order, `--limit`, filters, normal resume, `--retry-errored`, request-contract change, and interrupted-run resume;
- attempt/observation cardinality and atomicity;
- CLI summaries and stable nonzero exit behavior;
- repository dependency-boundary preservation.

After edits, validation follows `AGENTS.md`: collector tests with an isolated temporary base, platform `changed`, the applicable offline domain checkpoint, boundary tests, and one final full offline validation at the major checkpoint. Live validation runs only for the changed provider boundary and only after offline gates pass.

## 11. Live execution and data-completion sequence

Live work is ordered and gated:

1. Record the target database size, timestamps, sidecars, `quick_check`, schema, table counts, and SHA-256 before mutation.
2. Run a representative canary of 10–25 symbols covering common equities, ETFs, sparse metadata, invalid/no-data, and symbol-format cases.
3. Verify attempt/observation cardinality, outcome classifications, field coverage, sanitization, resume behavior, and that `tickers`, fundamentals, statements, supplemental tables, prices, actions, and legacy progress rows are unchanged.
4. Review the canary. Only then run the full registry without a hidden ticker cap from a clean committed collector revision.
5. Re-run the command normally to prove terminal outcomes resume without duplicate provider calls; use `--retry-errored` only as an explicit operator action.
6. Refresh daily prices, dividends, and splits through cutoff `2026-08-21`, unless audit evidence establishes a later fully completed market session before the refresh begins.
7. Close acquisition writers, create a consistent frozen SQLite copy using SQLite's supported backup/close procedure, and inventory the frozen copy under inventory format 2.0.
8. Recompute table counts, date coverage, metadata outcome/field coverage, source identity, schema hash, sidecar disposition, and file hash from the frozen copy.
9. Stop. The Phase 2 builder and all Phase 3 work remain separate reviewed milestones.

The pre-mutation hash is historical baseline evidence; a changed post-acquisition hash is expected. Counts and hashes for protected tables are compared around the metadata canary specifically, while price/action changes are permitted only in their later explicit refresh step.

## 12. Phase 2 handoff

The frozen source hands Phase 2 two distinct evidence classes:

- `ticker_metadata_observations` is consumed into a noncanonical candidate observation table;
- `ticker_metadata_attempts` and generic acquisition attempts are operational provenance summarized in the manifest but excluded from candidate row data.

Phase 2 preserves provider-reported values, request contract, observation time, and source linkage. It leaves canonical exchange, country, currency, security type, listing bounds, symbol-effective bounds, `available_at`, admission status, and research authority unresolved. Phase 3 alone may adjudicate those facts and grant or deny research use.

## 13. Acceptance and review gate

This design is accepted for implementation planning only when the principal confirms:

1. the command cannot create or silently select a production database;
2. it calls only `get_info()` and stores only the allowlist;
3. evidence is append-only and the legacy ticker projection is unchanged;
4. outcome, retry, circuit, resume, and redaction behavior are unambiguous;
5. the live canary precedes unbounded collection;
6. the milestone stops after acquisition, freeze, and inventory;
7. the Phase 2 amendment preserves metadata as noncanonical, unavailable, and research-inert.

Principal approval of this written specification authorizes a task-level implementation plan. It does not authorize implementation, a live provider call, mutation of the source database, the Phase 2 builder, or Phase 3.
