# 14g — G10 Current-State Matrix (IBKR Provider Convergence Audit)

**Status:** AUDIT (2026-09-08) — post G6/G7/G8/G9, G10 depth TTL + provider surface convergence  
**Live posture:** `LIVE_PROVIDER_UNVERIFIED`  
**Starting FULL baseline:** 4250 / 48 / 0 / 0

## G10 changes (this increment)

| Area | Classification | G10 disposition |
|------|----------------|---------------|
| `market_data/depth_admission.py` | **CANONICAL** | New runtime depth admissibility (BL-0303) |
| `market_data/live_admission.py` | **CANONICAL** | DEPTH TTL branch wired |
| `market_data/live_config.py` | **CANONICAL** | Provider-tuned `depth_freshness_policy()` |
| `market_data/observational_lanes.py` | **CANONICAL** | Stale depth blocks OFI/book features |
| `providers/ibkr_observational/historical_bars.py` | **CANONICAL** | Bar normalization boundary |
| `providers/ibkr_observational/account_observation.py` | **CANONICAL** | Read-only account facts |
| `providers/ibkr_observational/capability.py` | **CANONICAL** | +HISTORICAL_BARS, +ACCOUNT_READ |
| `providers/ibkr_observational/adapter.py` | **CANONICAL** | Idempotent `shutdown()`, reconnect guard |
| `market_data/runtime_composition.py` | **CANONICAL** | Idempotent composition shutdown |
| `tools/ibkr/*` streaming transport | **OUTER_PROVIDER_IMPLEMENTATION** | Unchanged owner |
| `tools/ibkr/*` REST seed | **OUTER_PROVIDER_IMPLEMENTATION** | Not runtime-wired; normalized inward |

## BL-0301 sub-capability matrix

| Capability | tools/ibkr | ibkr_observational | Runtime wired | Replay verified | Live verified | Status |
|------------|------------|-------------------|---------------|---------------|---------------|--------|
| L1 | transport | adapter | Yes | Yes | No | WIRED / UNVERIFIED |
| L2 | transport | adapter | Yes | Yes | No | WIRED / UNVERIFIED |
| TRADES | transport (G9) | adapter (G9) | Yes | Yes | No | WIRED / UNVERIFIED |
| CONTRACT/SECDEF | REST + TWS | TWS qualify | Partial | Yes (G8) | No | PARTIALLY_WIRED |
| HISTORICAL_BARS | REST/TWS | normalize module | No live wire | Yes (unit) | No | CANONICAL_NORM / OUTER_FETCH |
| ACCOUNT_READ | REST | observation contract | No live wire | Yes (unit) | No | READ_ONLY_OBS / OUTER_FETCH |
| ENTITLEMENT | callbacks | diagnostics | Partial | Yes | No | PARTIAL / BLOCKED_BY_LIVE |
| CAPTURE/REPLAY | REST + callback | callback capture | Yes (streaming) | Yes | N/A | CONVERGED (streaming) |

## Safety boundary

- src → tools.ibkr: **GREEN** (AST regression in G10 tests)
- Execution authority: **FORBIDDEN** (`IBKR_FORBIDDEN_CAPABILITIES` unchanged)
- Portfolio mutation from provider account facts: **BLOCKED** (`READ_ONLY_OBSERVATIONAL`)

## BL backlog posture (G10)

| ID | Status | Notes |
|----|--------|-------|
| BL-0301 | **PARTIAL** | Streaming + canonical norm for bars/account; live REST wire remains open |
| BL-0303 | **IMPLEMENTATION_COMPLETE** / live separate | Depth TTL admission wired; live depth canary unverified |
| BL-0304 | **COMPLETE (offline/replay)** | Preserved G9 CVD path |
| BL-0305 | **PARTIAL / BLOCKED_BY_LIVE_EVIDENCE** | Offline lifecycle + shutdown hardening; no live canary |
