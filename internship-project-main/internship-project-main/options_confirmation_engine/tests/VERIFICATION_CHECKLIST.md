# Standalone Options Engine Verification Checklist

## Unit Tests
- Run: `python -m unittest discover tests -v`
- Confirm tests pass for:
  - data ingestion normalization
  - feature calculations
  - scoring output and bias mapping
  - runner output structure

## CLI Smoke Tests
- `python cli.py score --ticker AAPL`
- `python cli.py score-batch --input contracts/examples/input_example.json`
- Confirm JSON output includes `options_score`, `options_bias`, and `feature_values`.

## State File Checks
- Confirm files exist and remain valid JSON:
  - `state/signals.json`
  - `state/trade_log.json`
  - `state/health.json`
- Confirm `state/agent.pid` is created and cleaned up.

## Dashboard Smoke Test
- Run: `streamlit run dashboard/app.py`
- Confirm dashboard loads without exceptions and displays current state.

## Evaluation Smoke Test
- Run: `python evaluation/backtest_runner.py`
- Confirm report is created in `evaluation/reports/`.

## Soak Test
- Run repeated batch jobs for several hours.
- Verify no JSON corruption, lock contention, or repeated crashes.

