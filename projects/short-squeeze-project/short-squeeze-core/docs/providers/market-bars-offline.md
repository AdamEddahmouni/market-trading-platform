# Offline Market-Bar Normalization

Phase 1H accepts immutable local `MARKET_BAR_V1` objects plus documented IBKR-, Schwab-, Yahoo-, and generic-shaped aliases. It performs no provider connection, authentication, download, entitlement discovery, or market-calendar lookup.

## Canonical mapping

The unchanged schema `1.0.0` `BarPayload` stores timeframe, OHLC, volume, trade count, and VWAP. Structured provenance stores provider identity, source record, inclusive start and exclusive end, interval magnitude/unit/kind, timestamp meaning, session/session date, volume unit, lifecycle status, revision, supersession, publication, capture, and raw provider metadata.

Supported intervals are `1_MINUTE`, `5_MINUTES`, `15_MINUTES`, `30_MINUTES`, `1_HOUR`, and `1_DAY`. Price fields are exact decimals. Volume and trade count are non-negative integers; missing values remain missing, while explicit zero volume and zero trade count remain zero and are diagnosed independently. OHLC is required and must satisfy `low <= open/close <= high`. Only equity records are accepted.

## Time rules

An offset or explicit IANA timezone is required whenever the source timestamp lacks one. Start-labelled and end-labelled records resolve to the same start-inclusive/end-exclusive boundary. Date-only daily bars require explicit session boundaries. Time-only values require a session date. Ambiguous or nonexistent DST-local times are rejected when the runtime provides IANA timezone data; an unknown named zone is never silently treated as UTC.

Publication, local receipt, and market-effective boundary remain separate. A completed bar may be published after its interval closes; a partial bar may be available before close.

## Fixture provenance

The archive review found historical request/field shapes but no defensible saved provider bar record with complete availability provenance. Therefore every Phase 1H case is labelled `SANITIZED_REPRESENTATIVE_SAMPLE` or `SYNTHETIC_EDGE_CASE`; none is labelled recorded. Symbols, exchanges, URLs, IDs, and values are non-production test data.
