# Phase 0 Formal AI Review Run Prompts

**Procedure:** AI-REVIEW-PROCESS-001 (`phase0.ai_review_procedure`)  
**Candidate evidence root:** `78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482`  
**Assertion run_id:** `DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66`  
**Workspace commit (read-only inspection baseline):** `67c78d6`

These prompts are **operator instructions only**. They do not claim that any review run, coverage result, acceptance index, or Phase 0 PASS exists.

## How to use

| Step | Action |
|------|--------|
| 1 | Open a **new** Cursor chat (fresh isolated context). Paste **only** the adversarial prompt file contents. |
| 2 | Open a **second new** Cursor chat. Paste **only** the integrity prompt file contents. |
| 3 | Let each run to completion. Save `review_run_id` from each `phase0.ai_review_run.json`. |
| 4 | Bring both qualifying run records to the principal for coverage qualification (`phase0.ai_review_coverage`). |

## Prompt files

| Review class | File |
|--------------|------|
| `ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT` | [2026-08-14-ai-review-run-prompt-adversarial-requirements-and-conformance-audit.md](./2026-08-14-ai-review-run-prompt-adversarial-requirements-and-conformance-audit.md) |
| `INTEGRITY_AND_REPRODUCTION_AUDIT` | [2026-08-14-ai-review-run-prompt-integrity-and-reproduction-audit.md](./2026-08-14-ai-review-run-prompt-integrity-and-reproduction-audit.md) |

## Isolation rules

- Use **separate** chats with **distinct** `review_run_id` values.
- Do not fork, inherit, or inject the project-authoring conversation or the peer review context.
- Write deliverables only to an isolated directory outside the candidate bundle (for example `evidence/phase0/review-runs/<NEW-ID>/`).
- Do not modify governed subject bytes, the candidate bundle, postroot suite, or manifests during a review run.

## Completed qualifying review runs

| Class | review_run_id | recommended_candidate_outcome | Output directory |
|-------|---------------|-------------------------------|------------------|
| `ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT` | `3B46DCFBBE324D97DE8D496EABD2C1B1DB648FF8AE8787FB04C7A492F1900651` | PASS | `evidence/phase0/review-runs/ADVERSARIAL-D269CB76475B4414/` |
| `INTEGRITY_AND_REPRODUCTION_AUDIT` | `5DE42893FB2248CB57172AFDF315D50506289F1E9EDA789C942D4EFD0FA4D4EF` | PASS | `evidence/phase0/review-runs/INTEGRITY-9983643AA5A6409E/` |

## Superseded review runs (do not use for coverage)

| Class | review_run_id | Outcome | Directory | Supersession reason |
|-------|---------------|---------|-----------|---------------------|
| `ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT` | `EABC35FB0D1B5B2EAAFCCF44B391F2394D986AA2F939797C698388D705557C99` | BLOCKED | `evidence/phase0/review-runs/ADVERSARIAL-BD319D5B7F1D46D3/` | Material GOV-002 effectivity findings before approval records |
| `ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT` | (see run manifest) | FAIL | `evidence/phase0/review-runs/ADVERSARIAL-BCB6EAEA64104F2E/` | Early adversarial attempt |
| `INTEGRITY_AND_REPRODUCTION_AUDIT` | (see run manifest) | FAIL | `evidence/phase0/review-runs/INTEGRITY-BE7AFCA2E104436E/` | Runner bugs fixed in final integrity run |
| `INTEGRITY_AND_REPRODUCTION_AUDIT` | (see run manifest) | FAIL | `evidence/phase0/review-runs/INTEGRITY-A15905E1D29241E4/` | Runner bugs fixed in final integrity run |

## Postreview gate artifacts

Built by `tools/postroot/build_postroot_gate.py` under `evidence/phase0/postreview/`:

| Logical ID | SHA-256 | Status |
|------------|---------|--------|
| `phase0.approval_records` | `C8737648CDE7E13480643E94BEE5FFFAA42C04F093136D2D910AC76B5D9CF278` | aggregate PASS |
| `phase0.ai_review_coverage` | `423B9F92008AF930FCCE3DFD2782A74EEB6E324C7C055C428B1AC319CC133A3B` | QUALIFIED |
| `phase0.ai_review_runs` | `9DA52BCD39E2CC9DDDAB8AF11769314C250842E7527DD467E84E581A76852D2D` | manifest |
| `phase0.acceptance_index` | `33032B063BAA167981D10E28C6B69BF372B8A43703C0C28B63FD852721F36814` | index_sha256 `A03044C69F977A34BF19FAB405194CE36A47F8EA032A539A4DED76B522F879DB` |
| `phase0.final_acceptance_result` | `ADF26F898F44E41EAA006EE9AF9AD6547AFB45CA3083ED2DAAE81DFA19A0E548` | outcome PASS |

Formal Phase 0 PASS was published in [2026-08-15-phase-0-pass-publication.json](./2026-08-15-phase-0-pass-publication.json) (SHA-256 `8992B4ACA21F2BD1F7CFF743DA2D084755100800E08F5234B0AB0B081324F0A7`).
