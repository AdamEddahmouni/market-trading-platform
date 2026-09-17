# IMP-DUAL-CORPUS-01 Lane B — Historical RTH Development Corpus

**Branch:** `data/historical-rth-development` (stack on `data/dual-corpus-contract`)  
**Authority:** `HISTORICAL_DEVELOPMENT` only (via Lane A `dual_corpus` APIs)

## CLI

```text
python tools/imp.py historical-data build \
  --provider moomoo-opend \
  --instrument AAPL \
  --start 2026-09-15 \
  --end 2026-09-15 \
  --resolution 1m \
  --session RTH
```

Fixture validation (no OpenD):

```text
python tools/imp.py historical-data build \
  --provider fixture \
  --fixture-path tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json \
  --instrument AAPL \
  --start 2026-09-15 \
  --end 2026-09-15 \
  --resolution 1m \
  --session RTH
```

Governance lines (always printed):

- `AUTHORITY: HISTORICAL_DEVELOPMENT`
- `PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED`
- `CALIBRATION_STATE_CHANGED: NO`
- `FTEP_STATE_CHANGED: NO`

## Artifact layout

```text
artifacts/historical-rth-development/runs/<run_id>/
  raw/<TICKER>_<YYYY-MM-DD>.json
  normalized/<TICKER>_normalized.json
  manifests/dataset_manifest.json
  quality/quality_report.json
```

Paths are excluded from Item 9 prospective discovery (`historical-rth-development` marker).

## Provider status

| Provider | CI | Live OpenD |
| --- | --- | --- |
| `fixture` | Verified via unit tests | N/A |
| `moomoo-opend` | `PROVIDER_UNVERIFIED` when OpenD/SDK absent | Requires loopback OpenD + `moomoo-api`; not claimed in CI |

## Module map

- `src/market_platform_foundation/market_data/historical_development/` — builder, RTH policy, quality
- `tools/moomoo/historical_rth_kline.py` — paginated day fetch
- `tools/historical_data/build_cli.py` — CLI implementation

Item 9 remains `NOT_CALIBRATED`; historical corpora never admit as prospective.

## Methodology gaps (this pass)

- **Early-close sessions:** `--early-closes` excludes a date from the build calendar but does not yet shorten expected RTH minute grids for partial sessions; quality `missing_intervals` and `incomplete_final_bar_count` assume full 390-minute RTH until a dedicated calendar lands.
- **Corporate actions:** provider QFQ only; no cross-source reconciliation.
