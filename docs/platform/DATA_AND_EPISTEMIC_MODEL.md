# IMP data and epistemic model

| Field | Value |
|---|---|
| Document ID | `IMP-DATA-EPISTEMIC-MODEL` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` with approved future analytical structure |
| Canonical Subject | Evidence classes, provenance, hypotheses, narrative, and motive method |
| Owner Role | IMP research and epistemic governance owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | No prior current whole-program epistemic model |
| Superseded By | None |

This document defines program-level analytical meaning. It creates no runtime
schema and does not replace existing event, evidence, hypothesis, prediction,
quality, or provenance contracts.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Evidence classes

| Class | Meaning | Required discipline |
|---|---|---|
| `OBSERVED_FACT` | Directly measured or captured event/state with source and time context | Preserve raw/source reference, clocks, revisions, quality, and limits of observation. |
| `REPORTED_FACT` | Factual claim reported by a source but not independently observed by IMP | Attribute the source and distinguish report time from event time. |
| `STATED_RATIONALE` | An actor's official or reported explanation for action | Treat as evidence of what was stated, not automatic proof of cause. |
| `INFERRED_BEHAVIOR` | A reasoned interpretation of observable actions or patterns | Record method, inputs, alternatives, confidence, and contradicting evidence. |
| `INFERRED_MOTIVE` | A hypothesis about incentives or intent | Never present as a secret true motive; retain alternatives and falsifiers. |
| `NARRATIVE` | A circulating framing that may shape attention, positioning, or price | Evaluate factual support separately from reach and market impact. |
| `HYPOTHESIS` | A testable explanation or forecast with explicit supporting/contradicting evidence | Preserve alternatives, status, and practical falsifiers. |
| `MODEL_OUTPUT` | A versioned computational result under identified inputs and settings | Preserve model/data/config/cutoff lineage; output is not fact or authority by itself. |

## Epistemic invariants

- An official statement is evidence; it is not automatic causal truth.
- An alternative motive is a hypothesis; it is not automatic causal truth.
- Supporting and contradicting evidence are both retained.
- Hypotheses preserve competing alternatives.
- Falsifiers are defined where practical.
- Narrative factual support and narrative market impact are separate.
- Source-incentive context is provenance metadata, not proof.
- Timing, revealed behavior, revisions, and methodological limits matter.
- A model output, narrative, or motive hypothesis does not grant risk,
  qualification, release, or execution authority.

Evidence must carry the best available event, publication, provider-receipt,
platform-availability, decision-cutoff, and revision context supported by the
controlling contracts. The point-in-time law and executable temporal controls
remain in [`contracts/common.py`](../../src/market_platform_foundation/intelligence/contracts/common.py)
and related temporal/normalization code.

## Narrative and reflexivity — approved future design

Future narrative analysis may keep separate dimensions for factual support,
reach, velocity, persistence, fear intensity, market confirmation,
institutional confirmation, and reflexive impact. These dimensions must not be
collapsed into a universal truth or authority score.

> A narrative may influence positioning and price even when its factual support is weak.

Current market-context, sentiment, and selected fixture-derived narrative
features are reusable foundations. A canonical live narrative engine is not
implemented.

## Motive hypotheses — approved future design

```text
actor
  -> observed actions
  -> stated rationales
  -> incentives
  -> timing
  -> market effects
  -> competing motive hypotheses
```

Future structured motive hypotheses preserve support, contradiction,
alternatives, falsifiers, and confidence/status. They may inform research but
cannot assert a “secret true motive” or create execution authority. A canonical
motive engine is not implemented.

## Separation of epistemics and authorization

Evidence class describes what kind of claim is being handled. Quality describes
its fitness under scoped criteria. Maturity describes implementation state.
Authority describes who or what may decide. None of these axes substitutes for
another, and uncertainty is preserved rather than hidden by a single score.
