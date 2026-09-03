# Multi-Source Data Integration Foundation Implementation Plan

> **For agentic workers:** This plan is executed inline in the current worktree. No commit, push, deployment, reset, checkout, or unrelated-file overwrite is authorized.

**Goal:** Add a stdlib-only, provider-agnostic foundation for registering source capabilities, preserving namespaced identity and immutable raw lineage, normalizing PIT observations, planning provider queries, and reconciling multi-source candidates without changing execution behavior.

**Architecture:** Extend the existing `providers` package with focused registry, identity, observation/raw-record, planning, and reconciliation modules. Reuse `providers/envelope.py`, `contracts/envelope.py`, `market_data` capture/timestamp/admission semantics, existing composition injection, and current UI/API boundaries. The initial storage implementation is bounded in-memory plus immutable raw-record interfaces; SQLite receives no tick/event warehouse schema change.

**Tech Stack:** CPython 3.11, standard library only, dataclasses, enums, typing protocols, existing `unittest`/manifest validation, existing canonical hashing utilities.

## Global Constraints

- Preserve the governed foundation’s CPython 3.11 stdlib-only dependency lock.
- Preserve Demo read-only, Paper authority gates, account identity/isolation, preview/submit validation, and the permanent Live execution block.
- Do not modify or overwrite unrelated uncommitted IBKR TWS, NewsAPI/Finnhub, Finviz, readiness, evidence, or documentation changes.
- Do not add OpenBB, MCP, paid feeds, DuckDB, MongoDB, event buses, or external provider SDKs.
- New fields are optional at API boundaries; legacy instrument references and records remain readable.
- Raw records and historical observations are immutable; reprocessing creates new versioned outputs.
- All PIT decisions use explicit `available_time_ns`; source, event, receive, ingest, normalized, and published clocks remain distinct.
- No provider credential values are stored, logged, or returned; only credential references and presence/state are allowed.
- Observation extensions are optional, structured, deeply immutable, bounded to 8 KiB/five levels, and secret-safe.
- No commits are created because the user explicitly prohibited commits.

## Files and boundaries

Create:

- `src/market_platform_foundation/providers/registry.py` — provider/capability descriptors, validation, deterministic registry.
- `src/market_platform_foundation/providers/identity.py` — namespaced entity/instrument identities and provider mappings.
- `src/market_platform_foundation/providers/observations.py` — typed source-attributed observations and common event envelope.
- `src/market_platform_foundation/providers/raw_records.py` — immutable bounded raw-record store and normalization lineage.
- `src/market_platform_foundation/providers/storage.py` — operational/analytical storage protocols and bounded local implementation.
- `src/market_platform_foundation/providers/testing.py` — deterministic fixture adapter for provider tests.
- `src/market_platform_foundation/providers/planner.py` — capability/PIT/license/health/rate/cache-aware planning.
- `src/market_platform_foundation/providers/reconciliation.py` — typed candidate scoring, conflicts, and selected values.
- `tests/providers/test_multi_source_foundation.py` — deterministic fake adapters and end-to-end foundation coverage.
- `docs/providers/MULTI_SOURCE_DATA_FOUNDATION.md` — provider onboarding and data-flow contract.
- `docs/architecture/adr/0009-multi-source-data-integration-foundation.md` — additive architectural decision.

Modify additively:

- `src/market_platform_foundation/providers/__init__.py` — export stable foundation symbols.
- `tools/validation_manifest.json` — include new source files in the existing `providers` suite.
- `docs/README.md` — add the new provider-foundation document to the provider architecture index without removing current uncommitted rows.
- `docs/engineering/WORK_LOG.md` — append a truthful implementation entry with exact validation results.

Do not modify:

- `src/market_platform_foundation/paper/**`
- `src/market_platform_foundation/operating_modes.py`
- `src/market_platform_foundation/operational_identity.py`
- current IBKR, news, Finviz, provider-readiness, evidence, or user-authored documentation changes except the explicitly additive index link.

---

### Task 1: Define registry and capability contracts

**Files:**
- Create: `tests/providers/test_multi_source_foundation.py`
- Create: `src/market_platform_foundation/providers/registry.py`
- Modify: `src/market_platform_foundation/providers/__init__.py`

