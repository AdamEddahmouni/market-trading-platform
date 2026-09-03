# Candidate Validation Contract

> Phase 3B relationship: original-platform surfaced status remains an independent comparison field. It cannot modify research detection, retrospective outcome labeling, or research classification.

## Additive outcome amendment contract

Historical acquisition occurs only in controlled scripts. Deterministic core code
accepts explicit manifests and fixed raw bytes, verifies SHA-256, normalizes through
existing Phase 1 contracts where compatible, and produces a separate BIYA amendment.
The only amendment conclusions are `OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED` and
`INSUFFICIENT_EVIDENCE`. A historical outcome can never produce
`VALIDATED_AS_RECORDED` without original values.

What `squeeze_core.validation` guarantees, and what it deliberately refuses to do.

## 1. Scope

A **validation case** answers one question about one historical candidate
identification:

> Can the original decision be reproduced from evidence that existed at the moment it
> was made, with materially accurate semantics?

It does not answer whether the candidate was a good trade, whether the symbol
subsequently moved, or whether the approach works in general.

## 2. Vocabularies

Each is closed. Adding a member is a contract change requiring an ADR.

| Vocabulary | Members |
| --- | --- |
| `DetectionTimeState` | `EXACT_TIMESTAMP`, `BOUNDED_TIME_WINDOW`, `UNKNOWN` |
| `ArtifactReliabilityClass` | `DIRECT_PLATFORM_RECORD`, `DERIVED_FROM_PLATFORM_RECORD`, `EXTERNAL_CORROBORATION`, `FILESYSTEM_METADATA_ONLY`, `USER_RECOLLECTION`, `UNKNOWN` |
| `OriginalValueState` | `RECOVERED`, `MISSING_IN_ARTIFACT`, `DEFAULT_SUBSTITUTED`, `DERIVED`, `AMBIGUOUS`, `UNKNOWN` |
| `ComparisonState` | `MATCH`, `MATCH_WITH_NORMALIZATION`, `DIFFERENT_VALUE`, `DIFFERENT_SEMANTICS`, `ORIGINAL_MISSING`, `REBUILT_UNAVAILABLE`, `ORIGINAL_DEFAULT_SUBSTITUTION`, `ORIGINAL_MISLABELED`, `INCOMPARABLE`, `UNKNOWN` |
| `RuleValidationState` | `SUPPORTED`, `SUPPORTED_WITH_CORRECTION`, `MOMENTUM_DISCOVERY_ONLY`, `MISLABELED`, `STALE`, `UNAVAILABLE_AT_DETECTION`, `MISSING_DEFAULT_SUBSTITUTION`, `REDUNDANT`, `UNSUPPORTED`, `UNKNOWN` |
| `MethodologyConclusion` | `VALIDATED_AS_RECORDED`, `PARTIALLY_VALIDATED`, `OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED`, `NOT_POINT_IN_TIME_VALID`, `INSUFFICIENT_EVIDENCE` |
| `CaseStatus` | `COMPLETE`, `PARTIAL`, `ARTIFACT_DISCOVERY_ONLY`, `BLOCKED_MISSING_DETECTION_TIME`, `BLOCKED_MISSING_ORIGINAL_OUTPUT`, `BLOCKED_MISSING_MARKET_DATA` |

None of these is a candidate-quality or trading label, and none may become one.

## 3. Guarantees

**Unknown never becomes zero.** `OriginalFieldValue` rejects a value in any state other
than `RECOVERED`, `DERIVED`, `DEFAULT_SUBSTITUTED`, or `AMBIGUOUS`. A field the artifacts
do not record cannot be given a value, at construction or through a case spec.

**Absolute local paths never reach canonical bytes.** `ValidationArtifact.relative_path`
rejects drive-rooted, UNC, and POSIX-absolute paths, so no hash and no export can depend
on the operator's filesystem layout.

**Sensitive artifacts cannot be published.** An artifact that is both `sensitive` and
`included_in_public_demo` fails validation, and the public exporter additionally filters
on both flags.

**Exact detection time requires a direct platform record.** Only an embedded event time
on a `DIRECT_PLATFORM_RECORD` yields `EXACT_TIMESTAMP`. Filesystem metadata, screenshots,
emails, and recordings bound a window.

**Conflicting evidence widens rather than resolves.** Two direct records disagreeing on
the event time produce a window spanning both claims and a
`VALIDATION_DETECTION_TIME_CONFLICTED` diagnostic — never a silent choice.

**Bounded detection means multiple replays.** `replay_boundaries()` returns both edges,
and callers replay all of them. Selecting the more favourable result is not expressible.

**No second point-in-time engine.** All as-of eligibility comes from
`build_point_in_time_evidence`; all structural diagnostics come from
`squeeze_core.readiness`. A test asserts `replay.py` contains no timestamp comparison
against `as_of`.

**Semantic incompatibility is checked before value comparison.** Units known to measure
different quantities yield `DIFFERENT_SEMANTICS`, never `DIFFERENT_VALUE`.

**Conclusions are derived, not authored.** `derive_conclusion()` is a deterministic
function of detection state, recovered-value count, rule classifications, comparison
states, and outcome availability.

**Outcome cannot upgrade a conclusion.** A case with no recoverable original values
concludes `INSUFFICIENT_EVIDENCE` regardless of how favourable an attached outcome is.
See ADR 0042.

**Identities are deterministic and order-invariant.** UUIDv5 over canonical JSON of an
identity dict, reusing `METRIC_NAMESPACE` with a `result_type` discriminator per model.

## 4. Prohibitions

The package contains no field, function, or diagnostic for: composite score, rank, tier,
confidence percentage, Prime/Subprime, bullish/bearish, buy/sell signal, entry, exit,
fill price, position size, stop, target, profit and loss, portfolio simulation, alert, or
order placement.

`CandidateOutcomeObservation` has no field capable of holding a simulated trade, and
`causal_interpretation` is only ever set from an explicit caller argument — never
inferred from price movement. A price rise is never auto-labelled a squeeze.

## 5. Schema

`1.0.0`, matching every prior phase. Phase 2V adds models; it modifies none.

## Phase 3A relationship

Candidate validation and candidate evaluation remain separate. Phase 2V reconstructs and
assesses a historical platform claim; Phase 3A evaluates explicit evidence under a new research
policy. An outcome confirmation cannot upgrade a Phase 3A rule, and a Phase 3A result cannot
rewrite Phase 2V's conclusion. They share supporting evidence IDs, not conclusions or labels.
