# Forward-Test Experimental Protocol V1

| Field | Value |
| --- | --- |
| **Classification** | `PLANNED` / `PRE-REGISTERED` / **NOT YET EMPIRICAL EVIDENCE** |
| **Protocol ID** | `FTEP-V1/0.1.0-PREREG` |
| **Preregistered** | 2026-09-11 (documentation freeze; no empirical run started) |
| **Owner** | Platform engineering (`docs/engineering/`) |
| **Governing increment** | Paper forward-testing bridge (PD-09 persistence closed) |
| **Machine-readable companion** | **OPEN DECISION** — see [§ Versioning](#versioning-and-change-control) |

> **This document is a protocol, not evidence.** It defines how the first governed
> Paper forward-test campaign will be conducted. No results, edge claims, or
> qualification closure are implied by its existence.

## Purpose

Freeze the experimental design for IMP's **first legitimate empirical Paper
forward-test campaign** before any live-market or Paper-session evidence is
collected. The campaign must:

1. use the [Paper forward-testing bridge](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md) with `run_kind=FORWARD_TEST`;
2. separate **signal quality** from **execution quality**;
3. preserve anti-look-ahead and pre-registration discipline inherited from
   [BUILD 26 forward shadow qualification](FORWARD_SHADOW_QUALIFICATION_V1.md),
   [EVIDENCE-01A](EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md), and
   [P6 Shadow Run 1](P6_SHADOW_RUN_1_PROTOCOL.md);
4. produce auditable artifacts without claiming strategy edge, promotion, or
   live-trading authority.

This protocol does **not** grant execution authority beyond governed Paper
`INTERNAL_SIMULATION` semantics. See [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).

## Relationship to adjacent programs

| Program | Role relative to FTEP-V1 |
| --- | --- |
| [PAPER_FORWARD_TESTING_BRIDGE](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md) | Runtime path: session → lock → optional Paper submit → observe → evaluate |
| [NEWS_STRATEGY_EVALUATION](../architecture/NEWS_STRATEGY_EVALUATION.md) | Upstream laboratory: baseline vs AI-enhanced **policy definitions** (software-fixture validated; not yet forward-tested) |
| [FORWARD_SHADOW_QUALIFICATION_V1](FORWARD_SHADOW_QUALIFICATION_V1.md) | Forecast shadow evidence class (`ACTUAL_FORWARD` vs `REPLAY`) |
| [EVIDENCE-01](EVIDENCE_01_LONGER_FORWARD_QUALIFICATION.md) | Separate forward-**qualification** sufficiency policy (forecast cohort); thresholds are precedent, not automatically binding on Paper forward tests |
| [EVIDENCE-01A](EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md) | Campaign orchestration pattern for forecast evidence; auto-bridge to Paper forward tests **not wired** |
| [FORWARD_VALIDATION_READINESS_CHECKLIST](FORWARD_VALIDATION_READINESS_CHECKLIST.md) | Prerequisite map — all forward campaigns currently `DEFERRED` until reopened deliberately |

## Campaign identity (frozen at activation)

| Field | Preregistered value | Notes |
| --- | --- | --- |
| `campaign_id` | Assigned at activation | Deterministic ID from activation manifest |
| `protocol_id` | `FTEP-V1/0.1.0-PREREG` | Bumped only via formal protocol revision |
| `evidence_class_target` | `ACTUAL_FORWARD` | Replay/fixture/synthetic excluded from empirical closure |
| `account_scope` | Single Paper account per campaign | Account isolation enforced by bridge store |
| `mode` | `INTERNAL_SIMULATION` / Paper only | Live production execution unreachable |

---

## 1. Hypothesis

**Primary hypothesis (H1):**

> A governed, time-locked Paper forward test of a **frozen strategy policy**
> produces measurable, auditable signal and (when enabled) execution outcomes
> that can be compared against a **pre-registered deterministic baseline** under
> identical eligibility rules, without look-ahead leakage.

**Secondary hypothesis (H2) — conditional on H1 infrastructure validity:**

> The **AI-enhanced policy variant** (`news_ai_enhanced@1.0.0`) yields
> strictly better pre-registered primary metrics than the **deterministic
> baseline** (`news_deterministic_baseline@1.0.0`) on the same eligible
> decision cohort, after transaction-cost treatment and multiple-testing
> controls.

H2 is **not** assumed true. Failure to reject the null for H2 is a valid
scientific outcome.

**OPEN DECISION — strategy binding**

| Option | Description |
| --- | --- |
| A | Bind first campaign to news-strategy-evaluation policies (ES / `FUTURES_EQUITY_INDEX` lane) |
| B | Bind to a simpler single-symbol equity smoke protocol (e.g. one liquid equity) |
| C | Defer campaign until Opportunity Engine candidate schema is frozen |

**Decision required before activation.** No default is selected in this preregistration.

---

## 2. Deterministic baseline

| Field | Value |
| --- | --- |
| Policy ID | `news_deterministic_baseline@1.0.0` |
| Source | [NEWS_STRATEGY_EVALUATION](../architecture/NEWS_STRATEGY_EVALUATION.md) |
| Classification | Catalyst + recency deterministic mapping |
| Execution authority | **NONE** at policy layer |
| Frozen at | `locked_at_ns` on each `ForwardTestDecision` (`strategy_version` + `decision_payload`) |

**OPEN DECISION — baseline if Option B/C selected above**

If the first campaign does not use news-strategy policies, a separate baseline
policy ID and version must be preregistered in the activation manifest before
any decision is locked.

---

## 3. AI-enhanced variant

| Field | Value |
| --- | --- |
| Policy ID | `news_ai_enhanced@1.0.0` |
| Source | [NEWS_STRATEGY_EVALUATION](../architecture/NEWS_STRATEGY_EVALUATION.md) |
| AI role | Feature input only (sentiment, impact, model-reported confidence) |
| Execution authority | **NONE** at policy layer |
| Comparison metric | `AI_INCREMENTAL_VALUE = AI_ENHANCED_OUTCOME − BASELINE_OUTCOME` (same horizon, same eligibility) |

**Reference only (not a campaign arm unless preregistered):**

| Policy ID | Role |
| --- | --- |
| `news_naive_reference@1.0.0` | Always-`NEUTRAL` sanity check; optional third arm |

**OPEN DECISION — live intelligence provider**

| Option | Description |
| --- | --- |
| A | Use recorded intelligence artifacts only (no live LLM at decision time) |
| B | Allow live governed intelligence with frozen prompt/model version in `provenance_snapshot` |
| C | Defer AI arm until `CLAUDE_LIVE_VALIDATION` blocker cleared |

---

## 4. Eligible universe

| Dimension | Preregistered rule |
| --- | --- |
| Asset classes | Must be admitted under XA-01 identity kernel |
| Execution mode | Paper `INTERNAL_SIMULATION` only |
| Run kind | `FORWARD_TEST` exclusively |
| Account | Single `account_id` per session; cross-account access rejected |

**OPEN DECISION — universe definition**

| Option | Universe |
| --- | --- |
| A | `FUTURES_EQUITY_INDEX` — primary `ES` (CME equity index futures family per strategy-eval lab) |
| B | Single-name equity (symbol TBD at activation) |
| C | Multi-symbol list frozen in `ForwardTestSession.universe` |

Precedent: strategy-eval lab selected ES; P6 used BIYA. **No symbol is binding until the activation manifest is signed.**

---

## 5. Instruments

Instruments must resolve to canonical XA-01 instrument keys before a decision
is locked. Continuous futures contracts are **non-executable** (G1/G4 guard).

| Field | Preregistered constraint |
| --- | --- |
| Identity | Canonical instrument key in `decision_payload` + `symbol` |
| Provider admission | Only admitted provider snapshots at `source_time_ns` |
| Derivatives | Options/futures Paper paths exist (G13) but first campaign instrument set is **OPEN DECISION** |

---

## 6. Session times

| Term | Definition |
| --- | --- |
| `decision_time_ns` | When IMP recorded the forward decision (bridge) |
| `source_time_ns` | Latest legitimate input source time at decision |
| `evaluation_time` | After `decision_time_ns + evaluation_horizon_ns` |
| Observation `source_time_ns` | Provider/source time of appended evidence |

**OPEN DECISION — calendar scope**

| Option | Session window |
| --- | --- |
| A | US equity regular hours (09:30–16:00 ET) — P6 precedent |
| B | Globex ETH for ES — requires explicit liquidity/fill assumptions |
| C | Operator-bounded windows declared per `ForwardTestSession.config` |

**OPEN DECISION — minimum campaign duration**

| Option | Floor |
| --- | --- |
| A | EVIDENCE-01A: ≥ 5 qualifying sessions, each ≥ 5 minutes |
| B | EVIDENCE-01: ≥ 5 distinct trading days |
| C | Custom floor declared in activation manifest (must be ≥ A or B, not weaker post-hoc) |

---

## 7. Market conditions

Eligible decisions may be generated only when pre-registered market-condition
gates pass at `source_time_ns`. Conditions are evaluated from admitted
observational facts — never from post-horizon prices.

**Preregistered exclusions (always):**

- `source_time_ns` in the future relative to decision creation
- Provider disconnected (when flagged) — EVIDENCE-01A precedent
- Clock drift beyond tolerance — observation excluded (`CLOCK_DRIFT`)
- Book/quote stale beyond policy threshold (when L2/L1 freshness evaluated)

**OPEN DECISION — regime filters**

| Option | Treatment |
| --- | --- |
| A | No regime filter (all admitted sessions) |
| B | Tag `XA-05` strategic state/regime in `provenance_snapshot`; segment post hoc |
| C | Hard exclude named regimes (list frozen at activation) |

---

## 8. Candidate-generation rules

A **candidate** is an instrument-time pair eligible for a forward-test
decision.

| Rule | Preregistered constraint |
| --- | --- |
| Timing | Candidate must be identified **before** `decision_time_ns` using only inputs with `available_time_ns ≤ decision_time_ns` |
| Payload | Frozen in immutable `decision_payload` after lock |
| Provenance | `provenance_snapshot` records strategy version, policy IDs, and input refs |
| Duplication | One locked decision per candidate per session unless preregistered overlap policy allows |
| Run kind | `run_kind=FORWARD_TEST`; backtest/replay candidates forbidden |

**OPEN DECISION — generation cadence**

| Option | Cadence |
| --- | --- |
| A | Event-driven (strategy match / opportunity signal) |
| B | Fixed interval buckets — P6 precedent: 60-second decision buckets |
| C | Hybrid — declared in `ForwardTestSession.config` |

**OPEN DECISION — overlap**

| Option | Same symbol concurrent decisions |
| --- | --- |
| A | Forbidden while any decision for symbol is `OBSERVING` or `PAPER_ACTIVE` |
| B | Allowed with distinct `forward_test_id` and preregistered max concurrent count |

---

## 9. Entry timing

| Mode | Entry rule |
| --- | --- |
| `SIGNAL_ONLY` | No Paper order; entry reference from first post-lock observation tagged `ENTRY` in observation payload |
| `EXECUTION` | Governed Paper preview → submit via [paper handoff](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md#paper-execution-integration); entry time = Paper submit acceptance time |

Entry price for signal metrics: `entry_reference_price` from observations
(bridge `compute_signal_outcome`). **No mid-horizon payload mutation** after lock.

**OPEN DECISION — first campaign `test_mode`**

| Option | Mode |
| --- | --- |
| A | `SIGNAL_ONLY` for infrastructure shakedown (no Paper fills) |
| B | `EXECUTION` for full signal + execution metric path |
| C | Phased — A until N decisions evaluated, then B with new preregistered segment |

---

## 10. Observation horizons

| Field | Source |
| --- | --- |
| Primary horizon | `ForwardTestSession.evaluation_horizon_ns` (per-session frozen) |
| Decision horizon | `ForwardTestDecision.evaluation_horizon_ns` (copied at creation) |
| Evaluation gate | `assert_evaluation_horizon_reached` — evaluation blocked before horizon |

**OPEN DECISION — horizon values**

| Option | Horizons |
| --- | --- |
| A | Strategy-eval lab defaults: 5m / 15m / 30m / 60m (separate sessions or segmented decisions) |
| B | Single horizon per campaign (value TBD at activation) |
| C | P6 precedent: 30-minute label horizon (forecast shadow; not automatically Paper horizon) |

Secondary horizons, if used, require **pre-registered segmentation** — not
chosen after observing primary results.

---

## 11. Fill assumptions / Paper execution rules

Applies when `test_mode=EXECUTION`.

| Rule | Binding behavior |
| --- | --- |
| Authority | Paper `INTERNAL_SIMULATION` + `PAPER_ONLY`; workspace preview/submit boundary |
| Handoff | `decision_source_snapshot` type `forward_test_decision`; correlation `forward_test:{forward_test_id}` |
| Duplicate submit | Blocked at store level (durable under PD-09 persistence) |
| Live brokers | **Unreachable** from forward-test path |
| Fill truth | Paper ledger fills are authoritative for execution metrics |
| Partial fills | Working-remainder / cancel-time reconciliation per G3 Paper correctness |

**SIGNAL_ONLY campaigns:** execution metrics quality = `NOT_APPLICABLE`;
fill assumptions do not apply.

**OPEN DECISION — sizing**

| Option | Quantity rule |
| --- | --- |
| A | Fixed unit size per decision (`quantity` frozen at lock) |
| B | Risk-budget-derived sizing from Paper preview (max loss frozen in payload) |
| C | Minimum 1-share / 1-contract smoke only |

---

## 12. Transaction-cost / slippage treatment

| Layer | Treatment |
| --- | --- |
| Signal metrics | **Gross** — observation reference prices; no implicit cost adjustment |
| Execution metrics | Paper ledger PnL (minor units) when available; includes simulated spread/fees per Paper economics |
| Comparison | Baseline vs AI-enhanced uses **same** cost treatment per arm |
| Canonical accounting | G4 exact-Decimal kernel for portfolio settlement when execution path used |

**OPEN DECISION — explicit slippage model**

| Option | Treatment |
| --- | --- |
| A | Paper internal simulation only (no additional slippage overlay) |
| B | Post-hoc slippage haircut on signal metrics for sensitivity analysis (frozen %) |
| C | Require explicit `transaction_cost_bps` in `decision_payload` |

---

## 13. Rejection conditions

A decision or observation is **rejected** (excluded from primary analysis cohort)
when any of the following hold:

| Code | Condition |
| --- | --- |
| `TEMPORAL_VIOLATION` | Observation `source_time_ns < decision_time_ns` |
| `FUTURE_SOURCE_TIME` | `source_time_ns` after decision creation clock |
| `IMMUTABLE_PAYLOAD_BREACH` | Post-lock payload mutation attempted |
| `WRONG_RUN_KIND` | `run_kind ≠ FORWARD_TEST` |
| `ACCOUNT_MISMATCH` | `account_id` does not match session |
| `DUPLICATE_PAPER_SUBMIT` | Second Paper submission for same `forward_test_id` |
| `PAPER_REJECTED` | Paper preview/submit returned governed rejection |
| `INSUFFICIENT_DATA` | Missing entry/exit observations at evaluation |
| `HORIZON_NOT_REACHED` | Evaluation attempted before `evaluation_horizon_ns` |
| `PROVIDER_DISCONNECTED` | Evidence collected during disconnect (EVIDENCE-01A precedent) |
| `CLOCK_DRIFT` | Observation excluded per campaign health rules |
| `CONFIG_DRIFT` | Resume blocked; campaign `INVALIDATED` if contamination suspected |
| `SHAKEDOWN` | Explicitly tagged shakedown segment (EVIDENCE-01A precedent) |

Terminal decision states: `REJECTED`, `CANCELLED`, `EXPIRED`, `INVALID`,
`INSUFFICIENT_DATA` — excluded from primary cohort unless preregistered salvage
analysis arm.

---

## 14. Sample minimums

Thresholds are **frozen at campaign activation**. Weakening after observing
results is forbidden (BUILD 26 / EVIDENCE-01 precedent).

**Proposed floors (pending OPEN DECISION confirmation):**

| Metric | Proposed floor | Precedent |
| --- | --- | --- |
| Locked forward-test decisions (total) | ≥ 30 | Between BUILD 26 (10) and EVIDENCE-01 (50) |
| Evaluated decisions (signal-complete) | ≥ 15 | EVIDENCE-01 settled floor (25) scaled for Paper scope |
| Distinct trading days | ≥ 5 | EVIDENCE-01 / P6 |
| Distinct qualifying sessions | ≥ 5 | EVIDENCE-01A |
| EXECUTION-mode decisions (if arm enabled) | ≥ 10 | Operational minimum for execution metric stability |
| Per-arm minimum (baseline vs AI) | ≥ 10 each | Paired comparison floor |

**OPEN DECISION — final binding floors**

Activation manifest must copy exact integers. Until activation, this section
is **PLANNED** only. `INSUFFICIENT_FORWARD_EVIDENCE` / `INSUFFICIENT_SAMPLE`
remain valid outcomes.

---

## 15. Metrics

### 15.1 Statistical metrics (signal)

Recorded in `signal_outcome` per [bridge evaluation](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md#outcome-metrics):

| Metric | Definition |
| --- | --- |
| `directional_correct` | Boolean when direction non-neutral |
| `absolute_return` | `exit_reference_price − entry_reference_price` |
| `percentage_return` | `absolute_return / entry_reference_price` |
| `quality` | `COMPLETE` \| `INSUFFICIENT_DATA` |

**Primary comparison (H2):** mean/median `percentage_return` and directional
accuracy by arm; paired difference where decision cohorts align.

**OPEN DECISION — primary statistical test**

| Option | Test |
| --- | --- |
| A | Paired bootstrap CI on per-decision return delta (BUILD 19/20 precedent) |
| B | Sign test on directional correctness |
| C | Both — primary pre-registered in activation manifest |

### 15.2 Operational metrics

| Metric | Source |
| --- | --- |
| Decision lock latency | `locked_at_ns − decision_time_ns` |
| Paper submit latency | `submitted_at_ns − locked_at_ns` (EXECUTION mode) |
| Observation append count | Per decision |
| Evaluation success rate | `EVALUATED` / eligible locked decisions |
| Restart recovery | PD-09 persistence replay success |
| Provider uptime | Health checks during campaign |
| Settlement backlog | Decisions past horizon not yet `EVALUATED` |

### 15.3 Opportunity-quality metrics

| Metric | Definition |
| --- | --- |
| Candidate yield | Locked decisions / candidates generated |
| Abstention rate | NEUTRAL or no-decision / candidates |
| Horizon completion rate | `EVALUATED` / `LOCKED` |
| Duplicate-block rate | Idempotency claims triggered |
| Cross-symbol concentration | HHI or max share on single symbol |

**OPEN DECISION — opportunity scoring linkage**

Opportunity Engine ranking is **not** in scope for FTEP-V1 runtime; metrics
are descriptive only.

### 15.4 Risk metrics

| Metric | Constraint |
| --- | --- |
| Max drawdown (Paper) | From canonical portfolio when EXECUTION enabled |
| Per-decision loss cap | From Paper preview risk binding |
| Concurrent exposure | Max open Paper positions per universe |
| Mode violation attempts | Must be **0** |
| Live execution attempts | Must be **0** |

---

## 16. Comparison methodology

| Rule | Requirement |
| --- | --- |
| Arms | Baseline vs AI-enhanced on **matched eligibility** |
| Matching key | `(symbol, decision_bucket, horizon)` or preregistered finer key |
| Cohort freeze | Analysis SQL/JSONL query frozen before unblinding |
| Naive reference | Optional descriptive arm; not used for promotion |
| Conflation | Signal and execution metrics reported separately — never a single blended score |

Incremental value:

```text
AI_INCREMENTAL_VALUE = metric(AI_ENHANCED) − metric(BASELINE)
```

Report point estimate + pre-registered uncertainty interval when sample
minimums met; otherwise report `NOT_EVALUABLE`.

---

## 17. Multiple-testing controls

**OPEN DECISION — family-wise error control**

| Option | Control |
| --- | --- |
| A | Single primary metric only; secondary metrics descriptive |
| B | Holm-Bonferroni across K preregistered secondary metrics |
| C | Holdout segment — train/holdout split by trading day (frozen split manifest) |

**Preregistered now:** at most **one** primary metric for H2 (chosen at
activation). All other metrics are exploratory unless explicitly listed in the
activation manifest secondary family.

---

## 18. Leakage controls

| Control | Implementation |
| --- | --- |
| Decision immutability | `decision_payload` frozen after lock |
| Source-time law | `available_time_ns ≤ decision_time_ns` for all inputs |
| Observation ordering | Append-only; cannot precede decision time |
| Outcome separation | Observations after lock only; evaluation after horizon |
| Run kind boundary | `FORWARD_TEST` ≠ `BACKTEST`; regression tested |
| Provenance | `provenance_snapshot` at lock |
| Replay | `REPLAY` / `FIXTURE` / `SYNTHETIC` excluded from `ACTUAL_FORWARD` closure |
| Post-hoc tuning | Strategy/policy version changes require new campaign segment |

---

## 19. Regime handling

| Phase | Rule |
| --- | --- |
| At decision | Regime tags (if any) recorded in `provenance_snapshot` only |
| During campaign | No regime-conditioned policy mutation |
| Analysis | Pre-registered segments by regime tag (if Option B/C in §7) |

XA-05 strategic state kernel exists but is **not** automatically wired to
forward-test decisions. Regime-aware segmentation is **OPEN DECISION**.

---

## 20. Versioning and change-control rules

| Artifact | Version rule |
| --- | --- |
| This protocol | `FTEP-V1/0.1.0-PREREG` → bump minor for binding field changes |
| `strategy_version` | Frozen per locked decision |
| Policy IDs | Frozen at lock (`news_*@1.0.0` until new arm preregistered) |
| Bridge schema | `intelligence/paper_forward_bridge/1.0.0` |
| Persistence schema | `local_state` v2 (PD-09) |
| Activation manifest | SHA-256 fingerprint; stored with campaign artifacts |

Changes after first locked decision require either:

1. **new campaign segment** with new protocol version, or
2. **explicit INVALIDATED** prior segment + documented contamination review.

---

## 21. Disposition criteria (KEEP / REJECT / REPEAT / MODIFY / BLOCKED)

Applied **after** sample minimums are evaluated or explicitly waived. No
disposition may be chosen using fabricated or fixture-only cohorts as
`ACTUAL_FORWARD` evidence.

### KEEP

Infrastructure and methodology are fit for continued Paper forward testing:

- leakage controls verified (no `TEMPORAL_VIOLATION` in primary cohort)
- PD-09 persistence recovery succeeded on restart drill
- ≥ preregistered sample minimums met
- signal metrics computable for ≥ 80% of locked decisions
- zero mode/authority violations
- H2 outcome **irrelevant** to KEEP (KEEP is about campaign machinery)

### REJECT

Campaign or arm fails closed — do not use cohort for inference:

- confirmed look-ahead or payload immutability breach
- `CONFIG_DRIFT` / contamination without isolated segment
- primary cohort dominated by `REJECTED` / `INVALID` (> 50%)
- wrong `run_kind` or account isolation failure
- EXECUTION arm: Paper path systematically broken (not transient)

### REPEAT

Run again with **same frozen protocol** to accumulate more `ACTUAL_FORWARD` evidence:

- `INSUFFICIENT_SAMPLE` or `INSUFFICIENT_DATA` but no integrity breach
- provider outage mid-campaign with clean partial cohort preserved
- SIGNAL_ONLY shakedown succeeded; repeat for EXECUTION phase per §9 Option C

### MODIFY

Requires **new protocol version** before additional locks:

- change universe, horizon, policy IDs, cost treatment, or sample floors
- add/remove AI arm or baseline
- change session-time or cadence rules

Prior segment remains immutable; new segment gets new `campaign_id`.

### BLOCKED

Cannot proceed until external prerequisite clears:

| Blocker | Example |
| --- | --- |
| `OPEN_D_NOT_INSTALLED` | Moomoo OpenD (TD-004) when provider required |
| `LIVE_PROVIDER_UNVERIFIED` | Real provider path not exercised |
| `PERSISTENCE_DISABLED` | `IMP_PERSIST_STATE` off when durability required |
| `EVIDENCE_01C_DEFERRED` | If campaign explicitly tied to 01C shakedown |
| Market hours / credentials | Operator env not ready per readiness checklist |

---

## 22. Evidence-class advancement criteria

| Evidence class | Qualifies for FTEP-V1 empirical closure |
| --- | --- |
| `ACTUAL_FORWARD` | **YES** — decision locked before horizon; live/admitted ingress |
| `LIVE_FORWARD` | **YES** — EVIDENCE-01A alias for real forward origin |
| `REPLAY` | NO — deterministic reproduction only |
| `FIXTURE` | NO — software validation only |
| `SYNTHETIC` | NO — mechanism tests only |
| `SHAKEDOWN` | NO — excluded segment (may advance to REPEAT) |

**Advancement ladder (planned, not yet achieved):**

```text
FTEP-V1 preregistration (this document)
  → activation manifest + env preflight
  → SIGNAL_ONLY or EXECUTION campaign ACTIVE
  → primary cohort EVALUATED
  → disposition KEEP | REJECT | REPEAT | MODIFY | BLOCKED
  → optional: feed summary into EVIDENCE / promotion programs (separate authority)
```

FTEP-V1 closure does **not**:

- close EVIDENCE-01 `INSUFFICIENT_FORWARD_EVIDENCE`
- promote champion/challenger (BUILD 20)
- authorize live execution
- prove profitability

---

## 23. Activation checklist (before first lock)

- [ ] All **OPEN DECISION** rows in this document resolved in activation manifest
- [ ] `FORWARD_VALIDATION_READINESS_CHECKLIST` row for this campaign reopened
- [ ] `IMP_PERSIST_STATE=1` or `IMP_STATE_DIR` set when durability required
- [ ] Paper account scoped; Live execution gates verified closed
- [ ] Provider connectivity preflight (if observational ingress required)
- [ ] Policy IDs and `strategy_version` pinned
- [ ] Sample floors copied verbatim into manifest
- [ ] Primary metric and multiple-testing option selected
- [ ] Shakedown segment tagged if used
- [ ] Operator runbook entry in `WORK_LOG.md`

---

## 24. Artifact layout (planned)

```
artifacts/forward-test-campaigns/<campaign_id>/
  ACTIVATION_MANIFEST.json      # frozen decisions from OPEN DECISION resolution
  PROTOCOL_REF.json             # { "protocol_id": "FTEP-V1/0.1.0-PREREG", "sha256": "..." }
  sessions/                     # ForwardTestSession exports
  decisions/                    # locked decision snapshots
  observations.jsonl            # append-only
  evaluations/                  # signal + execution outcome records
  DISPOSITION.json              # KEEP|REJECT|REPEAT|MODIFY|BLOCKED + rationale
```

**Not yet created.** Directory creation is part of campaign activation (Next B).

---

## 25. Related documents

- [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md)
- [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md)
- [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md)
- [FORWARD_VALIDATION_READINESS_CHECKLIST.md](FORWARD_VALIDATION_READINESS_CHECKLIST.md)
- [FORWARD_SHADOW_QUALIFICATION_V1.md](FORWARD_SHADOW_QUALIFICATION_V1.md)
- [EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md](EVIDENCE_01A_REAL_FORWARD_OBSERVATION_CAMPAIGN.md)
- [CHAMPION_CHALLENGER_PROMOTION_V1.md](CHAMPION_CHALLENGER_PROMOTION_V1.md)
- [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)

---

## 26. Professor-facing summary

1. **What is this?** A frozen experimental design for the first real Paper forward-test campaign.
2. **Is it evidence?** **No.** PLANNED / PRE-REGISTERED / NOT YET EMPIRICAL EVIDENCE.
3. **What is being tested?** Governed prospective decisions under the Paper forward bridge — optionally with Paper execution.
4. **Baseline vs AI?** Deterministic `news_deterministic_baseline@1.0.0` vs `news_ai_enhanced@1.0.0` when that arm is selected.
5. **What is still open?** Universe, horizons, cadence, sample floors, test mode, and several analysis choices — marked OPEN DECISION.
6. **What would falsify integrity?** Temporal violations, config drift, wrong run kind, or Live execution reachability.
7. **What happens next?** Resolve OPEN DECISIONs → activation manifest → operator preflight → first lock.
