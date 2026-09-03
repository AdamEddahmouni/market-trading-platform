# Momentum Discovery Rule Semantics

Momentum discovery describes observable market activity; it does not confirm short pressure.
`PRICE_RANGE` uses the latest eligible completed bar close. `PERCENTAGE_CHANGE_MINIMUM` and
`RELATIVE_VOLUME_MINIMUM` consume the existing versioned Phase 2A/2B metrics. `FLOAT_MAXIMUM`
uses an eligible snapshot and returns `UNKNOWN` when canonical float is absent.
`MARKET_DATA_AVAILABLE` and `COMPLETED_BAR_AVAILABLE` expose data state independently.

Future and out-of-provider-scope bars are excluded. A partial bar cannot satisfy the completed
bar rule. Missing metrics are `UNKNOWN`, insufficient histories are `INSUFFICIENT_DATA`,
conflicts are `CONFLICTED`, and incompatible units are `INSUFFICIENT_DATA`. No technical
indicator, sentiment, score, or directional inference is computed.

