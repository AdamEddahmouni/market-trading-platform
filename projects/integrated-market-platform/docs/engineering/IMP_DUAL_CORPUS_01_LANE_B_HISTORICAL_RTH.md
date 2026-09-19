# IMP-DUAL-CORPUS-01 Lane B — Historical RTH Development Corpus

**Status:** **MERGED** on `origin/main` at `60bf9e73` ([#243](https://github.com/AdamEddahmouni/market-trading-platform/pull/243))
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

## Multi-session expansion (IMP-OFFHOURS-RESEARCH-03 Lane C)

Bounded date ranges may include multiple completed RTH sessions. The builder emits one `raw/<TICKER>_<YYYY-MM-DD>.json` per tradable session day, merges with deterministic `time_key` ordering, and records `interval.session_dates` plus per-day `session_summaries` in the quality report. Holidays and early closes remain **operator-declared** (`--holidays`, `--early-closes`); IMP does not fetch exchange calendars at build time.

CLI JSON includes `provider_availability`: `FIXTURE` (fixture provider), `AVAILABLE` (OpenD verified), or `UNAVAILABLE` (OpenD absent / unverified). Fingerprints: `dataset_fingerprint` (manifest body), `normalized_fingerprint` (bars + provenance), `quality_fingerprint` (quality body excluding its self-hash field).

## Methodology gaps (this pass)

- **Early-close sessions:** declared `--early-closes` dates are tradable short sessions (13:00 ET close, 210 expected 1m bars). Shadow-run preflight still excludes early-close dates from full-grid capture; historical development uses `market_data/historical_development/rth_session.py` for session-kind-aware expectations.
- **Corporate actions:** provider QFQ only; no cross-source reconciliation.
- **IBKR historical TRADE pagination:** when a full page shares one `event_time_ns`, continuation cannot be proven safe; retrieval is marked incomplete with `SUSPECTED_SAME_TIMESTAMP_TRUNCATION` (bounded pages, no infinite loop).
