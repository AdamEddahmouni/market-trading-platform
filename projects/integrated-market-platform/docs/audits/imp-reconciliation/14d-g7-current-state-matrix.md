# 14d — G7 Current-State Matrix (Runtime Wiring / Provider Capability Convergence)

**Status:** G7 **closed** (2026-09-08, working tree uncommitted). Companion to 14a (G4), 14b (G5), 14c (G6).
Baseline entering G7: G6 closed (BL-0213), FULL **4107/48/0** · CHANGED **3572/48/0** · FAST 21/0.
G7 closure: FULL **4146/48/0** · CHANGED **3611/48/0** · FAST 21/0 · focused G7 **39/0**.
Live provider: **LIVE_PROVIDER_UNVERIFIED**.

## G7 test inventory (2026-09-08 reconciliation)

| File | Count | Notes |
|---|---:|---|
| `tests/providers/test_g7_runtime_capability.py` | 14 | `RuntimeCapabilityRegistry` + `ObservationalProviderSelector` |
| `tests/market_data/test_g7_observational_lanes.py` | 14 | lane requirements + `ObservationalLaneRuntime` |
| `tests/market_data/test_g7_runtime_composition.py` | **9** | 8 composition + 1 performance smoke (**not 11**) |
| `tests/cross_lane/test_g7_runtime_inputs.py` | 2 | canonical store → fusion input bridge |
| **Total** | **39** | Matches FULL **4107→4146** and CHANGED **3572→3611** deltas |

Prior informal closure arithmetic recorded composition as **11**, summing to **41**; the authoritative per-file count is **9**, reconciling the **+39 vs +41** mismatch. No tests were removed or weakened between the G6 and G7 closure runs.

## Capability authority hierarchy (G7)

| Layer | Authority | Role |
|---|---|---|
| Implemented capability metadata | `ProviderRegistry` (`providers/registry.py`) | Canonical provider/capability descriptors |
| Runtime readiness facade | `RuntimeCapabilityRegistry` (`providers/runtime_capability.py`) | Reads `ProviderRegistry`; adds entitlement, timeliness, health, observational authority axes; **not** a competing metadata registry |
| Live probe evidence (bounded) | `VerifiedCapabilityRegistry` (`market_data/capability_registry.py`) | Moomoo probe-file verification only; legacy `live_runtime` consumption |
| G7 selection | `ObservationalProviderSelector` (`providers/runtime_selection.py`) | Deterministic fail-closed selection over `RuntimeCapabilityRegistry` views |

There must not be multiple competing runtime-capability authorities. G7 converges selection through the facade; `VerifiedCapabilityRegistry` remains probe evidence, not a parallel runtime-capability truth for G7 wiring.

## Lane matrix

