# MATLAB integration readiness blueprint

**Current MATLAB path:** Research Export v1 JSON handoff
([RESEARCH_EXPORT_V1.md](../../../docs/research/RESEARCH_EXPORT_V1.md)).
This overnight Parquet-bridge blueprint is **historical** (`DEFER-MATLAB-BRIDGE`).
Do not implement `export_matlab_bundle.py` as the v1 MATLAB path.

**Lane:** G | **Date:** 2026-09-12  
**Gate:** `DEFER-MATLAB-BRIDGE` (reconciliation-gate)

## Current state

- IMP has **no** MATLAB/Python bridge module.
- `pipelines/stock_data` exports Parquet/CSV consumable by MATLAB, R, DuckDB.
- Short-squeeze sibling project has frozen export API (out of IMP scope).

## Blueprint (when owner approves)

### Phase 1 — Contract

- Define `MATLAB_HANDOFF_MANIFEST.json` schema: dataset identity (ADR-RDATA-001), SHA-256 of Parquet, column dictionary, PIT cutoff timestamp.

### Phase 2 — Export adapter

- CLI: `python tools/research/export_matlab_bundle.py --dataset-id ...` (stdlib + existing research manifests only).

### Phase 3 — Round-trip (optional)

- MATLAB generates signals → CSV → IMP fixture importer (read-only validation).

## Risks

- License/compliance for redistributed data in bundles.
- Duplicating PIT semantics outside `pit_gate` → require harness validation on import.

## Verdict

**SPEC_READY_FOR_LATER** — use Parquet path today; defer in-repo bridge.
