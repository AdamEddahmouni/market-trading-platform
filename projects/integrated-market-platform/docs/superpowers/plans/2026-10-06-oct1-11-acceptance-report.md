# OCT1-11 acceptance report

Status: SOFTWARE_ACCEPTED. This archive records local acceptance before protected integration; merged PR467 and the verified post-merge tracker receipt establish final integration. PR [467](https://github.com/AdamEddahmouni/market-trading-platform/pull/467). This report separates software acceptance from genuine prospective evidence. Final receipts are in [acceptance JSON](../../../artifacts/oct1-11-acceptance.json).

## A. Scope and verdict

Only OCT1-11 prospective outcome evaluation, metrics, reproducibility and iteration. No subsequent package is selected. Software acceptance is complete. The protected PR and post-merge tracker record establish the final integration verdict.

## B. Repository state

Monorepo `AdamEddahmouni/market-trading-platform`, canonical IMP under `projects/integrated-market-platform`. Base/OCT1-10 merge `cdcaca246e815f328ff96384b208ab2c07937ee2`; isolated branch `codex/oct1-11-prospective-evaluation`; implementation `634439dd12a6579dfec0fa35d023384e2f5dd1c1`. Primary unrelated dirt and leftover nested clone are preserved. Final main and merge parity require post-merge verification.

## C. Existing authorities reused

Immutable action/candidate repository and evidence snapshots; OCT1-07 locked next-session policy and observations; forward-test temporal guards; OCT1-09 experiment/cost/fill/equity ledger; OCT1-10 opening-fill episode identities; platform reproducibility/evaluation standards. No replacement evidence store is created.

## D. FTEP-V1 boundary

No campaign manifest, preregistration, scheduler, activation state or trading authority is changed. Temporal primitives are reused without campaign activation. Live capital remains blocked.

## E. Evaluation record contract

`decision-outcome/1.0.0`: account/experiment/instrument, decision and cutoff, original candidate/action/evidence references and hashes, original actual proposal/model/prompt/version, source and availability clocks, separate signal/execution outcomes, stored segment labels, class/quality/limitations. Detail verifies original source hashes before displaying the decision.

## F. Admission and exclusion

Primary prospective Paper excludes software/fixture/replay classes and manual/unlinked AI attribution. Invalid/future evidence clocks, missing lineage, corrupted candidate/action snapshot hashes, duplicate episodes, invalid fills/outcomes and unsupported currencies receive explicit reasons. The real audited prospective window has considered/admitted/excluded counts 0/0/0 because it produced no qualifying AI decision. Controlled browser primary cohort excludes its software records; controlled-cohort manual activity remains excluded.

## G. Exact formulas

Full definitions: [evaluation contract](../../architecture/PROSPECTIVE_OUTCOME_EVALUATION.md). Net P&L sums canonical fill realized deltas once per closed episode; gross = net + explicit costs. Wins/losses/flat = net >0/<0/=0; win rate = wins/(wins+losses). Average and median winning/losing net preserve signs. Payoff = average win/absolute average loss. Expectancy = total closed net/N closed including flat. Profit factor = summed winning net/absolute summed losing net; no losses is undefined. Observed drawdown = largest drop from prior stored peak, divided by that peak; recovery needs an actual later snapshot, and unrecovered duration is censored at the last observation. Streak follows close time, with flat breaking it. Exposure unions entry/close-or-cutoff wall-time intervals; occupancy divides by elapsed earliest-decision/cutoff time. Turnover = absolute executed notional/first eligible equity, with the denominator displayed. Commission and fees are included once; separate slippage is not modeled. Missing denominator/history yields unavailable.

## H. Reproducibility

Frozen run contains cutoff, original normalized records/equity/source refs, code SHA, environment and implementation hashes, policy `outcome-evaluation/1.0.0`, metric version `prospective-metrics/1.0.0`, admitted/excluded IDs, fingerprint and results. Canonical sorted JSON SHA-256 determines identity. Same-input rerun returns MATCH; missing/changed original sources separately return NOT_REPRODUCIBLE. Persistence uses existing local-state SQLite, with an explicit ephemeral mode. Recorded outputs are retained; stochastic inference is not replayed.

## I. Signal outcome

Uses locked original reference and next-session horizon. Eligible later observation must be received by cutoff and preserve source/delivery provenance. Market move and long/short directional correctness are distinct from executed P&L. No genuine qualifying signal was available in the audited window.

## J. Execution outcome

Opening decision owns one episode P&L; later decisions cannot count it again. Closed results use actual simulated fill deltas and costs. Open episodes are censored and excluded from completed win/loss/P&L statistics. Historical synchronized unrealized marks are unavailable. Manual episodes remain explicitly visible.

## K. Weekly evaluation

Monday weeks in America/New_York; episodes allocated by close timestamp. Weekly returns use only observed equity endpoints with partial-week coverage disclosed. Positive/negative/percentage-positive statistics remain descriptive; no complete prospective trade week exists here.

## L. Segmentation

Frozen setup, asset, regime, provider/model/version, prompt/version/hash, direction, instrument, stop and policy labels. Missing labels remain UNAVAILABLE. Every segment has N and consistent formulas. Server-side record pagination follows the chosen segment; model comparisons have no causal or promotion authority.

## M. Controlled dataset

SOFTWARE_CONTROLLED metric fixture: 6 decisions, 5 completed and 1 open; 2 wins, 2 losses, 1 flat; win rate 0.5; mean/median win +7500 and loss -7500 USD minor; expectancy 0; profit factor/payoff 1; net 0, gross 50, explicit costs 50 (commission 30, fees 20); turnover 0.012 against 10000000 reference equity. Separate exact tests cover profit factor 2, empty/all-win/all-loss, cost accounting, drawdown 800/101000 with observed recovery, temporal rejection, signal-only/no-action behavior, segment labels, duplicate/lineage failures, immutability and restart/account isolation. Production harness separately seeds governed positive, negative, flat and open fills plus manual activity.

## N. Actual prospective dataset

Archived OCT1-09 live observational window on 2026-10-06, 18:05–19:22:14 UTC. Experiment `PPE-1CA4528C6CA5C2409D745EDA5FC3BF1F`; Paper simulated capital $100000. Zero qualifying AI decisions, zero completed/open AI trades, zero recorded NO_ACTION decisions, admission 0/0/0. NO_QUALIFYING_ENTRY is a collection outcome, not an invented AI decision. Separate available debug/harness SQLite records were simulated and are excluded from empirical evidence. All source reads were read-only.

## O. Actual prospective metrics

One current equity snapshot supports the observed $100000 balance. It cannot measure equity return/drawdown. Closed-cohort net, expectancy, win rate, profit factor and exposure remain unavailable; weekly closed-trade results are absent. The frozen report contains no software fixture in primary metrics.

## P. Empirical conclusion

INSUFFICIENT_EVIDENCE. No profitability, calibration, causal model superiority, live qualification or autonomy claim.

## Q. Iteration output

Review sample coverage, stored missingness, cost drag and negative observed segment expectancy. Any future method/model/policy change requires human review, a new version and a future epoch; it cannot rewrite this run. No automatic mutation is introduced.

## R. Backend changes

Deterministic evaluator, canonical source adapters, immutable evaluation repository and authenticated account-scoped summary/records/detail/run/finalize/rerun APIs. Explicit bounds and truncation failures. No live-mark refresh or inference on evaluation reads.

## S. Frontend changes

Lazy portfolio evaluation route with class/cutoff/N, explicit unavailable values, costs, drawdown, weekly/segment results, admission reasons, original source/model/prompt detail, separately labeled current lifecycle, saved-run selection, finalization and rerun. No polling or order controls. Initial production bundle 100.77 KiB gzip remains inside the 130 KiB budget.

## T. Validation

Exact final canonical counts are recorded in acceptance JSON. Final focused backend 31 passed; final seven service checks passed; complete UI 1372 passed across 179 files. Compile/typecheck, format, build/budget, docs links and monorepo guard passed. Prior interrupted runs, four lazy-route failures (subsequent complete rerun passed), and FULL oversized-body WinError 10053 (isolated recheck passed) remain disclosed. Final CHANGED 6042 tests/35 skipped and FULL 8143 tests/53 skipped passed with zero failures/errors (297.120s and 421.317s). The supplemental exact open-exposure case was added after FULL discovery and passed in the final 31-case focused run; production evaluator code was unchanged. Exact-head protected CI and verified main are required before integration.

## U. Browser acceptance

Production bundle against isolated canonical Paper action/preview/fill/ledger service. Required 40 scenarios are exercised in 29 grouped asserted steps: metrics/weekly values, classification/cutoff/N, all stored segment dimensions, changing N, original PIT/provider/freshness/model/prompt/action/outcome fields, current lifecycle, exclusions, frozen finalization, exact rerun, software exclusion, manual separation, open censoring and submission absence. Fill/model-call counts remain 8/8; measured Paper and Live submission requests remain 0/0. Viewport screenshots are committed as `artifacts/oct1-11-desktop.png` and `artifacts/oct1-11-mobile.png`; full-page screenshots are retained locally. Evidence class SOFTWARE_CONTROLLED.

## V. Performance

100- and 1000-record aggregation plus all segments and exact rerun measured in [performance receipt](../../../artifacts/oct1-11-performance.json). Payloads approximately 125 KB/1.13 MB frozen and 13.3 KB/20.6 KB summaries; UI records page bounded to 100. No timer/background loop. Final FULL duration and observe-only regression flags remain in acceptance JSON; no strategy inference is drawn from timing.

## W. Known limitations

No qualifying prospective sample; simulated execution; sparse equity/partial weeks; unknown unstored versions/regimes; unavailable historical synchronized marks/notional exposure; bounded source/run payloads; existing market-provider/freshness limitations retained. Current lifecycle may use its existing mark refresh but does not replace frozen outcomes.

## X. PR and integration

PR467 is OCT1-11-only. Normal branch protection applies; no admin merge, direct main push or force push. Final head checks, merge ancestry and exact IMP tree parity must be verified before completion.

## Y. Tracker

Only OCT1-11 was moved to In progress at startup. It remains so until protected merge and main verification; then implementation/validation/outcome evidence is synchronized and read back. No unrelated task is changed.

## Z. Professor-feedback program state

Audited tracker and repository evidence show OCT1-01 through OCT1-10 Done and integrated (PR457–PR466). OCT1-11 final state depends on the verified integration described above. No additional work package starts after this closeout.
