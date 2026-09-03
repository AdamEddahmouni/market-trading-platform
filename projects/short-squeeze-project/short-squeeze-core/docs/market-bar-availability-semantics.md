# Market-Bar Availability Semantics

A bar is eligible at `as_of` only when its provider publication, local receipt, and effective timestamp are all no later than `as_of`. Interval close alone does not prove public or local availability. The evidence bundle reports interval age and correction age separately from receipt age.

Partial, completed, corrected, and cancelled records are immutable observations. A later lifecycle record does not rewrite an earlier point-in-time bundle. Explicit supersession links establish a revision chain; unlinked changed records at one semantic boundary remain conflicted. No provider wins and no OHLCV values are averaged.

Coverage domain `MARKET_BARS` is independent. A missing eligible bar yields missing coverage or an explicit series diagnostic; it is not inferred from a quote, snapshot, adjacent bar, closed session, or unknown calendar.

