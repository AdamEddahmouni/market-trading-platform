# FTEP Campaign Manifest Template V1

**Classification:** `TEMPLATE`  
**Rule:** a populated manifest may become `FROZEN_FOR_ACTIVATION` only after every required field and activation gate is resolved before qualifying prospective evidence begins.

## Identity

- `campaign_id`:
- `manifest_version`:
- `manifest_hash`:
- `ftep_core_version`:
- `asset_profile_version`:
- `strategy_profile_version`:
- `repository_source_sha`:
- `created_at`:
- `frozen_at`:
- `owner/authority`:
- `target_evidence_class`:

## Hypothesis and arms

- Primary hypothesis:
- Secondary hypothesis(es):
- Baseline policy/version:
- Treatment/challenger policy/version:
- AI/model/prompt binding, if applicable:
- Null/failure interpretation:

## Account, mode and instruments

- Paper account ID:
- Execution mode: `SIGNAL_ONLY` or governed Paper execution
- Live authority: `NONE`
- Asset class:
- Venue/exchange:
- Canonical instrument key(s):
- Dated futures contract month(s), if applicable:
- Currency/multiplier/tick economics:

## Market/news data bindings

For every source:

- capability-contract ID/version:
- provider/dataset/endpoint:
- data mode:
- observation type:
- coverage/venue scope:
- source/receive timestamp semantics:
- freshness rule:
- entitlement verified:
- intended-use rights verified:
- campaign role:
- known limitations:

## Comparator and calibration

- External comparator/environment:
- Comparator capability audit/version:
- Comparator known limitations:
- IMP simulator version/SHA:
- Calibration contract/version:
- Calibration cohort/window:
- Numeric fill/no-fill disagreement threshold:
- Numeric fill-price/slippage threshold:
- Numeric timing threshold, if material:
- Position/P&L reconciliation tolerance:
- Maximum unexplained material-divergence rate:
- Calibration disposition required before qualifying execution evidence:

Any required numeric field that cannot be justified is `UNSET/BLOCKING`.

## Timing and sessions

- Timezone:
- Eligible calendar/session window:
- Start date/time:
- End rule/date:
- Decision-time semantics:
- Information cutoff:
- Primary horizon:
- Secondary horizons, if any:
- Minimum qualifying sessions/days:
- Minimum qualifying decisions/events:

## Candidate generation

- Source/catalyst/feature eligibility:
- Candidate trigger/cadence:
- Dedupe rule:
- Same-symbol overlap rule:
- Regime/context filters:
- Freshness/staleness gates:
- Abstention rule:

## Execution assumptions

If `SIGNAL_ONLY`, mark execution fields `NOT_APPLICABLE` and define entry/exit reference observation rules.

If execution-bearing:

- order types:
- sizing rule:
- max concurrent exposure:
- spread/slippage treatment:
- fees/commissions:
- margin/collateral assumptions:
- partial-fill handling:
- stop/limit semantics:
- cancel/replace behavior:
- stale/missing-market behavior:

## Metrics and decision rules

- Primary metric(s):
- Secondary metric(s):
- Risk/drawdown/tail metrics:
- Calibration metrics:
- Transaction-cost sensitivity:
- Multiple-testing correction/accounting:
- Predefined segmentation:
- `KEEP` criteria:
- `REJECT` criteria:
- `REPEAT` criteria:
- `MODIFY` criteria:
- `BLOCKED` criteria:
- invalidation criteria:

## Exclusions and shakedown

- Rejection codes:
- Non-qualifying shakedown definition:
- Provider disconnect policy:
- Clock-drift policy:
- data-gap policy:
- configuration-drift policy:
- treatment of operational incidents:

## Evidence and artifact package

- campaign manifest path:
- immutable input/provenance artifacts:
- forward-test session/decision/observation IDs:
- market-data artifacts/references:
- comparator artifacts/references:
- calibration report:
- analysis artifact:
- final closure record:

## Freeze checklist

- [ ] All `OPEN DECISION` items resolved.
- [ ] FTEP Core, Asset Profile and Strategy Profile versions bound.
- [ ] Repository SHA bound.
- [ ] Paper account and exact executable instrument(s) bound.
- [ ] Market Data Capability Contracts verified.
- [ ] Entitlement and intended-use rights verified.
- [ ] Comparator audit completed if required.
- [ ] Calibration contract and numeric thresholds frozen if execution-bearing.
- [ ] Candidate, timing, horizon, sizing and cost rules frozen.
- [ ] Metrics, multiple-testing rules and disposition criteria frozen.
- [ ] Shakedown and qualifying cohort boundaries frozen.
- [ ] Artifact/reproducibility paths defined.
- [ ] Live authority explicitly remains `NONE`.

Only after every required item passes may the manifest status change from `DRAFT/PRE-REGISTERED` to `FROZEN_FOR_ACTIVATION`.