**Interfaces:**
- `CapabilityDescriptor(capability_id, asset_classes, venues, interfaces, supports_history, supports_pit, freshness_sla_ns, license_class, rate_policy_id, normalizer_version)`
- `ProviderDescriptor(provider_id, display_name, capabilities, health_state, credential_refs, schema_versions, priority)`
- `ProviderRegistry.register(provider)`, `.validate()`, `.providers_for(capability_id)`, `.manifest()`
- Duplicate provider IDs, duplicate capability IDs, invalid priorities, and capabilities missing from their provider must raise stable `ProviderRegistryError` codes.

- [x] **Step 1: Write failing tests**

```python
def test_registry_orders_providers_deterministically_and_validates_capabilities():
    registry = ProviderRegistry()
    registry.register(provider("zeta", priority=20, capability="quote"))
    registry.register(provider("alpha", priority=10, capability="quote"))
    assert [item.provider_id for item in registry.providers_for("quote")] == ["alpha", "zeta"]
    assert registry.manifest()["schema_version"] == "1.0"

def test_registry_rejects_duplicate_provider_ids():
    registry = ProviderRegistry()
    registry.register(provider("alpha", priority=1, capability="quote"))
    with pytest.raises(ProviderRegistryError, match="PROVIDER_ID_DUPLICATE"):
        registry.register(provider("alpha", priority=2, capability="quote"))
```

