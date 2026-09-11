# Strategy Readiness Model

**Classification:** `CURRENT_CANONICAL_RESEARCH_GOVERNANCE`  
**Purpose:** prevent one vague maturity label from implying readiness that has not been earned.

## Readiness vector

Every strategy/signal family is tracked independently across these axes:

| Axis | Question |
|---|---|
| Research maturity | Is the mechanism, literature, contradictory evidence and hypothesis set adequately specified? |
| Data readiness & rights | Are PIT-valid sources, coverage, entitlement and intended-use rights sufficient? |
| Signal/strategy implementation | Does governed implementation exist and match the research definition? |
| Historical/OOS validation | Has it survived preregistered historical/out-of-sample testing? |
| Prospective shadow | Has it operated prospectively without execution under real incoming information? |
| Paper execution | Has it completed governed Paper observations for the claimed scope? |
| Execution-model calibration | Is the simulator calibrated enough for the implementability claim being made? |
| Opportunity Engine integration | Can it emit the canonical Opportunity Contract and preserve provenance? |
| Portfolio/risk integration | Can authoritative risk/portfolio logic evaluate and constrain it correctly? |
| Live eligibility | Has separately governed Live authorization/qualification been granted? |

## Per-axis state vocabulary

Use one of:

- `NOT_STARTED`
- `PLANNED`
- `IMPLEMENTED`
- `VALIDATED`
- `BLOCKED`
- `NOT_APPLICABLE`

`VALIDATED` requires linked evidence appropriate to the axis. A software test can validate implementation behavior but cannot validate historical alpha, prospective edge, simulator realism or Live eligibility.

## Non-transitivity

Readiness axes do not automatically promote one another.

Examples:

- `Research maturity = VALIDATED/strongly specified` does not imply `Data readiness = VALIDATED`.
- `Historical/OOS validation = VALIDATED` does not imply `Paper execution = VALIDATED`.
- `Paper execution = VALIDATED` does not imply `Execution-model calibration = VALIDATED` unless the relevant calibration contract passed.
- No combination of research/OOS/Paper states automatically sets `Live eligibility = VALIDATED`.

## Summary labels

A UI or registry may show a compact summary such as `RESEARCH_READY`, `OOS_READY`, `SHADOW_READY`, `PAPER_READY`, or `BLOCKED`, but it must be derived from and link back to the readiness vector. The summary label cannot erase blocking axes.

## Promotion examples

### OOS-ready

Requires at minimum adequate research specification, sufficient historical/PIT data rights, governed implementation, frozen experiment design and no known leakage blocker.

### Shadow-ready

Requires OOS disposition appropriate to the hypothesis plus prospective-capable data/provider paths and time/provenance controls.

### Paper-ready

Requires shadow/operational readiness, authoritative Paper mode/risk/account boundaries, asset-specific execution semantics and any calibration prerequisites required by the intended claim.

### Live-eligible

Separate governance only. It is never inferred from this document and remains false/blocked unless explicitly authorized by the applicable Live safety process.

## Registry requirement

The Strategy & Signal Research Registry may retain prose summaries, but canonical status must be expressible using this vector. Future implementation should avoid a single `maturity` field as the source of truth.
