# MC16 — Multi-Document LLM Synthesis (fixture-first, experimental)

**Status:** Design complete — implemented (fixture-first)  
**Spec date:** 2026-08-21  
**Scope:** Cluster-level synthesis across multiple PIT-visible documents in an MC3 `InformationEvent` cluster, using fixture-precomputed LLM labels on admitted BOXL fixtures  
**Prerequisites:** MC3 IMPLEMENTED (event clustering), MC5 IMPLEMENTED (per-document extraction), MC14 IMPLEMENTED, MC15 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

MC5 performs **per-document** schema-bound LLM extraction (`fixture-llm-v1` in `boxl_llm_extraction_slice.json`). MC10 deferred live/LLM narrative synthesis. MC16 closes the gap: **cluster-level synthesis** that reconciles multiple documents belonging to the same `InformationEvent` cluster.

MC16 publishes **separate synthesis fields** — thematic agreement, contradiction detection, consolidated economic channels, and a governed thematic summary — without a universal news score. **Experimental** — not validated for trading.

MC5 still owns per-document typed extraction. MC8 still owns catalyst fusion. MC10 still owns narrative prevalence/velocity math. MC16 does not replace either; it adds a governed multi-document view for clusters with ≥ 2 PIT-visible member documents.

Resolves design intent for **MC-D16** (full `ModelVersionRef` on synthesis outputs, not only single-doc extraction rows).

## 2. Scoring model (`multi_document_synthesis_v1`)

### A. Inputs

Per MC3 cluster at PIT cutoff:

| Input | Source |
|---|---|
| `cluster_id` | MC3 `InformationEvent` |
| `member_document_ids` | Cluster membership (PIT-filtered) |
| Per-doc extractions | MC5 `rule-v1` + `fixture-llm-v1` labels |
| Per-doc sentiment | MC4 baseline sentiment (optional) |
| Revision lineage | MC1 document `revision_of_document_id` |

Minimum cluster size for synthesis: **2** PIT-visible documents. Single-document clusters produce no synthesis row (fail-closed, not neutral default).

### B. Synthesis output (`MultiDocumentSynthesisSummary`)

Separate fields — no fused context score:

| Field | Type | Description |
|---|---|---|
| `cluster_id` | str | MC3 cluster identifier |
| `entity_id` | str | Workspace symbol |
| `thematic_summary` | str \| null | Fixture-precomputed cluster narrative (display only) |
| `theme_agreement_score` | float \| null | 0..1 agreement across member extractions |
| `contradiction_detected` | bool | True when conflicting `company_event_type` or channel polarity |
| `consolidated_channels` | list[str] | Union of agreed economic channels (conflicts excluded) |
| `supporting_document_ids` | list[str] | Documents contributing to agreed theme |
| `contradicting_document_ids` | list[str] | Documents with conflicting extraction vs majority |
| `revision_superseded_ids` | list[str] | Earlier revisions superseded at cutoff (MC-D14) |
| `synthesis_confidence` | float \| null | Fixture-precomputed confidence 0..1 |
| `model_version` | ModelVersionRef | Required on every row (MC-D16) |
| `quality_flags` | list[str] | See §2.F |
| `available_time` | ISO-8601 | `max(member.available_time)` among included documents |
| `publication_state` | PublicationState | `AVAILABLE` or `UNAVAILABLE` |

`synthesis_id = uuid5(NAMESPACE, "synthesis|{cluster_id}|{entity_id}|{prediction_cutoff_ns}")`

### C. Theme agreement

For clusters with ≥ 2 PIT-visible MC5 LLM labels:

```
theme_agreement_score = agreeing_doc_count / eligible_doc_count
```

- **Agreeing** — same `company_event_type` and overlapping `economic_channels` with majority type
- **Eligible** — document has MC5 LLM label with `confidence >= 0.70` at cutoff
- When `eligible_doc_count < 2` → `theme_agreement_score = None`, `SYNTHESIS_INSUFFICIENT_DOCS`

### D. Contradiction detection

`contradiction_detected = true` when any of:

- Two+ documents map to incompatible `company_event_type` values (e.g., `EARNINGS` vs `EQUITY_ISSUANCE`)
- Conflicting channel polarity on same channel (e.g., `REVENUE_UP` vs `REVENUE_DOWN`)
- Revision pair where both V1 and V2 are visible but extractions disagree → `SYNTHESIS_REVISION_CONFLICT`

When `contradiction_detected`:

- `consolidated_channels` excludes conflicting channels (majority wins; tie → exclude channel)
- `contradicting_document_ids` populated
- Row still publishes with `publication_state = AVAILABLE` (partial synthesis allowed)
- Never default to neutral theme

### E. Revision handling (MC-D14)

- When `revision_of_document_id` chains exist, include only the **latest revision** visible at cutoff per lineage
- Superseded revisions listed in `revision_superseded_ids`
- If revision conflict cannot be resolved → `contradiction_detected = true`

### F. Quality flags

- `SYNTHESIS_INSUFFICIENT_DOCS` — fewer than 2 eligible documents
- `SYNTHESIS_REVISION_CONFLICT` — revision lineage disagreement
- `SYNTHESIS_EXTRACTION_PARTIAL` — some members lack MC5 LLM labels
- `SYNTHESIS_CONTRADICTION_PRESENT` — conflicting extractions detected
- `MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL` (always on produced rows)
- `NO_UNIVERSAL_NEWS_SCORE` (always on produced rows — UI doctrine)

