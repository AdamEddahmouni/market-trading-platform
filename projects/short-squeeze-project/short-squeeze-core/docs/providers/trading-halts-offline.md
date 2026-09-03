# Trading-Halt Offline Normalization

Phase 1F accepts strict, local `TRADING_HALT_V1` objects and emits immutable `TRADING_HALT` observations. The adapter has no exchange client, network access, authentication, downloader, streaming connection, or entitlement check. Input must already be sanitized and locally available.

## Input boundary

`TradingHaltRecord` preserves a source record identity, symbol, exchange, provider halt identity, objective halt code/text, lifecycle status, publication and event timestamps, session date/timezone, revision facts, and opaque provider metadata. Aliases cover a small documented representative shape; unknown fields are rejected.

Exact offset-bearing timestamps are preferred. Time-only values require both an explicit session date and timezone. Date-only or timezone-unknown values do not silently become exact instants. Publication, receipt, and event-effective time remain distinct.

The known code set (`T1`, `T2`, `T5`, `T6`, `T12`, `H10`, `LUDP`, `M`) is only an objective recognition set. Unknown well-formed codes are retained with a diagnostic; neither codes nor reason text are interpreted as a catalyst, prediction, recommendation, or trading signal.

## Output and lifecycle

Every accepted row produces a canonical observation whose raw-input SHA-256 and provider identifiers remain in provenance metadata. Scheduled quote/trade resumption times remain schedules. Only an observed actual resumption can populate the canonical payload `resume_time`; quote and trade milestones remain distinguishable in metadata.

Batch normalization is deterministic. Byte-identical source duplicates are diagnosed and emitted once. Same-identity disagreements are retained as immutable conflicting observations. Revisions link to prior records when the source relationship is available; they never overwrite earlier observations.

## Fixtures

The 30 provider cases under `tests/fixtures/providers/halts` are representative or synthetic only. Archive review found no preserved recorded halt row, so no fixture is labeled recorded. Symbols, exchange, identities, times, and values are invented. `tests/phase_1f_fixture_builders.py --write` regenerates the committed mixed replay and compatibility metadata.

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider halts --input tests\fixtures\providers\halts\representative_cases.json --context tests\fixtures\providers\halts\context.json --case halt-complete-v1
```
