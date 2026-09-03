# ADR 0042: Methodology validation is distinct from outcome confirmation

## Status

Accepted (Phase 2V).

## Context

Phase 2V exists because a candidate was reported to have moved favourably after the
platform surfaced it. The obvious reading — the platform worked — conflates two claims
that rest on entirely different evidence:

- **The stock moved afterward.** Established by market data after detection.
- **The methodology was valid.** Established by showing the original decision reproduces
  from evidence that existed at detection, with accurate semantics.

The second does not follow from the first. A screener that surfaces every stock up 10%
will surface some that continue rising; the subsequent move says nothing about whether
the selection logic was sound. This is especially sharp here, because the original
classification rule read no squeeze mechanic at all (see
`docs/phase-2v-original-rule-manifest.md`) — so a favourable outcome would be entirely
consistent with a momentum filter that happened to catch a mover.

The risk is not that someone would state the fallacy outright. It is that a permissive
model would let it happen quietly: attach a strong outcome to a thin case, and the
headline conclusion drifts upward.

## Decision

Methodology conclusion and outcome observation are **separate models, produced by
separate functions, and never merged**.

The conclusion is **derived**, not authored. `derive_conclusion()` is a deterministic
function of detection state, recovered-value count, rule classifications, comparison
states, and outcome availability — so a case's headline cannot drift from its support.

The derivation is ordered so that **the unrecoverable-original branch is evaluated first
and outcome data cannot escape it**. Concretely: when no original field value survives,
the conclusion is `INSUFFICIENT_EVIDENCE` regardless of how favourable an attached
outcome is. Where an outcome is present in that branch it adds a *finding* and a
*limitation* recording that outcome confirmation does not upgrade the conclusion — it
never changes the conclusion itself.

`OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED` exists for the genuinely different case where
original values *do* survive, the symbol *did* move, and the artifacts still cannot show
the method produced the result validly.

A test asserts the invariant directly: the same case, with and without a strongly
positive outcome, yields the identical conclusion.

## Consequences

The BIYA case concludes `INSUFFICIENT_EVIDENCE`. Producing market data for BIYA later
will not change that, because no original value exists to compare against. This is the
intended behaviour, and it is why acquiring the price series was not treated as
unblocking work.

`INSUFFICIENT_EVIDENCE` must be read as a statement about the surviving record, not a
verdict that the original platform was wrong. Both the root-cause report and the public
demonstration say so explicitly, because the label invites the harsher reading.

A future case with rich original values and a measured outcome can reach
`VALIDATED_AS_RECORDED` or `PARTIALLY_VALIDATED` — the framework is not biased toward
pessimism, only toward requiring the evidence the claim needs.
