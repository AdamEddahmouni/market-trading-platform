# Provider Normalization V1 (BUILD 03)

BUILD 03 answers:

> **How does raw heterogeneous source/provider information become one deterministic, provider-neutral `EventV1` with trustworthy timestamps, canonical identity, complete provenance, and reproducible normalization semantics?**

## Public API

```python
from market_platform_foundation.intelligence.normalization import (
    NormalizationContext,
    NormalizationResult,
    NormalizationError,
    normalize_event,
    require_normalized_event,
)
```

Module path: `src/market_platform_foundation/intelligence/normalization/`.

## Normalization boundary

```text
RAW PROVIDER DATA
        ↓
PROVIDER ADAPTER
        ↓
NORMALIZATION CONTEXT  (caller-supplied, clock-injected)
        ↓
SOURCE / PROVENANCE ANALYSIS
        ↓
TIMESTAMP NORMALIZATION
        ↓
INSTRUMENT / SCOPE NORMALIZATION
        ↓
CANONICAL EVENT IDENTITY
        ↓
NORMALIZED EVENT PAYLOAD
        ↓
EventV1
        ↓
BUILD 02 TEMPORAL VALIDATION
```

Provider record **≠** `EventV1`. Normalization guarantees:

- deterministic output for identical raw record + context + adapter version;
- explicit timestamp responsibilities (no provider timestamp bypassing availability);
- preserved provenance and native source identity;
- strict or diagnostic failure for malformed/untrusted records;
- no wall-clock reads inside core normalization logic.

## Raw vs canonical

| Layer | Role |
|-------|------|
| Provider record | Source evidence at the adapter edge (may be untyped/`Any`) |
| Normalization | Validates, maps, and derives canonical fields |
| `EventV1` | Intelligence-plane contract consumed by BUILD 02+ |

Raw provider payloads are **not** embedded wholesale in `EventV1`. Prefer `raw_payload_ref` and `raw_payload_hash` in `ProviderProvenance` (stored in `EventV1.metadata["normalization_provenance"]`).

## Timestamp responsibilities

| Timestamp | Source | Meaning |
|-----------|--------|---------|
| `event_time_ns` | Provider/source | When the underlying economic/market event occurred or is attributed |
| `provider_time_ns` | Provider | Provider-reported timestamp (evidence, not platform availability) |
| `received_time_ns` | Platform caller/runtime | Local observation/receipt time (required for live paths via `NormalizationContext`) |
| `available_time_ns` | Normalized platform semantics | Earliest legitimate intelligence use — **authoritative anti-lookahead gate** |

Provider timestamps are **evidence**. Platform availability is a **platform semantic**.

### Live example

```text
Exchange event         10:00:00.000   (event_time_ns)
Provider timestamp     10:00:00.005   (provider_time_ns)
Platform receives      10:00:00.040   (received_time_ns)
Platform availability  10:00:00.040   (available_time_ns)

Decision at 10:00:00.020 → NOT ELIGIBLE (BUILD 02)
Decision at 10:00:00.050 → ELIGIBLE
```

### Delayed feed example

```text
Market event             10:00:00       (event_time_ns)
Provider-delayed record  10:15:00       (provider_time_ns)
Platform receives        10:15:00.040   (received_time_ns)
Platform availability    10:15:00.040   (available_time_ns)

Decision at 10:00:00 → NOT ELIGIBLE — delayed data cannot be used at original event time.
```

### Historical publication example

```text
Economic fact relates to date T1        (event_time_ns)
Official file published at T2           (available_time_ns from publication evidence)

Point-in-time availability begins at T2, not T1.
Download/receipt time today must not overwrite historical availability.
```

## Ingestion modes

| Mode | Availability derivation |
|------|-------------------------|
| `LIVE_OBSERVED` | `max(trustworthy_provider_available, received_time_ns)` — local receipt is the floor |
| `HISTORICAL_RECONSTRUCTED` | From source evidence via `historical_available_time_ns` + provenance basis |
| `REPLAY` / `FIXTURE` | Same as historical reconstruction semantics |

Modes do **not** weaken BUILD 02 rules once `EventV1` exists.

## Availability basis

Represented in `AvailabilityDerivation`:

