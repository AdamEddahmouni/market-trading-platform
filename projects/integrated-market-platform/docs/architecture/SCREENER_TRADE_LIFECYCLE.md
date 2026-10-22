# Screener trade lifecycle (OCT1-10)

Authoritative contract for the trader-facing lifecycle view in the AI Screener:
selected candidate → evidence → decision → entry → position → stop → exit → P&L →
history. Completion record:
[OCT1-10 report](../superpowers/plans/2026-10-06-oct1-10-trade-lifecycle-screener.md).

## Purpose and boundary

The lifecycle is **read-only derived state**. It answers one question — what is
happening with this AI-selected candidate or trade, how did it get here, and what
happened before — from records other authorities already wrote. It is not a
decision, risk, execution or accounting authority.

| Fact | Authority (unchanged) |
|---|---|
| Selected candidate, rank, rationale, cited evidence | AI Screener run ([candidate reduction](SCREENER_AI_CANDIDATE_REDUCTION.md)) |
| Action state, conditions, blockers, frozen evidence snapshot | [Action decision](SCREENER_ACTION_DECISION.md) |
| Transitions and cadence | [Reevaluation](SCREENER_REEVALUATION.md) |
| Stop level, status, breach | [SMA trailing stop](PAPER_SMA_TRAILING_STOP.md) |
| Orders, fills, position, marks, realized and unrealized P&L | Paper experiment ledger ([experiment contract](PAPER_PORTFOLIO_EXPERIMENT.md)) |

Reading a lifecycle calls no model, asks no market-data provider for evidence,
writes no candidate, decision, stop, order or fill record, and cannot prepare or
submit an order. The current mark comes from the same mark refresh the Paper
portfolio read performs (`apply_live_marks_to_ledger`), with the same effect on
the ledger's stored marks. No lifecycle record is persisted; every request
re-derives the projection, so there is no cache to invalidate.

Out of scope: evaluation, metrics, win/loss labels, performance ranking (OCT1-11).

## Code map

| Concern | Module |
|---|---|
| Pure derivation (episodes, decision placement, statuses, timeline order) | `intelligence/inference/trade_lifecycle.py` |
| Service that reads the stores and builds the projection | `ui_api/screener_lifecycle.py` |
| Routes | `ui_api/server.py` |
| Route policy | `platform/security/route_policy.py` |
| Client contract (zod) | `ui/src/api/screenerLifecycle.ts` |
| View | `ui/src/components/screener/lifecycle/` and `panels/AiScreenerPanel.tsx` |

## Routes

Both are `GET`, `audit.read`, account scope `PAPER_LEDGER`.

| Route | Returns |
|---|---|
| `/screener/trade-lifecycles?run_id=&closed_limit=&closed_before=` | `trade-lifecycle-list/1.0.0`: summary lifecycles in four groups, the experiment context and the data/execution boundary |
| `/screener/trade-lifecycles/{lifecycle_id}?run_id=` | `trade-lifecycle/1.0.0`: one lifecycle with evidence, every decision and the timeline |

Errors: `SCREENER_LIFECYCLE_INVALID` (400), `SCREENER_LIFECYCLE_NOT_FOUND` (404).
`run_id` must name an AI Screener run. Reevaluation (`RR-`) and risk-control
(`RK-`) runs are never listed as selections.

### Groups

| Group | Contents |
|---|---|
| `SELECTED` | The candidates of the given run. A candidate with an open position is shown as that position episode. |
| `ACTIVE_MANAGED` | Open AI-governed positions the given run did not select. They stay listed until a simulated close fill. |
| `RECENT_CLOSED` | Closed AI-governed episodes, newest first. |
| `UNLINKED_PAPER_ACTIVITY` | Paper positions whose opening fill names no recorded action decision. Never presented as AI-selected. |

### Bounds

| Item | Bound |
|---|---|
| Selected | 5 |
| Active managed | 25 |
| Recent closed | default 5, maximum 20, cursor `closed_before` |
| Unlinked | 10 |
| Evidence items per category (detail) | 8, with a `truncated` count |
| Decisions (detail) | 50 newest, with a `truncated` count |
| Timeline rows (detail) | 200 newest, with a `truncated` count |
| Other episodes of the instrument (detail) | 5, with a `truncated` count |

The list carries no evidence bodies, fills arrays or timeline. Expanding one
lifecycle costs one detail request.

## Episode identity and lineage

The ledger has no trade-episode identifier, so the projection derives one from
the ledger's own fill rows (`PaperExecutionLedger.project_trades()`), in ledger
sequence, per instrument: an episode opens on the fill the ledger classified
`OPEN` and ends on the next `CLOSE`.

```
episode_id   = 'TE-' + hash(account_id, experiment_id, instrument_id, opening fill_id)
lifecycle_id = episode_id, or 'LC-' + hash(account_id, run_id, instrument_id) for a candidate with no position
```

Records are joined by their own identifiers only. A shared ticker never joins two
records.

| Join | Key |
|---|---|
| Fill → decision | the `ACTION_DECISION` reason the governed handoff wrote on the order |
| Decision → episode | named by one of the episode's fills, or on the `previous_decision_id` chain between that episode's opening and its close |
| Decision → candidate run | `evidence_snapshot.candidate_run_id`, following `source_run_id` for reevaluation runs |
| Episode → stop | `stop_state_id` on the episode's decisions and fills, and the stop service's current state for the open position |
| Decision → reevaluation receipt | `transitions[].new_decision_id` |

