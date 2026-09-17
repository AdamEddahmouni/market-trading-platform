# IMP-DUAL-CORPUS-01 Lane A — Recon Matrix & Lane Ownership

**Increment:** Lane A (`data/dual-corpus-contract`)  
**Base:** `origin/main` @ `cb6cbb7d2b156b97eb45eb36f4c97bf24cff175b` (docs #241)

## Canonical state vs expected (2026-09-17)

| Check | Expected | Observed | Affects Lane A? |
| --- | --- | --- | --- |
| `origin/main` | `cb6cbb7…` | `cb6cbb7…` | No |
| Code tip before docs-only merge | `03cd728…` | Ancestor of `cb6cbb7` | No |
| Frozen Sep 15 empirical | `7aade60…` | On `main` ancestry | No — do not touch |
| Frozen Sep 17 Item 9 collector | `fed2d9f7…` | On `main` ancestry | No — do not touch |
| Coordinator worktree HEAD | — | `c44231fa` on `item7/natural-settlement` (dirty) | No — isolated worktree used |
| Open PR #222 Item 7 | OPEN | OPEN | No — not merged/touched |
| Item 9 calibration | NOT_CALIBRATED / INSUFFICIENT | `item9_calibration_protocol.py` on `main`; dual-corpus admission/discovery wiring lands in Lane A PR #242 | Yes — Lane A wires `dual_corpus` into protocol scan/classify |
| FTEP | not EMPIRICAL_ACTIVE | Unchanged | No |

## Recon matrix

| CAPABILITY | CURRENT IMPLEMENTATION | AUTHORITY / TRUTH CLASS | REUSE / EXTEND / REPLACE_BOUNDED | GAPS | TARGET FILES | OWNER |
| --- | --- | --- | --- | --- | --- | --- |
| Corpus evidence taxonomy | Receipt-level classes in `bar_ohlcv_*`; research `authority_class` | `CURRENT_CANONICAL_ARCHITECTURE` + FTEP doctrine | **EXTEND** with `dual_corpus/evidence_authority.py` | No corpus-level `HISTORICAL_DEVELOPMENT` before Lane A | `paper/calibration/dual_corpus/` | Lane A |
| Item 9 receipt discovery | `governed_receipt_paths` in unmerged `item9_calibration_protocol` worktree; on `main` only direct `DEFAULT_RECEIPT_DIR` | Item 9 engineering docs | **EXTEND** `dual_corpus/discovery.py`; wire `persist_receipt` | No historical-root refusal on `main` | `bar_ohlcv_prospective_proof.py` | Lane A |
| Item 9 admission | Classify receipts in worktree protocol only | Item 9 PARTIAL / NOT_CALIBRATED | **EXTEND** `dual_corpus/admission.py` | Machine refusal for historical class | `dual_corpus/admission.py` | Lane A |
| Historical dataset manifest | Research `build_dataset_manifest` (ADR-RDATA) | Research export | **EXTEND** new historical manifest kind | Not tied to HISTORICAL_DEVELOPMENT authority | `dual_corpus/historical_manifest.py` | Lane A |
| Historical provenance | Bar provenance in `bar_ohlcv_sources` | Market evidence layer doctrine | **EXTEND** explicit retrieval record | Full CLI retrieval is Lane B | `dual_corpus/historical_provenance.py` | Lane A |
| Normalization | `normalize_moomoo_kline_row` | Item 9 bar sources | **REUSE** via `dual_corpus/normalization.py` | Determinism test only (Lane B builder) | `dual_corpus/normalization.py` | Lane A |
| Untouched forward protection | Item 9 split in unmerged protocol | BUILD 15 Path A policy | **EXTEND** `dual_corpus/consumption.py` + training_build guard | Does not rewrite 60/20/20 | `training_build.py` | Lane A |
| Moomoo historical CLI | Capability registry / OpenD kline loaders | Provider docs | **READ-ONLY** hooks | Lane B implements CLI | `tools/moomoo/*` (Lane B) | Lane B |
| Post-horizon labels | Path A outcome policy | BUILD 15 | **READ-ONLY** class definition | Lane C artifacts | `intelligence/outcomes/*` (Lane C) | Lane C |
| Frozen empirical artifacts | `artifacts/ftep-v1-002/item9-prospective-proof-receipts` | `HISTORICAL_TRUTH` | **FORBIDDEN** mutate | — | — | Program |

## Lane ownership map (A / B / C)

| LANE | OWNED DIRECTORIES / FILES | READ-ONLY DEPENDENCIES | FORBIDDEN OVERLAP | EXPECTED OUTPUT |
| --- | --- | --- | --- | --- |
| **A** `data/dual-corpus-contract` | `paper/calibration/dual_corpus/**`, `docs/architecture/DUAL_CORPUS_EVIDENCE_CONTRACT.md`, `docs/engineering/IMP_DUAL_CORPUS_01_LANE_A_RECON.md`, `manifests/paper/schemas/historical_development_dataset_manifest.schema.json`, `tests/platform/test_dual_corpus_contamination.py`, minimal hooks in `bar_ohlcv_prospective_proof.py` + `training_build.py` | `bar_ohlcv_sources`, FTEP doctrine, Item 9 docs | Lane B CLI implementation; Lane C label artifacts; frozen receipts; Item 9 calibration fitting | Authority taxonomy, manifests, contamination tests, docs |
| **B** `data/historical-rth-development` | `tools/moomoo/*` historical pull CLI, artifact dirs under `artifacts/historical-rth-development/` | Lane A manifest + provenance builders | Item 9 receipt dirs; prospective proof | Populated historical corpus + builder |
| **C** `intelligence/post-horizon-label-evidence` | Label evidence artifacts, POST_HORIZON emitters | Lane A class + validation helpers | Item 9 prospective admission; Path A 60/20/20 rewrite | Label evidence packages |

## Architecture decision summary

- **Reuse** `normalize_moomoo_kline_row`, canonical JSON hashing, and existing Item 9 receipt contract.
- **New bounded module** under `paper/calibration/dual_corpus/` rather than a second ProviderRegistry or parallel evidence ledger.
- **Do not merge** unmerged `item9_calibration_protocol.py` in this PR; dual-corpus gates are forward-compatible.
