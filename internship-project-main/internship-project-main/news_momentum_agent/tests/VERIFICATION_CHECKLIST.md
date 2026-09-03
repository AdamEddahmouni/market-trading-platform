# Stabilization Verification Checklist

## Unit tests
- Run: `python -m unittest discover tests -v`
- Confirm all tests pass:
  - threshold wiring (social + decision)
  - keyword normalization and aliases
  - scanner reason codes and funnel counters
  - state helper compatibility

## Smoke checks
- Run agent startup once:
  - `python main.py`
- Confirm files are written:
  - `state/watchlist.json`
  - `state/high_alert.json`
  - `state/health.json`
- Confirm wrapped state format:
  - `meta` + `items` keys present for watchlist/high-alert

## Runtime checks (30-minute soak)
- Confirm one concise health line each cycle:
  - includes cycle_id, watchlist_count, high_alert_count, zero reason
  - includes posts_fetched/posts_recent/posts_matched totals
- Confirm no contradictory flapping logs:
  - no repeated mismatch between generated high-alert and runner loop behavior
- Confirm dashboard diagnostics:
  - freshness status aligns with scan interval
  - process liveness shown
  - dominant no-signal reason visible when high-alert is empty

## Performance checks
- Compare before/after social phase time.
- Confirm reduced no-data request churn from cooldown skips.
- Confirm 429s are retried with bounded backoff.
