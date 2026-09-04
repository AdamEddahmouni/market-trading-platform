# BUILD 15 — Prediction Ledger & Deterministic Outcome Settlement

> BUILD 15 preregisters how each forecast will be judged, freezes its prediction-time anchor before future data is known, waits until a fixed horizon/availability cutoff closes the target observation universe, deterministically adjudicates the outcome, and persists immutable `OutcomeV1` without mutating `ForecastV1`.

## Forecast ≠ outcome

- `ForecastV1` remains immutable after creation.
- `OutcomeV1` is a separate immutable record linked by `forecast_id` and `PredictionLedgerEntryV1`.
- Settlement never writes resolved labels back onto forecasts.

## Why a ledger entry exists

At registration time BUILD 15 freezes:

- settlement policy identity
- anchor observation (P0)
- target time and event-time window
- availability cutoff
- observation source policy
- mode (`ACTUAL_LIVE` / `COUNTERFACTUAL`) and optional `scenario_id`

Pending settlement is derived: ledger entry exists and no matching outcome yet.

## P6 reuse

Promoted without modifying P6 modules:

| Semantics | Source |
|---|---|
| P0 eligible tape + last trade at/before decision | `shadow/predictor.py` via `outcomes/p6_compat.py` |
| Terminal first observation in `[target, target + tolerance]` | `shadow/labeling_job.py` pattern |
| Return formula `(P_target / P0) - 1` | P6 Run 1 spec §7 |
| `ZERO_RETURN` when `r == 0` exactly | P6 Run 1 spec §7 |
| Unlabelable codes `UNLABELABLE_NO_REFERENCE_PRICE`, `UNLABELABLE_NO_HORIZON_TRADE` | P6 naming preserved |

P6 shadow tests remain unchanged.

## Anchor / P0

- Resolved only from forecast decision context (`SnapshotV1` source events, else repository `query_events_as_of`).
- Requires `available_time_ns <= decision_time_ns`.
- Last eligible `TRADE` by maximum `event_time_ns` (P6 `reference_price`).

## Target time

```text
target_time_ns = forecast.decision_time_ns + forecast.horizon.duration_ns
```

## Target observation window

For `direction_up_down` default policy (`DIRECTION_UP_DOWN_5M_POLICY`):

```text
window = [target_time_ns, target_time_ns + 60s]
availability_cutoff_ns = target_window_end_ns
```

P6-compatible 30m policy uses 300s tolerance (`P6_DIRECTION_POLICY`).

## Event-time window vs availability cutoff

- **Event-time window** selects which market observations correspond to the horizon target.
- **Availability cutoff** bounds which observations may participate based on `available_time_ns <= cutoff`.
- `label_available_time_ns = availability_cutoff_ns` for settled labels.

### Late-arrival example

Target window ends at `T+5m+60s`. A trade with event time inside the window but `available_time_ns > cutoff` cannot alter settlement after the cutoff closes the admissible universe.

## Observation selection

Within eligible events:

1. Filter `available_time_ns <= availability_cutoff_ns`
2. Filter `target_window_start_ns <= event_time_ns <= target_window_end_ns`
3. Validate trade price (finite, positive; invalid quotes rejected)
4. Sort by BUILD 02 key `(available_time_ns, received_time_ns, event_time_ns, event_id)`
5. Select first observation

## Label semantics

| Condition | Result |
|---|---|
| `P_target > P0` | `Direction.LONG` (UP) |
| `P_target < P0` | `Direction.SHORT` (DOWN) |
| `P_target == P0` | `UNLABELABLE` / `ZERO_RETURN` |
| No in-window observation | `UNLABELABLE` / `UNLABELABLE_NO_HORIZON_TRADE` |
| No anchor | registration fails / `UNLABELABLE_NO_REFERENCE_PRICE` |

## Modes

- `ACTUAL_LIVE` — production/scientific actual outcomes
- `COUNTERFACTUAL` — replay research scenarios; distinct outcome IDs via `scenario_id`

## Registration helpers

- `register_control_forecast_for_settlement` — BUILD 08 controls
- `register_final_forecast_for_settlement` — BUILD 14 final forecasts

Late `ACTUAL_LIVE` registration after target time is rejected (`LATE_REGISTRATION`).

## Persistence

Collection: `prediction_ledger` (append-only, no TTL). Methods:

- `put_prediction_ledger_entry`
- `get_prediction_ledger_entry`
- `get_prediction_ledger_entries_by_forecast`

## BUILD 14 / BUILD 16 boundaries

- BUILD 14 predicts; BUILD 15 labels; no online calibration or model updates on settlement.
- BUILD 16 consumes immutable forecast/outcome pairs without reselecting target prices.

## Cross-links

- [FUSION_CALIBRATION_UNCERTAINTY_V1.md](./FUSION_CALIBRATION_UNCERTAINTY_V1.md)
- [BASELINE_PREDICTION_SYSTEM_V1.md](./BASELINE_PREDICTION_SYSTEM_V1.md)
- [IMMUTABLE_SNAPSHOT_ENGINE_V1.md](./IMMUTABLE_SNAPSHOT_ENGINE_V1.md)
- [P6 Shadow Run 1 spec](../superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md)
