# IBKR Desktop Gateway Observational Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional read-only TWS socket transport so the existing IBKR capability probe and capture tools can use the authenticated desktop Gateway on `127.0.0.1:4001`.

**Architecture:** Keep Client Portal REST as the default transport and add a separate `ib_insync`-backed adapter under `tools/ibkr`. Both transports satisfy the probe's restricted capability interface, while all TWS payloads cross the existing redaction and `CAPTURED_NOT_ADMITTED` evidence boundary. The TWS dependency is optional and never imported when the Client Portal transport is selected.

**Tech Stack:** CPython 3.11, `unittest`, standard-library configuration/capture code, optional `ib_insync` for the desktop Gateway socket, and the existing validation manifest.

## Global Constraints

- `IMP_IBKR_LIVE=1` is required for either transport.
- TWS host must be loopback-only and default to `127.0.0.1`.
- TWS default port is `4001`; port `4002` is accepted only when explicitly configured.
- The adapter exposes observations only: connection status, contract lookup, market snapshot, history, option definitions, scanner availability, and portfolio-read availability.
- No order submission, modification, cancellation, funding, execution authority, or generic unallowlisted request API may be added.
- Client Portal REST remains backward-compatible and remains the default.
- Missing optional dependencies fail closed with a sanitized setup error.
- Offline tests make no IBKR network calls.
- Live verification is explicit, bounded, local-only, and writes sanitized evidence.
- Do not commit changes during this work; the repository already contains user-owned uncommitted changes.

---

## File map

- Modify `tools/ibkr/config.py` to parse and validate the selected transport and TWS connection settings.
- Create `tools/ibkr/tws_client.py` as the narrow `ib_insync` wrapper. It will not expose the underlying broker object.
- Modify `tools/ibkr/probe.py` to construct the selected transport and include transport identity in reports.
- Modify `tools/ibkr/capture.py` so captures can identify either `IBKR_CLIENT_PORTAL_GATEWAY` or `IBKR_TWS_GATEWAY` while preserving recursive redaction.
- Modify `tools/ibkr/__init__.py` only if the public package exports need to include the transport factory.
- Modify `.env.example` and `docs/providers/IBKR_OBSERVATIONAL.md` with the TWS settings and installation/run commands.
- Add `tests/ibkr/test_tws_client.py` for fake-broker behavior and failure isolation.
- Modify `tests/ibkr/test_config_client.py`, `tests/ibkr/test_probe.py`, `tests/ibkr/test_capture.py`, and `tests/ibkr/test_safety.py` for transport selection, report identity, redaction, and safety invariants.
- Modify `tools/validation_manifest.json` only if new source/test paths are not already covered by the existing `ibkr` suite.

### Task 1: Transport configuration and selection

**Files:**
- Modify: `tools/ibkr/config.py`
- Modify: `tools/ibkr/probe.py`
- Test: `tests/ibkr/test_config_client.py`
- Test: `tests/ibkr/test_probe.py`

**Interfaces:**
- `IbkrConfig.transport: str` is either `client_portal` or `tws`.
- `IbkrConfig.tws_host: str`, `tws_port: int`, and `tws_client_id: int` hold validated local socket settings.
- `IbkrConfig.from_env()` reads `IMP_IBKR_TRANSPORT`, `IMP_IBKR_TWS_HOST`, `IMP_IBKR_TWS_PORT`, and `IMP_IBKR_TWS_CLIENT_ID`.
- `probe.main(..., client_factory=...)` remains injectable for offline tests and chooses the default REST factory when the transport is `client_portal`.

- [ ] **Step 1: Write failing configuration tests**

Add tests asserting:

```python
def test_tws_configuration_defaults_to_loopback_port_4001(self):
    config = IbkrConfig.from_env({"IMP_IBKR_TRANSPORT": "tws"}, root=Path("."))
    self.assertEqual(config.transport, "tws")
    self.assertEqual(config.tws_host, "127.0.0.1")
    self.assertEqual(config.tws_port, 4001)
    self.assertGreater(config.tws_client_id, 0)
```

