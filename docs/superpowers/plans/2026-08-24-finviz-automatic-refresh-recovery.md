# Finviz Automatic Refresh and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the mixed screener's Finviz universe updating automatically across transient rate limits, changed stored API keys, and recoverable Finviz login sessions.

**Architecture:** Preserve the standard-library Finviz export boundary and its existing 120-second mixed refresh. Strengthen the request manager with classified-response caching and bounded exponential 429 backoff, make credential recovery reload changed local credentials before login, update the login flow to Finviz's current endpoints, and let tool launchers optionally inject a Chrome-impersonating `curl_cffi` cookie session without importing third-party code into `src/`.

**Tech Stack:** CPython 3.11 standard library in `src/`, `unittest`, optional tool-layer `curl_cffi`, existing secure Finviz credential store, existing UI/API launcher.

## Global Constraints

- Do not start, stop, restart, probe, or otherwise interact with the running demo, its ports, or its processes.
- Do not install packages into the shared repository virtual environment during this implementation.
- `src/market_platform_foundation` remains CPython 3.11 standard-library-only and `phase0-dependency-lock.json` remains unchanged.
- Finviz exports remain read-only and execution authority remains `NONE`.
- The existing mixed refresh remains 120 seconds while visible and preserves its latest valid capture during failures.
- Never log, return, or persist outside the secure store any API key, password, cookie, credential-bearing URL, or login form body.
- Login recovery never automates MFA or CAPTCHA and must expose `AUTH_OPERATOR_ACTION_REQUIRED` for either challenge.
- Offline tests and validators must not contact Finviz, Moomoo, IBKR, or any other live provider.

## File map

- Modify `src/market_platform_foundation/finviz/http_client.py`: preserve actual redirect destinations on session responses.
- Modify `src/market_platform_foundation/finviz/login_recovery.py`: current Finviz login endpoints, primed cookie flow, injectable registered session factory, validation, and cleanup.
- Modify `src/market_platform_foundation/finviz/credential_manager.py`: reload and validate a changed non-environment credential before login recovery.
- Modify `src/market_platform_foundation/finviz/request_manager.py`: response headers, bounded exponential 429 backoff, and cache only authenticated CSV success.
- Create `tools/finviz/login_transport.py`: optional `curl_cffi` Chrome-impersonating session registration outside the governed foundation.
- Modify `tools/ui1/run_ui_api.py`: register the best available login recovery transport during launcher startup.
- Modify `tools/finviz/auth.py`: use the same transport selection for operator validation and repair.
- Modify `tests/finviz/test_auth_lifecycle.py`: offline redirect, login, credential reload, backoff, cache, and adapter tests.
- Modify `docs/providers/FINVIZ_ELITE.md`: automatic cadence, recovery order, optional transport, and setup behavior.

---

### Task 1: Current Finviz login flow and redirect-safe session boundary

**Files:**
- Modify: `tests/finviz/test_auth_lifecycle.py`
- Modify: `src/market_platform_foundation/finviz/http_client.py`
- Modify: `src/market_platform_foundation/finviz/login_recovery.py`

**Interfaces:**
- Consumes: a session implementing `get(url, timeout=..., params=...)`, `post(url, data=..., timeout=..., allow_redirects=True)`, and optional `close()`.
- Produces: `set_login_session_factory(factory)`, `reset_login_session_factory()`, and `recover_token_via_login(...) -> LoginRecoveryResult` using the current Finviz form endpoints.

- [ ] **Step 1: Write failing redirect and login-flow tests**

