# 14i — G11.1 Live Verification Forensic Matrix

**Status:** AUDIT (2026-09-09) — post bounded read-only live canary  
**Root cause class:** `SAFETY_GATE_STATE_MISCLASSIFIED_AS_PROVIDER_ENVIRONMENT_STATE`

## Executive finding

Prior G8–G11 closure agents **never attempted** a live IBKR canary despite an open Gateway on loopback `127.0.0.1:4001`. Closure prose conflated **`IMP_IBKR_LIVE` unset** (intentional safety opt-in) with **Gateway unreachable** (`ENVIRONMENT_UNAVAILABLE`). G11.1 measured the environment and corrected the semantic distinction without weakening execution boundaries.

## Forensic chain

| Layer | Expected | Actual | Verified by | Result | Defect? |
|---|---|---|---|---|---|
| 1. Gateway process | Desktop IB Gateway logged in | Open (user + TCP probe) | `Test-NetConnection` / TCP `127.0.0.1:4001` | **REACHABLE** | No |
| 2. Loopback port | TWS API 4001 or 4002 | **4001 OPEN**, 4002 closed, 5000 closed | socket probe | **4001 active** | No |
| 3. Configured host | Loopback only | `127.0.0.1` default | `tools/ibkr/config.py` | Match | No |
| 4. Configured port | 4001 or 4002 | Default **4001** | config + probe | Match | No |
| 5. IB client ID | Positive, non-conflicting | Default **37** works; **1** also works | ib_insync connect rotation | **CONNECTED** | Minor: default 37 can timeout when another session holds ID |
| 6. Read-only setting | `readonly=True` | `readonly=True` on connect | canary + TwsIbkrClient | Match | No |
| 7. `IMP_IBKR_LIVE` | Safety opt-in gate | **Unset in CI/agent env** | env inspection | **LIVE_ACCESS_NOT_ENABLED_BY_CONFIG** | **Yes — misreported as environment failure** |
| 8. `MP_OFFLINE` / offline gates | Block execution, not probe | Offline tests pass without live gate | validation baseline | Offline path intact | No |
| 9. Runtime provider preference | IBKR secondary observational | `ibkr.observational` registered | RuntimeCapabilityRegistry | Implemented | No |
| 10. Bootstrap / provider install | Outer `runtime_bootstrap.py` injects transport | Present | code inspection | Wired | No |
| 11. Canary precondition | Fail-closed on gate; distinguish gate vs transport | **Fixed G11.1** — `classify_gate()` separates gate vs TCP | `tools/ibkr/canary.py` | **Corrected** | **Was defective** |
| 12. Error handling | Classify config vs transport vs entitlement | Provider errors 10089/10092/10189 captured | live canary stderr + adapter diagnostics | Entitlement truth partial | Improved |
| 13. Environment vs config reporting | Do not equate unset gate with unreachable Gateway | Prior docs: "no reachable gateway / IMP_IBKR_LIVE off" | audit matrices 14f–14h | **False blocker** | **Yes — documentation defect** |

## G11.1 live canary results (2026-09-09)

| Capability | Connection | Request accepted | Data received | Entitlement | Freshness | Normalization | Result |
|---|---|---|---|---|---|---|---|
| IBKR_CONTRACT_RESOLUTION | Yes | Yes | Yes | UNKNOWN | UNKNOWN | Yes | **LIVE_PROVIDER_VERIFIED** |
| IBKR_HISTORICAL_BARS | Yes | Yes | Yes | ENTITLED | UNKNOWN | Yes | **LIVE_PROVIDER_VERIFIED** |
| IBKR_ACCOUNT_READ | Yes | Yes | Yes (redacted) | READ_ONLY_OBSERVATIONAL | UNKNOWN | Yes | **LIVE_PROVIDER_VERIFIED** |
| IBKR_L1 | Yes | Yes | Yes (delayed last) | DELAYED / UNKNOWN | DELAYED | Yes | **LIVE_PROVIDER_VERIFIED** (delayed, not realtime) |
| IBKR_L2 | Yes | Yes | No | NOT_ENTITLED (10092) | UNKNOWN | No | **LIVE_CONNECTED_NOT_ENTITLED** |
| IBKR_TRADES | Yes | Yes | No | NOT_ENTITLED (10189) | UNKNOWN | No | **LIVE_CONNECTED_NOT_ENTITLED** |
| ENTITLEMENT | Yes | Partial | Provider errors observed | Per-capability | — | — | **Measured** |
| CAPTURE_REPLAY | N/A | N/A | Offline proven | N/A | N/A | Yes | **CONVERGED** |

Evidence artifacts:

- `docs/audits/imp-reconciliation/g11-live-canary-summary.json`
- `docs/audits/imp-reconciliation/g11-live-capability-evidence.json`
- `projects/integrated-market-platform/evidence/market_data/ibkr/canary-report.json`

## Prior false-blocker correction

**Historical (G8–G11):** "Canary not attempted — `IMP_IBKR_LIVE` not enabled / no reachable Gateway."

**Current (G11.1):** Gateway was available on loopback 4001 throughout. Agents did not set `IMP_IBKR_LIVE=1` for a bounded process and conflated the safety gate with environment availability. Default transport `client_portal` (port 5000) was also incorrectly implied unreachable when TWS port 4001 was the active surface.

Execution remains **fail-closed** — no order APIs invoked.

## Performance (bounded canary, dev machine)

| Measurement | ms |
|---|---|
| Connection | ~114 |
| Contract/secdef | ~0 |
| Historical bars | ~1125 |
| Account read | ~83 |
| Streaming connect | ~114 |

Classification: **LIVE_PROVIDER_PERFORMANCE_MEASURED** (partial — only verified capabilities).
