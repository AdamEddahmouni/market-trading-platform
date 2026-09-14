# Research Export v1

Immutable, PIT-safe research packages for offline validation, Wave 1 experiments,
and downstream MATLAB/Python consumers. This layer **projects** admitted fixture
data; it does not authorize Live ingestion or duplicate provider stores.

## Authority

- Manifest spine: `market_platform_foundation.research.export_v1`
- PIT-A-001 binding: `market_platform_foundation.research.pit_export`
- Dataset fingerprints: `market_platform_foundation.research.dataset_manifest`
- Validation wrap: `ValidationDatasetManifestV1` via
  `intelligence.validation.dataset_manifest` (not a second backtester)

Canonical product contract: Notion **IMP Research Export v1** (research-data
interface; export consumes canonical identities, does not replace persistence).

## Profiles in V1

| Profile | Code | Fixture source |
| --- | --- | --- |
| A — Market / technical | `MARKET_TECHNICAL` | `tests/fixtures/providers/distribution/nvda_bars_slice.json` |
| C — Event / macro | `EVENT_MACRO` | `tests/fixtures/providers/futures/es_macro_events_slice.json` |

Both profiles emit separated `feature_snapshots` and `realized_outcomes` tables,
audit exclusions for unreleased macro events and terminal bars, deterministic
`export_id` / `manifest_hash`, `producing_code_sha256`, and embedded
`validation_dataset_manifest` when PIT audit passes.

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

## Load and verify (Python)

```python
from pathlib import Path
from market_platform_foundation.research.export_v1 import load_research_export_v1_package

package = load_research_export_v1_package(Path("/tmp/research-export-a"))
assert package.manifest["pit_audit"]["status"] == "PASS"
```

## MATLAB parity

Each written package includes `matlab_parity_reference.json` with declared
reference statistics (`bar_close_sum`, row counts, macro actual sums). MATLAB
loaders should recompute the same aggregates from the table JSON files and match
this sidecar; Python tests enforce parity via `matlab_parity_check`.

## Validation gates

Exports fail closed when duplicate keys, impossible times, outcome/feature leakage,
or validation dataset PIT violations are detected. Failed audits may still be
written for diagnosis but cannot pass `verify_research_export_v1_package` when
tampered.

## Tests

`tests/research/test_research_export_v1.py` — determinism, both profiles, loader
round-trip, frozen regeneration, tamper detection.
