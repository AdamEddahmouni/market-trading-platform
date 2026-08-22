# Phase 1 ADR acceptance-index hash drift (resolved)

**Status:** Resolved 2026-08-22 — the acceptance index now records the true LF
bytes of the ADR decision files and the FULL offline suite is green.
**Affected check (historical):** `tests/phase1/test_adr_verifier.py::test_decision_audits_verify_bundle`

## Symptom (historical)

`verify_bundle()` in `tools/phase1/run_decision_audits.py` hashes the current
working-tree bytes of every ADR decision file under
`docs/superpowers/decisions/` and compares them against the `sha256` values
recorded in `evidence/phase1/decision-bundle/adr-acceptance-index.json`. The
comparison reported 26 `hash mismatch phase1.adr_*` errors on every LF checkout,
so the FULL offline suite reported one failure in the `phase1` suite (6 tests).

## Root cause (proven)

The acceptance index was built at commit `38f199b` from **CRLF working-tree
bytes**. The repository blobs for all 26 ADR files are **LF-only and have never
changed** between `38f199b` and `HEAD`.

Proof for `2026-08-15-adr-data-001-admitted-fixture-identity.json`:

| Bytes | SHA-256 |
|---|---|
| Index-recorded hash (pre-fix) | `38834E2B91EC0BEE6E4D7669B113C2A7CB66752A3CFE2D5958B33E9357A14943` |
| Blob at `38f199b` (LF) | `DD8E1889960DD357D3E153019A115BAF63E72AE1458647743B2AE3C287D92B68` |
| Blob at `HEAD` (LF) | `DD8E1889960DD357D3E153019A115BAF63E72AE1458647743B2AE3C287D92B68` |
| CRLF conversion of blob | `38834E2B91EC0BEE6E4D7669B113C2A7CB66752A3CFE2D5958B33E9357A14943` (= old index) |

The CRLF-converted blob **equaled the recorded index hash exactly**. The drift
was a pure line-ending artifact of hashing raw working-tree bytes on a Windows
checkout; it was not content drift. The repository `.gitattributes`
(`* text=auto eol=lf`) renormalizes the working tree, so git reports the ADR
files as unmodified even though their raw bytes differ from the bytes that were
hashed at bundle publication time.

## Resolution (governed path, 2026-08-22)

Executed the governed path from the former "Decision" section under explicit
mutation authority:

1. **Normalized ADR source files** — verified all 26 ADR decision files are
   LF-only in the working tree and in the repository blobs (no source bytes
   changed; nothing to renormalize).
2. **Re-published the Phase 1 decision bundle** with hashes of the true LF
   bytes via `tools/phase1/build_decision_bundle.py` into
   `evidence/phase1/decision-bundle/`:
   - `adr-acceptance-index.json` — every member `sha256` now matches the LF
     file bytes (e.g. ADR-DATA-001 = `DD8E1889960DD357D3E153019A115BAF63E72AE1458647743B2AE3C287D92B68`);
     new `index_sha256` = `CD36F85EACCE16DD5F45CE376F9B3F2D5B0903912CBC3E337D0DF9E863533213`.
   - `adr-verifier-result.json` — per-ADR `decision_sha256` values refreshed to
     the LF bytes; status remains `PASS`, 26 accepted, 0 blocking.
   - `candidate-evidence-root.json` — new candidate root
     `80570499CDE0B4BCD8375B610D345E946B4EEE7DB828950A4CB96FDFBC654A40`
     (content-derived from the corrected index).
3. **Updated the verifier constants** in `tools/phase1/run_decision_audits.py`:
   - `CANDIDATE_ROOT` → `80570499CDE0B4BCD8375B610D345E946B4EEE7DB828950A4CB96FDFBC654A40`
   - `INDEX_SHA256` → `CD36F85EACCE16DD5F45CE376F9B3F2D5B0903912CBC3E337D0DF9E863533213`
   - `PROCEDURE_HASH` unchanged (verified still equal to the current
     `docs/superpowers/governance/2026-08-14-ai-review-process-001.json` bytes).

### Deliberately left frozen (closed-milestone historical evidence)

The following still record the CRLF-era review and are **not** part of the
re-publication; they remain the historical record of the Phase 1 acceptance
review performed on 2026-08-15:

- `evidence/phase1/postreview/*` (acceptance index, coverage, review runs,
  approval records, final acceptance result)
- `evidence/phase1/review-runs/**`
- `docs/superpowers/governance/2026-08-15-phase-1-decision-publication.json`
- `docs/superpowers/governance/2026-08-15-phase-1-postreview-supplement.json`
- `tools/phase1/build_postreview_gate.py` `CANDIDATE_ROOT` constant

`tests/phase1/.out/*` were refreshed to the corrected hashes by the bundle
builder test so the snapshot matches the re-published accepted record (the
"revert on landing" policy applied to accidental regeneration, not to the
authorized re-publication).

## Impact (post-resolution)

- `tests/phase1/test_adr_verifier.py` — 6/6 pass, including
  `test_decision_audits_verify_bundle`.
- `python tools/validate.py changed` — PASSED (27 tests).
- `python tools/validate.py full` — PASSED: 1485 tests / 7 skips / 0 failures /
  0 errors in 403s; machine-readable record in
  [`reports/post-drift-fix-full.json`](../../reports/post-drift-fix-full.json).
- The live ADR verifier (`manifests/phase1/adr-registry.json`) remains
  consistent with the LF bytes and passes (26 accepted, 0 blocking).
- Phase 1 final acceptance evidence is unaffected:
  `evidence/phase1/postreview/phase1.final_acceptance_result.json` reports
  `outcome: PASS`, `review_coverage_status: QUALIFIED`.

## Reproduction

```text
PYTHONPATH=src;.
python -m unittest tests.phase1.test_adr_verifier -v
```

Expected: 6 pass, 0 fail.
