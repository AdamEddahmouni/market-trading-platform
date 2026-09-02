# IMP-XA-05 — Cross-Asset Strategic State & Regime Kernel

## Audit conclusions

XA-01 through XA-04 already own identity, admitted evidence, and durable catalog truth. No
repository-equivalent regime or strategic-state kernel exists above that layer. Relevant reuse
targets:

| Existing surface | Reuse decision |
| --- | --- |
| `xa01.AnalyticalDomain`, `InstrumentRecord` | Preserve domain participation metadata in state snapshots |
| `xa02.AdmittedObservation`, `AdmissionEnvelope`, PIT helpers | Consume admitted evidence only; do not mutate admission semantics |
| `xa03` positioning envelopes | Same as XA-02; positioning remains reported quantities |
| `xa04.CrossAssetCatalogRepository` | Primary read surface for PIT reconstruction |
| `market_data.ObservationalStateStore` | Out of scope — live quote/trade state, not cross-asset macro/positioning |
| `intelligence.fusion` epistemic enums | Out of scope — forecast fusion, not cross-asset strategic state |
| `state` namespace | Empty placeholder; not the owner |

## Ownership boundary

`src/market_platform_foundation/xa05/` owns **immutable, reconstructable analytical state**
constructed at a decision time from canonical XA catalog evidence.

XA-05 does **not**:

- persist a second analytics database (states are ephemeral/reconstructable),
- mutate XA-01/02/03/04 semantics,
- grant trading, risk, execution, or adaptation authority.

## Central object

`CrossAssetStrategicState` — immutable point-in-time analytical snapshot with explicit:

- state identity and semantic fingerprint,
- decision/effective time and construction time (construction time excluded from semantic identity),
- participating analytical domains,
- bounded derived dimensions with versioned classifications,
- evidence references and provenance,
- completeness/conflict metadata,
- reproducibility metadata aligned with REBASE-02 determinism expectations.

## Initial bounded dimensions

1. `RATES_CURVE_CONFIGURATION` — steep / flat / inverted / insufficient / unknown
2. `POLICY_RATE_LEVEL` — restrictive / neutral / accommodative / insufficient / unknown
3. `POSITIONING_CONCENTRATION` — long_bias / short_bias / balanced / insufficient / unknown
4. `DATA_FRESHNESS` — fresh / aging / stale / insufficient / unknown
5. `CROSS_DOMAIN_PARTICIPATION` — explicit participating `AnalyticalDomain` set

## Persistence

Ephemeral/reconstructable only. XA-04 remains catalog authority.

## Operator surface

Read-only OF-03 capabilities: status, validate, construct-state, show-state, compare-states.
