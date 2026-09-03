# IBKR Offline Borrow Normalization

## Purpose and source basis

This adapter consumes a sanitized, local record shaped after the Interactive Brokers short-stock file columns documented in Phase 0 and the inherited parser comments. No recorded provider row was preserved. Therefore valid shape fixtures are labeled `SANITIZED_REPRESENTATIVE_SAMPLE`; deliberately malformed, duplicate, and conflicting cases are `SYNTHETIC_EDGE_CASE`. Values and symbols are invented, and fixtures contain no account data, credentials, tokens, sessions, or private URLs.

This data represents provider securities-lending fee and availability information. It is not exchange-wide short interest, published settlement short interest, covering volume, a squeeze measure, or proof of a real-time entitlement.

## Record shape

`IbkrBorrowRecord` accepts:

| Field | Meaning |
|---|---|
| `source_record_id` | Sanitized upstream row identity |
| `symbol` | Uppercased equity symbol |
| `fee_rate` | Provider fee value before explicit unit conversion; nullable |
| `fee_rate_unit` | `PERCENT_POINTS` or `DECIMAL_FRACTION`; nullable only when the fee is missing |
| `available_shares` | Nonnegative whole-share count; nullable |
| `lender_count` | Optional nonnegative whole-number count |
| `hard_to_borrow` | Optional provider status |
| `provider_timestamp` | ISO datetime, date-only string, or null |
| `provider_timezone` | Numeric UTC offset, `UTC`, supported IANA name, or null |
| `delay_status` | `KNOWN_DELAYED`, `NOT_DELAYED`, or `UNKNOWN` |

The Pydantic model forbids extra fields. The exact sanitized input object is canonically hashed before validation/default expansion. Each output stores this SHA-256 hash as `raw_payload_hash`.

## Output rule

A valid record normally produces two separate `PROVIDER_PUBLISHED` observations in this order:

1. `BORROW_FEE` / `borrow_fee`
2. `BORROW_AVAILABILITY` / `borrow_availability`

The adapter never combines them into short interest or a squeeze value. Invalid fee data omits only the fee observation when availability remains valid; invalid availability omits only availability when the fee remains valid. Missing-but-valid fields still produce nullable observations with `MISSING` quality. Structural or timestamp-timezone failure rejects the record.

Provider metadata retains adapter and normalization versions, source endpoint name, source record ID, delay status, and fee input unit. Envelope provenance retains source timestamp text/timezone, entitlement, completeness, and unit/name transformation flags.

## Units and numeric rules

- `PERCENT_POINTS`: input `0.325` means `0.325%` annualized.
- `DECIMAL_FRACTION`: input `0.325` means `32.5%` annualized, and provenance marks units modified.
- No magnitude-based inference occurs.
- Unsupported or absent units on a present fee omit fee output with `UNSUPPORTED_PERCENT_UNIT`.
- Negative, nonfinite, or nonnumeric fees are invalid. Negative fee/rebate semantics are not invented because the Phase 1A borrow-fee contract is nonnegative and the sample does not establish otherwise.
- Available shares and lender counts must be nonnegative whole numbers. Fractional or negative availability is invalid and never rounded/defaulted.

Known zero is a numeric value with `KNOWN_VALUE`. Missing fee or availability stays `null` with `MISSING`; it never becomes zero.

## Timestamp and delay rules

- An ISO timestamp with an embedded offset normalizes directly to UTC.
- A naive ISO timestamp requires `provider_timezone` or context `source_timezone`.
- A date-only value requires a timezone and normalizes to local start-of-day with `DATE_ONLY_PROVIDER_TIMESTAMP`.
- A missing provider timestamp uses explicit `ingested_at` only as an uncertain placeholder so the Phase 1A required timestamp can be represented. Both observations receive `MISSING` quality and `MISSING_PROVIDER_TIMESTAMP`; provenance retains a null source representation.
- A naive timestamp with no timezone assumption is rejected with `UNKNOWN_TIMEZONE`. No zone is fabricated.
- Numeric offsets are portable. IANA names use Python `zoneinfo` and require timezone data available in the runtime; unavailable names reject.
- `KNOWN_DELAYED` produces `DELAYED` freshness and quality. `UNKNOWN` emits `DELAY_STATUS_UNKNOWN`; it is not treated as live.

## Batch duplicate and conflict behavior

Exact raw hashes or repeated source record IDs are emitted once and diagnosed `DUPLICATE_SOURCE_RECORD`. Records for the same event, symbol, and effective timestamp with different payloads are all preserved, linked by a deterministic correlation ID, changed to `CONFLICTED` quality, and diagnosed `CONFLICTING_SOURCE_RECORD`. The adapter does not choose a winner.

## Offline CLI and replay

Normalize one embedded representative case:

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider ibkr --input tests\fixtures\providers\ibkr\representative_cases.json --context tests\fixtures\providers\ibkr\context.json --case ibkr-representative-complete-v1
```

Regenerate the normalized replay artifacts:

```powershell
.\.venv\Scripts\python.exe tests\provider_fixture_builders.py --write
.\.venv\Scripts\python.exe -m squeeze_core validate tests\fixtures\providers\ibkr\normalized_session.jsonl
.\.venv\Scripts\python.exe -m squeeze_core replay tests\fixtures\providers\ibkr\normalized_session.jsonl --mode strict
```

The CLI reads local JSON only, prints canonical machine-readable JSON, and returns nonzero for a rejected record. It includes no IBKR authentication, TWS/Client Portal connection, polling, subscription, account, order, token, or session behavior.
