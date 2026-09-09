# 14j — G12 Current-State Matrix (Post-IBKR Multi-Asset Runtime Completion)

**Status:** AUDIT (2026-09-09) — post G11.1 live capability truth + canonical multi-asset runtime projection  
**Starting FULL baseline:** 4330 / 48 / 0 / 0  
**Final FULL baseline:** 4355 / 48 / 0 / 0 (+25 G12 tests)

## G12 scope selected

**Primary:** Canonical multi-asset runtime domain projection (`cross_lane/multi_asset_runtime.py`) wiring XA-01 identity → observational lanes → portfolio valuation → risk probe → API envelope.

**Priority domains completed in runtime layer:**
1. Futures (specific contract; family/continuous rejected; multiplier mandatory)
2. Options (specific contract; underlying-only rejected; missing chain ≠ empty)
3. Crypto (pair isolation; USDT ≠ USD without FX evidence)
4. Bonds (typed identity; reference-only execution)
5. Gold/Silver/Commodities (economic/spot/proxy distinction)

**Deferred (intentional):** Live futures/options product UI expansion; futures margin model; bond tradability; crypto observational lane; unified instrument selector (Wave 7).

## External limitation isolation

| Capability | Implementation | Runtime | Replay | Live | External limitation | Active engineering blocker? |
|---|---|---|---|---|---|---|
| IBKR L1 | COMPLETE | WIRED | VERIFIED | LIVE_PROVIDER_VERIFIED (delayed) | Realtime top-of-book entitlement not proven | **NO** |
| IBKR L2 | COMPLETE | WIRED | VERIFIED | LIVE_CONNECTED_NOT_ENTITLED | Account subscription (10092) | **NO** |
| IBKR TRADES | COMPLETE | WIRED | VERIFIED | LIVE_CONNECTED_NOT_ENTITLED | Account subscription (10189) | **NO** |
| IBKR CONTRACT | COMPLETE | WIRED | VERIFIED | LIVE_PROVIDER_VERIFIED | — | **NO** |
| IBKR BARS | COMPLETE | WIRED | VERIFIED | LIVE_PROVIDER_VERIFIED | — | **NO** |
| IBKR ACCOUNT_READ | COMPLETE | WIRED | VERIFIED | LIVE_PROVIDER_VERIFIED (read-only) | — | **NO** |

## Multi-asset completion matrix

| Domain | Identity | Provider facts | History | Runtime | Portfolio | Valuation | Risk | Paper | API | UI | Tests | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EQUITY | COMPLETE | IMPLEMENTED_NOT_WIRED | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| OPTION | COMPLETE | IMPLEMENTED_NOT_WIRED | PARTIAL | COMPLETE | COMPLETE | COMPLETE | PARTIAL | PARTIAL | PARTIAL | PARTIAL | COMPLETE | PARTIAL |
| FUTURE | COMPLETE | IMPLEMENTED_NOT_WIRED | PARTIAL | COMPLETE | COMPLETE | COMPLETE | EXTERNAL_ENTITLEMENT_LIMIT | PARTIAL | PARTIAL | PARTIAL | COMPLETE | PARTIAL |
| CRYPTO | COMPLETE | MISSING | PARTIAL | COMPLETE | COMPLETE | COMPLETE | PARTIAL | MISSING | MISSING | MISSING | COMPLETE | PARTIAL |
| BOND | COMPLETE | MISSING | RESEARCH_ONLY | COMPLETE | IMPLEMENTED_NOT_WIRED | COMPLETE | REFERENCE_ONLY | MISSING | MISSING | MISSING | COMPLETE | PARTIAL |
| GOLD | COMPLETE | REFERENCE_ONLY | RESEARCH_ONLY | COMPLETE | REFERENCE_ONLY | REFERENCE_ONLY | REFERENCE_ONLY | MISSING | MISSING | MISSING | COMPLETE | PARTIAL |
| SILVER | COMPLETE | REFERENCE_ONLY | RESEARCH_ONLY | COMPLETE | REFERENCE_ONLY | REFERENCE_ONLY | REFERENCE_ONLY | MISSING | MISSING | MISSING | COMPLETE | PARTIAL |
| COMMODITY | COMPLETE | PARTIAL | PARTIAL | COMPLETE | PARTIAL | PARTIAL | PARTIAL | MISSING | PARTIAL | PARTIAL | COMPLETE | PARTIAL |

## G11.1 L1 capability-truth reconciliation

| Axis | Prior (incorrect) | G12 corrected |
|---|---|---|
| Live path | LIVE_PROVIDER_VERIFIED | LIVE_PROVIDER_VERIFIED (unchanged) |
| Entitlement | UNKNOWN | ENTITLED_DELAYED |
| Freshness/delivery | REALTIME | DELAYED |
| Realtime entitled | implied | **NOT PROVEN** (separate from live-path verification) |

Evidence: `g11-live-capability-evidence.json` freshness/entitlement axes; `tools/ibkr/canary.py` uses `quote.delayed` and `ENTITLED_DELAYED` when provider delivers delayed ticks.

## Shared architecture path (G12)

```
XA-01 identity (G1)
    ↓
provider qualification (G7 RuntimeCapabilityRegistry)
    ↓
canonical observation/history (G6/G11)
    ↓
runtime domain projection (G12 multi_asset_runtime)
    ↓
CanonicalPortfolio / valuation (G2/G4)
    ↓
risk/trading admission (G3 fail-closed)
    ↓
API/product projection (build_api_projection)
```

## G12 artifacts

| Artifact | Role |
|---|---|
| `cross_lane/runtime_status.py` | RuntimeDomainStatus vocabulary |
| `cross_lane/multi_asset_runtime.py` | Canonical projection owner |
| `tests/cross_lane/test_g12_multi_asset_runtime.py` | 25 architectural regressions |
| `tools/ibkr/canary.py` | L1 delayed freshness correction |

## Validation (G12)

| Gate | Tests | Skipped | Failures | Errors |
|---|---:|---:|---:|---:|
| Starting FAST | 21 | 0 | 0 | 0 |
| Starting FULL | 4330 | 48 | 0 | 0 |
| Focused G12 | 25 | 0 | 0 | 0 |
| CHANGED | 3820 | 48 | 0 | 0 |
| Final FULL | 4355 | 48 | 0 | 0 |

## Remaining active implementation backlog (post-G12)

1. Futures margin / variation-margin risk model (G4 explicit deferral)
2. Paper submit/fill for options/futures through canonical portfolio (not identity-only)
3. Crypto observational capability + workspace surface
4. Bond tradability decision + admission if execution authorized
5. Governed FX rate source for portfolio aggregation
6. Unified multi-asset instrument selector (Wave 7 / BL-0701)
7. Live verification rerun for L2/TRADES when account entitlements change (bounded canary only)

## External/account limitations (not implementation blockers)

- IBKR L2: LIVE_CONNECTED_NOT_ENTITLED (subscription 10092)
- IBKR TRADES: LIVE_CONNECTED_NOT_ENTITLED (subscription 10189)
- IBKR L1: delayed data observed; realtime top-of-book entitlement not proven
