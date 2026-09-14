# Research Export v1

Immutable, PIT-safe research packages for offline validation, Wave 1 experiments,
and downstream MATLAB/Python consumers. This layer **projects** admitted fixture
data; it does not authorize Live ingestion or duplicate provider stores.

MATLAB is a **consumer** of this package. Do not invent a second export, and do
not revive the overnight Parquet MATLAB bridge
(`artifacts/overnight/2026-09-12/MATLAB_INTEGRATION_PLAN.md`,
`DEFER-MATLAB-BRIDGE`) as the v1 path.

## Authority

- Manifest spine: `market_platform_foundation.research.export_v1`
- PIT-A-001 binding: `market_platform_foundation.research.pit_export`
- Dataset fingerprints: `market_platform_foundation.research.dataset_manifest`
- Validation wrap: `ValidationDatasetManifestV1` via
  `intelligence.validation.dataset_manifest` (not a second backtester)
- MATLAB toolbox honesty (QR-01): `research/matlab/environment/` plus
  `market_platform_foundation.research.matlab_environment`

Canonical product contract: Notion **IMP Research Export v1** (research-data
interface; export consumes canonical identities, does not replace persistence).

## Profiles in V1

| Profile | Code | Fixture source |
| --- | --- | --- |
| A — Market / technical | `MARKET_TECHNICAL` | `tests/fixtures/providers/distribution/nvda_bars_slice.json` |
| C — Event / macro | `EVENT_MACRO` | `tests/fixtures/providers/futures/es_macro_events_slice.json` |

Both profiles emit separated `feature_snapshots` and `realized_outcomes` tables,
audit exclusions for unreleased macro events and terminal bars, deterministic
`export_id` / `manifest_hash`, `producing_code_sha256`, embedded
`validation_dataset_manifest` when PIT audit passes, and operator metadata
`metadata.pit_status=PIT-PENDING` with `evidence_class=NON_EMPIRICAL_FIXTURE`.
Fixture `pit_audit.status=PASS` does **not** set `PIT-PASS`; Wave 1 OOS stays
blocked until an operator-classified **empirical IMP** export marks
`metadata.pit_status=PIT-PASS` without `NON_EMPIRICAL_FIXTURE` or
`EXTERNAL_RESEARCH_DATA`.

## Evidence classes

| `metadata.evidence_class` | Meaning | Wave 1 OOS |
| --- | --- | --- |
| `NON_EMPIRICAL_FIXTURE` | IMP fixture profiles A/C | Blocked |
| `EXTERNAL_RESEARCH_DATA` | MATLAB-only / non-IMP research file | Blocked; cannot mix with canonical IMP rows |
| Operator empirical class (not fixture) | IMP export classified `PIT-PASS` | Allowed only when `pit_status=PIT-PASS` and mix-clean |

`verify_research_export_v1_package` requires operator `pit_status` in
`{PIT-PENDING, PIT-PASS}` and fail-closes `MIXED_EXTERNAL_RESEARCH_DATA`.
Loaders never upgrade `PIT-PENDING` to `PIT-PASS`.

## Build (offline)

From `projects/integrated-market-platform/`:

```bash
export PYTHONPATH=src
python3 tools/research/build_research_export_v1.py \
  --profile MARKET_TECHNICAL \
  --output-dir /tmp/research-export-a
python3 tools/research/build_research_export_v1.py \
  --profile EVENT_MACRO \
  --output-dir /tmp/research-export-c
```

Operator builds may bind git HEAD (does not change PIT class):

```bash
python3 tools/research/build_research_export_v1.py \
  --profile MARKET_TECHNICAL \
  --stamp-git-head \
  --output-dir /tmp/research-export-a
```

## Load and verify (Python)

```python
from pathlib import Path
from market_platform_foundation.research.export_v1 import load_research_export_v1_package

package = load_research_export_v1_package(Path("/tmp/research-export-a"))
assert package.manifest["pit_audit"]["status"] == "PASS"
assert package.manifest["metadata"]["pit_status"] == "PIT-PENDING"
```

## MATLAB parity and handoff

Each written package includes:

- Per-table `*.json` files (MATLAB `jsondecode`)
- `validation_dataset_manifest.json` — copy of embedded `ValidationDatasetManifestV1`
- `matlab_handoff_manifest.json` — entry contract (`research_export_v1_matlab_handoff/1.0.0`)
  listing table files, operator metadata, and validation manifest
- `matlab_parity_reference.json` — reference statistics (`bar_close_sum`, row counts)

MATLAB loaders should start from `matlab_handoff_manifest.json`, load tables via
`jsondecode`, preserve nanosecond integers, and recompute parity statistics to
match `matlab_parity_reference.json`. The Python loader refuses handoff files
without operator `PIT-PENDING`/`PIT-PASS` metadata and refuses mixed
`EXTERNAL_RESEARCH_DATA`. No in-repo `.m` is required; cloud MATLAB is
`UNAVAILABLE` (see `research/matlab/`).

Python: `load_matlab_handoff_manifest`, `load_research_export_v1_package`,
`matlab_parity_check`.

## Validation gates

Exports fail closed when duplicate keys, impossible times, outcome/feature leakage,
validation dataset PIT violations, missing operator PIT metadata, or mixed
`EXTERNAL_RESEARCH_DATA` are detected. Failed audits may still be written for
diagnosis but cannot pass `verify_research_export_v1_package` when tampered.

Wave 1 `require_pit_pass_for_oos` / `oos_evaluation_authorized` stay fail-closed
on this fixture export. Do not run Wave 1 `--allow-oos` as empirical work.

## Tests

`tests/research/test_research_export_v1.py` — determinism, both profiles, loader
round-trip, frozen regeneration, tamper detection, PIT-PENDING honesty,
`EXTERNAL_RESEARCH_DATA` mix rule.
`tests/research/test_matlab_environment.py` — QR-01 UNAVAILABLE example.
`tests/research/test_wave1_experiment_harness.py` — OOS remains blocked.
