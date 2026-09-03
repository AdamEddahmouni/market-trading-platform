# FINRA-Shaped Offline Published Short-Interest Normalization

## Purpose and evidence basis

This adapter consumes local representative records shaped around published short-interest concepts. It does not claim to reproduce every FINRA schema and does not connect to, download from, authenticate to, or prove entitlement for FINRA.

No recorded FINRA row or file exists in the preserved archives. Phase 0 explicitly records FINRA short-interest and short-volume feeds as not found. The archived mocked Yahoo metadata test establishes only `sharesShort`, `dateShortInterest`, `floatShares`, and `shortPercentOfFloat` concepts; it does not establish FINRA delivery or publication timing. Valid fixtures are `SANITIZED_REPRESENTATIVE_SAMPLE`; timing, invalid, duplicate, revision, and conflict cases are `SYNTHETIC_EDGE_CASE`. None is recorded.

## Supported record and aliases

`FinraShortInterestRecord` requires `source_record_id`, `FINRA_SHORT_INTEREST_V1`, `PUBLISHED_SHORT_INTEREST`, fixture origin, and symbol. It forbids unknown fields.

| Canonical provider field | Supported aliases |
|---|---|
| `symbol` | `symbol`, `Symbol`, `security_symbol` |
| `short_shares` | `short_shares`, `Short Shares`, `shares_short` |
| `settlement_date` | `settlement_date`, `Settlement Date`, `reporting_date`, `observation_date` |
| `publication_date` | `publication_date`, `Publication Date`, `publication_timestamp` |
| `revision_status` | `revision_status`, `record_status` |

Other accepted fields use their canonical names: publication timezone/policy, previous short shares, average daily volume/reference, days to cover, float shares, short-float percentage/unit, market, exchange, revision number/link, provider record/timestamp/timezone, capture timestamp/timezone, and the explicit provider-timestamp-as-publication flag.

Daily short-sale volume is rejected as `FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED`. It is not open short interest and is never converted into `PUBLISHED_SHORT_INTEREST`.

## Time semantics

- Settlement date describes the reported position period.
- Publication date retains provider calendar meaning.
- Source timestamp is defensible publication availability.
- Received timestamp is explicit `AdapterContext.ingested_at`.
- Effective timestamp is `max(publication availability, received timestamp)`.
- Provider timestamp and capture timestamp remain separate provenance metadata.

Effective time is never settlement date. Capture time alone cannot establish publication. A missing publication value rejects unless a distinct provider timestamp is explicitly declared to represent publication availability.

Full timestamps require an embedded offset or an explicit timezone. Date-only publication uses one explicit policy:

- `STRICT_REJECT` rejects unknown availability precision.
- `END_OF_PUBLICATION_DATE` uses next local midnight as a conservative boundary and requires a timezone.
- `INGESTION_TIME_UNCERTAIN_PLACEHOLDER` uses receipt as an uncertain placeholder and marks quality partial/missing.

IANA timezone names require runtime timezone data. Numeric offsets and UTC are portable. No unavailable zone is replaced or guessed.

## Numeric, quality, and provenance rules

Share and volume counts are exact nonnegative integers; fractions, negatives, nonfinite values, separators, and unsupported formatting are invalid. Provider float must be positive when supplied. Short-float percentage requires `PERCENT_POINTS`, `DECIMAL_FRACTION`, or `FORMATTED_PERCENT_STRING`. Days to cover is a provider-published nonnegative decimal and is not recomputed.

Known zero stays numeric zero. Missing stays null. Optional invalid fields are omitted with `INVALID` quality while other defensible fields remain. Missing primary short shares produces `MISSING` quality. Cancelled records use `UNAVAILABLE`. Raw hashing covers the exact input object before aliases/defaults.

Provenance retains adapter/normalization versions, fixture origin, provider/capture/publication values, uncertainty policy, settlement date, revision facts, prior shares, average volume/reference, market/exchange, input percentage unit, and entitlement state.

## Revisions, duplicates, and conflicts

Statuses are `ORIGINAL`, `CORRECTED`, `REVISED`, `CANCELLED`, and `UNKNOWN`. Every accepted record creates a separate immutable observation. Batch normalization suppresses exact raw/source-ID duplicates, links available prior records with parent IDs and deterministic correlation IDs, and preserves unlinked same-period disagreement as conflicted evidence. Different settlement periods are not adapter conflicts.

Across receipts, provenance `supersedes_source_record_id` lets the evidence builder create a deterministic revision relationship without mutating either observation.

## Offline commands

```powershell
.\.venv\Scripts\python.exe -m squeeze_core normalize-provider --provider finra --input tests\fixtures\providers\finra\representative_cases.json --context tests\fixtures\providers\finra\context.json --case finra-complete-v1
.\.venv\Scripts\python.exe -m squeeze_core build-evidence --input tests\fixtures\evidence\normalized_phase_1d_point_in_time.jsonl --symbol TESTA --as-of 2026-02-01T15:30:00Z
.\.venv\Scripts\python.exe -m squeeze_core build-evidence-timeline --input tests\fixtures\evidence\normalized_phase_1d_point_in_time.jsonl --symbol TESTA --as-of-file tests\fixtures\evidence\short_interest_publication_timeline.json
```

Commands use local files and machine-readable canonical JSON only. Rejection returns nonzero.
