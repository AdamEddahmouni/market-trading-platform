# Trading-Halt Resumption Timeline

Phase 1F models a halt as an objective sequence of published lifecycle facts:

1. `HALT_ANNOUNCED`
2. `HALT_ACTIVE`
3. `QUOTE_RESUMPTION_SCHEDULED`
4. `QUOTES_RESUMED`
5. `TRADE_RESUMPTION_SCHEDULED`
6. `TRADING_RESUMED`

The sequence is descriptive, not assumed. A source may omit milestones, revise a scheduled time, cancel a resumption, or leave a halt indefinite. Quote resumption and trade resumption are not interchangeable. A schedule is never promoted to an actual event merely because its scheduled clock time has passed.

At each `as_of`, only observations passing publication, receipt, and effective-time gates contribute. The latest eligible lifecycle fact for an event determines the objective `halt_state`, unless eligible same-event facts conflict. Possible states are `NOT_OBSERVED`, `HALT_ANNOUNCED`, `HALTED`, `QUOTE_RESUMPTION_SCHEDULED`, `QUOTES_RESUMED`, `TRADE_RESUMPTION_SCHEDULED`, `TRADING_RESUMED`, `CANCELLED`, `CONFLICTED`, and `UNKNOWN`.

The committed timeline uses `tests/fixtures/evidence/halt_resumption_timeline.json` with the 12-observation mixed Phase 1F JSONL. It demonstrates that scheduled milestones do not become actual, actual quote resumption does not imply trade resumption, and later-received updates do not leak into earlier bundles.

```powershell
.\.venv\Scripts\python.exe -m squeeze_core build-evidence-timeline --input tests\fixtures\evidence\normalized_phase_1f_point_in_time.jsonl --symbol TESTA --as-of-file tests\fixtures\evidence\halt_resumption_timeline.json
.\.venv\Scripts\python.exe -m squeeze_core build-halt-state --input tests\fixtures\evidence\normalized_phase_1f_point_in_time.jsonl --symbol TESTA --as-of 2026-01-15T15:31:00Z
```
