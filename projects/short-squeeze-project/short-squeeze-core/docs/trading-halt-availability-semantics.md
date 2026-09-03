# Trading-Halt Availability Semantics

A halt fact is eligible at an `as_of` boundary only when its public source time, local receipt time, and effective time are all known and no later than `as_of`. Announcement/event time does not prove public availability, and publication does not prove local receipt.

The boundaries are intentionally separate:

- `source_timestamp` is the strict public-availability boundary.
- `received_timestamp` is local ingestion availability.
- `effective_timestamp` is when the represented lifecycle fact applies.
- event timestamps in the payload or provider metadata describe the halt or resumption milestone; they do not backdate knowledge.

An observation with unknown publication availability is excluded from strict point-in-time evidence. A published but not-yet-received record is also excluded. Later corrections and resumption updates cannot alter an earlier bundle because every lifecycle row is immutable and evaluated independently.

Evidence can require the domain with `include_trading_halts_domain=True` even when no halt is observed. Coverage then reports the absence or partialness instead of silently treating the domain as out of scope. The bundle exposes separate announcement, halt-event, and resumption-event ages only when their supporting timestamps exist.
