# ADR 0047: Missing evidence does not fail a candidate rule

Accepted. `FAIL` requires a known, compatible, point-in-time-eligible value that
violates an explicit condition. Unknown availability returns `UNKNOWN`, material
conflict returns `CONFLICTED`, inadequate history returns `INSUFFICIENT_DATA`, and an
inapplicable scope returns `NOT_APPLICABLE`.

