# OCT1-04 implementation plan

Subsequent action layer: [OCT1-06](2026-10-04-oct1-06-action-decision.md).
Candidate reduction remains separate from action inference and Paper authority.

Subsequent implementation: [OCT1-05 News and sentiment evidence](2026-10-03-oct1-05-news-evidence-integration.md)
extends the canonical packet and UI. The OCT1-04 receipts below remain historical.

**Goal:** Explicit operator-initiated reduction of the active Screener to at most five grounded candidates.
**Base:** `a3496d0af1ea41d34585469ec70f5f36a5dbcc08`, branch `codex/oct1-04-ai-screener`.
**Architecture:** Sibling structured market packet on the existing inference provider boundary. Reuse the News service's selected provider instance, catalog, launcher, secrets and shared budget. Server reconstructs the pinned query, takes its first 20 rows, projects bounded existing domain facts, then rechecks current/reference gates at the final cutoff. Unknown candidates/refs, weak support, malformed output and trade/forecast language fail closed.

- [x] Add packet/parser/cache tests in `tests/intelligence/test_ai_screener.py`; canonical focused selectors pass (13/13).
- [x] Implement `intelligence/inference/candidate_reduction.py` and shared schema dispatch; register dedicated prompt/task. Preserve News schema behavior.
- [x] Implement `ui_api/screener_ai.py`: pinned active scope, allowlisted numeric row projections, preview, explicit run, shared provider access. Add route policy and endpoint tests. Unconsumed specialist capabilities remain explicitly missing.
- [x] Add lazy `AiScreener` panel, API schemas and tests: no auto-run, scope guards, expiry, evidence cards, selection and errors.
- [x] Run inference/freshness/News regressions, complete UI tests/typecheck/build/bundle, changed and full validation; controlled browser and available local runtime acceptance.
- [x] Update architecture, work log and program status with exact evidence; review diff, commit explicit paths and open the existing branch's PR. The final check/merge/SHA and remote-main/Notion verification ledger belongs to the linked PR/task and final report.

Constraints: No OCT1-05/06 or autonomous loop, trading, targets, portfolio, new provider, new model download or separate budget. Fixtures remain SOFTWARE_CONTROLLED. Preserve historical timing failures.

Baseline: FAST 23 tests passed, 0 skipped/failures/errors, 12.754s; `SEVERE_REGRESSION` versus stored baseline. Ambient Python imports Hermes' `tools`; canonical interpreter with `PYTHONPATH=.;src` avoids that environment collision.

## Resume and validation ledger — 2026-10-03

Recovered the same existing worktree and branch at the original base, with 31
intended uncommitted files. The dirty primary checkout was preserved. Fetched
`origin/main` remained at the original base at recovery. No implementation was
rebuilt. The prior 13-test focused result and 139-test inference/provider,
budget, News and specialist regression result remain historical passing
evidence. Retained telemetry proved the previously interrupted lint invocation
had completed Python compilation and TypeScript checks successfully.

Reproduction-first fixes during resumption:

- Preserve the endpoint schema version instead of the model output version.
- Reproject each row through OCT1-03 at the final cutoff and join each fact to
  its exact covered-fields clock/state group; never admit mixed stale fields
  through another field's fresh status or promote a stale reference.
- Include view/screen, result-set identity, match count and snapshot clocks in
  the server scope and input hash; disable preview/run while the UI scope is
  unsettled and discard late responses after scope changes.
- Reject overlapping supporting/conflicting references and additional
  prohibited REDUCE/TARGET/STOP language.
- Use the canonical `input_tokens` counter accepted by the secret leak gate;
  verify real preview/result payloads at that gate.
- Register the launcher for Futures as well as the other four universes and
  update exact registry assertions. Display blocked evidence, explicit run
  errors, selected count, simulated flag, expiry and shared daily budget.

| Evidence | Result |
|---|---|
| Current AI backend selectors | 18/18 passed; packet/parser/cache, scope, source clocks, stale-reference exclusion, schema, leak gate and all-universe registry |
| Registry regression modules S5/S9/S10 | 67/67 passed |
| Isolated App/launcher plus AI API/panel | 92/92 passed, 4 files |
| AI panel including expiry/errors | 5/5 passed |
| App/Screener/AI API regression | 331/331 passed, 22 files |
| Complete UI after final display edits | 1,276/1,276 passed, 168 files, 177.68 seconds |
| FAST | 23/23 passed, 9.466 seconds; `SEVERE_REGRESSION` versus 1.821-second stored baseline, retained |
| Initial CHANGED | 5,675 tests, 35 skips, 3 failures and 20 errors; not green |
| Initial FULL | 7,820 tests: 7,743 passed, 55 skipped, 2 failures, 20 errors; 507.839 seconds, not green |
| Error/transient rerun | All 22 affected selectors passed with canonical interpreter and normal temporary-log access |
| Console/hidden-process FULL attempts | Interrupted after 210 passing tests; not closure evidence. Final run uses an independent Windows process group, as in OCT1-03 |
| Implementation-head CI CHANGED | 5,677 tests, 37 skipped, zero failures/errors, 207.603 seconds; `INCOMPATIBLE_BASELINE` timing classification |
| Final independent-process-group FULL | 7,822 tests: 7,769 passed, 53 skipped, zero failures/errors; all 71 suites passed, 542.342556 seconds; `SEVERE_REGRESSION` retained |
| Final lint/typecheck | Canonical `tools/imp.py lint --all` passed Python compilation and TypeScript |
| Final production build/bundle | Passed, 10.41 seconds; initial 99.70 KiB gzip against 200 KiB budget; AI panel lazy chunk 3.87 kB gzip |
| Formatting/documentation | `git diff --check` passed; links checked successfully in 286 governance markdown files; final CI must independently check the documentation head |

