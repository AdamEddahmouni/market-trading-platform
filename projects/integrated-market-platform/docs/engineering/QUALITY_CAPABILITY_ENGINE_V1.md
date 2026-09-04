# Quality & Capability Engine V1

BUILD 04 establishes the canonical quality-and-capability layer for the
Integrated Market Platform intelligent engine. It determines whether normalized,
temporally valid source information is trustworthy and operationally usable for a
particular downstream purpose.

## Pipeline position

```text
BUILD 03 — Provider Normalization & Provenance
        ↓
BUILD 04 — Quality & Capability Engine
        ↓
BUILD 04.5 — Intelligence Persistence Architecture
        ↓
BUILD 05 — Immutable Snapshot Engine
```

## Three levels (mandatory separation)

BUILD 04 separates observation, assessment, and decision:

```text
FINDING      objective detected fact
ASSESSMENT   structured capability/quality state
DECISION     caller-facing USE / DEGRADE / ABSTAIN / FAIL_CLOSED
```

Example:

```text
Finding:     BORROW_STALE
Assessment:  borrow supported and available, but freshness requirement not met
Decision:    ABSTAIN for a task requiring fresh borrow
```

A finding does **not** universally imply a decision. Policy plus caller
requirements determine the action.

## Public API

```python
from market_platform_foundation.intelligence.quality import (
    assess_capabilities,
    inspect_quality,
    require_quality_decision,
    select_usable_source,
    quality_summary_from_assessment,
)
```

Module path: `src/market_platform_foundation/intelligence/quality/`.

### Audit API (non-throwing)

`inspect_quality(...)` returns a `QualityAssessment` with findings, capability
assessments, and provider health observations.

### Strict API (fail-closed)

`require_quality_decision(...)` returns a `QualityDecision` or raises
`QualityCapabilityError` when action is `FAIL_CLOSED`.

## Quality vs temporal legality

BUILD 02 remains authoritative for temporal truth.

```text
available_time_ns <= decision_time_ns
```

`FUTURE_INFORMATION` is not merely degraded quality. BUILD 04 maps BUILD 02
violations into quality findings but **never** makes future information usable,
regardless of policy.

Staleness (`STALE_INFORMATION`, `BORROW_STALE`, `SHORT_INTEREST_STALE`) is
distinct from temporal illegality.

## Quality vs predictive value

BUILD 04 evaluates information trustworthiness, availability, freshness,
structural validity, and completeness. It does **not** assign predictive
importance, profitability, or provider reputation scores.

## Capability dimensions

Capability health is multi-dimensional:

| Dimension | Question |
|-----------|----------|
| `support` | Does the provider technically support this capability? |
| `availability` | Is it currently reachable/entitled/subscribed? |
| `freshness` | Is it fresh enough for the caller requirement? |
| `completeness` | Is the record complete enough? |
| `validity` | Is the payload structurally valid? |
| `conflict` | Do independent providers disagree beyond tolerance? |
| `temporally_legal` | Is BUILD 02 eligibility satisfied? |

These must not collapse into a single `has_capability` boolean.

### Support vs entitlement vs availability

```text
support = SUPPORTED, availability = UNAVAILABLE, reason = NOT_ENTITLED
```

is different from:

```text
support = UNSUPPORTED
```

and different from:

```text
connection = DISCONNECTED → PROVIDER_DISCONNECTED
```

## Decision actions

| Action | Meaning |
|--------|---------|
| `USE` | Requirements satisfied at acceptable quality |
| `DEGRADE` | Core requirements usable; optional/lower-priority evidence degraded |
| `ABSTAIN` | Insufficient evidence quality for the requested analytical task |
| `FAIL_CLOSED` | Hard invariant or mandatory capability violated; processing must stop |

`ABSTAIN` ≠ `FAIL_CLOSED`. Example: missing optional historical OI may `ABSTAIN`
for a predictive engine; a crossed top-of-book under a valid-quote policy should
`FAIL_CLOSED`.

