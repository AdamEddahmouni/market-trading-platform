# 14e — G8 Current-State Matrix (IBKR Runtime Convergence / Live Provider Verification)

**Status:** G8 **CLOSED** (2026-09-08, working tree uncommitted) after dependency-direction correction. Companion to 14c (G6), 14d (G7).
Baseline entering G8: G7 closed, FULL **4146/48/0** · CHANGED **3611/48/0** · FAST 21/0 · LIVE_PROVIDER_UNVERIFIED.
G8 functional baseline before correction: focused **63** · CHANGED **3674/48/0** · FULL **4209/48/0**.
Correction removed the `live_runtime.py` → `tools.ibkr.observational_transport` construction import.

## G8 test inventory (2026-09-08, post-correction)

| File | Count | Notes |
|---|---:|---|
| `tests/ibkr/test_observational_transport.py` | 13 | outer transport protocol + callback bridge |
| `tests/ibkr/test_runtime_bootstrap.py` | 2 | outer construction owner |
| `tests/providers/test_g8_contract_resolution.py` | 12 | XA-01 + provider qualification boundary |
| `tests/providers/test_g8_entitlement_reconnect.py` | 15 | entitlement / reconnect / pacing codes |
| `tests/market_data/test_g8_live_runtime_composition.py` | 16 | live_runtime + injected transport |
| `tests/market_data/test_g8_cvd_runtime.py` | 8 | CVD degraded without trade prints |
| `tests/market_data/test_g8_src_tools_boundary.py` | 4 | AST scan: no src→tools/ibkr implementation dependency |
| `tests/market_data/test_g8_runtime_performance.py` | 4 | four G8 runtime-overhead measurements |
| **Total focused G8** | **74** | All green offline |

## Runtime architecture (post-correction)

```text
outer/bootstrap/tools
    tools/ibkr/runtime_bootstrap.py
        constructs IbkrObservationalTransport
        injects IbkrObservationalTransportProvider
            ↓
src canonical runtime/composition
    live_runtime.configure()  (accepts injected transport / provider)
    ObservationalRuntimeComposition.attach_ibkr_adapter(transport)
            ↓
    IbkrTransport protocol
            ↓
    IbkrObservationalAdapter
            ↓
    ObservationalStateStore → IncrementalOrderBook → G7 lanes
```

Concrete TWS callback bridge remains `tools/ibkr/observational_transport.py`.
Canonical src never imports `tools/ibkr`. Moomoo `push_feed` path is unchanged.

## Concern matrix

