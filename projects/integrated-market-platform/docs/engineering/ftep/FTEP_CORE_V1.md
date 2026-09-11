# FTEP Core V1

**Classification:** `PREIMPLEMENTATION_CANONICAL_PROTOCOL`  
**Protocol family:** Forward-Test Experimental Protocol (FTEP)  
**Role:** universal rules inherited by every FTEP campaign

FTEP Core is not a strategy, asset profile or campaign. It supplies the rules that all campaign manifests must inherit.

## Core invariants

1. **Prospective integrity** — decisions use only information available by the frozen information cutoff.
2. **Pre-registration** — hypothesis, baseline/treatment, metrics, thresholds, exclusions, horizons and analysis rules are frozen before qualifying evidence.
3. **Version binding** — repository SHA, strategy/model/prompt versions, data contracts and execution assumptions are bound in the campaign manifest.
4. **Immutable decisions** — a locked decision cannot be rewritten after later information arrives.
5. **Append-only observations** — later observations/outcomes extend the record without rewriting the decision state.
6. **Evidence separation** — engineering validation, historical/OOS, shadow, Paper and repeated prospective evidence are distinct.
7. **Account/mode isolation** — Demo/Paper/Live and account identities cannot leak across a campaign.
8. **Paper-only authority by default** — FTEP never grants Live authority.
9. **No post-hoc success rules** — metrics, exclusions, thresholds and segmentation cannot be selected after outcomes are known.
10. **Contradictions retained** — negative, null, fragile and discrepant evidence is preserved.

## Required composition

Every activated campaign binds:

`FTEP Core version + Asset-Class Profile version + Strategy Profile version + Campaign Manifest version`

The strictest applicable rule wins. A lower layer cannot weaken Core controls.

## Evidence classes

- `ENGINEERING_VALIDATION`
- `HISTORICAL_REPLAY`
- `OUT_OF_SAMPLE_REPLAY`
- `LIVE_DAY_SHADOW`
- `PAPER_OBSERVED`
- `REPEATED_PROSPECTIVE_EVIDENCE`

Campaigns declare one primary target evidence class. Lower evidence may support readiness but cannot be relabeled upward.

## Required experiment definition

Before activation record:

- falsifiable primary and secondary hypotheses;
- deterministic/simple baseline where appropriate;
- treatment/challenger definition;
- universe and asset class;
- information cutoff and timing semantics;
- candidate-generation and dedupe rules;
- strategy/model/prompt versions;
- market/news/data capability contracts;
- execution mode and simulator/calibration references;
- metrics and numeric acceptance thresholds where material;
- rejection/exclusion/invalidation rules;
- minimum sample/session requirements;
- analysis, segmentation and multiple-testing policy;
- closure states and promotion boundaries.

## Temporal integrity

Preserve source/event/publication time separately from retrieval/receive time. Future bars, later revisions, future outcomes and post-horizon labels are prohibited from the decision path. Walk-forward or untouched OOS methods are required when parameters are estimated historically.

## Baseline and challenger discipline

Treatments should differ only in the component being tested where practical. For AI challengers, use identical eligible cohorts, information cutoffs and downstream policy except for the AI-derived component. Do not compare across different market periods and call the difference incremental model value.

## Multiple testing

Track explored strategies, prompts, models, features, parameterizations and segmentations. Pre-register the correction/sensitivity method appropriate to the experiment. A winning member of a large search family is not promoted as though it were the only hypothesis tested.

## Campaign change control

After `FROZEN_FOR_ACTIVATION`, a material change to source binding, strategy logic, model/prompt, candidate generation, horizon, sizing, execution policy, costs, thresholds, exclusions or analysis rules requires a new campaign version or explicit invalidation.

## Closure

A campaign closes as one of:

- `KEEP`
- `REJECT`
- `REPEAT`
- `MODIFY`
- `BLOCKED`
- `INVALIDATED`

The closure record states the evidence class actually achieved, not merely the class originally targeted.