## Canonical finding taxonomy

BUILD 04 reuses existing platform flags where possible:

```text
CROSSED_BOOK
INVALID_QUOTE
LOCKED_BOOK
PARTIAL_DATA
PROVIDER_DISCONNECTED
CAPABILITY_UNAVAILABLE
NOT_ENTITLED
NOT_SUBSCRIBED
BORROW_STALE
SHORT_INTEREST_STALE
CLOCK_DRIFT
PROVIDER_CONFLICT
FUTURE_INFORMATION
STALE_INFORMATION
CONFLICTING_DUPLICATE
```

Quote validation reuses `market_data.quality.assess_quote` via a thin adapter for
normalized intelligence payloads (`bid`/`ask` → `bid_price`/`ask_price`).

## BUILD 01 QualitySummary integration

Detailed assessments compress deterministically:

```python
summary = quality_summary_from_assessment(assessment)
```

`QualitySummary.state` uses BUILD 01 semantics:

```text
GOOD | DEGRADED | INVALID | UNKNOWN
```

Flags preserve canonical finding codes for auditability.

## Provider conflicts

Conflict detection requires:

- same canonical instrument
- same capability / measurement
- comparable values
- independent providers
- both observations structurally valid

Tolerance is policy-driven (`price_conflict_tolerance_bps`). BUILD 04 does not
average, blend, or silently pick a winner. Conflicts remain visible in findings
and decisions.

## Provider health input

BUILD 04 consumes explicit runtime observations via `ProviderHealthSnapshot` and
`ProviderCapabilityObservation`. It performs no network calls, polling, or
provider authentication.

## Policy

`QualityPolicy` is immutable and versioned (`policy_id`, `policy_version`).
Defaults are conservative: invalid required data fails closed; optional gaps
degrade; unknown mandatory state abstains.

Freshness thresholds are capability-specific via `freshness_max_age_ns` — no
hidden global stale defaults.

## Determinism and purity

Given identical:

```text
normalized events
temporal reports
provider health
requirements
policy
decision_time_ns
```

the engine produces identical semantic results. Core logic does not call wall
clock APIs, access databases, or mutate input records.

## No data repair

BUILD 04 detects and classifies problems. It does not:

```text
swap bid/ask
clamp invalid values
average conflicting providers
forward-fill missing fields
repair timestamps
```

## Future build boundaries

| Build | Responsibility |
|-------|----------------|
| BUILD 04.5 | Persistence / repository abstraction (MongoDB evaluated there) |
| BUILD 05 | Immutable intelligence snapshot engine |
| BUILD 06 | Feature/signal calculations |
| BUILD 07 | Replay runtime |
| BUILD 09+ | Expert routing / intelligence fusion |

BUILD 09 routing semantics are defined in [Event Detector & Smart Router V1](./EVENT_DETECTOR_SMART_ROUTER_V1.md); BUILD 04 remains the sole authority for `USE`, `DEGRADE`, `ABSTAIN`, and `FAIL_CLOSED` decisions.

BUILD 04 does not implement persistence, snapshots, features, replay, expert
routing, execution authority, or live-order paths.

## Related documents

- `docs/engineering/INTELLIGENCE_CONTRACTS_V1.md` — BUILD 01 contracts and `QualitySummary`
- `docs/engineering/TEMPORAL_INTEGRITY_V1.md` — BUILD 02 temporal rules
- `docs/engineering/INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md` — BUILD 04.5 persistence
- `docs/engineering/PROVIDER_NORMALIZATION_V1.md` — BUILD 03 normalization

## BUILD 04.5 handoff

Public records (`QualityFinding`, `CapabilityAssessment`, `QualityDecision`,
`ProviderHealthSnapshot`, `QualityPolicy`) are JSON-safe immutable value objects
designed for later persistence behind an `IntelligenceRepository` abstraction.
BUILD 04.5 will add storage; BUILD 04 defines semantics only.