Decisions are read for the bound account only, so a lifecycle never crosses
accounts or experiments. Flat decisions stay with their candidate, not with a
trade. A join that cannot be made is reported as `LINEAGE_UNAVAILABLE`; it is
not approximated.

A position reselected by a later run is shown in that run's list with the later
run's selection and `origin.same_as_current_run = false`. A closed episode keeps
the run it was opened from, even when the newest run selects the symbol again.

## Lifecycle blocks

`candidate`, `decision`, `entry`, `position`, `risk_control`, `exit`, `pnl`,
`origin`, `freshness`, `lineage`, `limitations`, `as_of`; detail adds `decisions`,
`timeline`, `prior_episodes`, `reevaluation`, `experiment`. Absent facts are
`null`, never zero.

### Semantic rules

| Rule | How it is enforced |
|---|---|
| ENTER is not a fill | `entry.status` is `DECIDED_ENTER` until the ledger has an opening fill; `position.state` stays `FLAT`; `entry.decision_reference` (a quote) is separate from `entry.fill` |
| EXIT is not a closed trade | `exit.status` is `EXIT_DECIDED` and `position` stays open until the ledger has a `CLOSE` fill |
| Position state comes from the ledger | never inferred from a candidate, a decision or a model |
| A current mark is not an entry price | `position.mark` and `entry.fill` are separate; `mark.quality` is `CURRENT`, `STALE`, `DEGRADED` or `UNAVAILABLE` |
| Stale is not current | `pnl.quality` carries the mark quality; a missing mark gives `unrealized_minor: null` |
| Episode P&L is the episode's | realized = sum of `realized_pnl_delta_minor` over the episode's fills, net of costs; never the experiment's or the instrument's cumulative total |
| A stop breach is not an AI opinion | `decision.origin = DETERMINISTIC_RISK_CONTROL`, `decision.model = null`; `risk_control.model = "none"` |
| A missing stop is stated | `risk_control.status = NOT_CONFIGURED`, `stop: null`; no zero level |
| History is immutable | each timeline row and each entry of `decisions` is built from that record's own frozen fields |
| No look-ahead | a decision's `evidence` is resolved from the packet that decision froze |
| Paper is not live capital | fills carry `kind: SIMULATED_PAPER_FILL`, `is_market_truth: false`; `experiment.live_capital: false` |

Entry statuses: `NOT_PROPOSED`, `CONSIDERED`, `DECIDED_ENTER`, `SUBMITTED_PAPER`,
`PARTIALLY_FILLED`, `FILLED`, `BLOCKED`, `EXPIRED`. Exit statuses: `NO_EXIT`,
`EXIT_DECIDED`, `EXIT_SUBMITTED`, `PARTIALLY_CLOSED`, `CLOSED`, `BLOCKED`. These
describe execution around a decision; they do not replace the six action states.

### Timeline

Derived, not stored. Rows come from the candidate run, decisions, stop events,
Paper orders and fills. Each row has `at` (the event's own time), `event`,
`source`, `reason`, `ref` and `clocks` (other clocks, such as submit time).
Order is event time, then causal kind at the same instant (selection, stop,
decision, order, fill), then ledger sequence. Storage order, row ids and fetch
order never decide it.

## UI

The AI Screener panel requests the list once per run (and every 15 s while
visible) with the run id in the cache identity, so a previous run's lifecycles
are never drawn under a new rank list. Each selected candidate renders as a
lifecycle card; active managed positions, unlinked activity and recent closed
episodes render below and do not depend on a run being loaded.

A card states, in text: the lifecycle stage, decision and who decided it,
evidence counts, entry, position, current mark, unrealized and realized P&L,
risk control and exit. **View lifecycle** loads the detail: why selected
(supporting, conflicting, weak, missing and excluded evidence as separate
sections), the decision with its conditions and blockers, the Paper experiment
context, and the history. Identifiers sit under **Details**.

The Paper Workspace remains the only submit boundary. The lifecycle offers
**Prepare Paper Exit** through the existing governed handoff
(`POST /screener/action-decision/handoff`) when the current decision is an
unexpired, preview-allowed EXIT; entry is prepared from the existing decision
assessment. Both open the Workspace, where preview and explicit confirmation are
still required.

## Limitations

- Episodes exist only for an active Paper experiment (portfolio-scoped ledger).
  On a legacy session the list reports `PAPER_EXPERIMENT_REQUIRED` and shows
  candidates and decisions without fills or P&L. Closed experiments are not read.
- A Paper preview that was never submitted leaves no record, so there is no
  "previewed" status.
- Mark quality is the ledger's. The projection reports the mark's age but
  applies no age threshold of its own.
- Decision history is read through the existing per-instrument history, which
  returns the newest 100 decisions.
- When an episode was opened and closed manually and a later manual episode
  follows with no flat decision between them, positioned decisions cannot be
  placed by identifier; they are reported under
  `DECISION_EPISODE_LINEAGE_UNAVAILABLE` rather than guessed.
- `position_epoch()` in the stop engine is not instrument-scoped. The lifecycle
  does not use it; stops are joined by `stop_state_id`.
