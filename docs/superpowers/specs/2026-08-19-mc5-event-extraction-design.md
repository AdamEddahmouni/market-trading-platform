# MC5 — Event Extraction (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** MC5 typed event extraction and deterministic numeric metrics on admitted BOXL raw-document fixtures  
**Prerequisites:** MC2–MC4 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Bridge fixture documents into versioned company/macro event ontologies, economic channels, and `ExtractedMetric` rows with governed provenance. Extraction is typed fact assembly — not economic surprise, catalyst strength, or trade direction.

## 2. Models

| Model | Runtime | Producer |
|---|---|---|
| Rule ontology + regex (`rule-v1`) | Stdlib in IMP | `market_context/extraction.py` |
| Schema-bound LLM labels | Fixture-only (precomputed offline) | `fixture-llm-v1` |
| Structured numeric facts | Fixture rows | `boxl_structured_metrics_slice.json` |

Live LLM extraction remains outside IMP CI. IMP has no transformers/torch dependency.

## 3. Ontology mapping (`rule-v1`)

| `canonical_event_type` | `CompanyEventType` | `MacroEventType` | Primary `EconomicChannel` |
|---|---|---|---|
| `earnings_beat` | `EARNINGS` | — | `REVENUE_UP` |
| `fda_clearance` | `FDA_APPROVAL` | — | `REGULATORY_RISK_DOWN` |
| `analyst_upgrade` | `ANALYST_UPGRADE` | — | `MARGIN_UP` |
| `offering_risk` | `EQUITY_ISSUANCE` | — | `DILUTION_UP`, `LIQUIDITY_RISK_UP` |
| `macro_headwind` | — | — | `UNCERTAINTY_UP` |

## 4. Deterministic numeric extraction (`rule-v1`)

Stdlib regex on normalized `title + body`:

- Price target: `price target (?:raised to|to) $X`
- Revenue: `revenue ... $X million|billion`
- Margin: `margin ... X%`

Fixture structured metrics supplement rows where free text lacks parseable numbers.

## 5. LLM fixture extractions

Fixture: `tests/fixtures/market_context/boxl_llm_extraction_slice.json`

| Field | Required |
|---|---|
| `document_id` | Yes |
| `company_event_type` | `CompanyEventType` value or null |
| `economic_channels` | List of `EconomicChannel` values |
| `confidence` | 0–1 |
| `model_id` | e.g. `fixture-llm-v1` |
| `prompt_version` | e.g. `mc5_extraction_prompt_v1` |
| `schema_version` | e.g. `mc5_extraction_schema_v1` |
| `source_span` | `EvidenceSpan` with excerpt |

Labels are generated offline and committed as golden replay truth with `ModelVersionRef`.

## 6. PIT rules

- Extract document only when `available_time <= prediction_cutoff`
- Excluded documents produce no extraction row (not neutral defaults)
- Missing title and body → no rule metrics; `NUMERIC_EXTRACTION_UNCERTAIN` when metrics expected but absent
- Entity ambiguous → `EXTRACTION_ENTITY_AMBIGUOUS` quality flag

## 7. Event aggregation

For each MC3 `InformationEvent` cluster:

- Union economic channels across PIT-visible member documents
- Merge metrics by `metric_name`; prefer official + first-party source rows
- Conflicting values for same metric → `EXTRACTION_METRIC_CONFLICT`
- Populate `InformationEvent.economic_channels` and `InformationEvent.extracted_metrics`

## 8. Cross-lane boundary

- **Display/research metadata only** — no SHARED P4 EV fusion, no squeeze state mutation (MC-D01)
- Extraction signals are not trade direction

## 9. Fixture outcome

`boxl_raw_documents_slice.json` (8 documents) → per-document extractions; 5 enriched event clusters with channels and metrics.

## 10. Out of scope

- Live LLM runtime in IMP
- MC6 expectations/surprise
- MC8 catalyst provider refactor
- Trade-signal mapping

## 11. Completion definition

MC5 complete when fixture pipeline produces deterministic typed extractions per document and enriched `InformationEvent` clusters, PIT adversarial tests pass, workspace projection includes extraction summaries for BOXL, MC-D04/MC-D16 partial (IMP fixture path), and full test suite remains green.

## Appendix A — Offline LLM extraction label generation

```text
1. Load boxl_raw_documents_slice.json document titles/bodies
2. Schema-bound prompt produces company_event_type + economic_channels + EvidenceSpan
3. Commit rows to boxl_llm_extraction_slice.json with model_id, prompt_version, schema_version
```

Not executed in IMP CI.
