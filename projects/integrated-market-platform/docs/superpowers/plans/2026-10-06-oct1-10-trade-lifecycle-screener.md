# OCT1-10 — Final AI-selected trade lifecycle Screener

Classification: SOFTWARE_CONTROLLED. Implementation date: 2026-10-06.
Current architecture: [Screener trade lifecycle](../../architecture/SCREENER_TRADE_LIFECYCLE.md).

## Requirement

The trader can see, from the running product and without repository knowledge:
the selected candidate, supporting and conflicting evidence, the decision, entry
state/time/price, current position state, stop/SMA context, exit
state/time/price, realized and unrealized P&L, and the state-change history with
reasons.

This item owns the consolidated view. It adds no strategy, decision method,
stop method or accounting, and it does not own evaluation or metrics (OCT1-11).

## Repository boundary

- Precondition: OCT1-09 (`980c4f7947027c07490929e5e0e4f38c6738819d`, PR #465) merged as
  `42088bcbb3fbebc98af7d317df03dc5ea565d7cf`; `980c4f79` verified as an ancestor of `origin/main` before any OCT1-10 source existed.
- Base: `origin/main` `42088bcbb3fbebc98af7d317df03dc5ea565d7cf`.
- Branch `codex/oct1-10-trade-lifecycle-screener`, worktree `.worktrees/oct1-10-trade-lifecycle-screener`.
- Edits only under `projects/integrated-market-platform/`. The primary checkout and every other worktree were not touched.
- Exact implementation and merge SHAs, required checks and verified remote main belong to the PR and the OCT1-10 task ledger.

## Audit of the base

| Finding on `42088bcb` | Consequence |
|---|---|
| The AI Screener result lives in component state; a selected candidate shows rank, rationale and evidence only | Position, fill, stop and P&L were reachable only in Paper Workspace and Portfolio |
| Showing five candidates with decision and history took 17 browser requests and 15 clicks | One list projection, one detail request per expansion |
| No trade-episode identifier exists; the position row's `realized_pnl_minor` is cumulative per instrument | Episodes are derived from the ledger's fills; episode P&L is summed from the episode's own fills |
| A decision links to its run only through `evidence_snapshot.candidate_run_id`; reevaluation runs point back with `source_run_id` | Origin run resolved by identifier hops, never by ticker |
| Paper → decision is recorded on the order (`ACTION_DECISION` reason, plus `lineage_refs` on experiment ledgers) | Used as the fill → decision join |
| Stop events are queryable by account and instrument only | Filtered by the `stop_state_id`s the episode's decisions and fills name |
| `position_epoch()` in the stop engine does not filter by instrument | Not used here; recorded as a follow-up, stop engine unchanged |
| The Screener had no `data-testid`s | `lifecycle-*` test ids added on the new view only |

## What changed

### Backend

- `intelligence/inference/trade_lifecycle.py` — pure derivation: episodes from fills, decision placement on the predecessor chain, entry/exit/stage statuses, evidence and decision views, timeline ordering.
- `ui_api/screener_lifecycle.py` — `TradeLifecycleService`: one request context reads each store once and builds the list or one detail.
- `ui_api/server.py` — `GET /screener/trade-lifecycles` and `GET /screener/trade-lifecycles/{lifecycle_id}`.
- `platform/security/route_policy.py` — both routes `audit.read` on the Paper ledger scope.

No existing service, repository, engine or schema was modified.

### Frontend

- `api/screenerLifecycle.ts` — zod contract and the two fetch functions.
- `components/screener/lifecycle/` — `LifecycleCard`, `LifecycleDetail`, `TradeLifecycleGroups`, `lifecyclePresentation`, fixture.
- `panels/AiScreenerPanel.tsx` — one list query keyed by run; each selected candidate is a lifecycle card; active managed positions, unlinked activity and recent closed episodes below. The existing decision assessment stays on the card; the run's raw source evidence and News detail move under one disclosure.
- `panels/ActionDecisionPanel.tsx` — `PaperHandoff` exported for reuse; optional `onChanged` so an evaluation refreshes the lifecycle. Behaviour otherwise unchanged.
- `panels/dock.css` — `lifecycle-*` styles with a container-query collapse for narrow panels.

## Decisions worth knowing

- **Episode identity** is the opening fill: `TE-` + hash(account, experiment, instrument, opening fill id). Two trades of one symbol are never one episode.
- **A reselected position** appears in the newest run's list with that run's selection and is labelled as opened from an earlier run. A **closed** episode always keeps the run it was opened from.
- **Unlinked Paper activity** (opening fill names no recorded decision) is listed in its own group and never called AI-selected, even when a later run selects the symbol.
- **Same-instant ordering** in the timeline is causal: stop, then decision, then order, then fill — so a breach precedes the exit it causes.
- **No cache.** The projection is re-derived per request (list about 15 ms, detail about 6 ms locally), so there is no cross-account, cross-run or cross-episode cache to get wrong.
- **`PREVIEWED` was dropped** from the planned entry/exit statuses: an unsubmitted preview leaves no record, and a status with no authority behind it would be a guess.

## Requirement-to-test map

| Requirement | Test |
|---|---|
| ENTER without fill is not a position | `test_enter_without_fill_is_decided_not_executed_and_never_a_position`; UI `shows an ENTER decision without a fill…` |
| EXIT without close fill is not closed | `test_exit_decision_without_close_fill_keeps_the_position_open`; UI `keeps the position open after an EXIT decision…` |
| Stale or missing mark is not current P&L | `test_stale_mark_never_reads_as_current_pnl`; UI `never presents a stale or missing mark as current P&L` |
| Missing stop is not a `$0` stop | `test_missing_stop_is_stated_and_never_a_zero_level`; UI `states a missing or stale stop…` |
| Conflicting and missing evidence stay visible | `test_selected_candidate_shows_rank_and_every_evidence_group`; UI `loads evidence and history…` |
| Position survives leaving the candidate list | `test_active_position_stays_visible_when_the_newest_run_drops_it`; UI `shows managed positions before any AI run…` |
| Same-symbol episodes never cross-join | `test_two_episodes_of_one_symbol_never_share_entry_stop_or_pnl`; pure `test_same_symbol_trades_are_separate_episodes…` |
| New candidate after a closed episode inherits nothing | `test_new_candidate_after_a_closed_episode_inherits_nothing` |
| Scale-in / partial exit | `test_scale_in_shows_average_first_entry_and_both_fills`, `test_partial_exit_keeps_the_episode_open_with_split_pnl` |
| SMA breach is deterministic, model none, position still open | `test_stop_breach_is_a_deterministic_exit_and_the_position_stays_open` |
| Complete closed trade | `test_complete_closed_trade_has_every_acceptance_field` |
| NO_ACTION / CONSIDER_ENTRY / REVALIDATION_REQUIRED | `test_no_action_is_a_complete_flat_lifecycle`, `test_consider_entry_has_no_paper_fill`, `test_expired_decision_requires_revalidation_and_is_not_execution_ready` |
| Orphan Paper fill is not AI-selected | `test_unlinked_paper_activity_is_shown_and_never_called_ai_selected` |
| Chronological, deterministic history | `test_timeline_orders_interleaved_decisions_stops_and_fills_by_event_time`; pure `test_order_is_event_time_then_causal_kind…` |
| History immutability | `test_later_decisions_never_rewrite_earlier_history` |
| Frozen evidence for old decisions | `test_historical_decision_shows_its_own_frozen_evidence`; UI `shows an old decision with the evidence it froze…` |
| Current mark vs historical fill | `test_open_position_uses_fill_time_and_price_not_the_decision` |
| P&L equals the OCT1-09 authority | `test_pnl_matches_the_ledger_trade_and_valuation_authorities` |
| Schema enums, nullability, bounds | `test_enums_nullability_and_bounds`, `test_lists_are_bounded_and_closed_episodes_page`; UI `screenerLifecycle.test.ts` |
| Reads call no model and write nothing | `test_reading_a_lifecycle_calls_no_model_and_writes_nothing` |
| Late response / run change / malformed payload | UI `does not let one lifecycle's late response populate another`, `never draws a previous run's lifecycle under a new rank list`, `fails visibly when the lifecycle payload does not match this build` |

Backend tests: `tests/trading_correctness/test_trade_lifecycle.py` (service and HTTP over the real experiment ledger, action service and stop service) and `tests/intelligence/test_trade_lifecycle.py` (pure).

## Controlled browser acceptance

`node tools/ui1/oct1_10_browser.cjs` starts `tests/acceptance/harness_trade_lifecycle.py` and the production bundle (`vite build`, `vite preview`) and drives Chromium. Receipt: `artifacts/oct1-10-browser.json`.

Fixtures: clock, completed-bar feed, last-trade quote, marks, candidate receipts, model proposal, governed Opportunity, auth. Production: lifecycle projection, action-decision service, stop service, experiment service, Paper preview/submit route, pre-trade risk, simulator, ledger, SQLite local state, UI.

Result: **39 of 39 steps and 6 extra scenarios passed.**

- Primary trade (AAPL): selected #1 → evidence groups → ENTER (decided, not executed) → governed handoff → Workspace preview and explicit submit → simulated fill 6 @ $150.00 → position found again with no run loaded → mark $151.00, unrealized +$6.00 → stop not configured, then ACTIVE at $140.00 → HOLD → stop tightened to $142.00 → breach at $141.00 with no model call → EXIT decided, position still open → Prepare Paper Exit → explicit submit → close fill 6 @ $141.00 → POSITION CLOSED, realized −$54.00, equal to the ledger trade history → history in order → the old ENTER shows its frozen $150.00 quote → zero Live submissions.
- Extra scenarios: NO_ACTION; ENTER not executed; EXIT not filled; active position not in the latest run; stale mark; two episodes of one symbol.

Step 23 ("run/consume reevaluation") produced the HOLD through an explicit Evaluate Decision on a fresh run; the scheduled reevaluation worker is not started in this harness. The receipt-to-timeline join is covered by `test_reevaluation_receipts_join_by_decision_id_through_the_real_repository`.

## Validation

| Gate | Run | Passed | Skipped | Failures / errors | Seconds |
|---|---:|---:|---:|---:|---:|
| Focused backend (32 service/HTTP + 10 pure) | 42 | 42 | 0 | 0 / 0 | 13.632 |
| FAST (recovered) | 23 | 23 | 0 | 0 / 0 | 2.783 |
| CHANGED (recovered) | 5,954 | 5,919 | 35 | 0 / 0 | 324.617 |
| FULL (recovered, 71 suites) | 8,113 | 8,060 | 53 | 0 / 0 | 412.196 |
| Complete UI (178 files) | 1,370 | 1,370 | 0 | 0 / 0 | 112.83 |

Focused frontend cases in the complete run: lifecycle card/detail 17, API/schema 12,
AI Screener panel 14. The real reevaluation-repository test passes in both FULL
and the resumed focused run. Python compile and TypeScript pass in recovered
lint telemetry. Format/index checks, production build/bundle budget (19.01 s),
docs links (291 governance files), actionlint 1.7.12 over all three root workflows,
monorepo manifest/history validation and all nine root guard tests pass.

The completed canonical ladder is reused because production and test source is
unchanged. Final source hashes are checked against the staged bytes in
[`artifacts/oct1-10-acceptance.json`](../../../artifacts/oct1-10-acceptance.json).
The browser receipt predates this hash binding; its original run did not store
source hashes. The recovered screenshots were checked for final consistency.

Retained non-green history: the interrupted session reported five App/Participants
failures, followed by 93/93 in isolation (`INTERMITTENT / LOAD_RELATED`; original
raw UI log unavailable). Resumed sandbox UI collected zero tests with 171 EPERM
errors; sandbox focused tests hit temporary audit-store permissions, and one
root guard test hit temporary Git-config permissions (`ENVIRONMENT`). Unchanged
unsandboxed reruns pass. Two invalid focused-selector invocations ran zero tests;
exact method selectors corrected the command. An earlier partial browser receipt
is retained locally as incomplete (`UNKNOWN` cause), not claimed as a pass.

Timing is not green: FAST `SEVERE_REGRESSION` +52.810% vs 1.821 s; FULL
`SEVERE_REGRESSION` +107.257% vs 198.882 s; CHANGED `INSUFFICIENT_DATA`.
The budget is PROVISIONAL / OBSERVE_ONLY. The stored FULL baseline has 4,528
tests versus 8,113 now; no same-workload OCT1-09 comparison establishes incremental
attribution. Do not call this a timing pass.

Read-only staged review: no blocking OCT1-10 finding. Fill/account/experiment
identity isolates repeated symbols; decisions, stops and receipts retain their
own identifiers. Decisions are not fills, historical evidence remains frozen,
and P&L reuses ledger fills/valuation. Detail/list cache keys and abort signals
protect lifecycle/run switches. The view adds no automatic submit, Live path,
provider acquisition or inference; existing governed Workspace handoff remains.
List groups, evidence categories, decisions and timeline have explicit limits;
per-instrument histories retain their existing 100-record source bound.
The API does not create browser request fan-out across authority histories.


## Performance (local, SOFTWARE_CONTROLLED)

`tools/research/measure_oct1_10_performance.py` → `artifacts/oct1-10-performance.json`. In-process timings over the production service with SQLite local state; 158 ledger events, 26 fills, 12 closed episodes, 33 decisions for the instrument, 6 stop events.

| Read | Mean | p95 | Payload |
|---|---|---|---|
| List (2 selected, 12 closed at `closed_limit=20`) | 15.3 ms | 22.9 ms | 69.0 KB |
| Detail, open episode (19 timeline rows, 9 decisions) | 6.2 ms | 8.8 ms | 53.2 KB |
| Detail, closed episode (7 timeline rows, 2 decisions) | 7.5 ms | 7.4 ms | 22.5 KB |

Browser: one list request per panel refresh (every 15 s while visible), one detail request per expansion — against 17 requests for five candidates before. Bundle: initial 100.63 KiB gzip (100.61 before; budget 130); the lazy `AiScreenerPanel` chunk is 72.2 KB raw (budget 500,000 B).

A separate resumed list measurement with one selected candidate and one active
managed position (absent the latest run) measured mean 0.475 ms, p95 0.950 ms,
8,279-byte payload, 30 samples. This smaller fixture does not replace the larger
recovered measurement above.

Screenshot evidence: [open position](../../../artifacts/oct1-10/oct1-10-open-position.png)
and [closed episode](../../../artifacts/oct1-10/oct1-10-closed-lifecycle.png).

## Known limitations

- Episodes, fills and P&L are projected for an active Paper experiment only. A legacy session shows candidates and decisions with `PAPER_EXPERIMENT_REQUIRED`; closed experiments are not read.
- No "previewed" status: an unsubmitted Paper preview leaves no record.
- Decision history comes from the existing per-instrument read (newest 100).
- Mark quality is the ledger's; the view shows the mark's age but applies no threshold of its own.
- Positioned decisions between two manually opened episodes of one instrument cannot be placed by identifier and are reported, not guessed.
- The upstream Finviz price-evidence freshness gap recorded by OCT1-09 is unchanged; such evidence appears as excluded/blocked.
- `position_epoch()` in the OCT1-08 stop engine is not instrument-scoped. Not used and not changed here; a separate follow-up.
- The scheduled reevaluation worker was not exercised in the browser acceptance.

## Scope stop

OCT1-11 was not started.
