# Intelligence Persistence Architecture V1

BUILD 04.5 establishes backend-independent durable storage for canonical
intelligence records. MongoDB is the preferred **operational** persistence
backend, but intelligence semantics remain independent of any database.

> MongoDB is the preferred operational intelligence persistence backend, but
> intelligence semantics remain backend-independent.

See also: [INTELLIGENCE_CONTRACTS_V1.md](INTELLIGENCE_CONTRACTS_V1.md),
[TEMPORAL_INTEGRITY_V1.md](TEMPORAL_INTEGRITY_V1.md),
[PROVIDER_NORMALIZATION_V1.md](PROVIDER_NORMALIZATION_V1.md),
[QUALITY_CAPABILITY_ENGINE_V1.md](QUALITY_CAPABILITY_ENGINE_V1.md),
[IMMUTABLE_SNAPSHOT_ENGINE_V1.md](IMMUTABLE_SNAPSHOT_ENGINE_V1.md).

## Architectural principle

```text
DOMAIN / INTELLIGENCE CODE
        │
        ▼
IntelligenceRepository
        │
        ├──────────────────────────────┐
        ▼                              ▼
InMemoryIntelligenceRepository   MongoIntelligenceRepository
        │                              │
        │                              ▼
        │                         MongoDB normal collections
        ▼
deterministic tests / local replay support
```

Domain contracts, temporal rules, normalization, and quality evaluation **do
not** import PyMongo. Persistence depends on domain; never the reverse.

Live runtime processing does **not** read MongoDB as an event bus. Providers
flow through the runtime pipeline; a persistence writer may append canonical
records to MongoDB asynchronously or after processing.

## Storage tiers

| Tier | Technology | Role |
|------|------------|------|
| 0 — Hot runtime | in-memory state, queues, rolling state | live processing |
| 1 — Operational intelligence | **MongoDB normal collections** | canonical immutable records, operational lookups, lineage |
| 2 — Historical / research | Parquet + DuckDB | bulk history, replay datasets, training corpora |
| 3 — Scale-out analytics | ClickHouse (future only) | introduced only if measured scale justifies |

BUILD 04.5 implements Tier 1. Tier 2/3 boundaries are documented only; no
archive pipeline is implemented.

Canonical IDs and `schema_version` must survive future tier movement.

## Public repository API

Import surface:

```python
from market_platform_foundation.intelligence.persistence import (
    IntelligenceRepository,
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryUnavailableError,
)

from market_platform_foundation.intelligence.persistence.mongo import (
    MongoIntelligenceRepository,
    MongoRepositoryConfig,
)
```

Typed operations: `put_*` / `get_*` for all nine BUILD 01 contracts, plus
bounded queries (`query_events_as_of`, `query_signals_as_of`,
`get_evidence_by_snapshot`, `get_forecasts_by_instrument`,
`get_outcomes_by_forecast`, `get_opportunities_by_instrument`).

No canonical `update`, `replace`, `patch`, or `delete` APIs.

### Write semantics

| Case | Result |
|------|--------|
| same canonical ID + same semantic content | idempotent success (`ALREADY_PRESENT`) |
| same canonical ID + different content | `RepositoryConflictError` |
| updates / deletes | not exposed |

Semantic comparison uses BUILD 01 canonical serialized dicts, not object identity.

### Driver choice

**Synchronous PyMongo** (`pymongo.MongoClient`) — one reused client per
repository instance; connection pooling managed by the driver. No Motor.

## Canonical persistence classification

| Contract / record | Persisted now? | Collection | Retention class | Notes |
|-------------------|----------------:|------------|-----------------|-------|
| EventV1 | Yes | `events` | TIERABLE / ARCHIVABLE | operational Mongo; future Parquet archive |
| SnapshotV1 | Yes | `snapshots` | PERMANENT / AUDIT | reference-oriented; no embedded history |
| SignalV1 | Yes | `signals` | PERMANENT / AUDIT | canonical lineage signals |
| EvidenceV1 | Yes | `evidence` | PERMANENT / AUDIT | |
| HypothesisV1 | Yes | `hypotheses` | PERMANENT / AUDIT | |
| ForecastV1 | Yes | `forecasts` | PERMANENT / AUDIT | scientific ledger |
| OpportunityV1 | Yes | `opportunities` | PERMANENT / AUDIT | |
| OutcomeV1 | Yes | `outcomes` | PERMANENT / AUDIT | separate from forecast |
| RunManifestV1 | Yes | `run_manifests` | PERMANENT / AUDIT | reproducibility |
| QualityFinding | No | — | EPHEMERAL | runtime finding; no durable ID |
| QualityAssessment | No | — | EPHEMERAL | decision-time assessment |
| QualityDecision | No | — | EPHEMERAL | policy output |
| CapabilityAssessment | No | — | EPHEMERAL | embedded in assessment |
| ProviderHealthSnapshot | No | — | EPHEMERAL | runtime health |

`QualitySummary` on contracts is persisted as part of canonical records; BUILD
04 detailed quality objects remain runtime-only.

## Mongo collection plan

Stable collection names with `schema_version = "1"` in documents (not
`_v1` collection suffixes).