| Lane | Current Input | Current Provider | Canonical Identity? | Canonical Store? | Source Time? | Provenance? | Freshness? | Duplicate Authority? | G7 Disposition |
|---|---|---|---|---|---|---|---|---|---|
| L1 | Moomoo push / IBKR adapter `apply_quote_update` | Moomoo live; IBKR G6 adapter (orphaned from live_runtime) | Partial (symbol uppercase) | **Yes** — `ObservationalStateStore.quotes` | Yes (`event_time_ns`) | Yes (`provider`) | Partial (`freshness_ms` quote-only) | No | **PARTIALLY_WIRED** → G7 canonical lane runtime |
| L2 | Moomoo full-book push; IBKR `DepthUpdate` → `apply_depth_update` | Moomoo live; IBKR adapter (tests only) | Partial | **Yes** — `canonical_books` + projection `books` | Yes | Yes | Partial (`book_status`, `sequence_status`) | No (engine authoritative) | **PARTIALLY_WIRED** → G7 lane runtime + composition |
| CVD | `ObservationalStateStore.trades` / fixture bars | Moomoo ticks; fixture whale ledger | Symbol-level | Store trades canonical; bars fixture | Yes | Yes (`aggressor_provenance`) | Partial | No | **PARTIALLY_WIRED** — live UI only; G7 lane runtime |
| OFI | Book snapshot pairs | Fixture adapters; donor bridge; **not live** | N/A (book rows) | Via `books` projection | Via book `event_time_ns` | Via book `provider` | Via `book_state_valid` | No | **UNWIRED** live → G7 price-aligned OFI from canonical book |
| Book features | `compute_book_features(bids, asks)` | Derived in `_refresh_book_projection` | N/A | **Yes** — embedded in `books` dict | Yes | Yes | Via `book_state_valid` | No | **DERIVED_PROJECTION** — store wired; live UI omits → G7 expose via lane runtime |
| Squeeze | Regulatory/short-pressure fixtures → fusion | Fixture whale ledger | Fixture symbol | WhaleLedger (research) | Fixture timestamps | Fixture provider | Fixture freshness | No | **UNWIRED** to live observational → G7 evidence adapter from canonical inputs |
| Cross-lane fusion | Dict snapshots via `opportunity_adapter` | Research workspace builder | Snapshot-level | No live store | Snapshot timestamps | Lane producer versions | Snapshot quality flags | No | **CANONICAL** engine; **UNWIRED** to live → G7 optional canonical evidence inputs |
| Options | `FixtureOptionsProvider` → whale ledger | Fixture-only | Partial (symbol not contract) | WhaleLedger summaries | Yes | Yes | Fixture | No | **PROVIDER_INPUT** fixture → G7 contract-level observation gate + analytics bridge |
| Futures | `FixtureFuturesProvider` + optional donor bridge | Fixture + bridge | Partial (ES fixture) | WhaleLedger / bridge state | Yes | Yes | Partial | Bridge OFI state = **DUPLICATE_TRUTH** risk | **PARTIALLY_WIRED** → G7 specific FUTURE_CONTRACT gate + canonical quote path |
| Historical data | Fixture bars / FRED vintages | Fixture providers | Varies | Dataset cache | Yes | Yes | Varies | No | **CANONICAL** fixture path; out of G7 live scope |
| Replay/capture | JSONL envelopes / IBKR callback capture | `market_data/replay.py`; IBKR capture | Yes (G6 replay) | ObservationalStateStore | Replay clocks | Yes | Replay deterministic | No | **CANONICAL** — G7 end-to-end replay pipeline tests |
| Provider capability lookup | `ProviderRegistry` → `RuntimeCapabilityRegistry` facade; Moomoo probe via `VerifiedCapabilityRegistry` | IBKR metadata in `ProviderRegistry`; runtime axes in facade; Moomoo probe evidence bounded | N/A | Facade reads metadata authority | N/A | N/A | Moomoo probe staleness | **CONVERGED** (G7): selection via facade; probe registry is evidence-only | G7 closed duplicate-truth risk for runtime selection |
| Provider composition | `ProviderComposition` slots | Env fixture defaults | N/A | Composition manifest | N/A | Provider id per slot | N/A | No | **PARTIALLY_WIRED** — G7 `runtime_composition` boundary |
| Live/runtime wiring | `live_runtime.py` Moomoo-only | Hardcoded Moomoo push | Symbol map | ObservationalStateStore | Yes | Moomoo | Probe-based | No | **UNWIRED** IBKR → G7 provider-neutral composition |

## Classification summary

| Classification | Lanes |
|---|---|
| **CANONICAL** | L1 primitives, L2 engine, CVD/OFI formulas, fusion engine, replay clocks, ObservationalStateStore |
| **DERIVED_PROJECTION** | book features, `books` snapshot dict, workspace projections |
| **PROVIDER_INPUT** | Moomoo push, IBKR callbacks, fixture options/futures |
| **COMPATIBILITY_ADAPTER** | `apply_admitted` snapshot path, donor futures bridge, rank-based OFI |
| **PARTIALLY_WIRED** | L1/L2 live, CVD live UI, futures fixture, provider composition |
| **UNWIRED** | IBKR→live_runtime, OFI live, fusion←live, squeeze←live |
| **DUPLICATE_TRUTH** | bridge OFI carry state (capability registries converged in G7 — see capability hierarchy section) |

## G7 target architecture

```
Provider transport / capture / replay
        ↓
Provider adapter (src)
        ↓
RuntimeCapabilityRegistry (facade over ProviderRegistry implemented metadata + runtime state axes; VerifiedCapabilityRegistry = Moomoo probe evidence only)
        ↓
RuntimeSelection (deterministic, fail-closed)
        ↓
RuntimeComposition (transport injection; no src→tools inversion)
        ↓
Canonical identity + timestamps + provenance
        ↓
ObservationalStateStore
        ↓
ObservationalLaneRuntime (CVD/OFI/book-features/options/futures)
        ↓
Derived projections / research outputs (provenance preserved)
```

## Key gaps closed by G7 implementation

1. Unified runtime capability axes (implemented vs runtime vs entitlement vs timeliness vs health).
2. Deterministic observational provider selection with explicit failure modes.
3. Composition boundary for IBKR adapter injection without `src` importing `tools/ibkr`.
4. Lane runtime wiring from canonical store to existing analytics (no formula redesign).
5. Options/futures identity gates (OPTION_CONTRACT / FUTURE_CONTRACT required).
6. End-to-end replay tests proving deterministic hashes across the pipeline.
