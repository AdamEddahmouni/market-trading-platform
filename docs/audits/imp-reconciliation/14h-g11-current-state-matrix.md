# 14h — G11 Current-State Matrix (IBKR Read-Only Query Surface Convergence)

**Status:** AUDIT (2026-09-09) — post G10 depth TTL + provider surface convergence  
**Live posture:** `LIVE_PROVIDER_UNVERIFIED`  
**Starting FULL baseline:** 4280 / 48 / 0 / 0

## G11 changes (this increment)

| Area | Classification | G11 disposition |
|------|----------------|-----------------|
| `providers/ibkr_observational/query_provider.py` | **CANONICAL** | Read-only query protocol + service |
| `market_data/ibkr_query_bridge.py` | **CANONICAL** | Outer query provider injection bridge |
| `market_data/runtime_composition.py` | **CANONICAL** | Query attach + composition methods |
| `market_data/live_runtime.py` | **CANONICAL** | Query service attach on IBKR startup |
| `providers/ibkr_observational/capture.py` | **CANONICAL** | Query capture records |
| `providers/runtime_capability.py` | **CANONICAL** | +CAP_ACCOUNT_READ; hist/acct in implemented_capabilities |
| `tools/ibkr/query_provider.py` | **OUTER_PROVIDER_IMPLEMENTATION** | REST/TWS query adapter |
| `tools/ibkr/canary.py` | **OUTER_TOOLS_HARNESS** | Bounded live canary (fail-closed) |
| `tools/ibkr/runtime_bootstrap.py` | **OUTER_PROVIDER_IMPLEMENTATION** | Registers query bootstrap |

## BL-0301 sub-capability matrix (G11 entry)

| Capability | Canonical contract | Outer implementation | Injected | Runtime callable | Replay verified | Live verified | Gap |
|------------|-------------------|---------------------|----------|------------------|-----------------|---------------|-----|
| L1 | adapter/L1QuoteFacts | observational_transport | Yes | Yes | Yes | No | LIVE_UNVERIFIED |
| L2 | adapter/DepthUpdate | observational_transport | Yes | Yes | Yes | No | LIVE_UNVERIFIED |
| TRADES | adapter/TradePrintFacts | observational_transport | Yes | Yes | Yes | No | LIVE_UNVERIFIED |
| CONTRACT_SECDEF | contract_resolution + query_service | query_provider secdef | Yes | Yes | Yes (unit) | No | LIVE_UNVERIFIED |
| HISTORICAL_BARS | historical_bars + query_service | query_provider history | Yes | Yes | Yes (unit) | No | LIVE_UNVERIFIED |
| ACCOUNT_READ | account_observation + query_service | query_provider accounts | Yes | Yes | Yes (unit) | No | LIVE_UNVERIFIED |
| ENTITLEMENT | diagnostics/callbacks | partial | Yes | Partial | Yes | No | LIVE_CANARY_ABSENT |
| CAPTURE_REPLAY | capture.py streaming + query | callback + query capture | Yes | Yes | Yes | N/A | CONVERGED |

## Safety boundary

- src → tools.ibkr: **GREEN** (AST regression preserved)
- Execution authority: **FORBIDDEN** (unchanged)
- Provider account facts → G2 portfolio: **BLOCKED** (`READ_ONLY_OBSERVATIONAL`)
- Historical bars → live L1/L2 state: **NO SILENT MERGE**

## VerifiedCapabilityRegistry audit

`VerifiedCapabilityRegistry` remains **Moomoo-probe-specific** by design. IBKR query readiness uses `RuntimeCapabilityRegistry` only — no fourth registry created.

## Subscription manager audit (BL-0305)

No IBKR capability key collision found requiring subscription manager changes. L1/L2/TRADES subscription identity remains scoped by provider+capability+instrument_id+generation in G6 adapter.

## BL backlog posture (G11)

| ID | Status | Notes |
|----|--------|-------|
| BL-0301 | **IMPLEMENTATION_COMPLETE / LIVE_VERIFICATION_PENDING** | All sub-surfaces implemented + runtime-wired offline |
| BL-0303 | **IMPLEMENTATION_COMPLETE** / live separate | Depth TTL preserved (G10 regression green) |
| BL-0304 | **COMPLETE (offline/replay)** | G9 CVD path preserved |
| BL-0305 | **IMPLEMENTATION_COMPLETE / BLOCKED_BY_LIVE_EVIDENCE** | Lifecycle + canary harness; live canary not executed |

## G11 closure (2026-09-09)

| Capability | Implemented | Runtime wired | Replay verified | Live verified | Status |
|------------|-------------|---------------|-----------------|---------------|--------|
| L1 | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| L2 | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| TRADES | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| CONTRACT_SECDEF | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| HISTORICAL_BARS | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| ACCOUNT_READ | Yes | Yes | Yes | No | LIVE_VERIFICATION_PENDING |
| ENTITLEMENT | Partial | Partial | Yes | No | LIVE_VERIFICATION_PENDING |
| CAPTURE_REPLAY | Yes | Yes | Yes | N/A | CONVERGED |

**Validation:** Starting FAST **21/0/0/0**; starting FULL **4326/48/2/0** (2 ibkr safety failures on `query_provider.py` src import — corrected); final FULL **4326/48/0/0**; CHANGED **3791/48/0/0**; focused G11 **46/0/0/0**.

**G8 boundary fix:** `tools/ibkr/query_provider.py` no longer imports `market_platform_foundation`; registration consolidated in `runtime_bootstrap.py` only.

**Performance (G11_RUNTIME_PERFORMANCE_MEASURED, dev machine):** contract_qualification 36.38 ms / 5000 iter; historical_bar_normalization 10.48 ms; account_observation_normalization 9.41 ms; query_service_round_trip 15.71 ms / 1000 iter; depth_ttl_regression 12.07 ms; capability_resolution 25.36 ms.

**Live canary:** `tools/ibkr/canary.py` executed G11.1 with `IMP_IBKR_LIVE=1` — Gateway reachable on loopback 4001. Prior "not enabled / no reachable gateway" wording was a **false blocker** (gate conflated with environment). See [14i-g11-live-verification-matrix.md](../../audits/imp-reconciliation/14i-g11-live-verification-matrix.md).
