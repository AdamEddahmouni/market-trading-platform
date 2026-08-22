# Moomoo observational market-data provider

Status: **read-only observational boundary** under `ADR-LIVE-001`.
This is not an admitted research dataset, not paper execution, and not live execution.

Evidence classes used below: **DOCUMENTED**, **OBSERVED**, **INFERRED**, **UNTESTED**.
Observed runtime evidence outranks documentation.

## Architecture

```text
lane request (US_EQUITY_DEPTH)
        ↓
provider router / composition (ADR-PROV-001)
        ↓
captured JSONL adapter  OR  optional OpenD probe process
        ↓
canonical envelopes (stdlib)
        ↓
quality + PIT clocks + replay
```

Vendor SDK (`moomoo-api`) is **not** a dependency of `market_platform_foundation`.
The official Moomoo API Skill may assist agents; it is never on the runtime path.

```text
tools/moomoo/*   (optional processes, moomoo-api; probe.py / record.py /
                 capture_live.py / push_feed.py / check_live_environment.py /
                 smoke_live.py / smoke_paper.py / smoke_reconnect.py)
        ↓ serialized JSON/JSONL
src/market_platform_foundation/market_data/   (CPython 3.11 stdlib)
  live_config → live_runtime → live_admission → observational_state
  ↓ subscription_manager / capability_registry / recorder
ui_api/live_projections → Explore / Workspace / ContextBar
```

## Live observational runtime (Platformization P2/P2.1)

`LiveObservationalRuntime` is the operational ingest path (stdlib only,
no `moomoo` import in `src/`): OpenD callbacks are normalized into canonical
provider envelopes, checked by the quality pipeline, and admitted through a
two-level gate:

| Level | Use |
|---|---|
| `DISPLAY_ADMITTED` | UI may render with quality annotation |
| `EXECUTION_ADMITTED` | Internal simulator may consume (only when enabled) |
| `BLOCKED` | Fail closed |

Live internal paper (`INTERNAL_SIMULATION`) is **not** enabled by live data
alone: it requires `IMP_PAPER_EXECUTION=1` + `IMP_LIVE_INTERNAL_SIMULATION=1`
and an `EXECUTION_ADMITTED` quote after the order intent time. Display-admitted
tape is never executable. See [PLATFORM-DATA-001](../superpowers/specs/2026-08-21-platform-data-001-design.md)
and [P3.1 closure](../superpowers/specs/2026-08-21-platform-p31-live-execution-closure.md).

Env gates (all default off): `IMP_LIVE_OBSERVATIONAL`, `IMP_MOOMOO_LIVE`,
`IMP_LIVE_INTERNAL_SIMULATION`, `IMP_LIVE_FIXTURE_FEED` (local JSONL feed for
CI/offline), `IMP_LIVE_CAPTURE_ROOT`, `IMP_MOOMOO_SUBSCRIPTION_QUOTA`, and the
freshness/wait knobs documented in [`.env.example`](../../.env.example).

Tooling (all read-only observational): `probe.py` (capability report),
`record.py` (bounded JSONL recorder), `capture_live.py` (bounded capture
through the runtime ingest path), `push_feed.py` (fixture feed push),
`check_live_environment.py` (OpenD environment preflight), and
`smoke_live.py` / `smoke_paper.py` / `smoke_reconnect.py`.

## OpenD requirement

- Host: `127.0.0.1` only. Binding to `0.0.0.0` is forbidden.
- Port: `11111`
- Telnet: must remain disabled
- Timezone: UTC recommended
- Probe refuses non-localhost hosts

## SDK requirement

Optional characterization environment (not the governed foundation):

- CPython 3.11
- `moomoo-api==10.10.7008` matching OpenD `10.10.7008`

Known working venv: `C:\Users\adame\moomoo-api-test\.venv` (outside this repository).

## Security boundary

Forbidden in this package: `unlock_trade`, place/modify/cancel orders, fund transfers,
OpenTradeContext, paid entitlement purchases, Hermes modification, WAN exposure of OpenD.

## How to probe

```powershell
& C:\Users\adame\moomoo-api-test\.venv\Scripts\python.exe tools/moomoo/probe.py `
  --output evidence/market_data/moomoo/capability-report.json `
  --subscribe-seconds 8
```

Bounded recorder:

```powershell
& C:\Users\adame\moomoo-api-test\.venv\Scripts\python.exe tools/moomoo/record.py `
  --codes US.AAPL --seconds 6
```

Live opt-in tests:

```powershell
$env:IMP_MOOMOO_LIVE = "1"
python -m unittest discover -s tests/live_moomoo -v
```

Ordinary CI does **not** run `tests/live_moomoo`.

## Data admission

```text
OBSERVED → CAPTURED → VALIDATED → QUALITY_CHARACTERIZED → ADMITTED
```

Admission requires a separate ADR. Replay of captured JSONL is research-path
compatibility only (`CAPTURED_REPLAY_NOT_ADMITTED`).

## Related contracts

- Clocks: `event_time`, `provider_time`, `available_time`, `received_time`, `ingested_time`
- Live envelopes populate `live_received_time` and forbid `historical_ingested_time` (TC-002)
- Replay envelopes invert that pairing so PIT joins can use `available_time`
- Aggressor: `ticker_direction` maps to `AggressorSource.PROVIDER_NATIVE`, never exchange ground truth
- Quality: reuse `OrderFlowQualityFlag` plus existing `INVALID_QUOTE` / volume codes

## Observed LV3 depth (2026-08-20 probe)

OBSERVED for `US.AAPL` via `get_order_book(num=10)` and `SubType.ORDER_BOOK`:

- 10 bid levels and 10 ask levels (MBP)
- Fields per level: price, size, order_count, order-details dict
- `order_count` was **0** on every sampled level
- order-details dicts were **empty**
- `order_book_type`: `NORMAL`
- `svr_recv_time_bid` / `svr_recv_time_ask` populated on some push snapshots, empty on some cache snapshots
- No venue identifier on the book payload (`VENUE_PARTIAL`)
- US market state at probe: `AFTER_HOURS_END` with populated overnight/pre/after snapshot fields

Do not claim full US consolidated MBO or TotalView/ArcaBook identity from this OpenAPI surface.

## Quotas (OBSERVED)

## Known limitations (see capability report for OBSERVED details)

- US options and CME-group futures are expected fail-closed without entitlement
- LV3 US depth is not claimed as full national consolidated MBO
- Short interest, borrow, SEC filings, news, and macro are out of scope for Moomoo
- Crypto characterization does not authorize PI14+