| Basis | Typical use |
|-------|-------------|
| `LOCAL_RECEIPT` | Live platform observation |
| `PROVIDER_REPORTED_AVAILABILITY` | Provider-declared availability later than receipt |
| `PUBLICATION_TIME` | SEC filings, regulatory publications |
| `RELEASE_TIME` | Macro/economic releases |
| `RECONSTRUCTED_FROM_SOURCE` | Historical imports from source evidence |
| `UNKNOWN_OR_APPROXIMATE` | Date-only public files with documented uncertainty |

Confidence: `DIRECTLY_OBSERVED`, `SOURCE_REPORTED`, `DERIVED`, `APPROXIMATE`.

## Event identity

Priority:

1. Strong provider-native immutable ID (e.g. SEC accession number)
2. Documented composite source identity
3. Deterministic derived canonical identity (`sha256` composite)
4. Generated local identity only when unavoidable

Identity excludes mutable payload fields when a stable source ID exists — enabling BUILD 02 `CONFLICTING_DUPLICATE` detection when the same source identity arrives with different content.

Implementation reuses `contracts.identity.normalized_event_id()` (UUID v5 over stable identity components).

## Provenance

`ProviderProvenance` records:

- provider/source ID and native record ID
- provider-native symbol
- adapter ID/version and normalization version
- raw payload reference/hash
- availability derivation basis and confidence
- source publication/revision identifiers

Queryable facts for future BUILD 04.5 persistence without implementing storage now.

## Provider scope (BUILD 03)

| Provider/source | Existing state | BUILD 03 action | Status |
|-----------------|----------------|-------------------|--------|
| Moomoo/OpenD | ACTIVE SOURCE | Direct capture → `EventV1` | **NORMALIZED** |
| Finviz Elite | DISCOVERY-ONLY | Discovery candidate → `EventV1` | **NORMALIZED** |
| SEC EDGAR | PARTIAL (fixture-first) | Filing dict → `EventV1` | **NORMALIZED** |
| SEC FTD | ACTIVE SOURCE | `FailsToDeliverObservation` → `EventV1` | **NORMALIZED** |
| FINRA short interest | ACTIVE SOURCE | `ShortInterestObservation` → `EventV1` | **NORMALIZED** |
| FRED/macro | ACTIVE SOURCE | `MacroObservation` → `EventV1` | **NORMALIZED** |
| Revision-1 envelopes | Existing whale/market paths | Envelope bridge → `EventV1` | **COMPATIBILITY ADAPTER** |
| IBKR | ADAPTER/STUB (tooling only) | Interface hook, no fabricated streams | **INTERFACE READY** |
| Tradier/tastytrade | ADAPTER/STUB / declared | Not implemented | **NOT CURRENTLY SUPPORTED** |
| Databento | FUTURE/DECLARED | Not implemented | **NOT CURRENTLY SUPPORTED** |
| Crypto | FUTURE/DECLARED | Not implemented | **NOT CURRENTLY SUPPORTED** |

## Error taxonomy

Distinct from BUILD 04 quality states:

`MISSING_REQUIRED_FIELD`, `INVALID_TIMESTAMP`, `UNKNOWN_TIMESTAMP_UNIT`, `INVALID_INSTRUMENT`, `UNSUPPORTED_EVENT_TYPE`, `INVALID_NUMERIC_VALUE`, `INVALID_PROVIDER_IDENTIFIER`, `INSUFFICIENT_PROVENANCE`, `UNDETERMINABLE_AVAILABILITY`, `MALFORMED_PAYLOAD`, `UNSUPPORTED_PROVIDER_RECORD`.

## Future build boundaries

| Build | Owns |
|-------|------|
| BUILD 04 | Quality/capability evaluation, provider ranking, conflict resolution |
| BUILD 04.5 | MongoDB / intelligence persistence |
| BUILD 05 | Immutable snapshot persistence |
| BUILD 06 | Features/signals |
| BUILD 07 | Replay runtime |

BUILD 03 owns none of those. No MongoDB, no persistence, no feature calculation, no replay scheduler.

## Related docs

- `docs/engineering/INTELLIGENCE_CONTRACTS_V1.md` — BUILD 01 contracts
- `docs/engineering/TEMPORAL_INTEGRITY_V1.md` — BUILD 02 temporal rules
- `docs/engineering/INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md` — BUILD 04.5 persistence
