# ADR-LIVE-002 IBKR Observational Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CPython 3.11 standard-library-only, read-only Client Portal Gateway observation boundary with offline-verifiable safety, pacing, capture, and capability reporting.

**Architecture:** Keep all IBKR-specific behavior under `tools/ibkr`; `src/market_platform_foundation` remains unchanged and receives no IBKR dependency. A fail-closed configuration and endpoint allowlist wrap an injected HTTP transport, a shared synchronous pacer owns token-bucket/history/penalty-box state, and all response evidence crosses the boundary only through redacted JSON/JSONL files.

**Tech Stack:** CPython 3.11 standard library (`urllib`, `ssl`, `json`, `threading`, `time`, `pathlib`, `unittest`).

## Global Constraints

- Preserve the existing uncommitted `.env.example`, `docs/providers/IBKR_OBSERVATIONAL.md`, and ADR-LIVE-002 changes byte-for-byte.
- Do not add order submission, modification, cancellation, execution integration, fund movement, or a generic unallowlisted request API.
- Reject every non-loopback gateway URL before transport construction or invocation.
- Ordinary and final validation are offline and must not make live network calls.
- Do not add a vendor SDK or any third-party dependency.
- Do not commit during this work; the worktree already contains user-owned uncommitted changes.

---

### Task 1: Configuration and read-only endpoint boundary

**Files:**
- Create: `tools/ibkr/__init__.py`
- Create: `tools/ibkr/config.py`
- Create: `tools/ibkr/client.py`
- Test: `tests/ibkr/test_config_client.py`

**Interfaces:**
- Produces: `IbkrConfig.from_env(env, root)`, `validate_gateway_url(url)`, `IbkrClient.request_json(method, path, *, params, body)`, `TransportResponse`.
- Consumes: an injected `transport(request, ssl_context, timeout)` callable; the real transport uses `urllib.request` only.

- [ ] Write failing tests proving disabled-by-default behavior, HTTPS loopback and `/v1/api` enforcement, rejection before transport invocation, rejection of order/write paths, and acceptance of documented observational GET plus read-semantic POST paths.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.ibkr.test_config_client -v` and confirm failures are caused by missing `tools.ibkr` modules.
- [ ] Implement immutable config parsing, strict URL validation, the explicit method/path allowlist, injected transport, and sanitized response/error types.
- [ ] Re-run the focused test and `tools/validate.py changed` with `PYTHONPATH=src`; require both to pass.

### Task 2: Global, historical, and 429 pacing

**Files:**
- Create: `tools/ibkr/pacing.py`
- Modify: `tools/ibkr/client.py`
- Test: `tests/ibkr/test_pacing.py`

**Interfaces:**
- Produces: `TokenBucket.acquire()`, `HistoricalLimiter.acquire(query_key)`, `PenaltyBox.enter(...)`, `PenaltyBox.wait_if_active()`, and `RequestPacer.slot(path, query_key)`.
- Consumes: injected monotonic clock and sleep function, plus an append-only journal callback.

- [ ] Write failing fake-clock tests for the 10 request/second token bucket, 15-second identical-history spacing, rolling 50/600-second cap, history single-flight locking, and a 900-second 429 penalty that is journaled before later traffic sleeps.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.ibkr.test_pacing -v` and confirm the expected missing-symbol failures.
- [ ] Implement only the synchronous pacing needed by those tests; make the client enter the penalty box on HTTP 429 and never auto-retry the failed request.
- [ ] Re-run the focused tests and changed validation; require both to pass.

### Task 3: Redacted append-only JSONL capture

**Files:**
- Create: `tools/ibkr/capture.py`
- Modify: `tools/ibkr/client.py`
- Test: `tests/ibkr/test_capture.py`

**Interfaces:**
- Produces: `redact(value)`, `redact_text(text)`, `JsonlJournal.append(record)`, and `ObservationCapture.record(...)`.
- Consumes: request metadata and parsed/raw response payloads from `IbkrClient`.

- [ ] Write failing tests with nested username/password/TOTP/token/cookie/authorization/query-string secrets and assert that every line parses as JSON, contains `CAPTURED_NOT_ADMITTED`, and contains none of the supplied values.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.ibkr.test_capture -v` and verify the missing implementation failure.
- [ ] Implement conservative recursive/text redaction and locked append-only UTF-8 JSONL writes; wire captures and the penalty journal into the client.
- [ ] Re-run the focused tests and changed validation; require both to pass.

### Task 4: Offline-testable capability probe

**Files:**
- Create: `tools/ibkr/probe.py`
- Test: `tests/ibkr/test_probe.py`

**Interfaces:**
- Produces: `CapabilityProbe.run(symbol) -> dict[str, object]`, `write_report(path, report)`, and a gated CLI `main()`.
- Consumes: the restricted `IbkrClient`; probes auth status, contract search, delayed snapshot, history, option-definition, scanner-parameter, and portfolio-account surfaces independently.

- [ ] Write failing fake-client tests proving deterministic capability classification, partial-failure isolation, conid-dependent probe skipping, report redaction, and zero calls when `IMP_IBKR_LIVE` is disabled.
- [ ] Run `.venv\Scripts\python.exe -m unittest tests.ibkr.test_probe -v` and verify the expected missing implementation failure.
- [ ] Implement the bounded sequential probe and fail-closed CLI. Do not invoke the CLI with live enabled during validation.
- [ ] Re-run the focused tests and changed validation; require both to pass.

### Task 5: Validation inventory and final safety audit

**Files:**
- Modify: `tools/validation_manifest.json`
- Test: `tests/ibkr/test_safety.py`

**Interfaces:**
- Produces: offline `ibkr` suite owning `tools/ibkr/**` and `tests/ibkr/test_*.py`.

- [ ] Write a failing AST/text safety test that rejects vendor-SDK imports, socket/order/execution symbols, non-stdlib imports, and any order-like allowlist entry.
- [ ] Add the offline suite to the manifest and run changed validation.
- [ ] Run the complete IBKR unit suite, then `.venv\Scripts\python.exe tools\validate.py full` with `PYTHONPATH=src`; do not run a live selector.
- [ ] Compare `git diff -- .env.example docs/providers/IBKR_OBSERVATIONAL.md docs/superpowers/decisions/2026-08-23-adr-live-002-ibkr-gateway-observational.json` against the initial state and confirm user-owned documentation was not modified.