- [x] **Step 2: Run the focused test and confirm the expected missing-symbol failure**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.providers.test_multi_source_foundation.RegistryTests -v
```

Expected: FAIL because the new registry symbols do not exist.

- [x] **Step 3: Implement the minimal immutable descriptors and registry**

Use frozen/slot dataclasses, tuple-backed capability collections, stable error codes, and sorting by `(priority, provider_id)`. Do not import any provider SDK or network code.

- [x] **Step 4: Run focused registry tests**

Expected: registry tests pass with no network access.

- [x] **Step 5: Refactor only after green**

Keep the registry independent from `ProviderComposition`; composition selects runtime instances, registry describes operational capability.

### Task 2: Add namespaced identity and mapping contracts

**Files:**
- Modify: `tests/providers/test_multi_source_foundation.py`
- Create: `src/market_platform_foundation/providers/identity.py`
- Modify: `src/market_platform_foundation/providers/__init__.py`

**Interfaces:**
- `EntityIdentity(namespace, entity_id, asset_class)`
- `InstrumentIdentity(namespace, instrument_id, asset_class, venue_id, currency)`
- `ProviderIdentifierMapping(provider_id, source_instance_id, provider_identifier, canonical_instrument, mapping_version, conflict_state)`
- `.qualified_id()` and `.to_dict()` on each identity.
- Empty identifiers, invalid namespaces, and conflicting canonical mappings fail closed.

- [x] **Step 1: Write failing tests**

Cover distinct provider aliases for one canonical instrument, ticker collision across venues, stable qualified IDs, and mapping conflicts.

- [x] **Step 2: Run the focused identity tests**

Expected: FAIL because identity classes do not exist.

- [x] **Step 3: Implement identity dataclasses**

Reuse validation style from `contracts/identity.py` and `SymbolMapping`, but do not replace either. Preserve compatibility by allowing existing plain instrument strings to be represented as legacy namespace values.

- [x] **Step 4: Run identity tests**

Expected: PASS, including proof that `NASDAQ:AAPL` and `NYSE:AAPL` are not equal.

- [x] **Step 5: Refactor after green**

Keep provider mapping separate from `OperationalIdentity`; account identity must not be reused as market identity.

### Task 3: Add immutable raw records, observations, and envelope lineage

**Files:**
- Modify: `tests/providers/test_multi_source_foundation.py`
- Create: `src/market_platform_foundation/providers/observations.py`
- Create: `src/market_platform_foundation/providers/raw_records.py`
- Modify: `src/market_platform_foundation/providers/__init__.py`

**Interfaces:**
- `ObservationClocks(event_time_ns, source_publish_time_ns, effective_time_ns, available_time_ns, received_time_ns, ingested_time_ns, normalized_time_ns, published_time_ns, validity_start_ns, validity_end_ns)`
- `RawRecord(raw_record_id, request_identity, provider_id, source_instance_id, received_time_ns, payload_hash, payload, schema_version, ingestion_version, license_class, storage_ref, redacted_request)`
- `Observation(observation_id, instrument, capability_id, provider_id, source_instance_id, clocks, value, raw_record_id, quality, confidence, revision_id, adjustment_state, license_class, normalizer_version)`
- `RawRecordStore.put(record)`, `.get(raw_record_id)`, `.reprocess(raw_record_id, normalizer_version, normalizer)`, `.manifest()`
- `build_observation_envelope(observation)` returns the existing canonical envelope shape with additive optional lineage/provenance fields.

- [x] **Step 1: Write failing tests**

Cover canonical request hashing, payload deduplication, secret-free request metadata, raw immutability, PIT visibility, revision lineage, and explicit timestamp preservation.

- [x] **Step 2: Run focused raw/observation tests**

Expected: FAIL because raw-record and observation contracts do not exist.

- [x] **Step 3: Implement bounded immutable storage**

Use `canonical_bytes()` and `sha256_bytes()` from `canonical.py`. Store defensive copies, reject conflicting writes for the same raw ID, enforce a configured record/byte bound, and retain prior normalized versions.

- [x] **Step 4: Implement envelope conversion**

Reuse `validate_envelope()` and existing `build_provider_metadata()`. Never populate historical/live-inapplicable fields incorrectly. Preserve `available_time` as the PIT knowledge clock.

- [x] **Step 5: Run focused tests**

Expected: PASS, including reprocessing producing a new observation lineage while leaving the raw record unchanged.

### Task 4: Add deterministic query planning and policy

**Files:**
- Modify: `tests/providers/test_multi_source_foundation.py`
- Create: `src/market_platform_foundation/providers/planner.py`
- Modify: `src/market_platform_foundation/providers/__init__.py`

**Interfaces:**
- `QueryRequest(capability_id, instrument, as_of_time_ns, freshness_max_age_ns, license_purpose, mode, fanout, max_candidates)`
- `ProviderPolicy(enabled, priority, allowed_license_classes, max_retries, base_backoff_ns, cache_ttl_ns, serve_stale, rate_budget, circuit_failure_limit)`
- `QueryPlan(selected_provider_ids, fallback_provider_ids, fanout, cache_key, diagnostics)`
- `QueryPlanner(registry, policies, clock_ns)`. `.plan(request)` and `.record_result(provider_id, success)`.

- [x] **Step 1: Write failing tests**

Cover priority selection, disabled/unhealthy providers, capability/PIT/license filtering, explicit fan-out, deterministic cache keys, circuit opening, bounded retry metadata, and stale-cache policy.

- [x] **Step 2: Run focused planner tests**

Expected: FAIL because planner symbols do not exist.

- [x] **Step 3: Implement deterministic planner**

Use registry descriptors and policy objects only. No network calls are made by planning. Provider-specific conditions stay in descriptors/policies, not planner branches.

- [x] **Step 4: Add bounded cache/rate/circuit state**

Reuse canonical hashing and align cache semantics with `DatasetCache`, `ProjectionDiskCache`, and `AccountSnapshotCache`; do not alter those existing implementations in this increment.

- [x] **Step 5: Run focused tests**

Expected: PASS with explicit diagnostics for fallback, disabled, unhealthy, license-rejected, and no-provider cases.

### Task 5: Add reconciliation and quality scoring

**Files:**
- Modify: `tests/providers/test_multi_source_foundation.py`
- Create: `src/market_platform_foundation/providers/reconciliation.py`
- Modify: `src/market_platform_foundation/providers/__init__.py`

**Interfaces:**
- `QualityScore(completeness, freshness, timestamp_validity, entitlement, consistency, source_reliability)`
- `CandidateObservation(observation, quality_score)`
- `ReconciliationResult(selected, candidates, conflicts, selection_reason, quality_summary)`
- `reconcile_candidates(candidates, value_type, policy)` retains all candidates and returns deterministic selection/conflict data.

- [x] **Step 1: Write failing tests**

Cover numeric tolerance, exact string conflicts, timestamp-invalid candidates, stale candidates, equal-score provider-ID tie breaks, and all-candidates-conflict behavior.

- [x] **Step 2: Run focused reconciliation tests**

Expected: FAIL because reconciliation symbols do not exist.

- [x] **Step 3: Implement datatype-sensitive scoring**

Numeric values use a declared tolerance; strings/enums require exact agreement. Quality scores are bounded and explainable. No candidate disappears from the result.

- [x] **Step 4: Run focused tests**

Expected: PASS with stable selected values and conflict codes.

### Task 6: Integrate exports, validation coverage, and documentation

**Files:**
- Modify: `src/market_platform_foundation/providers/__init__.py`
- Existing `providers` manifest suite already covers `src/market_platform_foundation/providers/**` and `tests/providers/test_*.py`; no manifest edit is required.
- Create: `docs/providers/MULTI_SOURCE_DATA_FOUNDATION.md`
- Create: `docs/architecture/adr/0009-multi-source-data-integration-foundation.md`
- Modify: `docs/README.md`

- [x] **Step 1: Add exports and confirm existing manifest source globs**

Keep the existing `providers` test suite; do not add a competing validation domain.

- [x] **Step 2: Document provider onboarding**

Document registry descriptors, identity mapping, raw capture, PIT clocks, normalization/reprocessing, license/rate/cache policy, reconciliation, observability, execution-plane separation, and future OpenBB/MCP boundary.

- [x] **Step 3: Add ADR-0009**

Record that provider registry, composition, raw lineage, and execution authority remain separate. Explicitly defer paid consolidated feeds, workers, DuckDB, MongoDB, OpenBB/MCP, and production execution.

- [x] **Step 4: Add an additive documentation index link**

Preserve all current rows and uncommitted documentation changes.

### Task 7: Verify, update the plan, and record work

**Files:**
- Modify: `docs/superpowers/plans/2026-09-01-multi-source-data-foundation.md`
- Modify: `docs/engineering/WORK_LOG.md`

- [x] **Step 1: Run focused provider tests after each TDD cycle**

- [x] **Step 2: Run linter diagnostics on all edited Python files**

- [x] **Step 3: Run repository validation**

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.providers.test_multi_source_foundation -v
.venv\Scripts\python.exe tools\validate.py fast
.venv\Scripts\python.exe tools\validate.py changed
.venv\Scripts\python.exe tools\validate.py full
.venv\Scripts\python.exe tools\check_docs_links.py
cd ui
npm test
npm run typecheck
npm run build
```

The full repository and UI commands are executed only after the focused implementation is green. Any failure is investigated and recorded as pre-existing or introduced based on evidence.

- [x] **Step 4: Review the final diff**

Check for accidental edits, secrets, network access, execution-path changes, unbounded storage, unfinished placeholders, and overlap with the user’s existing work.

- [x] **Step 5: Update this plan and work log with exact results**

No commit is created.

### Verification record

- Remediation used red-green focused cycles for envelope lineage, mapping
  conflicts, deep immutability, idempotent normalization, planner controls,
  storage identity deduplication, and reconciliation policy/scoring.
- Provider-specific observation extensions now survive envelope and
  normalization serialization; raw identity hashes include provider and
  source-instance scope.
- Focused foundation suite: `25/25` passed.
- Complete `tests/providers`: `125/125` passed.
- Python compile check for all edited modules/tests: passed.
- Complete IBKR suite: `47/47` passed; news: `5/5`; provider-readiness: `6/6`.
- Linter diagnostics: no errors on edited foundation files.
- `tools/validate.py changed`: failed in dirty-tree finviz/platform/ui1/validation suites (`940 tests, 9 skipped, 1 failure, 7 errors`).
- `tools/validate.py domain core`: failed in dirty-tree finviz/platform/intelligence/validation suites (`1392 tests, 9 skipped, 1 failure, 89 errors`).
- `tools/validate.py full`: failed in dirty-tree finviz/platform/intelligence/ui1/ui2/validation suites (`2133 tests, 9 skipped, 1 failure, 91 errors`).
- The broader validation failures remain unrelated dirty-tree baseline issues;
  no failing suite was altered or suppressed. UI and docs validation were
  previously recorded as passing and were not changed by this remediation.
- Completion remains conditional until the repository's changed/full
  validation baseline is repaired outside this foundation scope.

## Deferred integrations

- IBKR TWS and Client Portal remain observational tool adapters until migrated through the registry.
- NewsAPI/Finnhub remain read-only source clients until integrated through the registry and canonical API provenance.
- Moomoo remains the current live market-data runtime; this plan does not generalize or alter its execution eligibility.
- Tradier and Moomoo paper adapters remain fixture-first and mutually exclusive.
- The nested `pipelines/stock_data/` project remains mutable acquisition staging.
- DuckDB analytical storage, object storage, MongoDB, worker processes, OpenBB, MCP, paid feeds, hosted identity, and production execution remain deferred.
