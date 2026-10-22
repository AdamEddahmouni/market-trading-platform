# OCT1-07 — Next-session snapshot and reevaluation: implementation and acceptance

Classification: SOFTWARE_CONTROLLED. Implementation date: 2026-10-06.
Current architecture: [next-session snapshots and governed reevaluation](../../architecture/SCREENER_REEVALUATION.md).

## Repository boundary

Canonical monorepo: AdamEddahmouni/market-trading-platform. IMP path:
projects/integrated-market-platform. Base: e78797fb76f8a478b98a19128e14876c8ae7f759
(OCT1-06 merge, PR #462), verified against `origin/main` before branching.
Branch: codex/oct1-07-reevaluation. Isolated worktree outside the primary
checkout; the dirty primary checkout, `ui/screener-demo-polish`, older OCT1
worktrees and the nested leftover clone were not touched. Exact implementation
and merge SHAs, required checks and verified remote main belong to the PR and
the OCT1-07 task ledger; Done requires that receipt.

## Audit and reuse

| Authority | Finding | Use |
|---|---|---|
| OCT1-06 `ScreenerActionService` / `ActionDecisionV1` / local-state history / `ACTION_ASSESSED` trace | Deterministic preview, one model call per run, gate already fails closed on held-position ENTER, pending orders, stale quote and stale position snapshot | Every reevaluation decision goes through it unchanged; snapshots reference its records |
| OCT1-04 `ScreenerAiService._packet` / `CandidateReducer` | Bounded deterministic evidence rebuild; reduction is one model call | Evidence check tick and candidate-universe refresh |
| OCT1-03 freshness contract | Each evidence item already carries source, delivery mode, status, policy, `as_of`, `valid_until` | Cadence truth table; no new clocks |
| `paper_forward_bridge` | Service `create_decision`/`lock_decision` require campaign binding and activation | Only state names, transition table, temporal guards and outcome split are reused; campaign machinery untouched |
| Calendar | `shadow.session.session_bounds_ns`; EVIDENCE-01 frozen US holidays 2025–2026; no early-close list | Next-session target; unsupported cases fail visibly |
| Runtime | No shared scheduler; per-feature daemon threads; lease pattern in the enrichment outbox; no `governance/` package exists | One small worker with an expiring SQLite lease |
| Engine budget | `budget_status()` on paid providers; cache-only News preview path | Hard caps plus existing provider budget; no News refresh |
| Paper ledger | Positions, orders and consumed Opportunity provenance | Position authority and duplicate-entry checks |

## What was built

Backend

- `intelligence/inference/reevaluation.py` — pure policy: trigger/transition/status
  enums, `reevaluation-policy/1.0.0`, effective cadence, slot math, material
  fingerprint and change reasons, stability (dwell + safety precedence),
  per-capability provider states, readiness, worst-case call projection.
- `local_state/reevaluation.py` — snapshots, append-only observations, cycle
  receipts, loop configuration/liveness/lease on the existing local-state DB.
- `ui_api/screener_next_session.py` — target session, frozen evaluation policy,
  draft/lock/observe/evaluate, comparison.
- `ui_api/screener_reevaluation.py` — `ReevaluationService` (configure, status,
  start, stop, run-once, history, single core `evaluate_cycle`) and
  `ReevaluationWorker`.
- `ui_api/server.py`, `platform/security/route_policy.py` — eleven routes.
- Additive only in OCT1-06/OCT1-04 code: `ScreenerActionService.run(...,
  revalidation_reason=)`, `_authority()`, `ScreenerAiService._packet(...,
  include_flow=)`, `run(..., refresh_news=)`. Defaults preserve prior behaviour.

Frontend

- `api/screenerReevaluation.ts`; `NextSessionPanel` inside the action-decision
  panel (current decision and each history entry); `ReevaluationPanel` inside
  the AI Screener panel. Every state is text; nothing depends on colour.

## Decisions worth knowing

- **Run Once and the scheduler share one function.** There is no second decision path.
- **Material gate before any model call.** Unchanged cycles write a ~2 kB receipt
  and nothing else.
- **Held positions do not depend on AI reselection.** A server-authored per-cycle
  candidate run carries fresh evidence into the OCT1-06 service.
- **Churn is controlled by not re-asking**, not by discarding an answer: inside
  the dwell after ENTER/EXIT/HOLD a non-safety change is recorded as
  `CHURN_SUPPRESSED` and no decision record or handoff authority is created.
- **Safety beats dwell**: position change, new pending order, lost quote, lost
  Paper authority, met exit condition.
- **Overrun policy is skip.** A slot that passed while a cycle was running is
  counted as missed, never run late or in parallel.
- **Downtime is a single `NOT_OBSERVED` receipt.** Nothing is backfilled.
- **Nothing auto-starts**, including after restart (`INTERRUPTED` until the
  operator presses Start).
- **Dwell, price threshold and age defaults are operational**, chosen to bound
  work and churn; they are not tuned trading parameters.

## Validation ledger

Final-source results (Windows, Python 3.11.15, canonical runner):

| Gate | Tests | Skipped | Failures / errors | Seconds | Disposition |
|---|---:|---:|---:|---:|---|
| FAST | 23 | 0 | 0 / 0 | 2.934 | PASSED |
| CHANGED | 5,841 | 35 | 0 / 0 | 349.656 | PASSED |
| FULL | 7,928 | 53 | 0 / 0 | 423.718 | PASSED |
| Focused backend (OCT1-07 + OCT1-04/05/06 + forward-test) | 183 | 0 | 0 / 0 | 10.947 | PASSED |
| OCT1-07 suites alone (`test_next_session`, `test_reevaluation`) | 63 | 0 | 0 / 0 | — | PASSED |
| Focused UI (new panels + action panel) | 15 | 0 | 0 / 0 | — | PASSED |
| Complete UI, 171 files, single worker | 1,296 | 0 | 0 / 0 | 316.13 | PASSED |

FULL has 7,875 non-skipped passing tests. A last CHANGED pass after the
documentation and receipts were added selected 5,783 tests (35 skipped) and passed
with zero failures/errors in 369.549 s; product source was identical. Timing: FAST and FULL report
`SEVERE_REGRESSION` against the historical baseline and CHANGED reports
`INSUFFICIENT_DATA`; these are observe-only, were already present before this
task, and are recorded here independently without rebasing any baseline. FULL
measured 412.8 s at OCT1-06 and 423.7 s here on a different host condition; no
timing claim is made either way.

Static: canonical lint (Python compile + TypeScript typecheck) and format passed;
production build passed (initial 99.71 KiB gzip against the 200 KiB budget,
+0.01 KiB versus the OCT1-06 record; the lazy AI Screener chunk is 39.88 kB raw /
11.63 kB gzip); documentation links, monorepo guard and history-ledger validation
passed.

Non-green attempts, retained:

| Attempt | Result | Classification |
|---|---|---|
| First FULL (before two late review fixes) | 7,928 / 53 skipped / 0 / 0 in 433.719 s | superseded by final-source FULL |
| Second FULL | 1 error: `tests/ui1/test_news_event_v1_request_path.py::NewsIngestHttpTests::test_http_post_rejects_oversized_body`, `WinError 10053` | `INTERMITTENT` / `ENVIRONMENT` — same selector and error recorded at OCT1-05; passed in isolation and in the final FULL |
| Complete UI, default parallelism, run concurrently with FULL | 4 failures, all `src/App.test.tsx` lazy-route navigation | `INTERMITTENT` — 76/76 in isolation |
| Complete UI, default parallelism, run alone | 4 failures: 3 `App.test.tsx`, 1 `Participants.test.tsx` | `INTERMITTENT` — 93/93 in isolation; single-worker complete run passed |
| `imp.py test focused` with file-path selectors | worker error `invalid selector` | `ENVIRONMENT` (operator error: the runner needs `path::Class::method`); suites rerun with unittest |

No assertion, timeout or guard was changed to obtain a pass. No failure was
classified `OCT1_07_REGRESSION`.

## Requirement-to-test map

| Requirement | Test |
|---|---|
| Lock immutability (state, evidence, target, policy) | `test_lock_makes_every_frozen_field_immutable` |
| Weekend / holiday / coverage | `test_friday_targets_monday_not_saturday`, `test_market_holiday_is_skipped_from_the_calendar_authority`, `test_outside_calendar_coverage_fails_visibly` |
| No look-ahead | `test_lock_refuses_look_ahead`, `test_later_evidence_and_reevaluation_never_enter_the_frozen_snapshot` |
| Observation order | `test_observation_clocks_are_guarded` |
| Evaluation too early | `test_evaluation_before_frozen_horizon_is_rejected` |
| Later outcome | `test_later_outcome_is_compared_and_original_is_unchanged` |
| Signal vs execution | `test_signal_without_paper_execution_is_not_applicable_not_zero`, `test_execution_outcome_requires_a_real_paper_order_for_this_decision` |
| 60 s cadence, no overlap | `test_sixty_second_cadence_identities_and_no_overlap` |
| Effective cadence | `test_effective_cadence_drives_the_schedule_and_both_are_reported` |
| Slow / delayed provider | `test_slow_reference_evidence_is_never_labelled_minute_fresh`, `test_delayed_quote_stays_delayed_and_degrades_readiness` |
| Stale critical quote | `test_stale_quote_fails_visibly_without_model_or_handoff` |
| No material change / material change | `test_first_cycle_then_no_material_change_avoids_model_and_records_receipt`, `test_material_change_creates_new_immutable_decision`, `test_small_price_noise_is_not_material` |
| New / removed candidate, bounds | `test_new_and_removed_candidates_are_bounded_and_history_survives` |
| Duplicate entry | `test_duplicate_entry_is_suppressed_for_held_position`, `test_active_enter_is_not_reissued_for_the_same_state`, `test_consumed_opportunity_does_not_get_a_new_entry_path` |
| Churn / safety exit | `test_churn_oscillation_is_suppressed_with_explicit_reason`, `test_safety_exit_is_not_blocked_by_dwell_but_the_flip_back_is` |
| Pending order / position change | `test_pending_order_blocks_duplicate_entry_without_model`, `test_position_change_uses_current_ledger_not_prior_decision` |
| Missed cycles / restart | `test_process_downtime_marks_missed_cycles_without_backfill`, `test_stop_then_start_records_not_observed_gap_and_resumes_prospectively`, `test_stalled_runtime_is_not_observed_not_reconstructed`, `test_overrun_skips_slots_instead_of_overlapping` |
| Duplicate worker / lease recovery | `test_duplicate_worker_rejected_and_expired_lease_recoverable`, `test_heartbeat_renews_lease_while_waiting` |
| Restart persistence / persist-off | `test_locked_snapshot_observations_and_config_survive_restart`, `test_reconfigure_requires_stop_and_persist_off_is_ephemeral` |
| Model budget / caps / engine | `test_paid_budget_exhaustion_blocks_before_any_request`, `test_policy_hourly_cap_is_a_hard_bound`, `test_missing_engine_is_model_unavailable_not_a_silent_switch` |
| Prompt injection | `test_market_text_cannot_reconfigure_cadence_or_submit` |
| Paper / Live submit spies | `test_cycles_never_submit_paper_or_live`, `test_routes_are_account_scoped_and_never_carry_submit_capability` |
| Provider and model fan-out | `test_provider_and_model_fanout_stay_bounded` |

## Controlled browser acceptance

`tests/acceptance/harness_reevaluation.py` (loopback, isolated `IMP_STATE_DIR`,
SQLite persistence on, every `/paper/*`, `/live/*` and submit route refused and
counted) with `tools/ui1/oct1_07_browser.cjs`. Production services, routes,
persistence, lease and receipts; fixtures are the Screener evidence reader, model
proposal, held-position/pending-order projections, auth and the clock. The
schedule runs on an **accelerated controlled clock** through the production
worker: this is software/runtime evidence, not market-data freshness proof.
Receipt: `artifacts/oct1-07-browser.json`. All 27 required steps passed; the run
ended with 14 cycle receipts, 6 model calls, 2 reductions, 14 evidence reads,
0 News provider refreshes, 0 submit-route attempts and 0 added ledger events.

Found and fixed by the real server path during acceptance: a response key named
`calendar_authority` was blocked by the existing secret-leak audit (renamed
`calendar_source`); the pre-start readiness assessment was dropped by the panel's
refresh; a restarted loop was reported `DELAYED` against a pre-stop completion.

## Runtime and provider acceptance

| Kind | Status |
|---|---|
| Fixture / accelerated-clock runtime | Executed (unit, worker and browser) |
| Real wall-clock worker thread | Executed once in `test_real_thread_start_stop` and the performance run: start, first cycle, stop, join. Runtime evidence only |
| Real 60-second wall-clock loop | `NOT_EXECUTED` |
| Local model runtime | `NOT_EXECUTED` (not configured in this environment) |
| Hosted model | `NOT_EXECUTED` (no paid request was sent) |
| Live provider cadence (source/receive timestamps, skipped cycles) | `NOT_EXECUTED` |

`ONE_MINUTE_REALTIME_VALIDATED` is **not** claimed.

## Performance and projected request volume

`artifacts/oct1-07-performance.json` (fixture model, SQLite WAL, five tracked
candidates, one held position):

- no-material-change cycle: p50 0.98 ms, p95 1.52 ms, 0 model calls, 1 evidence read;
- material cycle (excluding real model latency): p50 4.26 ms, p95 8.78 ms;
- lease acquire / heartbeat: p50 0.07 ms; first-cycle start drift 0 ms;
- receipt 2.0–2.5 kB (bound 32 kB); write p50 0.04 ms; 20-row history p50 0.16 ms.

Request volume, not cost (no pricing metadata is used): at a 60 s cadence over a
390-minute session the caps allow at most **120 model calls per loop per day**
(3 per cycle, 30 per hour, 120 per day), versus 2,340 for a naive
"reduce + five actions every minute". The provider's own daily request/token
budget applies in addition. Real model latency was not measured.

## Review

Read-only review of the diff against: look-ahead leakage, scheduler overlap,
duplicate workers, restart semantics, duplicate-entry risk, state churn, provider
fan-out, paid-model runaway, stale evidence, accidental Paper submission.
Findings fixed before integration:

- a worker could be retargeted if another scope was configured while it ran —
  cycles are now bound to the leased loop id and configure is refused while a
  worker is alive;
- Stop from a non-owning process would have marked another process's loop stopped
  without stopping it — now refused;
- a storage failure inside the worker left it looking idle — now `STALLED` with
  `last_error`;
- a provider budget refusal was counted as a model call — now excluded.

## Known limitations

- Calendar: 2025–2026 holidays only, no early-close list; next-session supports
  US equities/ETFs only and refuses everything else.
- Single host: thread in the UI API process with a SQLite lease. After a crash a
  new process waits out the old lease (≤180 s) before it can start.
- Model-call caps are per loop; only the provider budget bounds several loops together.
- A held instrument outside the bounded intake is read by symbol search; if the
  Screener cannot return it the cycle records `HELD_INSTRUMENT_EVIDENCE_UNAVAILABLE`.
- Operational defaults (50 bps, 300 s dwell, 900 s age, 300 s candidate refresh)
  are untuned against real sessions.
- No empirical cadence, model-latency or provider evidence was collected.
- The UI exposes cadence only; other policy overrides are API-only.

## Scope stop

No SMA or trailing-stop logic, no experimental portfolio or P&L lifecycle, no
final trade-lifecycle Screener, no performance metrics, no automatic Paper or
Live submission. OCT1-08, OCT1-09, OCT1-10 and OCT1-11 were not started.
