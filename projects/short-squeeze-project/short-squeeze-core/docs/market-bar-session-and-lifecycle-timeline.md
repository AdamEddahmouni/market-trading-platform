# Market-Bar Session and Lifecycle Timeline

For the synthetic `TESTA` lifecycle fixture, the boundary is `[14:30:00Z, 14:31:00Z)` in the regular session:

1. Before `14:30:30Z`, no partial record is published.
2. After its `14:30:31Z` receipt, the partial record is eligible.
3. The completed record is published at `14:31:01Z` and eligible after receipt at `14:31:02Z`.
4. A correction is published at `14:35:00Z` and eligible after receipt at `14:35:01Z`.

Every rebuild retains immutable history and explicit lifecycle relationships. The objective series orders boundaries and records deterministically, reports independent duplicates and overlaps, and selects no synthetic winner.

Sessions are explicit `PREMARKET`, `REGULAR`, `AFTER_HOURS`, `OVERNIGHT`, `EXTENDED`, `CLOSED_SESSION`, or `UNKNOWN` facts. Daily and cross-session fixtures carry a session date and explicit boundaries. Expected-missing, session-closed, and unknown-expectation states are supplied by fixture policy; the library contains no exchange calendar and does not invent expected bars.
