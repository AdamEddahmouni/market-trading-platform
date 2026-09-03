# DS-340W fantasy-football prediction donor notes

These notes describe an external, immutable donor snapshot. Revision 3 is the
authority if this summary conflicts with it. Nothing here authorizes donor
execution, dependency installation, data copying, model implementation, or a
phase transition.

## Identity and inspection boundary

- Logical root: `PROTO-DS340W-001`
- Observed collection-relative path:
  `DS-340W-Fantasy-Football-Prediction-main/DS-340W-Fantasy-Football-Prediction-main`
- Git state: `UNAVAILABLE_NO_GIT_METADATA`; neither nested snapshot level
  contains usable `.git` metadata.
- Purpose: annual fantasy-football forecasting and comparison of univariate
  ARIMA, ARIMAX, and neural-network approaches using R and nflverse-family data.
- Inspection was offline and read-only. No R code ran, no package was installed,
  and no remote dataset was contacted.

## Source inventory and observations

The active-looking R sources are `DS340_Parent_Code.R`,
`ARIMAX_DS340W_Code.R`, `NN_340w_Code.R`,
`NN_ARIMAX_340W_Comparison.R`, and
`ARIMA_ARIMAX_NN_340W_Comparison.R`. `DS340W_scratchwork.R` and
`Tempcode_DS340W.R` contain exploratory work. The project also contains an R
project file and a short README.

Observed techniques include:

- per-player time-series preparation and forecasting;
- univariate ARIMA baselines;
- ARIMAX with exogenous regressors;
- neural-network time-series models;
- training-derived scaling, zero-variance removal, and QR-rank handling;
- explicit model-fit fallbacks and per-entity parallel work;
- CSV forecast, player-level comparison, aggregate error, and win-rate output.

The scripts reference R packages and nflverse/nflreadr/nflfastR-style remote
data acquisition. Some scripts attempt dynamic package installation. There is
no observed repository dependency lock, automated test suite, or deterministic
seed contract. No repository license was found.

## Point-in-time defect

The comparison workflows construct future-regressor inputs from actual rows in
the held-out period. In particular, realized holdout offensive activity such as
pass and rush attempts can reach the ARIMAX and neural-network comparison paths.
Those inputs would not have been knowable at forecast time. Consequently:

- the affected comparison metrics are look-ahead contaminated;
- donor backtest and win-rate outputs are not admissible platform evidence;
- no donor result supports a financial prediction, strategy, or profitability
  claim; and
- any future canonical implementation must rebuild evaluation around explicit
  `event_time`, `observed_at`, availability, and forecast-origin rules.

## Dataset and output inventory

Only schemas, file sizes, and row counts were inspected for this inventory; no
row values are reproduced. The workbook is 820,049 bytes, contains `Sheet1`,
has dimension `A1:AI4401` (4,400 data rows and 35 columns), and uses this header:

`Rk, Player, FantPos, Tm, Age, G, GS, Cmp, PassAtt, PassYds, PassTD, Int, RushAtt, RushYds, Y/A, RushTD, Tgt, Rec, RecYds, Y/R, RecTD, Fmb, FL, TD, 2PM, 2PP, FantPt, PPR, DKPt, FDPt, VBD, PosRank, OvRank, Year, FantPtHalf`

The workbook is annual-style (`Year` is present and no week field was observed).

