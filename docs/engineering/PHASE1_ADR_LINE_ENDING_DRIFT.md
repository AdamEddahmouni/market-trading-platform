# Phase 1 ADR acceptance-index hash drift (known, documented)

**Status:** Known and accepted — documented per governed fail-closed posture.
**Date:** 2026-08-22
**Affected check:** `tests/phase1/test_adr_verifier.py::test_decision_audits_verify_bundle`

## Symptom

`verify_bundle()` in `tools/phase1/run_decision_audits.py` hashes the current
working-tree bytes of every ADR decision file under
`docs/superpowers/decisions/` and compares them against the `sha256` values
recorded in `evidence/phase1/decision-bundle/adr-acceptance-index.json`. The
comparison reports 26 `hash mismatch phase1.adr_*` errors on every LF checkout,
so the FULL offline suite reports one failure in the `phase1` suite (6 tests).

## Root cause (proven)

The acceptance index was built at commit `38f199b` from **CRLF working-tree
bytes**. The repository blobs for all 26 ADR files are **LF-only and have never
changed** between `38f199b` and `HEAD`.

Proof for `2026-08-15-adr-data-001-admitted-fixture-identity.json`:

| Bytes | SHA-256 |
|---|---|
| Index-recorded hash | `38834E2B91EC0BEE6E4D7669B113C2A7CB66752A3CFE2D5958B33E9357A14943` |
| Blob at `38f199b` (LF) | `DD8E1889960DD357D3E153019A115BAF63E72AE1458647743B2AE3C287D92B68` |
| Blob at `HEAD` (LF) | `DD8E1889960DD357D3E153019A115BAF63E72AE1458647743B2AE3C287D92B68` |
| CRLF conversion of blob | `38834E2B91EC0BEE6E4D7669B113C2A7CB66752A3CFE2D5958B33E9357A14943` (= index) |

The CRLF-converted blob **equals the recorded index hash exactly**. The drift is
a pure line-ending artifact of hashing raw working-tree bytes on a Windows
checkout; it is not content drift. The repository `.gitattributes` (`* text=auto
eol=lf`) renormalizes the working tree, so git reports the ADR files as
unmodified even though their raw bytes differ from the bytes that were hashed at
bundle publication time.

## Impact

- Phase 1 final acceptance evidence is unaffected:
  `evidence/phase1/postreview/phase1.final_acceptance_result.json` reports
  `outcome: PASS`, `review_coverage_status: QUALIFIED`.
- The live ADR verifier (`manifests/phase1/adr-registry.json`) is consistent
  with current LF bytes and passes (`test_verifier_passes`, 26 accepted, 0
  blocking).
- Only the historical decision-bundle byte-comparison test fails, because it
  compares against CRLF-era recorded hashes.
- `tests/phase1/.out/*` are generated artifacts; they are kept at their
  committed (accepted) record and any test-run regeneration is reverted on
  landing so the tree does not silently carry drifted hashes.

## Decision

Do **not** regenerate the decision bundle, the acceptance index, or the
candidate evidence root. Regeneration would re-litigate an accepted Phase 1
milestone, change the hardcoded constants in `run_decision_audits.py`
(`CANDIDATE_ROOT`, `INDEX_SHA256`), and alter governed evidence — none of which
is authorized. Phase 1 is a closed, PASSED milestone.

If the drift must be eliminated, the only governed path is: normalize the ADR
source files under explicit mutation authority, re-publish the Phase 1 decision
bundle with the new hashes, and update the verifier constants — deferred and not
authorized by this document.

## Reproduction

```text
PYTHONPATH=src;.
python -m unittest tests.phase1.test_adr_verifier -v
```

Expected: 5 pass, 1 fail (`test_decision_audits_verify_bundle`, 26 hash
mismatches as described above).