### G. Model versioning (MC-D16)

Fixture synthesis labels carry:

| Field | Example |
|---|---|
| `model_id` | `fixture-llm-synthesis-v1` |
| `model_version` | `1.0.0` |
| `prompt_version` | `mc16_synthesis_prompt_v1` |
| `schema_version` | `mc16_synthesis_schema_v1` |
| `feature_version` | `market_context_synthesis_v1` |

Runtime never calls live LLM. Labels are generated offline and committed as golden replay truth.

## 3. PIT rules

- Include document only when `available_time <= prediction_cutoff`
- Exclude future cluster members (no synthesis row for that member)
- Cluster `available_time` for synthesis row = `max(included_member.available_time)`
- Exclude clusters where all members are future-dated → no row
- Revision supersession evaluated at cutoff (not event_time)

## 4. Cross-lane boundary

Publish display/research metadata only when thresholds met:

- `SYNTHESIS_THEME_ELEVATED` when `theme_agreement_score >= 0.75` and `contradiction_detected == false`
- `SYNTHESIS_CONTRADICTION_DETECTED` when `contradiction_detected == true`

Does **not** fuse into SHARED P4. Does **not** replace MC8 catalyst rows or MC10 narrative velocity. Downstream MC7/MC8 may **read** `consolidated_channels` as optional enrichment in a future gated integration — not in MC16 v1.

## 5. Fixtures

Built from existing admitted BOXL documents — no new data procurement.

| Fixture | Scope |
|---|---|
| `boxl_raw_documents_slice.json` | MC3 cluster inputs (earnings cluster: `mc-doc-earnings-1`, `mc-doc-earnings-2`, revision `mc-doc-earnings-1-v2`) |
| `boxl_llm_extraction_slice.json` | MC5 per-doc labels (input to synthesis) |
| `boxl_multidoc_synthesis_slice.json` | Fixture-precomputed synthesis labels + adversarial contradiction cluster |
| `boxl_multidoc_synthesis_expected.json` | Golden MC16 regression |

### Adversarial cases in slice fixture

1. **Earnings cluster (agreement)** — 2+ docs, high theme agreement, no contradiction
2. **FDA cluster (agreement)** — wire + pickup, consolidated `REGULATORY_RISK_DOWN`
3. **Contradiction cluster** — incompatible event types in same cluster (synthetic adversarial)
4. **Revision supersession** — V2 supersedes V1; V1 excluded from agreement denominator
5. **Insufficient docs** — single-member cluster → no synthesis row
6. **Future document** — member with `available_time > cutoff` excluded

## 6. Workspace

- `multi_document_synthesis_available`
- `multi_document_synthesis_producer_id`, `multi_document_synthesis_producer_version`
- `multi_document_synthesis_count`
- `multi_document_synthesis_summaries` with separate fields per §2.B
- `multi_document_synthesis_adapter_rows`
- `research_only: true`
- Disclaimer: "MC16 synthesizes separate cluster fields from admitted documents — no universal news score. Fixture-precomputed LLM labels only."

UI explain ref: `explain:synthesis:{symbol}:{cluster_id}`

## 7. Gate tool

`tools/market_context/run_mc16_gate_validation.py` (implement in next session):

- Load `boxl_multidoc_synthesis_expected.json`
- Run `run_mc16_gate_validation()` against `GATE_PREDICTION_CUTOFF` / `GATE_EARLY_CUTOFF`
- Assert PIT exclusion, revision supersession, contradiction flags, and golden field parity
- Write report to `evidence/market_context/mc16-gate-validation-report.json`

## 8. Implementation plan (next session)

| Step | Deliverable |
|---|---|
| 1 | `src/market_platform_foundation/market_context/synthesis.py` |
| 2 | Contract quality flags in `contracts/market_context.py` |
| 3 | Cross-lane signals in `cross_lane/evidence.py` |
| 4 | Workspace projection in `providers/projections.py` |
| 5 | UI explain ref in `ui_api/projections.py` |
| 6 | Fixtures `boxl_multidoc_synthesis_{slice,expected}.json` |
| 7 | `tests/market_context/test_synthesis.py` |
| 8 | Gate tool + admission manifest row |
| 9 | Roadmap update to IMPLEMENTED |

## 9. Out of scope

- Live LLM runtime in IMP CI
- Transformers / torch dependency
- MC8 catalyst fusion refactor
- MC10 narrative velocity replacement
- Universal news / context score in UI
- Trade-signal mapping
- Cross-entity synthesis (MC15 scope)

## 10. Completion definition

MC16 complete when:

- Fixture pipeline produces deterministic synthesis rows per eligible MC3 cluster
- PIT adversarial tests pass (future docs, revision supersession, contradiction)
- Workspace projection includes `multi_document_synthesis_summaries` for BOXL
- Gate tool PASS on golden expected fixture
- MC-D16 resolved for synthesis path (full `ModelVersionRef`)
- `python tools/validate.py domain market_context` and FULL remain green

## Appendix A — Offline synthesis label generation

```text
1. Load boxl_raw_documents_slice.json clusters + boxl_llm_extraction_slice.json labels
2. Schema-bound prompt produces thematic_summary, theme_agreement_score, contradiction flags
3. Commit rows to boxl_multidoc_synthesis_slice.json with model_id, prompt_version, schema_version
```

Not executed in IMP CI.
