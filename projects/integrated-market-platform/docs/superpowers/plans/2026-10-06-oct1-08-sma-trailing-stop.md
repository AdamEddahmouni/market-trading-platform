# OCT1-08 — SMA trailing-stop risk control: implementation and evaluation

Classification: SOFTWARE_CONTROLLED (software behaviour) and HISTORICAL_REPLAY (method comparison). Implementation date: 2026-10-06.
Current architecture: [SMA trailing-stop risk control](../../architecture/PAPER_SMA_TRAILING_STOP.md).

## Requirement

The professor proposed a trailing stop based on an SMA rather than on raw
price, to "stop bleeding". The tracker item asks that the behaviour be formally
defined and reproducible, that long and short behaviour be explicit, that stop
updates cannot loosen risk, that a paper/replay evaluation compare it with
appropriate alternatives, and that no superiority be claimed without evidence.

This is a method to implement and test. It is not assumed to work.

## Repository boundary

- Base: `origin/main` `47131a22cbcf34a32a961cdd7672314f9537dd38` (OCT1-07 merge, #463), re-fetched and unchanged at start.
- Branch `codex/oct1-08-sma-trailing-stop`, worktree `.worktrees/oct1-08-sma-trailing-stop`.
- Edits only under `projects/integrated-market-platform/`. The primary checkout, `ui/screener-demo-polish` and every other worktree were not touched.
- Exact implementation and merge SHAs, required checks and verified remote main belong to the PR and the OCT1-08 task ledger.

## Audit and reuse

| Authority | Finding | Use |
|---|---|---|
| Paper ledger (`paper/ledger.py`) | Event-sourced, integer minor units, one net equity position per session, no position identity | Position truth; episode derived from `PositionChanged` fill lineage |
| Paper order types | `MARKET`, `LIMIT` only | Unchanged; no native stop order added |
| Paper close handoff (`screener_action.handoff`, `validate_order_source`) | EXIT quantity from the ledger, re-checked at preview and submit | Reused unchanged as the only route to an order |
| OCT1-06 action decisions | EXIT required a model proposal; validator bans model-authored stops/SMA/levels | Extended with one server condition; validator unchanged |
| OCT1-07 reevaluation | Safety precedence bypassed the dwell but not model availability or call caps | Stop check added before the model; a breach bypasses both |
| `ExecutionDecisionTraceV1` | Extensible through rule evaluations and config refs | Stop policy and stop state referenced; no schema or enum change |
| Local-state SQLite | Lazy-DDL repositories with in-memory fallback | New `sma_stop_records` / `sma_stop_events` in the same database |
| Completed bars (`market_data/current_bars.py`) | Complete vs forming bars, freshness states | Live bar source; forming bar never read |
| Decision quote | Last trade is the one current price | Trigger basis `LAST_TRADE_PRICE` |
| `BarConservativeSimulator` | SELL fills at the bar low; no stop or gap semantics | Its worst-in-bar convention is the replay exit model |
| SMA / technical code | No shared SMA; a float SMA-20 research example and a private Pine helper | Not reused; a new exact integer SMA |
| Pinned replay corpus | AAPL 1-minute RTH, 5 sessions, 1,950 bars, `HISTORICAL_DEVELOPMENT` | The evaluation corpus, fingerprint-verified, read-only |

## What was built

### Backend

- `risk/sma_trailing_stop.py` — pure policy: versioned policy and state, bar normalization, exact integer SMA with direction-aware rounding, monotonic trailing, effective-time rule, quote and bar triggers, position episode from the ledger.
- `local_state/sma_trailing_stop.py` — policies, stop state and append-only stop events; refuses loosening and terminal-state revival at the storage layer; bounded reads.
- `ui_api/paper_risk_control.py` — the one evaluation used by Evaluate Stop Now and by the reevaluation cycle; bounded configuration; read-only projections; server EXIT through the unchanged decision append path.
- `intelligence/inference/action_decision.py` — `SMA_TRAILING_STOP_BREACHED` server condition; gate exits without a proposal; the condition is excluded from model-selectable ids.
- `ui_api/screener_action.py` — server-exit record (`server_exit`, null model), trace references, read-only `risk_control` context.
- `intelligence/inference/reevaluation.py`, `ui_api/screener_reevaluation.py` — breach as a safety reason; stop evaluated before any model; deterministic stop updates recorded without a model call.
- `research/sma_stop_evaluation.py`, `tools/research/run_oct1_08_sma_stop_evaluation.py` — frozen definition, point-in-time replay, receipt.
- Routes under `/paper/risk-control/sma-stop` with `audit.read` / `state.write`; none carries `paper.order.submit`.

### Frontend

- `api/paperRiskControl.ts` — zod schemas for status, config, history and the replay receipt.
- `paper-workspace/PaperTrailingStopPanel.tsx` with `buildPaperTrailingStopModel.ts` — mounted in the Paper cockpit after the risk context: status, LONG/SHORT stop in words, policy, window, SMA, candidate, active and previous stop, distance, last update, monitoring, warm-up, stale, clamp and breach text, bounded policy form, bounded history, Evaluate Stop Now.
- `paper-workspace/SmaStopEvaluationTable.tsx` — four-method comparison with captions, conclusion, sample note and hashes.
- `screener/panels/ActionDecisionPanel.tsx` — server-authored exits show the stop, observation and policy, and "Model: none".
- Every state is text. Colour carries no meaning.

## Decisions worth knowing

- **Monitor, not an order.** No STOP/OCO order type was added. The UI and API say `NONE_STOP_MONITOR_ONLY` and `Paper close: NOT SUBMITTED`.
- **Reference configuration.** SMA 20 on completed 1-minute bars, fixed before any outcome was read and labelled `REFERENCE_TEST_CONFIG`. No window was searched.
- **Rounding toward protection.** Long stop rounds up, short stop rounds down, tick 1 minor unit.
- **Effective time.** A level computed from bar k is in force only for observations at or after bar k's availability.
- **Window may span a session break; a missing intraday bar blocks the update.** No close is ever synthesized.
- **First stop already through the price** is an immediate exit condition, not stored as protection.
- **Policy change while active is rejected.** Disable is explicit; re-enabling on the same position carries the earlier level.
- **Breach keeps the EXIT under degraded inputs.** Pending order, lost authority or stale quote block the preview, not the risk state.
- **Stop facts are context, not a capability.** Adding a capability would have changed the missing-evidence set every model proposal must echo.
- **Response guard.** The API secret-leak guard rejects keys containing "auth"; the stop projections use `source`, `origin` and `corpus_evidence_label`, and tests run the guard on every projection.

## Evaluation method

Frozen in `evidence/historical-research/oct1-08-sma-trailing-stop-replay-v1/pre_execution_frozen_experiment_definition.json`
and committed, with the policy and evaluation code, before the comparison was run.
The runner refuses to execute if the committed definition differs from the code.

| Item | Frozen choice |
|---|---|
| Corpus | pinned OpenD AAPL 1-minute RTH bars, sessions 2026-09-10, -11, -14, -15, -16; 1,950 bars; 0 missing intervals; `HISTORICAL_DEVELOPMENT`; split adjustment `PROVIDER_QFQ_NOT_RECONCILED` |
| Policy | `REFERENCE_TEST_CONFIG`: SMA 20, 1-minute completed bars |
| Entries | fixed schedule: signal at the first bar with a full in-session window, then every 30 bars; entry at the next bar's open; at least 30 bars after entry; long (primary) and short |
| Matched risk | `D = |entry - initial SMA stop|`, the same for the fixed stop and the raw-price trail |
| Methods | SMA trail; raw-price trail (high-water of completed closes minus D); fixed initial stop; no-trail (session-close exit) |
| Trigger | long `low <= stop`, short `high >= stop`, only for a stop effective at the bar's start |
| Fill | stop exit at the trigger bar's worst price, never at the stop level; horizon exit at the last close |
| Costs | 5 bps per side (the existing historical-research default); gross and net reported separately |
| Exclusions | initial stop not protective (`D <= 0`); gap in the signal window; session too short |
| Conclusion | four tokens, none asserting superiority; `INSUFFICIENT_EVIDENCE` below 20 sessions or 3 instruments |

No parameter was changed after results existed. Definition hash
`48769d3d422944d0455c5936840b309c450aecae06f6672ada9617221b399883`; result hash
`2b77ff44aafb503c94b7a359e31c32adb2fe0802a09438b483b4244eb63d24e0`, reproduced
on a second run; corpus file hashes identical before and after.

## Comparative results

120 scheduled episodes (60 long, 60 short). 59 were evaluable (31 long, 28
short); 61 were excluded because the SMA was not on the protective side of the
entry price. That exclusion is structural: at each entry only one side has a
protective SMA.

Long episodes (primary), basis points of entry price:

| Method | Episodes | Stopped | Mean adverse excursion | Mean max drawdown | Worst drawdown | Loss severity | Mean gross return | Mean net return | Exited before a better horizon price | Mean bars held |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA trail | 31 | 100.0% | 7.34 | 12.18 | 30.22 | -8.86 | -1.53 | -11.53 | 48.4% | 7.42 |
| Raw-price trail | 31 | 100.0% | 8.26 | 12.33 | 30.22 | -11.01 | -2.78 | -12.78 | 48.4% | 5.23 |
| Fixed initial stop | 31 | 93.5% | 10.97 | 25.59 | 141.59 | -11.27 | -2.52 | -12.52 | 41.9% | 25.00 |
| No-trail (session close) | 31 | 0.0% | 47.16 | 75.05 | 157.23 | -46.43 | 16.17 | 6.17 | 0.0% | 206.45 |

Short episodes (policy math only):

| Method | Episodes | Stopped | Mean adverse excursion | Mean max drawdown | Worst drawdown | Loss severity | Mean gross return | Mean net return | Exited before a better horizon price | Mean bars held |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA trail | 28 | 100.0% | 8.46 | 12.28 | 26.49 | -9.09 | -3.59 | -13.59 | 42.9% | 6.93 |
| Raw-price trail | 28 | 100.0% | 10.61 | 14.91 | 93.03 | -11.54 | -8.19 | -18.19 | 50.0% | 7.61 |
| Fixed initial stop | 28 | 89.3% | 13.42 | 21.76 | 125.80 | -13.87 | -7.51 | -17.51 | 39.3% | 32.07 |
| No-trail (session close) | 28 | 0.0% | 60.67 | 73.85 | 224.76 | -52.61 | -17.90 | -27.90 | 0.0% | 207.14 |

What the measurements show, and no more:

- Every stop method cut adverse excursion and drawdown sharply against holding to the close. That is what a stop does; it is not specific to the SMA.
- On long episodes, holding to the close had the highest mean gross return (+16.17 bps) and every stop method had a negative one. The stops were hit in almost every episode, typically within a few minutes, and about half of the SMA exits happened before a better horizon price. Downside fell and return fell with it.
- Among the three stop methods the SMA trail had the lowest mean adverse excursion and loss severity in this sample, by small margins (for example 7.34 against 8.26 and 10.97 bps). The session-level sign of that difference agreed in at least four of five sessions against each alternative.
- One long SMA exit gapped through the stop. Exits are priced at the bar's worst price, so no stop is assumed to fill at its level; under the alternate fill (worse of stop and open) mean long gross return is +0.72 bps for the SMA trail, +0.63 raw, -0.10 fixed.
- With 5 bps per side, every stop method is net negative in both directions.

**Conclusion under the frozen rule: `INSUFFICIENT_EVIDENCE`.** In-sample pattern
(description only): `NO_CLEAR_DIFFERENCE`. Superiority claim: none. Five
sessions of one instrument, with overlapping episodes inside each session,
cannot support a directional claim about the SMA trail against the raw-price
trail or the fixed stop, and the comparison against no stop shows the expected
tradeoff rather than an advantage.

## Validation ledger

Local Windows, Python 3.11.15, final source.

| Gate | Result |
|---|---|
| Focused backend (stop policy, decision integration, replay evaluation, OCT1-06/07 regressions) | 163 tests, 0 failures (73 new) |
| Focused UI (Paper Workspace and Screener panels) | 161 tests, 25 files, 0 failures |
| Complete UI, default parallelism | 1,313 tests, 173 files, 0 failures |
| UI typecheck, build, bundle budget | pass; initial 99.73 KiB gzip (99.71 before; budget 130) |
| `imp.py format`, `imp.py lint` | pass |
| FAST | 23 tests, 0 skipped, 0 failures, 0 errors |
| CHANGED | 3,580 tests, 31 skipped, 0 failures, 0 errors (275.2 s) |
| FULL | 8,001 tests, 53 skipped, 0 failures, 0 errors (414.5 s) |
| Docs links, monorepo guard, history ledger | pass |
| Controlled Chromium acceptance | 27/27 steps plus a SQLite-recovery check |

Timing classifications reported by the runner (`SEVERE_REGRESSION` on FAST and
FULL, `INSUFFICIENT_DATA` on CHANGED) are observe-only against a historical
baseline, were present before this work, and are recorded unchanged.

Non-green attempts during development, all `OCT1_08_REGRESSION` and fixed before the final runs:

| Attempt | Cause | Fix |
|---|---|---|
| New episode started above the old stop | a fresh state replayed bar history from before activation | a new episode starts from the latest completed bar only; regression test added |
| Second EXIT recorded for one breach | the loop re-recorded a breach already recorded by Evaluate Stop Now | `STOP_EXIT_ALREADY_RECORDED` suppression; test added |
| API returned an error for decisions and the replay receipt | response secret guard rejected keys containing "auth" | fields renamed; the guard now runs in tests on every stop projection |
| Browser step 18 read quantity 1 | acceptance script read the ticket before the handoff re-rendered it | script waits for the handed-off draft |

## Requirement-to-test map

| Requirement | Test |
|---|---|
| Long never loosens (100/102/101/105 -> 100/102/102/105) | `MonotonicTests.test_long_stop_never_moves_down` |
| Short never loosens (100/98/99/95 -> 100/98/98/95) | `MonotonicTests.test_short_stop_never_moves_up` |
| Adverse SMA clamps; random paths | `test_adverse_sma_clamps_and_says_so`, `test_random_paths_never_loosen` |
| Warm-up, partial, future, duplicate, shuffled, missing, malformed bars | `BarAdmissionTests` |
| No same-bar look-ahead (stop and first stop) | `TemporalTests.test_stop_from_bar_k_is_not_applied_to_bar_k`, `test_first_stop_is_not_tested_against_its_own_bar` |
| Long/short breach boundaries, gap | `test_long_bar_breach_boundaries`, `test_short_bar_breach`, `test_gap_through_stop_is_recorded_not_filled_at_the_stop` |
| Stale quote; quote older than the stop | `test_stale_quote_proves_neither_breach_nor_safety`, `test_quote_older_than_the_stop_cannot_trigger_it` |
| Episode lifecycle: close, reversal, partial reduction, late activation | `ServiceTests`, `EpochTests` |
| Restart; different position after restart; storage guards | `PersistenceTests` |
| Config change cannot loosen | `test_config_change_while_active_is_rejected_and_cannot_loosen` |
| Stale bars, unavailable bars, downtime gap, bounded history | `ServiceTests` |
| Dwell does not block the breach; no model call; no model available | `ReevaluationStopTests.test_breach_exits_inside_the_dwell_without_a_model_call`, `test_breach_exits_with_no_model_available_at_all` |
| Model cannot author, select or veto | `ConditionTests` |
| Zero Paper/Live submission; no order code in the stop modules | `test_breach_never_submits_paper_or_live` |
| Handoff uses ledger quantity | `test_handoff_uses_current_ledger_quantity_not_the_stop` |
| Tightening without a model call; unchanged stop | `test_routine_tightening_is_recorded_without_a_model_call` |
| Matched baselines; baseline anti-look-ahead | `EpisodeTests` |
| Reproducibility and hashes; corpus untouched | `EvaluationTests` |
| No superiority token | `FrozenDefinitionTests.test_no_superiority_token_exists` |
| UI states, breach, handoff, comparison, insufficient evidence | `PaperTrailingStopPanel.test.tsx`, `buildPaperTrailingStopModel.test.ts`, `ActionDecisionPanel.test.tsx` |

## Controlled browser acceptance

`tests/acceptance/harness_sma_trailing_stop.py` with `tools/ui1/oct1_08_browser.cjs`,
isolated state directory, ports 18808/15108. Production stop, decision, trace,
reevaluation and SQLite code; controlled bars, quote, position, model proposal,
auth and clock. Receipt: `artifacts/oct1-08-browser.json`.

All 27 required steps passed: Paper position context; stop view; reference
policy; warm-up at 5 of 20 bars; active stop 148.00 with SMA 148.0000;
tightening to 148.10; a falling SMA (candidate 148.00) held at 148.10; a
controlled short episode (147.90 -> 147.50, then a rising candidate of 148.10
held at 147.50); stale bars with the level kept; recovery; a breach at 148.05
against 148.10; a server EXIT 60 seconds into a 300-second dwell with no model
call; the stop policy and evidence in the decision record with the earlier
HOLD byte-identical; the existing exit handoff with quantity 7 and side SELL;
zero submit attempts and zero ledger events; zero Live calls; the four-method
replay table; the `INSUFFICIENT_EVIDENCE` conclusion; hashes; and an unchanged
corpus file. An extra step re-read the stop from SQLite through a fresh service.

The ticket's own revalidation preview of the handed-off draft ran once and was
rejected (`UNKNOWN_INSTRUMENT`), because the harness instrument is a fixture
the replay store does not know. An accepted Paper preview of a stop exit was
therefore not shown in the browser.

## Runtime and market acceptance

| Class | Status |
|---|---|
| Fixture / software-controlled | Executed (unit, integration, browser) |
| Historical replay | Executed on the pinned corpus; `REPLAY_EVALUATED` |
| Current Paper position, prospective observation | `NOT_EXECUTED` — no real open Paper position was used; none was fabricated |
| Live provider bars and quotes | `NOT_EXECUTED` |
| Real one-minute scheduled loop | `NOT_EXECUTED` |

## Performance

Local measurements (`tools/research/measure_oct1_08_performance.py`, receipt `artifacts/oct1-08-performance.json`).

| Measure | Result |
|---|---|
| Stop update, window 20, 390 bars | mean 0.011 ms, p95 0.014 ms |
| State write / read (SQLite) | mean 0.044 ms / 0.011 ms |
| Reevaluation cycle, controlled fixtures | 0.74 ms without a stop; with a stop p95 3.3 ms (mean 7.0 ms including the first evaluation and the fixture bar builder); 0 extra model calls |
| Replay | 120 episodes over 1,950 bars in 0.11 s |
| UI bundle | initial +0.02 KiB gzip; Paper Workspace chunk 18.91 kB gzip |
| FULL | 414.5 s for 8,001 tests (423.7 s for 7,928 at OCT1-07) |

## Review

Read-only review of the final diff against the stated risks:

| Risk | Finding |
|---|---|
| Look-ahead; same-bar update and trigger | Both triggers go through `effective_stop`; new episodes take only the latest completed bar. One defect found and fixed (history replay into a new episode). |
| Long/short inequalities | One `_crossed` function for both triggers; boundary tests on each side. |
| Stop loosening | `trail` plus a storage-layer refusal; config change rejected; re-enable carries the level. |
| Float and rounding | Integer minor units and `Decimal` only; floats appear in display-only basis points. |
| Episode contamination | State keyed by ledger-derived epoch; flat, reversal and epoch change close it. |
| Restart | State and policy re-read; a different epoch is closed, not applied; downtime is a gap event. |
| Stale quote | `TRIGGER_UNAVAILABLE`; neither breached nor safe. |
| Auto-submit | No order, preview or handoff call exists in the stop modules; asserted by source scan and spies. |
| Unfair baselines | One distance D, one trigger rule, one fill rule for all stop methods. |
| Superiority overclaim | No such token; conclusion fixed by sample-size rule; UI text scanned in tests. |

## Known limitations

- The stop is evaluated only while the reevaluation loop runs or on request. Time IMP is not running is `NOT_OBSERVED`.
- The current trigger samples the last trade at each evaluation; a cross that recovers between evaluations is not seen.
- Evidence is one instrument and five sessions with overlapping episodes; conclusions are descriptive.
- The corpus's split adjustment is not reconciled (`PROVIDER_QFQ_NOT_RECONCILED`).
- The replay entry rule is a schedule, not a strategy; results say nothing about any entry signal.
- Worst-in-bar exit pricing is deliberately harsh and affects all stop methods equally.
- An EXIT decision needs admissible evidence for the instrument; without it the breach is recorded on the stop only.
- The Paper equity projection is one net position per session.
- No prospective Paper or live-provider run was performed.

## Scope stop

OCT1-09, OCT1-10 and OCT1-11 were not started. No $100,000 portfolio, no
lifecycle Screener redesign, no performance framework, no native stop orders,
no parameter search, no profitability claim.