The prior 1,263-pass/8-failure Vitest result is retained. Its launcher assertion
was updated for the intended new entry. The other seven App async failures
passed the recovered isolated 87-test run, current isolated 92-test run,
331-test regression run and two complete 1,276-test runs. They are classified
`INTERMITTENT` suite contention, not current OCT1-04 regressions. No timeout or
product behavior was weakened to make them pass.

The initial backend registry failures were real outdated expected-contract
assertions and were fixed. SDK log permission and Windows temporary cleanup
errors are `ENVIRONMENT`; the P1 acceptance transient is `INTERMITTENT`. A
source-cleanliness check overlapped a production build and passed without that
race (`ENVIRONMENT`). The 22-selector rerun passed all errors/transients. No
unproved pre-existing-baseline designation is used. Initial raw results remain
non-green and are not replaced by the rerun ledger. Final FULL independently
passed all inference, canonical providers/budgets, News, OCT1-03 freshness,
Platform and software acceptance suites. The complete independent run resolves
the console interruptions without treating an interrupted run as passing.

## Controlled browser and model acceptance

Actual production UI and HTTP handlers were exercised in Chromium using an
isolated internal fixture reader and canonical provider interface. This is
`SOFTWARE_CONTROLLED`, not empirical live-source or real-model proof.

Opening/reopening the panel and changing view, search and an actual Price filter
caused zero automatic inference calls. Each explicit Run caused one call.
The result showed supporting, conflicting, weak, missing, blocked and uncertainty
sections; a supporting evidence card exposed its source facts. The stale RSI
sentinel was absent from the serialized model prompt. A returned AMD candidate
opened in Workspace even though the loaded table page contained only AAPL.
A delayed completed POST result did not repaint after a scope change. Request
capture contained zero Paper/Live execution mutations. UI tests also prove
deadline withdrawal without an additional model call and explicit failure UX.

Fixture provider: executed through the canonical inference boundary and
simulated flag. Existing local runtime: `LOCAL_NOT_CONFIGURED`,
`NO_SYNTHESIS_PROVIDER_CONFIGURED`, `NOT_EXECUTED`; no second install or model
download. Hosted runtime: `NOT_EXECUTED`; no paid acceptance invocation.

## Performance and limitations

A controlled 100-match/20-row intake produced 40 admitted facts and a
50,629-byte packet. Across 20 construction repetitions, median was 1.554 ms,
maximum 2.110 ms. Identical fixture requests yielded one provider call and a
cache hit. Fixture metadata reported 1 ms and 100 input/50 output tokens;
these are fixture values, not a real LLM benchmark.

Final initial bundle remains 99.70 KiB gzip (the same rounded value as OCT1-03),
below the 200 KiB budget. The AI panel is a lazy 3.87 kB gzip chunk. Production
build took 10.41 seconds; the build/bundle gate passed.

The initial full suite took 507.839 seconds versus the stored 198.882-second
baseline (`SEVERE_REGRESSION`, +155.3%). Final FULL took 542.342556 seconds
(`SEVERE_REGRESSION`, +172.696%, +343.460556 seconds); slowest suites were
Intelligence 207.346 seconds, Platform 110.433 seconds and software fullstack
acceptance 69.423 seconds. Both remain observe-only timing evidence. There is
no controlled same-machine incremental baseline proving that OCT1-04 caused
or resolved the timing regression.

Only existing allowlisted quote/technical/rates row facts are consumed.
Order Flow, CVD, Level 2, Options, Futures specialist, cross-asset specialist,
squeeze, fundamentals, News and sentiment remain missing unless a supported
projection is added in a separate scoped change. Unknown source clocks can
produce zero grounded candidates. First-20 intake is deterministic but does
not assess the remainder of a large match set. Expiry is conservative and
clock-dependent. No external retrieval, new sentiment methodology, forecasts,
targets, execution, portfolio evaluation or autonomous reevaluation was added.

## Integration ledger

Implementation commit: `244db16ddb348a622359e343b0c3ff4ccc25a084`.
Review: [PR #460](https://github.com/AdamEddahmouni/market-trading-platform/pull/460),
targeting the unchanged original remote-main base. All implementation-head CI
jobs passed, including CHANGED, FAST, UI and workflow lint; final documentation
head must independently pass applicable checks before merge. Remote-main and
Notion Done verification are recorded in this existing task's PR/tracker and
the final report after integration. This document does not infer a merge from
local passing tests.
OCT1-05 and OCT1-06 were not started.
