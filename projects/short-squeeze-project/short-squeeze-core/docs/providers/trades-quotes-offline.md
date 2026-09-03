# Offline Trade and Quote Normalization

Phase 1I accepts strict local provider-neutral `TRADE_QUOTE_V1` objects only. The archive contained request code and mocked last-price snapshots, but no defensible recorded event row with publication, receipt, venue, sequence, conditions, and lifecycle provenance. Fixtures are therefore sanitized representative or synthetic edge cases; none is recorded.

Trades preserve exact positive price, nullable whole size, explicit size unit, exchange, venue, sequence scope, and objective conditions. Quotes preserve independent bid/ask prices and sizes, side IDs, quote condition/source, and explicit `VENUE`, `NBBO`, `CONSOLIDATED`, `PROVIDER_AGGREGATED`, or `UNKNOWN` market scope. One-sided and size-without-price rows remain visible; missing and zero remain different.

Publication, event, capture, receipt, and effective times remain separate. Originals, corrections, cancellations, and deletions are immutable. The adapter detects exact duplicates and same-identity conflicts without merging providers.

There is no live connection, provider alias guessing, order-book depth, synthetic NBBO, bar aggregation, aggressor side, buy/sell volume, order-flow calculation, spread or midpoint, score, recommendation, or signal.

