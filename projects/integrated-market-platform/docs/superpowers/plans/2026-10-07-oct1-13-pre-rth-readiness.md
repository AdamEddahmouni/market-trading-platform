# OCT1-13 pre-RTH readiness, 2026-10-07

Scope: the Screener and the AI decision/execution layer on top of it. Internal Paper simulation only.
Receipts: [`oct1-13-pre-rth-readiness.json`](../../../artifacts/oct1-13-pre-rth-readiness.json),
[`oct1-13-premarket-operational.json`](../../../artifacts/oct1-13-premarket-operational.json).

## Outcome

- The prospective session started on time on canonical `746b93f8` in a fresh namespace. At 09:30:18 ET all 20 window rows were `ADMISSIBLE / CURRENT` from Moomoo with provider clocks.
- Under the original 18-gate standard the verdict is `PRE_RTH_BLOCKED` on `G17` alone: two browser acceptance scripts did not complete. Before the open the operator replaced that standard with a ready rule; under it `READY_TO_START_RTH = YES`.
- One defect was found after the open and fixed through a protected merge (PR #472). The runtime moved to `0d745925` at 09:42 ET in the same namespace.
- First real AI Screener result: `NO_GROUNDED_CANDIDATES` (0 of 20). No Action Decision, no Paper order, no position. Nothing was changed to produce a candidate.

## Gates

| Gate | Status | Basis |
|------|--------|-------|
| `G1_CANONICAL_MAIN` | PASS | 746b93f8 was origin/main at the open. The runtime moved to 0d745925 (origin/main after PR #472) at 09:42 ET. |
| `G2_CLEAN_RUNTIME_TREE` | PASS | git status --short empty before each start and after the AI Screener run. |
| `G3_PROVIDER_CONNECTIVITY` | PASS | OpenD, Finviz reference, Finnhub, NewsAPI (delayed), SEC user agent, FinBERT, Anthropic. Optional providers absent and reported as such. |
| `G4_LIVE_PRICE_PIT` | PASS | At 09:30:18 ET 20 of 20 window rows ADMISSIBLE / CURRENT from Moomoo with provider clocks, including symbols blocked on 2026-10-06. |
| `G5_AI_PROVIDER` | PASS | anthropic.messages / claude-haiku-4-5-20251001, operator-selected; budget 30 requests and 200,000 tokens per UTC day. |
| `G6_AI_CANDIDATE_PATH` | PASS | Controlled tests and the read-only preview passed before the open. The first live run found a defect (see post_open); after PR #472 the real run completed. |
| `G7_ACTION_DECISION` | PASS | Controlled: OCT1-10 browser acceptance and focused tests. Not exercised live: no candidate was selected. |
| `G8_PAPER_100K` | PASS | 29 focused service tests; live experiment created at exactly $100,000.00 and restored unchanged across a real runtime restart. |
| `G9_REEVALUATION` | PASS | Controlled: OCT1-07 browser acceptance and 61 focused tests on the OCT1-12 head. Live worker NOT_CONFIGURED: no position. |
| `G10_HELD_QUOTE_CONTINUITY` | PASS | Controlled OCT1-12 tests only. Not exercised live: no position. |
| `G11_SMA_STOP` | PASS | Controlled: OCT1-08 browser acceptance on the 746b93f8 bundle. |
| `G12_LIFECYCLE` | PASS | Controlled: OCT1-10 browser acceptance, 39 steps and 6 extra scenarios, on the 746b93f8 bundle. |
| `G13_EVALUATION` | PASS | 7 focused service tests including HTTP finalize and rerun. The OCT1-11 browser script did not run (ENVIRONMENT). |
| `G14_NO_LIVE_CAPITAL_AUTHORITY` | PASS | IMP_LIVE_EXECUTION set nowhere; start script removes it; runtime context INTERNAL_SIMULATION / PAPER_ONLY; experiment live_capital false. |
| `G15_RTH_STATE_NAMESPACE` | PASS | C:\Users\adame\.imp-state\prospective-rth-2026-10-07, empty before the 09:28:33 ET start. |
| `G16_CLOCK_SESSION_BOUNDARY` | PASS | Host within about 14 ms of NTP; server label PREMARKET at 09:29:47 and REGULAR at 09:30:19 ET. |
| `G17_BROWSER_CONTROLLED_E2E` | BLOCKED | 3 of 5 scripts passed (OCT1-07, 08, 10). OCT1-09 failed at step 24 on a stale locator; OCT1-11 could not launch its browser. Operator ruling: not a start blocker once the service smokes pass. |
| `G18_VALIDATION` | PASS | On the 746b93f8 tree: FULL 8,195 run / 53 skipped / 0 failures / 0 errors; UI 179 files / 1,374 tests; production build. 0d745925 adds PR #472: protected CI 9 of 9, 110 focused tests, FAST; FULL not rerun on it. |

## Defects fixed today

| PR | Merge | Defect |
|----|-------|--------|
| #471 | `746b93f8` | Clock-less OpenD QUOTE pushes left actively traded symbols `BLOCKED: NO_OBSERVATION_TIME`. Found premarket. |
| #472 | `0d745925` | With the whole window live the AI Screener packet exceeded its 96 KB cap and the run was refused before inference. Found at 09:31 ET. |

Neither change touches thresholds, the packet cap, intake cap, prompt, model, budgets, stop logic or risk limits.

## Browser acceptance scripts that did not complete

| Script | Classification | Cause | Path verified instead |
|--------|----------------|-------|-----------------------|
| `oct1_09_browser.cjs` | `STALE_ACCEPTANCE_HARNESS` | Locator `Prepare Paper Exit` matches two buttons since OCT1-10. Steps 1 to 23 passed. | 29 Paper experiment service tests, and the live experiment surviving a real restart at exactly $100,000.00 |
| `oct1_11_browser.cjs` | `ENVIRONMENT` | Launches a Chromium build that is not installed; ignores the configured path. | 7 evaluation service tests including HTTP finalize and rerun |

## Session record so far

| Item | Value |
|------|-------|
| State namespace | `C:\Users\adame\.imp-state\prospective-rth-2026-10-07` |
| Paper experiment | `PPE-057A0EAD0E004F40887DFD6DDBB36234`, created 09:30:54 ET, $100,000.00 cash and equity, `INTERNAL_SIMULATION`, `PAPER_ONLY`, `live_capital` false |
| AI Screener, 09:31 and 09:32 ET | Refused before inference, `EVIDENCE_PACKET_BOUND_EXCEEDED`, no model call |
| AI Screener, cutoff 09:43:54 ET | `NO_GROUNDED_CANDIDATES`, 0 of 20, claude-haiku-4-5-20251001, 43,638 tokens of 200,000 |
| Not observed | 09:42:18 to 09:42:47 ET (restart onto `0d745925`); nothing backfilled |
| Live-capital submissions | 0 |

## Operator notes

- **Keep the Main Screener open** during candidate selection: non-held candidate quotes are page-driven.
- Start and stop with `C:\Users\adame\.imp-state\START-RTH-2026-10-07.ps1` and `STOP-RTH-2026-10-07.ps1`. A restart must use the same namespace; never reseed, recreate the experiment or backfill.
- AI Screener runs are operator actions. About three more worst-case runs fit in today's token budget.
- Reevaluation is operator-started and only matters once a Paper position exists. An `EXIT` still needs the explicit Paper handoff.

## Known limitations

- A full live window reaches the model with no news stories; Finviz technicals stay blocked as undated. The model saw price and volume only, which is what it cited for selecting nothing.
- The Radar investigation screener read returns 500 (secret-leak guard, fail-closed). Not on the Main Screener path.
- While hidden, the Screener page does not refresh its universe list or session label.
- Mark-age and cost/slippage policies are unchanged. The session label is not holiday-aware.