| File | Data rows | Header |
|---|---:|---|
| `backtest_player_level_ff_sum.csv` | 299 | `player,TEAM,FF_hat_arimax,FF_hat_nn,FF_actual,err_arimax,err_nn,abs_err_arimax,abs_err_nn,sq_err_arimax,sq_err_nn` |
| `backtest_player_level_ff_sum_3way.csv` | 299 | `player,TEAM,FF_hat_ARIMA,FF_hat_ARIMAX,FF_hat_NN,FF_actual,err_ARIMA,err_ARIMAX,err_NN,abs_ARIMA,abs_ARIMAX,abs_NN,sq_ARIMA,sq_ARIMAX,sq_NN` |
| `backtest_summary_ff_sum.csv` | 2 | `metric,ARIMAX,NN,NN_vs_ARIMAX_rel` |
| `backtest_summary_ff_sum_3way.csv` | 2 | `metric,ARIMA,ARIMAX,NN,NN_vs_ARIMA_rel,NN_vs_ARIMAX_rel,ARIMAX_vs_ARIMA_rel` |
| `backtest_win_rates_3way.csv` | 1 | `N,ARIMA_win_rate,ARIMAX_win_rate,NN_win_rate` |
| `forecast_defense.csv` | 32 | `Team,DEF.Fant..Pts.,DEF Fant. Pts.` |
| `forecast_kickers.csv` | 120 | `player,PAT,FGS,FGM,FGL,FFP` |
| `forecast_offense.csv` | 600 | `player,pa,pc,py,ints,tdp,ra,ry,tdr,trg,rec,recy,tdrec,fum,FF` |
| `forecast_offense_ARIMA_uni.csv` | 299 | `player,TEAM,ARIMA_FF` |
| `forecast_offense_arimax_fast.csv` | 299 | `player,TEAM,pa,pc,py,ints,tdp,ra,ry,tdr,trg,rec,recy,tdrec,fum,FF` |
| `forecast_offense_ARIMAX_xreg.csv` | 299 | `player,TEAM,ARIMAX_FF` |
| `forecast_offense_nn_fast.csv` | 299 | `player,TEAM,pa,pc,py,ints,tdp,ra,ry,tdr,trg,rec,recy,tdrec,fum,FF` |
| `forecast_offense_NN_xreg.csv` | 299 | `player,TEAM,NN_FF` |

The workbook and every CSV remain external. Their provenance and redistribution
rights are unresolved, and none is a financial dataset or financial result.

## Reuse classification

`PORT_ADAPT` means independently reimplement the technique behind a canonical
interface after rights, phase, and test gates; it does not mean copy donor code.

| Component | Class | Canonical destination | Earliest phase | Preconditions and verification |
|---|---|---|---|---|
| ARIMA baseline | `PORT_ADAPT` | model baseline/evaluation interfaces | Phase 5R | Accepted model ADR; deterministic synthetic walk-forward tests; provenance record |
| ARIMAX structure | `PORT_ADAPT` | forecast-model adapter | Phase 5R | Forecast-origin covariate contract; reject actual-future regressors; baseline comparison |
| Neural-network structure | `CONCEPT_ONLY` | model research protocol | Phase 5R | Locked runtime, deterministic seed policy, calibration and ablation tests |
| Train-derived preprocessing | `PORT_ADAPT` | feature/preprocessing contract | Phase 5R | Fit only inside each training fold; leakage sentinel tests |
| Fit fallback and rank checks | `PORT_ADAPT` | model failure-policy contract | Phase 5R | Typed failure reasons; no silent success; adversarial fixtures |
| Per-entity parallelism | `CONCEPT_ONLY` | bounded research scheduler | Later research authorization | Deterministic ordering, resource bounds, isolated failures |
| Holdout comparison as written | `DO_NOT_USE` | none | Never | Actual-future exogenous inputs contaminate evaluation |
| Dynamic package installation | `DO_NOT_USE` | none | Never | Violates offline, locked, reproducible execution |
| Workbook and CSV artifacts | `DO_NOT_USE` | none | Never unless separately licensed and governed | Rights/provenance unresolved; domain semantics are football, not markets |

## Required future tests

- forecast-origin availability and delayed-publication fixtures;
- train-only transformation fitting for every fold;
- unknown/missing future covariate rejection;
- deterministic seeds, dependency lock, and byte-stable run manifests;
- naive and simple statistical baselines before complex models;
- predictive metrics separated from strategy, risk, execution, and accounting;
- fallback-path, rank-deficiency, zero-variance, and per-entity failure tests.

The authoritative cross-donor disposition is in
[DONOR_REUSE_MATRIX.md](DONOR_REUSE_MATRIX.md). Rights states are recorded in
`docs/superpowers/governance/2026-08-14-donor-code-permissions.json`.