| Concern | Current Owner | Current Runtime Path | Canonical? | Wired? | Evidence | G8 Disposition |
|---|---|---|---|---|---|---|
| TWS connection | `tools/ibkr/observational_transport.py` | `IbkrObservationalTransport.connect(readonly=True)` | Yes | **Yes** (gated) | transport tests + offline fakes | **WIRED** |
| Concrete transport construction | `tools/ibkr/runtime_bootstrap.py` | `IbkrObservationalRuntimeBootstrap.construct()` | Yes | **Yes** | bootstrap + boundary tests | **WIRED** |
| reqMktData | transport → adapter | `req_mkt_data` → `subscribe_l1` | Yes | **Yes** | G6+G8 tests | **WIRED** |
| cancelMktData | transport | `cancel_mkt_data` | Yes | **Yes** | transport tests | **WIRED** |
| reqMktDepth | transport | `req_mkt_depth` | Yes | **Yes** | G6+G8 tests | **WIRED** |
| cancelMktDepth | transport | `cancel_mkt_depth` | Yes | **Yes** | transport tests | **WIRED** |
| updateMktDepth | transport callback bridge | `on_mkt_depth` | Yes (op 0/1/2) | **Yes** | G6 mapping tests | **PRESERVED** |
| updateMktDepthL2 | transport callback bridge | `on_mkt_depth_l2` | Yes | **Yes** | G6 replay | **PRESERVED** |
| contract details/secdef | src `providers/ibkr_observational` qualification | qualify → `ContractQualification` | Yes | **Partial** | G8 contract tests | **WIRED** (equity/options/futures rules) |
| reqId allocation | G6 adapter | `_allocate_req_id` | Yes | **Yes** | G6 lifecycle | **UNCHANGED** |
| contract qualification | G6 `identity.py` + G8 resolver | XA-01 admission before subscribe | Yes | **Yes** | G8 tests | **WIRED** |
| L1 subscription lifecycle | G6 adapter + G8 transport | subscribe/cancel/state machine | Yes | **Yes** | G6+G8 tests | **WIRED** |
| L2 subscription lifecycle | G6 adapter + G8 transport | subscribe/cancel/reset | Yes | **Yes** | G6+G8 tests | **WIRED** |
| reconnect | G6 `handle_reconnect` | bounded, new reqIds/generation | Yes | **Yes** | G8 entitlement tests | **WIRED** |
| entitlement errors | G6 `on_error` normalization | 354/depth failures | Yes | **Yes** | G8 tests | **WIRED** |
| delayed data | G6 L1 accumulator + error path | quality=DELAYED | Yes | **Yes** | G8 tests | **WIRED** |
| pacing | G6 `LocalPacingState` | cooldown on code 100 | Yes | **Yes** | G6+G8 tests | **WIRED** |
| provider health | G7 `RuntimeCapabilityRegistry` | `sync_ibkr_runtime_state` | Yes | **Yes** | composition tests | **WIRED** |
| capture | G6 `CallbackCapture` | JSONL optional path | Yes | **Yes** | G6 replay tests | **UNCHANGED** |
| replay | G6 `on_captured_record` | offline deterministic | Yes | **Yes** | G6+G7 tests | **UNCHANGED** |
| runtime startup | outer bootstrap + `live_runtime.configure` | injected transport only | Yes | **Yes** | G8 composition + bootstrap tests | **WIRED** |
| capability registration | G7 registry | IBKR metadata + runtime axes | Yes | **Yes** | G7 tests | **UNCHANGED** |
| capability selection | G7 selector | fail-closed | Yes | **Yes** | G8 composition tests | **UNCHANGED** |
| canonical store | `ObservationalStateStore` | quotes + depth | Yes | **Yes** | G5/G6/G7 | **UNCHANGED** |
| CVD live input path | G7 lanes | trades via TICK admission only | Yes | **Degraded** | G8 CVD tests | **EXPLICIT_UNAVAILABLE** from L1-only |
| src→tools/ibkr dependency | forbidden | AST scan of `src/market_platform_foundation/` | Yes | **Yes** | `test_g8_src_tools_boundary.py` | **CLOSED** |

## Live provider evidence

**Classification:** `LIVE_PROVIDER_UNVERIFIED` (no configured TWS session in CI/dev closure run).

| Capability | Live status |
|---|---|
| IBKR L1 | NOT_ATTEMPTED / offline verified |
| IBKR L2 | NOT_ATTEMPTED / offline verified |
| contract resolution | offline verified / live environment unavailable |
| entitlement | environment unavailable |
| IBKR CVD | FAILED_SAFE because L1 does not fabricate trade prints |

Per-capability offline evidence: replay + fake transport **VERIFIED**; real-time canary **NOT_ATTEMPTED**.

## Performance evidence

Classification: **LIVE_RUNTIME_PERFORMANCE_MEASURED** — development-machine observational measurement only; not provider-network throughput; not production SLA.

Recorded in `docs/audits/imp-reconciliation/g8-runtime-performance.json` (copy of IMP artifacts). Isolated rerun, 5000-iteration fake/replay (startup 200 repeats):

| Measurement | Time | Rate |
|---|---:|---:|
| 1. outer callback bridge → canonical adapter | 5.416661 s | 923.08 events/s |
| 2. startup composition | 0.004866 s total (200×) | 24.33 µs each |
| 3. subscribe/cancel lifecycle | 0.105144 s | 47,554 cycles/s |
| 4. capture/replay bridge | 0.253692 s | 19,709 events/s |

## Backlog disposition (evidence-based)

| ID | G8 status | Rationale |
|---|---|---|
| BL-0301 | **PARTIAL** | Observational L1/L2 runtime wired; broader adapter (account/secdef/bars REST surface) remains open per backlog wording |
| BL-0304 | **PARTIAL** | CVD path explicit for classified trades; IBKR L1 alone does not fabricate trades — tick-by-tick not wired |
| BL-0305 | **PARTIAL / BLOCKED_BY_LIVE_EVIDENCE** | Subscription/entitlement/reconnect state machine proven offline; live entitlement canary not collected (`Runtime validation: recorded + live-gated canary`) |