Also add tests that a non-loopback TWS host, port outside `4001/4002`, zero client ID, and unknown transport raise `ConfigError`.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_config_client tests.ibkr.test_probe -v
```

Expected result: the new tests fail because `IbkrConfig` does not yet expose TWS settings.

- [ ] **Step 3: Implement minimal transport configuration**

Add strict parsing that:

```python
transport = env.get("IMP_IBKR_TRANSPORT", "client_portal").strip().lower()
if transport not in {"client_portal", "tws"}:
    raise ConfigError("IMP_IBKR_TRANSPORT must be client_portal or tws")
```

Validate the host with the existing loopback policy, accept only ports `4001`
and `4002`, and require a positive integer client ID. Leave all existing Client
Portal URL and pacing validation unchanged.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run the same unittest command. Expected result: all configuration and existing
probe tests pass with zero failures.

### Task 2: Read-only TWS adapter

**Files:**
- Create: `tools/ibkr/tws_client.py`
- Test: `tests/ibkr/test_tws_client.py`
- Modify: `tools/ibkr/capture.py`

**Interfaces:**
- `TwsDependencyError(RuntimeError)` identifies an unavailable optional SDK.
- `TwsIbkrClient(config: IbkrConfig, broker_factory: Callable | None = None)` creates a bounded broker session through an injected factory.
- `TwsIbkrClient.request_json(method, path, *, params=None, body=None) -> object` accepts only the same seven observation paths already consumed by `CapabilityProbe`.
- `TwsIbkrClient.close() -> None` disconnects the socket safely and is idempotent.
- `ObservationCapture.record(..., provider: str = "IBKR_CLIENT_PORTAL_GATEWAY")` retains the current default and allows TWS capture identity.

- [ ] **Step 1: Write failing fake-broker tests**

Create a fake broker with `connect`, `disconnect`, `reqMatchingSymbols`,
`reqMktData`, `reqHistoricalData`, `reqSecDefOptParams`,
`reqScannerParameters`, and portfolio-read methods. Test that:

```python
def test_contract_search_uses_read_only_matching_symbols_request(self):
    client = TwsIbkrClient(config, broker_factory=lambda: fake_broker)
    result = client.request_json(
        "GET",
        "/iserver/secdef/search",
        params={"symbol": "AAPL"},
    )
    self.assertEqual(result[0]["symbol"], "AAPL")
    self.assertEqual(fake_broker.order_calls, [])
```

Add tests for snapshot preflight behavior, historical bars, option definitions,
scanner parameters, portfolio-read shape, unsupported method/path rejection,
missing `ib_insync`, and disconnect cleanup. Every fake broker must record
order-like calls and assert that the list remains empty.

- [ ] **Step 2: Run the adapter tests and confirm the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_tws_client -v
```

Expected result: import or symbol failures because `tools.ibkr.tws_client` does
not yet exist.

- [ ] **Step 3: Implement the narrow adapter**

Import `ib_insync` lazily inside the default broker factory. Construct it with
the validated host, port, client ID, and read-only connection option. Map each
allowlisted path to a fixed wrapper method; reject every other path before any
broker call. Normalize only the fields required by the existing capability
probe, and represent unavailable/empty broker results as ordinary observed
payloads rather than fabricated values.

Use the configured timeout for connection and bounded waits. Do not retain or
serialize the underlying broker object. Ensure `close()` runs from the probe's
`finally` block.

- [ ] **Step 4: Extend capture identity and run adapter tests**

Pass `provider="IBKR_TWS_GATEWAY"` for TWS observations. Keep the existing
redaction of account IDs, usernames, cookies, tokens, and authorization
headers. Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_tws_client tests.ibkr.test_capture -v
```

Expected result: all adapter and capture tests pass with zero failures.

### Task 3: Probe factory and report integration

**Files:**
- Modify: `tools/ibkr/probe.py`
- Modify: `tests/ibkr/test_probe.py`
- Modify: `tools/ibkr/__init__.py` if required by imports

**Interfaces:**
- `build_client(config: IbkrConfig) -> object` selects `TwsIbkrClient` only for `config.transport == "tws"` and otherwise returns `IbkrClient`.
- `CapabilityProbe.run()` adds `transport` and `provider` to the top-level report without including raw broker payloads.
- The CLI still returns `2` and makes no client/network call when `IMP_IBKR_LIVE` is disabled.

- [ ] **Step 1: Write failing probe-factory tests**

Add tests that a TWS environment constructs the TWS adapter, a default
environment constructs the REST adapter, and a disabled gate constructs neither.
Add a report assertion:

```python
self.assertEqual(report["transport"], "tws")
self.assertEqual(report["provider"], "IBKR_TWS_GATEWAY")
```

- [ ] **Step 2: Run probe tests and confirm the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_probe -v
```

