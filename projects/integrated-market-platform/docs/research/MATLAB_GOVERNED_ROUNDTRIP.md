# MATLAB governed research round-trip (Phase 4 Lane G)

MATLAB is a **research consumer** only. It may analyze fixture or governed exports;
it may not set `MODE_AUTHORITY`, submit Paper/Live orders, or mint opportunity rank.

## Flow

1. Build or load **Research Export v1** (`research_export_manifest.json` + tables).
2. MATLAB (or Python reference) emits **`matlab_research_result_v1.json`** bound to
   `export_id`, `manifest_hash`, and `source_sha256`.
3. IMP validates lineage and projects **`MATLAB_RESEARCH_EVIDENCE_ARTIFACT`** (evidence
   class `EVIDENCE_NOT_PREDICTION`).

## Readiness tokens

| Token | Meaning |
| --- | --- |
| `CONTRACT_READY` | Golden fixture / Python reference path; lineage verified |
| `MATLAB_RUNTIME_NOT_AVAILABLE` | No MATLAB on host; use fixture contract tests |
| `MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY` | MATLAB smoke + lineage verified on operator host |

Fixture exports remain `PIT-PENDING` / `NON_EMPIRICAL_FIXTURE`. Do not stamp `PIT-PASS`.

## Commands

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe tools\research\matlab_governed_roundtrip.py --work-dir .local\matlab-roundtrip-smoke
```

Python API: `market_platform_foundation.research.export_v1_matlab_roundtrip`.

MATLAB smoke: `research/matlab/smoke/imp_matlab_parity_smoke.m` (base MATLAB only).
