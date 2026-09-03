# Observation Contract

## Phase 1I trade and quote compatibility

Schema `1.0.0` remains current. `TradePayload.size` is nullable so unavailable size is not fabricated as zero; existing integer-size bytes are unchanged. Crossed quotes no longer require invalid quality because `CROSSED` is objective structure, while explicit invalid quality remains accepted. Sequence scope, market scope, venue, side identity, quote condition/source, lifecycle, and event/publication/capture details remain structured provenance.

## Phase 1H market-bar compatibility

Phase 1H keeps schema `1.0.0` and does not modify `BarPayload`. Timeframe, OHLC, volume, trade count, and VWAP use existing canonical fields. Boundary start/end, interval components, timestamp meaning, session/date, volume unit, lifecycle state, revision/supersession, publication, capture, and provider facts are additive structured provenance. Start is inclusive and end is exclusive.

## Phase 1G news compatibility

Phase 1G keeps schema `1.0.0` and does not modify `NewsItemPayload`. Headline, provider summary, sanitized URL, publisher, original publication time, and explicit associated symbols use existing canonical fields. Author, updated time, language, content type, lifecycle status, provider availability/capture, provider identity, canonical URL identity, and revision facts are additive provenance metadata.

## Version and envelope

The only supported schema is `1.0.0`. Unknown versions fail validation rather than being guessed or migrated silently.

Required fields are `schema_version`, `event_type`, `symbol` (present but nullable for market-wide/source events), `asset_class`, `source`, `source_record_id`, `source_timestamp`, `received_timestamp`, `effective_timestamp`, `market_session`, `data_freshness`, `observation_kind`, `quality`, `payload_type`, `payload`, and `provenance`. `observation_id` may be supplied or is deterministically created during validation.

Optional fields are `sequence_number`, `exchange`, `currency`, `timezone`, `correlation_id`, `parent_observation_ids`, `raw_payload_hash`, `normalization_version`, and `notes`.

## Time meanings

- `source_timestamp`: when the source says the event/value occurred.
- `received_timestamp`: when the application received or ingested it.
- `effective_timestamp`: when downstream replay state treats it as effective.

All three are distinct, required, timezone-aware, and normalized to UTC. Canonical output always uses six fractional digits and `Z`, for example `2026-01-02T14:30:00.000000Z`. Provenance can preserve the source's original text and timezone label.

## Identity strategy

When an ID is absent, UUIDv5 is computed in a fixed project namespace over stable JSON containing schema version, event type, symbol, source, source record ID, source timestamp, payload type, and payload content. The same normalized source record and content therefore produce the same ID. Random UUIDs and wall-clock input are never used. An explicit fixture ID is preserved.

## Payload types

The envelope binds every event to one model:

| Event | Payload highlights |
|---|---|
| `TRADE` | price, size, exchange, conditions |
| `QUOTE` | bid/ask prices and sizes, exchange |
| `BAR` | timeframe, OHLC, volume, trade count, VWAP |
| `PUBLISHED_SHORT_INTEREST` | short/float shares, short-float percent, settlement/publication dates, days to cover |
| `BORROW_AVAILABILITY` | available shares, lender count, hard-to-borrow flag |
| `BORROW_FEE` | annualized fee percent, fee type |
| `NEWS_ITEM` | headline, summary, URL, publisher, published time, associated symbols; no sentiment |
| `SEC_FILING` | form, accession, filed time, period, primary document, issuer CIK |
| `TRADING_HALT` | status, reason, halt and resume times |
| `CORPORATE_ACTION` | action type, effective date, description |
| `DERIVED_INDICATOR` | calculation/version, parent IDs, parameters, result; no calculation implementation |
| `SOURCE_STATUS` | status, latency, last success, error code, message |
| `MARKET_SNAPSHOT` | nullable descriptive price/volume/float/short-float/classification/earnings fields; not a trade, quote, bar, or published-short-interest report |

Models reject unknown fields. Source-legitimate omissions are nullable. Prices, percentages, VWAP, days-to-cover, confidence, and derived numeric results use decimal arithmetic. Counts and share quantities are integers. Canonical decimals are non-exponent strings with insignificant trailing zeroes removed; `10.2500` becomes `"10.25"`, and zero becomes `"0"`.

Phase 1D determined that `PublishedShortInterestPayload` is sufficient and made no canonical contract change. For its supported offline normalization, settlement date is the described market period, publication date retains calendar meaning, source timestamp is publication availability, received timestamp is local ingestion, and effective timestamp is their maximum. Provider timestamps, capture timestamps, auxiliary values, market scope, and revision facts remain provenance metadata; relationships use existing parent/correlation fields.

## Provenance

Provenance requires provider, retrieval/ingestion method, origin kind, and normalization status. It can also retain normalization version, upstream IDs, completeness, unit/name alterations, entitlement state, source timezone/text, and provider-specific metadata. Provider metadata is opaque; canonical behavior does not depend on its keys.

`observation_kind` and provenance `origin_kind` must match. Kinds distinguish provider-published, market-observed, derived, human-annotated, and synthetic records. Derived inputs are carried both in the derived payload and provenance/parent fields.

## Quality

Quality is an object with `state`, reasons, evaluation time, age, expected delay, source health, completeness, and confidence. Optional context remains null when unknown. Non-`KNOWN_VALUE` states require at least one reason.

States are `KNOWN_VALUE`, `MISSING`, `UNAVAILABLE`, `NOT_APPLICABLE`, `STALE`, `DELAYED`, `INVALID`, `CONFLICTED`, and `ESTIMATED`. Conflict records remain separate observations linked by correlation metadata; Phase 1A does not choose a winner.

## Phase 1E SEC compatibility

`SecFilingPayload` remains unchanged. Its canonical fields are form, accession, filed time, period of report, primary document, and CIK. Public availability uses envelope source time, local receipt uses received time, and effective time is their maximum. Acceptance/publication representations and auxiliary objective metadata remain provenance; amendments use parent/correlation fields. Schema remains `1.0.0`, and no filing-content interpretation exists.

## Phase 1F trading-halt compatibility

Phase 1F makes no canonical schema change. `TradingHaltPayload` continues to carry objective halt status, reason code/text, halt time, and actual resume time. Exchange, event key, lifecycle milestone, quote/trade schedules and actuals, publication facts, session context, raw-input hash, and revision facts are retained in structured provenance metadata. This additive design preserves every earlier serialized observation and hash.
