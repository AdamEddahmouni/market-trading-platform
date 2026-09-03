# Expert Blackboard & Blind Multi-Expert Council V1 (BUILD 12)

> BUILD 12 coordinates independently scheduled specialists through a sealed blind first pass, publishes their immutable EvidenceV1 outputs to a read-only evidence blackboard only after all participants are terminal, analyzes agreement/conflict with explicit provenance correlation, and opens a bounded deliberation phase only when meaningful conflict justifies it.

## Why blindness exists

Early expert output can anchor later experts. Blind-first-pass reduces confirmation bias, herding, premature consensus, and cross-expert contamination.

**Persistence ≠ visibility.** EvidenceV1 may be persisted before all participants finish, but still-running blind specialists must not query it.

## Canonical flow

```
CouncilPlan (frozen participants)
        │
        ▼
BLIND FIRST-PASS BARRIER
        │
        ├── each specialist receives only its own frozen context
        ├── each specialist executes through BUILD 10
        └── each emits independent EvidenceV1
        │
        ▼
ALL PARTICIPANTS TERMINAL
        │
        ▼
BLACKBOARD PUBLICATION (immutable EvidenceV1 refs)
        │
        ▼
EVIDENCE RELATION ANALYSIS (agreement/conflict/orthogonal/incomparable + provenance)
        │
        ▼
DELIBERATION GATE
        ├── NOT_REQUIRED (default)
        └── REQUIRED → bounded second-pass request
```

## Council phases

| Phase | Meaning |
|-------|---------|
| `PLANNED` | Frozen council plan sealed |
| `BLIND_RUNNING` | Awaiting terminal participant outcomes |
| `BLIND_TERMINAL` | All participants terminal |
| `BLACKBOARD_PUBLISHED` | Blind blackboard revision 1 published |
| `RELATIONS_ANALYZED` | Relation report computed |
| `DELIBERATION_NOT_REQUIRED` | Gate closed without second pass |
| `DELIBERATION_REQUIRED` | Structured deliberation request issued |
| `DELIBERATION_COMPLETE` | Optional deliberation blackboard revision 2 |
| `CLOSED` | Council result finalized |

## Production specialist coverage

| Domain | Production specialist | Blind pass | Deliberation pass |
|--------|----------------------|------------|-------------------|
| MICROSTRUCTURE | `MicrostructureSpecialist` | Yes | Not required in v1 |

Multi-expert council infrastructure is implemented and tested with **deterministic synthetic test specialists** under `tests/intelligence/`. These are not production domain implementations.

## Blackboard

The blackboard is an immutable published view of independently produced EvidenceV1 references and participant outcomes. It is **not** a shared scratchpad, chat room, or agent memory.

- Identity: `evidence-blackboard-sha256-v1`
- Revision 1: blind-pass evidence only
- Revision 2: blind + permitted deliberation-pass evidence (revision 1 remains immutable)

## Provenance resolution

Explicit lineage only:

```
EvidenceV1.source_signal_refs → SignalV1 → source_event_refs → EventV1
EvidenceV1.source_event_refs → EventV1
```

No broad repository expansion (`query all evidence/signals/events for snapshot`).

### Source correlation v1 rules

| Condition | Classification |
|-----------|----------------|
| Same non-empty terminal source set | `STRONGLY_CORRELATED` |
| Any terminal-source overlap | `CORRELATED` |
| Disjoint non-empty terminal sets | `SOURCE_INDEPENDENT` |
| Missing provenance | `UNKNOWN` |

**False consensus example:** three EvidenceV1 records all derived from signal S1 are one shared provenance group — not three independent confirmations.

## Comparability

Relations are computed only when comparison adapters produce a valid `comparison_key` and matching scope.

| Relation | Meaning |
|----------|---------|
| `AGREES` | Comparable evidence points same direction (agreement ≠ truth) |
| `CONFLICTS` | Comparable opposing evidence (conflict ≠ expert failure) |
| `ORTHOGONAL` | Both may be valid but different dimensions |
| `INCOMPARABLE` | No safe comparison adapter |

Microstructure examples:

- `ORDER_FLOW_TRANSITION` with same scope/semantic event: comparable directional conflict/agreement
- `LIQUIDITY_STRESS` vs `ORDER_FLOW_TRANSITION`: orthogonal

## No voting / no fusion

BUILD 12 does **not** use majority voting, expert weights, consensus probability, or final market direction.

BUILD 13 consumes blackboard evidence to form composite hypotheses. BUILD 14 handles fusion/calibration.

## Deliberation gate

| Outcome | Typical condition |
|---------|-------------------|
| `INSUFFICIENT_EVIDENCE` | Single production specialist council |
| `NO_COMPARABLE_EVIDENCE` | No operational comparable evidence |
| `NOT_REQUIRED` | Agreement, orthogonal-only, or policy-disabled |
| `REQUIRED` | Independent (or policy-allowed correlated) comparable conflict |

Default `max_deliberation_rounds = 1`.

## BUILD boundaries

| Build | Authority |
|-------|-----------|
| BUILD 09 | Routing |
| BUILD 10 | Scheduling |
| BUILD 11 | Specialist evidence creation |
| BUILD 12 | Blind coordination + evidence relation analysis |
| BUILD 13 | Hypothesis synthesis |
| BUILD 14 | Fusion/calibration |

## Cross-links

- [Microstructure Specialist V1](./MICROSTRUCTURE_SPECIALIST_V1.md)
- [Inference Scheduler V1](./INFERENCE_SCHEDULER_V1.md)
- [Event Detector & Smart Router V1](./EVENT_DETECTOR_SMART_ROUTER_V1.md)
- [Intelligence Contracts V1](./INTELLIGENCE_CONTRACTS_V1.md)

## Package location

```
src/market_platform_foundation/intelligence/council/
```

Public API includes `CouncilPlan`, `CouncilPolicy`, `BlindCouncilOrchestrator`, `BlackboardSnapshot`, `EvidenceRelationReport`, `DeliberationGate`, and `SpecialistRegistry`.
