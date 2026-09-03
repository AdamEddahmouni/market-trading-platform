# Trade and Quote Availability Semantics

A trade or quote is eligible only when its provider publication boundary, local received timestamp, and effective timestamp are no later than `as_of`, and its event time is not in the future. Effective time is normally `max(publication, received)`. Event time never grants availability.

`STRICT` rejects missing publication. Capture and receipt placeholder policies retain uncertainty explicitly; the original publication field remains missing. Capture is not renamed publication.

Event, publication, availability, capture, and correction ages are separate. A later corrected or cancelled record does not rewrite an earlier bundle. `TRADES` and `QUOTES` coverage is independent from snapshots, bars, halts, news, filings, short interest, and borrow evidence.

