# Dual-Corpus Evidence Contract (IMP-DUAL-CORPUS-01 Lane A)

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`  
**Purpose:** Keep historical development research corpora strictly separate from Item 9 prospective calibration evidence.

## Corpus classes

| Class | Role | Item 9 prospective admission |
| --- | --- | --- |
| `HISTORICAL_DEVELOPMENT` | Offline RTH bar/feature research with full retrieval provenance | **REFUSED** — never composes prospective corpus |
| `PROSPECTIVE_FEATURE_EVIDENCE` | Lawful prospective observations at decision cutoff | Allowed only via existing Item 9 receipt rules (not rewritten here) |
| `POST_HORIZON_HISTORICAL_LABEL_EVIDENCE` | Labels derived after horizon on historical windows (Lane C owns artifacts) | Not Item 9 receipts; schema hook only in Lane A |
| `UNTOUCHED_FORWARD_EVALUATION` | Protected holdout for forward evaluation | Cannot be consumed by selection/training helpers |

Authority is declared on manifests and provenance records. **Directory placement alone never grants authority.**

## Historical Development Corpus

**Purpose:** Versioned, manifest-backed historical bar datasets for software validation and research feature work (Lane B builder extends retrieval).

**Non-purpose:** Item 9 calibration, FTEP empirical activation, or “real data / calibrated” operator language.

Each retrieval record must use `corpus_evidence_authority=HISTORICAL_DEVELOPMENT` and satisfy `dual_corpus.historical-provenance/1.0.0` (see `historical_provenance.py`).

Dataset manifests use `historical_development_dataset_manifest_v1` with fingerprinted bodies (`dual_corpus.historical-dataset-manifest/1.0.0`).

## Prospective corpus (preserved meaning)

Item 9 prospective proof receipts remain under `artifacts/ftep-v1-002/item9-prospective-proof-receipts/` (or explicit `--receipt-out`). Discovery scans **only** non-historical roots via `iter_item9_prospective_receipt_paths`. Item 9 stays `PARTIAL_NOT_CALIBRATED` until lawful prospective evidence earns gates elsewhere — this contract does not weaken the 3-date or observation floors.

## Post-horizon historical labels

Lane A defines the `POST_HORIZON_HISTORICAL_LABEL_EVIDENCE` class and manifest hooks. Full label artifact production is **Lane C**.

## Untouched forward evaluation

`UNTOUCHED_FORWARD_EVALUATION` is protected from Path A training/selection consumption (`assert_corpus_consumable_for_selection_or_training`). Item 9 chronological 60/20/20 split logic is **not** rewritten in this increment.

## Operator language

Use explicit **HISTORICAL_DEVELOPMENT** vs **PROSPECTIVE** labels. Do not describe historical research pulls as “calibrated” or generic “real data” for Item 9.

## Implementation map

- Authority + admission: `src/market_platform_foundation/paper/calibration/dual_corpus/`
- Item 9 receipt persist guard: `bar_ohlcv_prospective_proof.persist_receipt`
- Path A training guard: `intelligence/production/training_build.py`
