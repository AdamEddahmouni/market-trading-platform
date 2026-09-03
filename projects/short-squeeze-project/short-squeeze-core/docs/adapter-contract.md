# Offline Adapter Contract

## Phase 1I trades-quotes extension

The `trades-quotes` adapter accepts local provider-neutral `TRADE_QUOTE_V1` records through the existing immutable context/result/diagnostic boundary. It requires explicit provider identity, event time, publication policy, venue and market scope, sequence scope, size unit, condition, and lifecycle semantics. Missing versus zero remains distinct. Unknown scope and one-sided quotes are preserved; no provider alias, synthetic NBBO, aggressor side, spread, or order-flow meaning is inferred.

## Phase 1H market-bar extension

The market-bar adapter accepts only immutable local objects in provider-neutral or documented IBKR-, Schwab-, Yahoo-, and generic-shaped forms. Unknown fields, unsupported intervals/assets, invalid OHLC, ambiguous time boundaries, and timezone-less local times are rejected with structured diagnostics. It keeps missing volume distinct from zero, exact duplicates distinct from conflicts, and publication distinct from receipt and interval close. It performs no I/O beyond the caller-provided object.

## Phase 1G news extension

The news adapter accepts only immutable local `NEWS_ITEM_V1` objects and the documented Finviz-, Yahoo-, and NewsAPI-shaped aliases. Unknown fields and unsupported shapes are rejected. It preserves only explicit symbol associations, never fetches URLs, and separates publication, provider availability, capture, receipt, update, and lifecycle facts. Exact duplicates emit once; conflicts, revisions, withdrawals, deletions, and cross-provider syndication remain deterministic immutable records.

## Boundary

The provider-neutral adapter boundary is:

```text
local provider-shaped object
  -> provider record validation
  -> pure point-in-time normalization
  -> canonical observations
  -> structured diagnostics or typed rejection
```

`AdapterContext`, `NormalizationDiagnostic`, `RejectedRecord`, and `NormalizationResult` are immutable Pydantic models. A result contains a typed tuple of Phase 1A `Observation` objects, a typed tuple of diagnostics, and optionally a typed rejection. A rejected result cannot also contain observations. Partial accepted results may contain valid observations and diagnostics for invalid fields.

The boundary does not read the clock, environment, `.env` files, credentials, broker state, network sockets, databases, or archived repositories. Context and provider-shaped input are the only normalization inputs.

## Point-in-time context

Required context fields are `ingested_at`, `source_timezone` (nullable only to represent no assumption), `provider`, `adapter_version`, `normalization_version`, `entitlement_status`, and `collection_method`. Optional fields are `account_scope`, `request_id`, `session_id`, `expected_delay_ms`, and `source_endpoint_name`.

`ingested_at` must be timezone-aware and is normalized to UTC. It becomes `received_timestamp` and `quality.evaluated_at`; normalization never calls a wall clock. A provider timestamp is not replaced by ingestion time silently.

## Results and diagnostics

Diagnostics contain a stable code, severity, field, message, continuation flag, and non-secret context. Implemented codes are:

- `MISSING_PROVIDER_TIMESTAMP`
- `DATE_ONLY_PROVIDER_TIMESTAMP`
- `UNKNOWN_TIMEZONE`
- `MISSING_BORROW_FEE`
- `MISSING_AVAILABLE_SHARES`
- `EXPLICIT_ZERO_BORROW_FEE`
- `EXPLICIT_ZERO_AVAILABLE_SHARES`
- `UNSUPPORTED_PERCENT_UNIT`
- `INVALID_NUMERIC_VALUE`
- `DUPLICATE_SOURCE_RECORD`
- `CONFLICTING_SOURCE_RECORD`
- `DELAY_STATUS_UNKNOWN`
- `ENTITLEMENT_UNKNOWN`
- `PARTIAL_RECORD`

Diagnostics supplement canonical quality semantics; they do not replace them. Exceptions at the provider-validation boundary are converted to typed rejections.

## Extension rule

A future adapter should define a provider-specific immutable record model and pure normalization function, while reusing this result/context boundary and Phase 1A observations. Live acquisition belongs outside this package and is not part of Phase 1B.

Phase 1C follows this rule for Finviz-shaped local records. It adds prefixed structural/parsing diagnostics, including unsupported schema/type/origin/aliases, invalid or zero price, unsupported percent units, invalid quantity suffixes, approximate quantities, unknown relative-volume reference, date-only/ambiguous earnings, partial rows, duplicates, conflicts, and uncertain timestamp placeholders. Diagnostics never include secret-bearing raw content.

Phase 1D follows the same boundary for FINRA-shaped published short interest. Its source timestamp is defensible publication availability, receipt is context ingestion, and effective time is their maximum. Settlement remains payload reporting-period metadata. Full publication timestamps require explicit timezone meaning; date-only publication requires strict rejection, a timezone-bound conservative window, or an uncertain receipt-time placeholder. Capture-only availability rejects. Corrections remain new observations and may link to prior records without mutation.

The FINRA adapter accepts only local objects. It includes no provider acquisition, download, HTTP/FTP, credentials, authentication, database, or daily short-sale-volume normalization.

## Phase 1E SEC-shaped extension

Exact publication time is preferred; otherwise exact SEC acceptance is the public boundary. Date-only availability requires an explicit policy. Filed date and period of report never grant availability. CIK/accession/form parsing is conservative, remote references are omitted, and amendments remain immutable linked observations. The adapter has no SEC/EDGAR client, download, document parser, credentials, or interpretation logic.

## Phase 1F trading-halt extension

The halt adapter accepts only local `TRADING_HALT_V1` records. It validates source shape/origin, symbol, exchange, lifecycle status, halt code, publication/event times, session context, and revision metadata. Time-only inputs require explicit session date and timezone; date-only and unknown-timezone values are not guessed.

Schedules and actual events are separate facts. Only actual resumption populates canonical `resume_time`; detailed quote/trade milestones remain structured provenance metadata. Batch normalization suppresses byte-identical duplicates, retains same-identity disagreements as conflicts, and links immutable revisions where possible. Unknown well-formed provider codes are preserved with diagnostics, not interpreted.
