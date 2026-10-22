# OCT1-09 — $100K live-market Paper portfolio and complete P&L lifecycle

Classification: SOFTWARE_CONTROLLED (accounting lifecycle) and
PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA (one bounded live-market
session, no trade). The two are separate evidence classes and their numbers are
never combined. Implementation date: 2026-10-06.
Current architecture: [Paper portfolio experiment](../../architecture/PAPER_PORTFOLIO_EXPERIMENT.md).

## Requirement

The Paper environment initializes with approximately $100,000 of simulated
capital; tracks cash and buying power, positions, quantity, entry and exit,
realized and unrealized P&L, total equity and trade history; states slippage
and fee assumptions where modeled; and keeps live/current market data and
simulated execution clearly distinct from live-capital execution.

This item owns the Paper experiment and its accounting. It does not own the
final lifecycle Screener (OCT1-10) or profitability metrics (OCT1-11), and it
makes no claim that any strategy is profitable.

## Repository boundary

- Base: `origin/main` `7800b690f0fcf4184c50a528dae8af9f242e3577` (OCT1-08 merge, #464), unchanged at start and at resume.
- Branch `codex/oct1-09-100k-paper-portfolio`, worktree `.worktrees/oct1-09-100k-paper-portfolio`.
- Edits only under `projects/integrated-market-platform/`. The primary checkout and every other worktree were not touched.
- Exact implementation and merge SHAs, required checks and verified remote main belong to the PR and the OCT1-09 task ledger.

## Audit of the base

| Finding on `7800b690` | Where |
|---|---|
| The account id hashed the seed instrument, so each instrument got its own account and its own starting cash | `paper/ledger.py` `open_session` |
| Starting cash was always the $1,000,000 default; no API could set it | `risk/policy.py`, `ui_api/store.py` |
| Equity fills of every instrument pooled into one scalar position | `paper/ledger.py`, `portfolio/ledger.py` |
| One global mark, taken from the focused instrument, valued every position | `paper/ledger.py`, `ui_api/live_projections.py` |
| No equity in the account projection; "total P&L" was realized only | `ui_api/paper_projections.py` |
| No per-fill position effect, realized P&L or entry/exit clocks; lineage fields never populated by the API | `paper/execution.py` |
| An equity sell beyond holdings silently reversed to a short | `paper/execution.py` |
| No experiment identity and no equity history | — |

## What changed

### Account identity (additive, versioned)

`PaperExecutionLedger.open_session(..., experiment_id=...)` derives a
portfolio-scoped account id with no instrument in it (`account_identity_version
2`, `account_scope PORTFOLIO`). Without `experiment_id` the derivation is byte
identical to before. A ledger is portfolio scoped only if its own
`PaperAccountCreated` event says so, so persisted legacy sessions keep their
account id, pooled position and single mark. Legacy order intents are also byte
identical: lineage is recorded on experiment orders only.

### Per-instrument accounting and marks

`portfolio/ledger.py` gained `apply_portfolio_fill`, which runs the existing
per-fill arithmetic on the instrument's own slice of a shared-cash state and
records `position_effect`, costs, fill time and realized P&L delta per entry.
The ledger gained instrument-keyed marks, `position_shares_for`,
`reserved_cash_minor`, `project_valuation` and `project_trades`; for an
experiment account `project_positions` returns one row per instrument with its
own mark, market value and unrealized P&L (or `None` when unmarked). Pre-trade
risk and the financial check read the requested instrument's position. An
experiment sell beyond the held quantity is refused.

### Experiment contract, persistence, service, API

`paper/experiment.py` (contract), `local_state/paper_experiments.py`
(repository: experiments and append-only equity snapshots),
`ui_api/paper_experiment.py` (create, restore, read, close, trades, equity
history, boundary and assumptions blocks) and seven routes with route
policies. The existing preview and submit routes are reused; they now refuse
orders on a closed experiment or on a data-mode mismatch, attach lineage
references and the governed risk decision id, and return an
`experiment_context` on preview.

Schema: the two tables are created on demand, as the OCT1-08 stop repository
does. They are additive, nothing existing is migrated, and a database without
them reads as "no experiments", so no global schema version bump was added.

### Frontend

Paper Portfolio: experiment header, data/execution boundary, ten summary
values, valuation quality, per-instrument positions, trade history with
decision drilldown, assumptions, equity history, explicit create and
fail-closed close. Paper Workspace: experiment context above the order ticket.
The legacy "Archive session" and "New Paper Session" controls are hidden while
an experiment account is bound.

### Defects found and fixed while finishing

| Defect | Fix |
|---|---|
| The legacy `/paper/portfolio` unrealized sum crashed on an unmarked experiment position | sum skips missing values; the display is unavailable when any is missing |
| The experiment repository singleton was keyed by `id(connection)`, which can be reused after a reopen | holds the connection object itself |
| A forced close snapshot with the same numbers as the last fill was deduplicated away | lifecycle rows hash their trigger |
| `CANDIDATE_RUN` lineage read a field the action record does not have | reads `evidence_snapshot.candidate_run_id` |
| A governed EXIT without Opportunity lineage is handed off on a lane, and the lane snapshot dropped the action-decision references, so the exit was neither revalidated at the boundary nor attributed to its decision | the lane snapshot keeps `reasons` (`ui/src/components/paper/paperDecisionSourceSnapshot.ts`) |
| Return in basis points floored, so a loss rounded away from zero | truncates toward zero for both signs |
| An experiment could be created while internal Paper simulation was not authorized | create fails closed with `PAPER_EXECUTION_NOT_AUTHORIZED` before anything is written |
| A closed experiment hid the create action | the closed experiment stays readable and a new one is offered explicitly |

## Controlled complete lifecycle (SOFTWARE_CONTROLLED)

`tests/acceptance/harness_paper_experiment.py` with
`tools/ui1/oct1_09_browser.cjs`, isolated state directory, ports 18809/15109,
the production UI bundle. The production experiment service, preview/submit
route, pre-trade risk, bar-conservative simulator, ledger, SQLite state and
action-decision service are used. Only the completed-bar feed, the marks, the
candidate receipt, the model proposal, the governed Opportunity and auth are
fixtures. A restart is a real process kill and respawn over the same state
directory.

Receipt: `artifacts/oct1-09-browser.json` — 33 steps and 6 extra scenarios.

| Event | Cash | Realized | Unrealized | Equity |
|---|---:|---:|---:|---:|
| create | 100,000.00 | 0.00 | 0.00 | 100,000.00 |
| BUY 6 AAPL @ 150.00 (governed ENTER) | 99,100.00 | 0.00 | unavailable (no mark) | unavailable |
| mark AAPL 155.00 | 99,100.00 | 0.00 | +30.00 | 100,030.00 |
| BUY 50 NVDA @ 240.00 (operator ticket) | 87,100.00 | 0.00 | unavailable (NVDA unmarked) | unavailable |
| mark NVDA 236.00 | 87,100.00 | 0.00 | +30.00 − 200.00 | 99,830.00 |
| SELL 2 AAPL @ 155.00 (operator ticket) | 87,410.00 | +10.00 | +20.00 − 200.00 | 99,830.00 |
| process restart | 87,410.00 | +10.00 | −180.00 (marks restored, DEGRADED) | 99,830.00 |
| mark AAPL 153.00 | 87,410.00 | +10.00 | +12.00 − 200.00 | 99,822.00 |
| SELL 4 AAPL @ 153.00 (governed EXIT) | 88,022.00 | +22.00 | −200.00 | 99,822.00 |
| SELL 50 NVDA @ 236.00 (operator ticket) | 99,822.00 | −178.00 | 0.00 | 99,822.00 |
| process restart, duplicate submit retried | 99,822.00 | −178.00 | 0.00 | 99,822.00 |

The governed entry is six shares because the existing governed pre-trade risk
engine approves at most six AAPL shares at 150.00 on this account; nothing was
changed to make it larger. The partial close and the second instrument are
operator tickets, because a governed EXIT must close the exact held quantity.

Extra scenarios: missing mark never valued at zero; one unmarked position makes
equity unavailable; a stale mark degrades the valuation; close refused with
open positions; restart with two open positions; a flat experiment closes and
stays readable.

The controlled run ends at −$178.00. That is arithmetic on fixture prices. It
says nothing about any strategy.

## Prospective live-market session (PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA)

Receipt: `artifacts/oct1-09-prospective.json`. Tuesday 2026-10-06, US regular
session, Moomoo OpenD, worktree API on a loopback port with its own state
directory.

| Fact | Value |
|---|---|
| Experiment | `PPE-1CA4528C6CA5C2409D745EDA5FC3BF1F`, created about 14:05 ET |
| Initial simulated capital | $100,000.00 |
| Data mode / execution | `LIVE_OBSERVATIONAL` (Moomoo) / `INTERNAL_SIMULATION` |
| API restarts | 2; same experiment, $100,000.00, no re-seed, execution deferred until fresh execution-health authorization |
| Live quotes | Moomoo `REALTIME` quotes admitted by the decision-freshness policy (9 of 20 symbols in the saved window; examples in the receipt) |
| AI Screener | `NO_GROUNDED_CANDIDATES / INSUFFICIENT_EVIDENCE` on both configured runs (an earlier run returned `NOT_CONFIGURED`) |
| Action decision | `SELECTED_CANDIDATE_REQUIRED` |
| Result | `NO_QUALIFYING_ENTRY` |
| Orders / trades / live-capital orders | 0 / 0 / 0 |
| Paid model calls | 0 (the deterministic evidence gate stopped before any model call) |
| Equity at last read (19:22 UTC) | $100,000.00 |

No entry was forced: no threshold, gate, prompt, action state or risk policy
was altered, and no fixture was injected into the live path. The platform
refused to trade when grounded current evidence was insufficient, and that
result is kept as it is. A prospective realized lifecycle was not observed.

### Upstream limitation

Streaming quotes were healthy, but the AI Screener's admissible price evidence
remained the Finviz snapshot without an observation timestamp, so the OCT1-03
freshness gate correctly excluded it (`NO_OBSERVATION_TIME`) and no candidate
met the evidence gate. This is a narrow statement about which price evidence
the Screener rows carry in the live stack; it is not a claim that the live
Screener is broken. It was not changed here: the freshness policy, the
candidate gate and the Screener are outside OCT1-09. Until it is addressed, a
live AI-driven entry into the experiment is unlikely.

## Validation

All commands ran from the worktree on Windows with the project virtualenv.

| Gate | Result |
|---|---|
| New accounting suite (`test_paper_experiment_accounting.py`) | 41 / 41 |
| Experiment service, HTTP, persistence and restart suite (`test_paper_experiment_api.py`) | 29 / 29 |
| `tests/trading_correctness` (Paper ledger, execution, preview/submit, idempotency) | passed inside CHANGED and FULL |
| FAST | 23 tests, 0 skipped, 0 failures, 0 errors (2.8 s) |
| CHANGED | 5,970 tests, 35 skipped, 0 failures, 0 errors (325.8 s) |
| FULL | 8,071 tests, 53 skipped, 0 failures, 0 errors (521.0 s) |
| Complete UI (`npm test`) | 1,337 / 1,337 in 176 files |
| UI typecheck, `imp.py lint`, `imp.py format` | passed |
| UI production build and bundle budget | passed; initial 100.61 KiB gzip (budget 130; 99.73 before) |
| Docs links (`tools/check_docs_links.py`) | passed (290 governance files) |
| Monorepo guard, history ledger guard | passed |
| Workflow lint | not applicable (no workflow file changed) |
| Controlled Chromium acceptance | 33 / 33 steps, 6 extra scenarios |

OCT1-06, OCT1-07 and OCT1-08 suites (`tests/intelligence`, `tests/research`,
`tests/ui1`) run inside CHANGED and FULL. EXIT quantity still comes from the
ledger, now per instrument for an experiment account.

Failure classification during the work:

- `ENVIRONMENT/LOAD`: a first complete UI run that shared the machine with
  Python suites timed out 11 screener tests; the same tree passed 1,337 / 1,337
  when run alone.
- `ENVIRONMENT`: two earlier CHANGED runs on the final tree each reported
  errors and no failures (run 1: two, in `ui1` and `intelligence`; run 2: one,
  `tests/intelligence/test_agent_enrichment_ingest_http.py`
  `test_http_post_rejects_oversized_content_length_before_read`,
  `ConnectionAbortedError [WinError 10053]`, a Windows loopback socket abort).
  OCT1-09 does not touch those tests; they pass alone, in FULL, and in the
  third CHANGED run recorded above. No test was changed or skipped.
- `OCT1-09 REGRESSION (fixed)`: 14 `App.test.tsx` failures in that first run
  were a hooks mock missing the new experiment hooks.
- `TEST HARNESS`: two earlier regression attempts used a discovery form the
  repository does not support and produced no result; they are not counted.

The validator's timing classification (`perf=`) is observe-only and compares
against a baseline from a different load; it is not a pass/fail gate.

## Performance (local, SOFTWARE_CONTROLLED)

Receipt: `artifacts/oct1-09-performance.json`.

| Measurement | Result |
|---|---|
| Positions projection, 1 position (8 events) | 0.0185 ms mean |
| Valuation, 1 position | 0.0979 ms mean |
| Positions projection, 10 positions (62 events) | 0.2172 ms mean |
| Valuation, 10 positions | 0.6368 ms mean, 1.1353 ms p95 |
| Full `/paper/portfolio` payload, 10 positions | 2.8821 ms mean |
| Mark update, one instrument | 0.0009 ms mean |
| Mark update, all 10 positions | 0.0139 ms mean |
| Trade history page of 25 (200 fills, 1202 events) | 36.2429 ms mean |
| Equity history page of 50 (63 snapshots) | 0.5494 ms mean |
| Store boot and experiment readback (1202 events) | 477.7 ms mean |
| UI initial bundle | 100.61 KiB gzip (+0.88 KiB; budget 130) |
| FULL validation | 521.0 s |

Nothing was optimised. Trade-history paging recomputes the ledger per request;
that is the first place to look if experiments grow to thousands of fills.

## Known limitations

- The prospective session produced no trade, so the realized lifecycle is proven only under controlled fixtures.
- In fixture replay there is no per-instrument mark source: an open experiment position reports its mark as unavailable. Live observational mode marks each held instrument from its own quote.
- The ledger takes mark quality from the provider and marks an unreadable quote `STALE`; it has no mark-age threshold of its own. The mark's provider, time and age are shown.
- The experiment account is equity/ETF only; option and future orders are refused.
- Slippage is not separately modeled; adverse execution is the conservative bar fill. Commission and fees are zero under the frozen policy.
- Shorts and reversal are not enabled in the experiment account.
- The ledger recomputes from events on each projection; trade-history paging cost grows with ledger length (measured in the receipt).
- The Workspace order ticket's Preview button stays disabled after a handed-off draft's automatic preview under the React development server (StrictMode double effect). It does not occur in the production bundle, which the acceptance uses. Not changed here.
- `ledger_from_session` does not rebuild the derivative canonical portfolio on restore, and `intelligence/execution/snapshot.py` clamps its own equity estimate to at least cash. Both predate this item; the experiment valuation does not use them.

## Scope stop

OCT1-10 and OCT1-11 were not started. No win rate, expectancy, profit factor,
drawdown, strategy optimisation or model ranking was built.
