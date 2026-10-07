# Prospective outcome evaluation (OCT1-11)

Evaluation is a bounded, derived audit of canonical action decisions, frozen candidate evidence, OCT1-07 locked next-session observations, OCT1-09 simulated fills/equity and OCT1-10 trade episodes. It never generates a proposal, refreshes a quote, submits an order, promotes a model, changes a strategy or activates FTEP. Live capital remains blocked.

## Contracts and authorities

`decision-outcome/1.0.0` retains account/experiment/instrument identity; original action and decision cutoff; candidate-run/evidence snapshot references; original provider/model/prompt/version; source hash; available/source clocks; separate signal and execution outcomes; stored segment labels and limitations. Detail resolves the original immutable decision only after its hash matches. Stochastic inference is not replayed.

`prospective-evaluation-run/1.0.0` freezes normalized records, source references, observed equity snapshots, cutoff, code SHA, policy and metric version, admission counts, included/excluded IDs, fingerprint and result. Canonical JSON SHA-256 determines `PE-` identity. Runs are immutable and account scoped in the existing local-state database; persistence-off is explicitly ephemeral. Read endpoints are audit-only; finalization writes this artifact only. Rerun reports metric equality separately from reconstruction of original decisions, fills, outcome observations and equity.

The policy is `outcome-evaluation/1.0.0`; metric definitions are `prospective-metrics/1.0.0`. Mutation or an unknown policy fails closed. The cutoff must be a timezone-aware instant no later than the service clock. Configurations and source hashes are part of the fingerprint.

## Admission

Explicit cohorts: prospective Paper with live observational data, prospective signal-only, SOFTWARE_CONTROLLED, historical replay and fixture. Fixture delivery or simulated model provenance dominates a live experiment label. Missing/unrecognized delivery cannot become prospective evidence. Replay never enters the primary prospective aggregate. Manual/unlinked episodes are excluded from AI results and remain visible. Decision and evidence clocks must be at/before cutoff; fills and signal observations must be strictly after the decision. Missing lineage, future available-time, invalid outcomes, currency mismatch and duplicate episodes have explicit exclusion reasons. Unknown model/version/regime/setup labels remain UNAVAILABLE.

A trade episode contributes execution P&L once, on its opening decision. Later exit/reevaluation decisions stay visible but cannot duplicate episode P&L. Every fill needs a matching canonical instrument/decision and temporal order. Reversals fail closed. A later close never rewrites an earlier open/censored projection. Open trade realized amounts are not included in completed-trade statistics. Historical unrealized marks remain unavailable without a canonical synchronized mark history.

## Exact metric definitions

All financial sums use integer USD minor units; ratios use Decimal precision 28. Net completed P&L is the sum of canonical fill realized deltas, which already include explicit costs. Gross equals net plus costs; commission and fees are summed once. Slippage is not separately modeled. Wins/losses/flat are net >0/<0/=0. Win rate = wins/(wins+losses), excluding flat; no nonflat outcomes yields unavailable. Average/median win and loss preserve signs. Payoff = average win / absolute average loss. Expectancy = total net / completed trades, including flat. Profit factor = sum winning net / absolute sum losing net. No losses produces undefined, not infinity; no completed observations produces unavailable.

Losing streaks follow close timestamp then stable evaluation identity; flat breaks a streak. Exposure is the union of observed entry-to-close (or cutoff for open) elapsed wall-time intervals, including session gaps. Time in market divides this union by elapsed time from earliest admitted decision to cutoff. Gross-notional/equity average and peak are unavailable without synchronized position-mark history. Executed notional sums absolute fill price times quantity. Turnover divides executed notional by first eligible account equity, with this denominator exposed; missing reference equity yields unavailable.

Maximum observed equity drawdown is the largest absolute drop from a prior stored peak; its fraction uses that peak. Recovery requires a later stored equity at/above the peak. Unrecovered duration is censored at the last stored observation. Sparse/missing periods are never interpolated. One snapshot cannot measure drawdown or equity return. Account equity is whole-account accounting and cannot be causally allocated among models or setups.

Weeks start Monday in America/New_York. Closed trades belong to their close week. Weekly equity return is (last observed minus first observed)/first observed within the week; coverage explicitly states sparse observed endpoints, not a full-week return. Positive/negative week counts concern observed closed Paper net only. Segments use frozen setup/asset/regime/model/prompt/direction/instrument/stop/policy labels, each with N and the same definitions.

Signals use the original OCT1-07 frozen reference and horizon, locked before observation start. The last eligible received observation in that window determines market move; long/short direction determines directional correctness. A market return is never substituted for actual Paper P&L. Missing observations stay unavailable.

## Limits and operation

Current projection reads existing source authorities without applying live marks. Record/equity bounds are 10,000; source truncation fails explicitly. Pages are at most 100 records; stored run payloads at most 16 MB. There is no evaluation polling loop or background trading. The UI at `/portfolio/evaluation` shows classification, N, cutoff, exclusions, weekly/segment results, source drilldown, current lifecycle and reproducibility. Current lifecycle is labeled separately from frozen historical outcomes. Review findings remain human-reviewed, descriptive and insufficient for strong profitability or causal superiority claims. A future methodology change needs a new version and prospective epoch.

Controlled browser reproduction: build `ui`, start `.venv/Scripts/python.exe tests/acceptance/harness_prospective_evaluation.py` with `PYTHONPATH=src;.` on Windows (`src:.` on Unix), then run `node tools/ui1/oct1_11_browser.cjs` from IMP root. Set `IMP_PLAYWRIGHT_MODULE` to an installed Playwright module when needed. This isolated harness seeds software fixtures; it must never be used as prospective market evidence.