Add an `UrllibSession._finalize` test whose fake response has `geturl()` returning `https://elite.finviz.com/api_explanation`; assert `HttpResponse.url` equals that final URL. Add a successful login recovery test with three ordered GET responses (login page, API explanation containing `?auth=<uuid>`, valid CSV export) and a POST response on an allowed Finviz host. Assert the first request is `GET https://finviz.com/login-email?remember=true`, the POST is `https://finviz.com/login_submit` with exactly `email`, `password`, and `remember`, and the session closes.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe -m unittest tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_session_records_final_redirect_url tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_current_login_flow_primes_session_and_validates_export -v`

Expected: FAIL because `_finalize` records the requested URL and recovery posts to `login_submit.ashx` without priming the login page.

- [ ] **Step 3: Implement the current, injectable login flow**

Set:

```python
LOGIN_PAGE_URL = "https://finviz.com/login-email?remember=true"
LOGIN_SUBMIT_URL = "https://finviz.com/login_submit"
```

Make `_finalize` prefer `response.geturl()` over the requested URL. Add a locked module-level optional session factory with setters/resetter. In `recover_token_via_login`, create the chosen session, GET and allowlist-check `LOGIN_PAGE_URL`, POST `{"email": username, "password": password, "remember": "on"}`, allowlist-check the returned URL, then fetch/extract/validate the Elite key as before. Treat manual-auth markers at every HTML step as `MANUAL_AUTH_REQUIRED`; do not require the login POST itself to land on `elite.finviz.com` because the API explanation/export validation proves authentication. Close the session in `finally`.

- [ ] **Step 4: Run focused login tests and changed validation**

Run the Step 2 command, then `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe tools\validate.py changed`.

Expected: both focused tests and changed validation pass offline.

- [ ] **Step 5: Commit the login boundary**

```powershell
git add tests/finviz/test_auth_lifecycle.py src/market_platform_foundation/finviz/http_client.py src/market_platform_foundation/finviz/login_recovery.py
git commit -m "fix(finviz): update automatic login recovery"
```

### Task 2: Changed-token reload before login recovery

**Files:**
- Modify: `tests/finviz/test_auth_lifecycle.py`
- Modify: `src/market_platform_foundation/finviz/credential_manager.py`

**Interfaces:**
- Consumes: existing secure token and provider-env readers plus `validate_token(token) -> bool`.
- Produces: `FinvizCredentialManager.attempt_recovery()` that first adopts a changed non-environment token, then performs the existing bounded login recovery.

- [ ] **Step 1: Write failing reload tests**

Add one test with active token `old`, source `PRIVATE_FILE`, `read_secure_token()` returning a different UUID, and `validate_token()` accepting it. Assert recovery returns true, does not call `recover_token_via_login`, adopts the new token/source, and reports `HEALTHY`. Add a second test where the stored token is unchanged and assert the login recovery path still runs. Add a test that `_raw_get` accepts the `headers=` argument used by `validate_token`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe -m unittest tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_recovery_adopts_changed_secure_token_before_login tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_unchanged_secure_token_falls_through_to_login tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_request_raw_get_accepts_validation_headers -v`

Expected: FAIL because `attempt_recovery` currently requires login credentials immediately and `_raw_get` rejects `headers=`.

- [ ] **Step 3: Implement safe reload and adoption**

Extract a side-effect-free configured-token reader returning `(token, FinvizCredentialSource)` in the existing environment/secure/provider-file precedence, and use it from `load()`. After entering the recovery single-flight/cooldown window, re-read that source. For a different token from `PRIVATE_FILE` or `PROVIDER_ENV_FILE`, validate first, then atomically update `_token`, `_source`, `_state`, `_last_auth_error`, and credential-generation metadata. Do not rewrite the same token or attempt automatic replacement of an environment-provided token. If reload fails, continue to the current bounded login recovery. Update `_raw_get` to accept optional headers and merge them with the manager's sanitized request headers.

- [ ] **Step 4: Run focused auth tests and changed validation**

Run the Step 2 command, the full `tests.finviz.test_auth_lifecycle` module, and `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe tools\validate.py changed`.

Expected: all commands pass offline.

- [ ] **Step 5: Commit changed-token recovery**

```powershell
git add tests/finviz/test_auth_lifecycle.py src/market_platform_foundation/finviz/credential_manager.py src/market_platform_foundation/finviz/request_manager.py
git commit -m "feat(finviz): reload rotated credentials automatically"
```

### Task 3: Bounded exponential 429 recovery and safe caching

**Files:**
- Modify: `tests/finviz/test_auth_lifecycle.py`
- Modify: `src/market_platform_foundation/finviz/request_manager.py`

**Interfaces:**
- Consumes: response status/body/content-type/headers and the request manager's minimum interval.
- Produces: `FinvizRequestManager(..., max_429_retries=2, sleeper=time.sleep)` with production waits of 5 then 10 seconds when no larger valid `Retry-After` is supplied.

- [ ] **Step 1: Write failing backoff and cache tests**

