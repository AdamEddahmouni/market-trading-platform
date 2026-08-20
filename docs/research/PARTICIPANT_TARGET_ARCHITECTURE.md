# Participant Intelligence — Target Architecture (Deliverable 5)

**Schema version:** `participant.v1`  
**Code:** `src/market_platform_foundation/contracts/participant.py`  
**Bridge:** `src/market_platform_foundation/participant/bridge.py`

---

## Lane position

```text
PLATFORM (time, identity infra, provenance, quality, EV)
│
├── DOMAIN INTELLIGENCE
│   ├── Short Squeeze / Options / Futures / Crypto* / Prediction*
│
└── CROSS-DOMAIN INTELLIGENCE
    ├── Order Flow (microstructure primitives)
    ├── Market Context (information / catalyst)
    └── Participant Intelligence (identity + intent + copyability)
```

Participant Intelligence **strengthens** domain lanes via evidence contracts. It does **not** set squeeze state, P vs Q, COT interpretation, or news extraction.

---

## Ownership (Participant Intelligence owns)

| Concept | Contract | Status |
|---|---|---|
| Participant types | `ParticipantType` | PI1 IMPLEMENTED |
| Identity confidence | `IdentityConfidence` | PI1 IMPLEMENTED |
| Entity graph edges | `ParticipantRelationship` | PI1 IMPLEMENTED (schema) |
| Action semantics | `ParticipantAction`, `ParticipantActionType` | PI2 IMPLEMENTED |
| Insider discretion | `InsiderDiscretion` | PI2 IMPLEMENTED |
| Mechanism taxonomy | `ParticipantMechanism` | PI7 schema stub |
| Research classifications | `ParticipantResearchClassification` | PI7 schema |
| Cross-lane envelope | `ParticipantEvidenceEnvelope` | PI3 schema |
| Participant skill | Walk-forward shrinkage (PI5) | **PI5 IMPLEMENTED** |
| Copyability / entry quality | TBD | PI9 **IMPLEMENTED** (fixture) |
| Metaorder interpretation | TBD | PI6 **IMPLEMENTED** (consumes OF) |

## Does NOT own

CVD, OFI, DOM, options open/close, dealer gamma, COT categories, squeeze states, news extraction, physical P, shared EV.

---

## Data flow

```text
SOURCES                    EXISTING WHALE LEDGER           PARTICIPANT LANE
────────                   ─────────────────────           ────────────────
Form 4/13D/13F/13G    →    regulatory_disclosure      →    ParticipantIdentity
Large prints          →    large_transactions         →    ParticipantAction (anonymous)
Order flow            →    order_flow                 →    MetaorderEvidence (PI6)
Options activity      →    options                    →    consume O5 semantics
COT                   →    (F4 engine, not ledger)    →    cross-asset context
Crypto transfers*     →    (future)                   →    CryptoEntityFlowEvidence

                              ↓
                    INTENT / MECHANISM (PI7)
                              ↓
                    SKILL / COMMITMENT / HORIZON (PI5)
                              ↓
                    COPYABILITY / ENTRY QUALITY (PI9)
                              ↓
                    ParticipantEvidenceEnvelope
                              ↓
              Short Squeeze / Options / Futures / Context / EV
```

---

## Point-in-time rules (mandatory)

| Source | `action_time` | Copyable `available_time` |
|---|---|---|
| Form 4 transaction | Trade date (when parsed) | Filing acceptance / dissemination |
| 13D accumulation | Purchase dates in filing | Filing publication |
| 13F holding | Quarter end (behavior research only) | Filing publication |
| Metaorder | Child trade times | Same as Order Flow |
| Crypto entity label | Transfer time | `label_available_time` |

---

## Entity graph (PI1)

Supported relationship types:

- `person → officer_of → issuer`
- `fund → managed_by → investment_manager`
- `wallet → clustered_with → wallet_cluster`
- `wallet_cluster → attributed_to → entity`
- `ETF → advised_by → asset_manager`

Use shared platform identity keys; do not double-count affiliated funds without independence evidence.

---

## Cross-lane evidence contracts (PI3 target)

| Contract | Producer | Consumers |
|---|---|---|
| `ParticipantEvidence` | Participant | All lanes |
| `InsiderEvidence` | Participant | SS, Context, EV |
| `ActivistEvidence` | Participant | SS, Context |
| `InstitutionalHoldingEvidence` | Participant | SS crowding, Context | PI4 IMPLEMENTED |
| `MetaorderEvidence` | Participant (from OF) | SS, OF execution | PI6 IMPLEMENTED |
| `ForcedFlowEvidence` | Participant | SS, fade research |
| `ParticipantCrowdingEvidence` | Participant | SS, Futures |
| `CopyabilityEvidence` | Participant | Shared EV |
| `ParticipantSkillEvidence` | Participant | SS, Context, ignition cards | PI5 IMPLEMENTED |

Each envelope requires: `event_time`, `available_time`, `identity_confidence`, `mechanism`, `directional_clarity`, `horizon`, `quality_flags`, `producer_version`.

---

## Implementation map

| Module | Purpose |
|---|---|
| `contracts/participant.py` | Canonical types |
| `participant/bridge.py` | Disclosure → action |
| `participant/skill.py` | PI5 walk-forward skill |
| `participant/metaorder.py` | PI6 metaorder lifecycle |
| `participant/mechanism.py` | PI7 (future) |
| `participant/copyability.py` | PI9 copyability scoring |

---

## Research status labels

Every capability must carry `ResearchStatus`: RESEARCHED | IMPLEMENTED | VALIDATED | EXPERIMENTAL | UNAVAILABLE.

PI1–PI2: **IMPLEMENTED** (contracts + disclosure bridge).  
PI3–PI4: **IMPLEMENTED** (disclosure enrichment + 13F QoQ).  
PI5: **IMPLEMENTED** (walk-forward skill + cross-lane publish).  
PI6: **IMPLEMENTED** (metaorder lifecycle + cross-lane publish).  
PI7+: **PLANNED** until validated.
