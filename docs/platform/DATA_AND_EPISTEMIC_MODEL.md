# IMP data and epistemic model

| Field | Value |
|---|---|
| Document ID | `IMP-EPISTEMIC-MODEL` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Analytical evidence, claim, inference, narrative, and hypothesis method |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current program-wide epistemic method |
| Superseded By | None |

This document defines analytical method and controlled vocabulary. It does not
create runtime schemas, a universal ontology, a scalar truth score, or any
execution authority.

## Epistemic roles

| Role | Meaning |
|---|---|
| `OBSERVED_FACT` | A directly measured event or state within defined provenance and temporal limits. Observation and measurement error remain possible. |
| `REPORTED_CLAIM` | An assertion attributed to a source. The label makes no verification claim and requires provenance, timing, and corroboration treatment. |
| `STATED_RATIONALE` | An actor's declared explanation for an action or policy. It is evidence of what was stated, not automatic proof of actual motive. |
| `INFERRED_BEHAVIOR` | Behavior interpreted from observed or reported actions or patterns rather than directly asserted by the actor. |
| `INFERRED_MOTIVE` | A structured causal-intent hypothesis. It is never a secret “true motive” field. |
| `NARRATIVE` | A proposition, story, or framing plus its dissemination characteristics among relevant actors or market participants. Prevalence is not truth. |
| `HYPOTHESIS` | A testable analytic proposition that may combine evidence roles and should retain support, contradictions, alternatives, and falsifiers where material. |
| `MODEL_OUTPUT` | A statistical, ML, or AI-derived estimate or classification with model and input provenance. A model result is not observational fact or authority. |

These roles are not mutually exclusive rungs on one truth ladder. One source
item may support several separate analytic records, and a hypothesis may
reference observations, reported claims, narratives, and model outputs.
`REPORTED_FACT` is not an IMP role; reporting an assertion does not verify it.

## Orthogonal dimensions

Keep these dimensions separate:

- provenance, source identity, jurisdiction, ownership, and collection method;
- event, publication, receipt, availability, decision, and revision time;
- direct observation versus source assertion;
- corroborating and contradicting evidence;
- analytic confidence and uncertainty;
- factual support;
- belief prevalence;
- narrative reach, velocity, and persistence;
- market confirmation and market impact;
- model, input, configuration, and code provenance for model outputs.

Confidence belongs to an observation-quality or analytic-assessment context,
not to a source label alone. Conflicting reports remain represented with source
and timing. Revisions append or supersede with lineage; they do not silently
rewrite prior evidence.

## Invariants

- An official statement is not automatic causal truth.
- An alternative-motive account is not automatic causal truth.
- Supporting and contradicting evidence both matter.
- Material hypotheses retain alternatives and practical falsifiers.
- A narrative's factual support is different from its market influence.
- Source incentive context is not proof of truth or falsehood.
- Timing, revisions, methodology, and provenance affect interpretation.
- Model output, research, prediction, narrative, and motive inference do not
  grant risk, release, session, order, or broker authority.

Source-incentive analysis is actor-neutral. Relevant context may include
self-interest, institutional mandate, reporting incentives, legal constraints,
methodology, revision practice, timing, jurisdiction, ownership, and
self-reporting. No government, private, media, or other source is reliable or
unreliable by category alone.

## Hypothesis discipline

For material causal or motive questions, use competing hypotheses rather than
a preferred story encoded as fact:

| Element | Required treatment |
|---|---|
| H1 / H2 / H3 | Distinct plausible explanations |
| Supporting evidence | Evidence that raises the plausibility of that hypothesis |
| Contradicting evidence | Evidence that lowers its plausibility |
| Timing consistency | Whether event, publication, availability, and reaction timing fit |
| Incentive consistency | Whether known incentives support the explanation without proving it |
| Market consistency | Whether observed price, flow, volatility, or positioning is consistent, while allowing alternatives |
| Falsifiers | Observations that would materially weaken or reject the hypothesis |

Do not create an `actor_secret_true_motive` field. A stated rationale remains a
`STATED_RATIONALE`; an analyst's causal-intent interpretation remains an
`INFERRED_MOTIVE` or `HYPOTHESIS`.

## Narrative treatment

Assess separately:

1. whether the narrative's propositions have factual support;
2. who appears to believe or repeat it;
3. its reach, velocity, persistence, and audience;
4. whether markets confirm, ignore, or oppose it;
5. whether observed impact could have competing causes.

A false proposition can influence markets, and a well-supported proposition may
have little market influence. Neither dimension substitutes for the other.

## Canonical identity across domains

A canonical instrument or asset identity may participate in multiple analytical
domains without being duplicated into disconnected identities:

```text
Gold
|- commodity analysis
|- monetary and reserve analysis
```

The same principle may later apply to Treasuries, currencies, stablecoins,
crypto assets, or other instruments. This is an identity-participation
principle, not an implemented schema or universal ontology.

## Hypothesis-neutral cross-asset relationships

Future Japan/rates/FX intelligence may relate JPY, JGBs, BOJ actions, FX
intervention, reserve activity, Treasury holdings, cross-border flows, and
hedging costs. Records must preserve source and time, distinguish observation
from claim, and support competing causal explanations. No official, user, or
alternative account is predetermined as fact.