| Collection | Domain ID | Mongo `_id` | Retention |
|------------|-----------|-------------|-----------|
| `events` | `event_id` | `event_id` | operational → eventual archive |
| `snapshots` | `snapshot_id` | `snapshot_id` | permanent |
| `signals` | `signal_id` | `signal_id` | permanent |
| `evidence` | `evidence_id` | `evidence_id` | permanent |
| `hypotheses` | `hypothesis_id` | `hypothesis_id` | permanent |
| `forecasts` | `forecast_id` | `forecast_id` | permanent |
| `opportunities` | `opportunity_id` | `opportunity_id` | permanent |
| `outcomes` | `outcome_id` | `outcome_id` | permanent |
| `run_manifests` | `run_id` | `run_id` | permanent |

### Indexes (query → index)

| Index | Query |
|-------|-------|
| `idx_events_available_time` | point-in-time candidate filter |
| `idx_events_instrument_available_time` | instrument + as-of |
| `idx_events_event_type_available_time` | event type + as-of |
| `idx_events_point_in_time_sort` | deterministic sort support |
| `idx_snapshots_decision_time` | snapshot time lookups |
| `idx_signals_scope_instrument_as_of` | signal as-of by instrument |
| `idx_signals_as_of_time` | signal time range |
| `idx_evidence_snapshot_id` | evidence by snapshot |
| `idx_forecasts_scope_instrument_decision_time` | forecasts by instrument/time |
| `idx_forecasts_decision_time` | forecast time window |
| `idx_outcomes_forecast_id` | outcomes by forecast |
| `idx_opportunities_scope_instrument_created` | opportunities by instrument |
| `idx_opportunities_valid_until` | validity window |
| `idx_run_manifests_created_at` | manifest time |

## Time-series decision

Canonical immutable records use **normal MongoDB collections**.

MongoDB time-series collections are **not** used because they lack unique indexes,
schema validation, change streams, and safe immutable conflict semantics.

BUILD 04.5 creates **no** time-series collection. Future BUILD 06 dense
measurements (feature observations, telemetry) may use time-series or Parquet;
canonical `SignalV1` audit records remain in normal collections.

## Temporal precision

`*_time_ns` integer nanoseconds are authoritative. Optional BSON Date mirror
fields are not used in BUILD 04.5.

Point-in-time event queries:

```text
Mongo indexed candidate filter (available_time_ns <= T)
        ↓
deserialize EventV1
        ↓
BUILD 02 select_events_as_of / eligible_as_of
        ↓
final deterministic order
```

BUILD 02 remains temporal authority; Mongo predicates are optimizations only.

## Forecast / outcome separation

```text
ForecastV1
    │ forecast_id
    ▼
OutcomeV1
```

Separate immutable records. Forecasts are never mutated to append outcome data.

## Schema validation

BUILD 01 application contracts = authoritative semantics.

MongoDB `$jsonSchema` validators = persistence defense-in-depth (required IDs,
`schema_version`, core timestamp numeric types). Validators allow additional
fields; strict domain deserialization remains in Python.

Bootstrap: `MongoIntelligenceRepository.ensure_schema()` / `MongoSchemaManager`
— idempotent, non-destructive. Incompatible validator or index drift raises
`RepositorySchemaError` (no automatic drops).

## Persistence failure semantics

| Condition | Meaning |
|-----------|---------|
| Mongo unavailable | `RepositoryUnavailableError` — persistence health |
| Provider disconnected | BUILD 04 quality finding — separate concern |
| Invalid data | BUILD 01 / BUILD 04 quality — separate concern |

Persistence outage does not rewrite `QualitySummary` to `INVALID`.

## Runtime configuration

| Variable | Purpose |
|----------|---------|
| `IMP_MONGODB_URI` | operational Mongo URI (development: `mongodb://127.0.0.1:27017`) |
| `IMP_MONGODB_DATABASE` | database name (default `imp_intelligence`) |
| `IMP_MONGODB_SERVER_SELECTION_TIMEOUT_MS` | optional timeout |
| `IMP_MONGODB_APPLICATION_NAME` | optional client app name |
| `IMP_TEST_MONGODB_URI` | opt-in integration tests only |
| `IMP_TEST_MONGODB_DATABASE` | must start with `imp_test_` |

Credentials are redacted in `repr(config)` and error details.

**Local development only:** bind Mongo to loopback without auth is not
production guidance. Production requires authentication, TLS, replication,
backup, and monitoring — out of BUILD 04.5 scope.

## Integration tests

```powershell
$env:IMP_TEST_MONGODB_URI = "mongodb://127.0.0.1:27017"
$env:IMP_TEST_MONGODB_DATABASE = "imp_test_manual"
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m unittest tests.intelligence.test_persistence_mongo_integration -v
```

Tests drop only databases whose names begin with `imp_test_`.

## BUILD 05 handoff

BUILD 05 (Immutable Snapshot Engine) will:

- compose `SnapshotV1` content (references, hashes, selection policy);
- persist via `IntelligenceRepository.put_snapshot` / `get_snapshot`;
- resolve referenced events/signals through repository getters;

without importing PyMongo. Repository does not dictate snapshot composition.

## Tests

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest discover -s tests/intelligence -v
```

Persistence-specific modules:

- `test_persistence_conformance.py` — InMemory conformance
- `test_persistence_codec.py` — codec / redaction
- `test_persistence_mongo_schema.py` — schema plan unit tests
- `test_persistence_mongo_integration.py` — opt-in real Mongo
