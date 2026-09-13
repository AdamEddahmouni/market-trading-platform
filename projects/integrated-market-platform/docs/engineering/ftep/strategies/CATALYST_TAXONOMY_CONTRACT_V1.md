# FTEP Catalyst Taxonomy Contract V1

**Classification:** `PREIMPLEMENTATION_PROFILE`  
**Inherits:** `NEWS_CATALYST_PROFILE_V1`  
**Executable registry:** `src/market_platform_foundation/news/catalysts.py` (`news/catalysts/1.0.0`)

## Purpose

Freeze a deterministic catalyst vocabulary for US-equity news-catalyst campaigns before qualifying evidence. The registry is the authority; this document is the governance contract.

## Binding rules

1. Campaign manifests must reference `catalyst_taxonomy_version: CATALYST_TAXONOMY_CONTRACT_V1`.
2. `enabled_catalyst_ids` must be a subset of registry `catalyst_id` values with `enabled=true`.
3. For FTEP-V1-002, default eligible asset-class filter is `EQUITY` (macro-only catalysts excluded unless owner expands OD-2).
4. Matching uses normalized headline text only; no LLM classification in the baseline lane.
5. Taxonomy changes require a new contract version and manifest amendment before empirical collection.

## Default FTEP-V1-002 eligible catalysts (proposed)

Corporate: `earnings`, `guidance`, `partnership`, `contract`, `acquisition`, `merger`, `offering`, `financing`, `analyst`, `bankruptcy`, `management`  
Regulatory: `fda`, `approval`, `clinical`, `sec_filing`, `investigation`

Excluded unless owner preregisters: macro futures catalysts (`cpi`, `payroll`, `rate_decision`, `opec`, …).

## Schema

Machine-readable subset: `manifests/forward_test/schemas/catalyst_taxonomy_binding.schema.json`.
