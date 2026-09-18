# IMP-INTEGRATE-AND-EXPERIMENT-05 — Lane R1 prediction-coupled simulator

**Hypothesis:** `LANE-E-HYP-SIMULATOR-PREDICTION-COUPLED-V1`  
**Authority:** `HISTORICAL_DEVELOPMENT` only  
**Item 9 / calibration:** `NONE` — every result carries `result_kind = SIMULATOR_RESEARCH_RESULT`

## Bridge

```text
strategy predictions → trade intents → historical bar simulator → fills / PnL
```

Predictions are rows with `decision_time_ns` and `predicted_direction` (`-1` short, `0` abstain, `1` long). The harness maps non-zero directions to strategy signal interpretations, builds order intents, runs pre-trade risk, and simulates fills on scoped replay bars. The Phase 7 walk-forward strategy path is **not** invoked for research simulator runs.

## No-trade invariant

When the baseline produces zero trade intents, the run must report zero fills and zero turnover unless `external_position_documented=True`. Violations raise `PredictionCoupledSimulatorError` and fail the research run.

## Distinction from Item 9

Historical strategy simulation under this bridge is research infrastructure only. It must not set Item 9 thresholds, sample floors, Paper realism parameters, or Live authority.

## Entry points

- `run_historical_development_simulator_research(..., predictions=...)`
- `build_signal_interpretations_from_predictions`
- Historical research harness pipeline passes development-validate predictions only.