Inject a sleeper that records delays and return responses `[429, 429, 200 valid CSV]`; assert three calls, two delays `[5.0, 10.0]` at the default interval, and final success. Return `429` with `Retry-After: 12` and assert the first delay is `12.0`. Return `200 text/html` login content twice with a cache TTL and assert two raw calls, proving authentication failures are not cached.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe -m unittest tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_429_uses_bounded_exponential_backoff tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_429_honors_larger_retry_after tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_login_html_is_never_cached -v`

Expected: FAIL because the manager currently retries 429 once with a fixed delay and caches every HTTP 200 response.

- [ ] **Step 3: Implement classified-response retry and caching**

Return normalized response headers from `_execute_request`. Parse a finite non-negative numeric `Retry-After`; for retry index `0..max_429_retries-1`, sleep `max(min_interval_s * 2**index, retry_after)` and retry. Mark the manager rate-limited on every 429 and stop after the bound. Cache only when the final classification is `AUTH_OK`, status is 200, and the body contains the expected CSV header; never cache 429, HTML, auth failure, or provider error responses.

- [ ] **Step 4: Run request tests and changed validation**

Run the Step 2 command, `tests.finviz.test_auth_lifecycle`, `tests.finviz.test_finviz_provider`, and `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe tools\validate.py changed`.

Expected: all commands pass offline.

- [ ] **Step 5: Commit retry and cache behavior**

```powershell
git add tests/finviz/test_auth_lifecycle.py src/market_platform_foundation/finviz/request_manager.py
git commit -m "fix(finviz): back off and preserve valid cache only"
```

### Task 4: Optional curl impersonation registration and final documentation

**Files:**
- Create: `tools/finviz/login_transport.py`
- Modify: `tools/ui1/run_ui_api.py`
- Modify: `tools/finviz/auth.py`
- Modify: `tests/finviz/test_auth_lifecycle.py`
- Modify: `docs/providers/FINVIZ_ELITE.md`
- Modify: `docs/superpowers/plans/2026-08-24-finviz-automatic-refresh-recovery.md`

**Interfaces:**
- Consumes: `IMP_FINVIZ_LOGIN_TRANSPORT=auto|urllib|curl_cffi` (default `auto`).
- Produces: `configure_login_transport(mode=None) -> "CURL_CFFI" | "URLLIB"`; `auto` registers Chrome impersonation when importable and otherwise retains urllib, while explicit unavailable `curl_cffi` raises a sanitized configuration error.

- [ ] **Step 1: Write failing adapter-selection tests**

Test `urllib` mode without importing `curl_cffi`. Inject a fake curl requests module whose `Session` records `impersonate="chrome"`, register `curl_cffi` mode, invoke the registered factory, and assert its responses expose `status_code`, `text`, `headers`, and final `url`. Test `auto` with a missing dependency returns `URLLIB` without error. Assert the launcher calls transport configuration only after local environment loading.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH='src'; ..\..\.venv\Scripts\python.exe -m unittest tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_login_transport_urllib_mode tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_login_transport_registers_chrome_impersonation tests.finviz.test_auth_lifecycle.FinvizAuthLifecycleTests.test_login_transport_auto_falls_back_without_dependency -v`

Expected: FAIL because `tools.finviz.login_transport` does not exist.

- [ ] **Step 3: Implement tool-layer transport selection**

Keep every `curl_cffi` import inside `tools/finviz/login_transport.py`. Wrap `curl_cffi.requests.Session(impersonate="chrome")` behind the login session protocol and register its factory through `set_login_session_factory`. In `auto`, catch only dependency import failure and retain urllib; in explicit `curl_cffi`, raise `RuntimeError("curl_cffi login transport is unavailable")` without environment or credential values. Call configuration from `tools/ui1/run_ui_api.main()` and `tools/finviz/auth.py` after local configuration is loaded and before validate/repair actions.

- [ ] **Step 4: Document and run final offline verification**

Document the 120-second re-fetch, five-second request floor, 5/10-second 429 backoff, changed-token reload, current login flow, `IMP_FINVIZ_LOGIN_TRANSPORT`, and operator-action states. Mark all plan checkboxes complete. Run:

```powershell
$env:PYTHONPATH='src'
..\..\.venv\Scripts\python.exe -m unittest tests.finviz.test_auth_lifecycle tests.finviz.test_finviz_provider -v
..\..\.venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery -v
..\..\.venv\Scripts\python.exe tools\validate.py full
Set-Location ui
npm run test
npm run build
```

Expected: every command exits 0. Do not run any live provider validation while the user's demo is running.

- [ ] **Step 5: Review and commit the completed recovery slice**

Run `git diff --check` and confirm only intended feature files plus the two pre-existing audit JSON modifications are present. Stage exact feature paths only, then commit:

```powershell
git add tools/finviz/login_transport.py tools/ui1/run_ui_api.py tools/finviz/auth.py tests/finviz/test_auth_lifecycle.py docs/providers/FINVIZ_ELITE.md docs/superpowers/plans/2026-08-24-finviz-automatic-refresh-recovery.md
git commit -m "feat(finviz): enable automatic live discovery recovery"
```

Do not stage `evidence/ui1/assistant-audit/conversations.json` or `evidence/ui1/assistant-audit/messages.json`.