Expected result: the new factory/report assertions fail because the probe has
no TWS selection or transport metadata.

- [ ] **Step 3: Implement selection and cleanup**

Move client construction behind `build_client`, retain the injectable
`client_factory` used by tests, and close clients that provide `close()` after
the report is written. Keep the existing fake-client request sequence and
partial-failure behavior unchanged.

- [ ] **Step 4: Run the complete offline IBKR suite**

Run:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m unittest discover -s tests/ibkr -v
```

Expected result: all offline IBKR tests pass with zero failures and no network
requests.

### Task 4: Documentation and safety coverage

**Files:**
- Modify: `.env.example`
- Modify: `docs/providers/IBKR_OBSERVATIONAL.md`
- Modify: `tests/ibkr/test_safety.py`
- Modify: `tools/validation_manifest.json` only if needed

- [ ] **Step 1: Write failing safety assertions**

Add AST/text checks that the TWS module contains no order-like symbols, no
credential names in logging/persistence code, no non-loopback default host,
and no public generic broker escape hatch. Add a test that the example
configuration keeps TWS disabled unless both the transport and live gate are
explicitly set.

- [ ] **Step 2: Run the safety test and confirm the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_safety -v
```

Expected result: the new assertions fail until documentation/configuration and
the TWS module's safety markers are present.

- [ ] **Step 3: Add operator documentation**

Document:

```powershell
$env:PYTHONPATH = "src"
$env:IMP_IBKR_LIVE = "1"
$env:IMP_IBKR_TRANSPORT = "tws"
$env:IMP_IBKR_TWS_PORT = "4001"
.venv\Scripts\python.exe -m pip install ib_insync
.venv\Scripts\python.exe tools\ibkr\probe.py --symbol AAPL --output $env:TEMP\ibkr-tws-report.json
```

State that the desktop Gateway must already be logged in, that the report is
observational and not admitted research evidence, and that order operations
remain unavailable. Keep Client Portal instructions as the default path.

- [ ] **Step 4: Run safety and documentation checks**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.ibkr.test_safety -v
.venv\Scripts\python.exe tools\check_docs_links.py
```

Expected result: both commands exit `0`.

### Task 5: Verification and bounded live connection

**Files:**
- No source changes unless a verification failure identifies a scoped defect.
- Output: sanitized report under the system temporary directory only.

- [ ] **Step 1: Run changed validation**

Run:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe tools\validate.py changed
```

Expected result: changed validation passes; any pre-existing validation-suite
failure is recorded separately and does not get hidden.

- [ ] **Step 2: Install the optional socket dependency only if absent**

Check import availability without printing package metadata:

```powershell
.venv\Scripts\python.exe -c "import importlib.util; print('ib_insync=' + ('present' if importlib.util.find_spec('ib_insync') else 'missing'))"
```

If missing, install it into the existing local virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install ib_insync
```

- [ ] **Step 3: Run the bounded live TWS probe**

Run only after the local Gateway remains connected:

```powershell
$env:PYTHONPATH = "src"
$env:IMP_IBKR_LIVE = "1"
$env:IMP_IBKR_TRANSPORT = "tws"
$env:IMP_IBKR_TWS_HOST = "127.0.0.1"
$env:IMP_IBKR_TWS_PORT = "4001"
.venv\Scripts\python.exe tools\ibkr\probe.py --symbol AAPL --output "$env:TEMP\ibkr-tws-capability-report.json"
```

Expected result: exit `0`, a report with `provider=IBKR_TWS_GATEWAY`, and
sanitized `OBSERVED`/`UNTESTED` capability statuses. The output must contain
no account identifier, credential, or raw broker secret.

- [ ] **Step 4: Review the final diff and working tree**

Run:

```powershell
git diff --check
git status --short
```

Confirm that only the scoped adapter, tests, docs, configuration, and any
temporary ignored local environment artifacts changed. Do not commit or push.
