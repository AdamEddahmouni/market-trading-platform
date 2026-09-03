# Integration Promotion Criteria

## Goal
Define objective pass/fail gates before integrating the standalone options engine into:

- `/Users/strzala/Desktop/news_momentum_agent`

## Functional Gates
- 0 input/output schema validation errors for 3 consecutive daily runs.
- `state/signals.json`, `state/trade_log.json`, and `state/health.json` are written on every successful run.
- PID lock correctly prevents duplicate writers when `runtime.single_instance_required=true`.

## Data Quality Gates
- `no_data` bias rate under 35% for the target ticker universe.
- Less than 5% runs with `fetch_error` quality flag.
- At least 80% of scored tickers contain all required feature keys.

## Performance and Stability Gates
- 7-day soak test without corrupted state files.
- Average batch runtime stays within agreed limit for target universe size.
- Atomic writes remain enabled in production settings.

## Signal Quality Gates
- Options-confirmed track shows measurable improvement in win-rate proxy vs baseline.
- False-positive reduction potential is positive while keeping practical coverage.
- Reasoning summaries are interpretable and mapped to feature values.

## Promotion Decision
Promote only when all mandatory gates pass. If any mandatory gate fails, continue standalone iteration and re-test.

