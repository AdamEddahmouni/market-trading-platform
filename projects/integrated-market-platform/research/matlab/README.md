# MATLAB research lab (QR-01 honesty recorder)

MATLAB is a **research / challenger / independent-validation lab**. It is not
IMP production runtime, not a FAST/CHANGED dependency, and not a
`MODE_AUTHORITY` subject.

This tree records whether MATLAB exists on the operator host. Cloud and CI
commit only the UNAVAILABLE example. A real `environment/toolbox_manifest.json`
stays local and gitignored.

## Consume Research Export v1 — do not invent a second export

MATLAB loaders start at `matlab_handoff_manifest.json` from a Research Export v1
package. Contract: [RESEARCH_EXPORT_V1.md](../../docs/research/RESEARCH_EXPORT_V1.md).

Governed result import and smoke round-trip:
[MATLAB_GOVERNED_ROUNDTRIP.md](../../docs/research/MATLAB_GOVERNED_ROUNDTRIP.md).
Smoke script: `smoke/imp_matlab_parity_smoke.m`.

The overnight Parquet blueprint
(`artifacts/overnight/2026-09-12/MATLAB_INTEGRATION_PLAN.md`) is **historical**.
Do not implement `export_matlab_bundle.py` as the v1 MATLAB path.

## Honesty rules

- Fixture exports keep `metadata.pit_status=PIT-PENDING` /
  `evidence_class=NON_EMPIRICAL_FIXTURE`. Do not stamp `PIT-PASS`.
- `EXTERNAL_RESEARCH_DATA` cannot mix with canonical IMP rows and cannot enter
  Wave 1, FTEP, Opportunity Engine, or BUILD 20.
- Wave 1 stays `IN_SAMPLE_ONLY` until an operator-classified empirical export is
  `PIT-PASS` without `NON_EMPIRICAL_FIXTURE` or `EXTERNAL_RESEARCH_DATA`.
- Datafeed Toolbox and Database Toolbox are `PROHIBITED_AS_CANONICAL`.
- No Live, hop, OpenD, Alpaca, FTEP session, or Paper submit from this tree.

## Cloud / this checkout

Every PRIMARY toolbox is `UNAVAILABLE`. `smoke_status=BLOCKED_NO_MATLAB`.
That is a valid QR-01 software close. Do not infer INSTALLED from docs.
