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
The Primary L1 adapter loads `tools/moomoo/opend_quote_transport.py` by file
path and lazy-imports `moomoo` there. Missing SDK fails closed.

```text
tools/moomoo/*   (optional processes, moomoo-api; probe.py / record.py /
                 capture_live.py / push_feed.py / check_live_environment.py /
                 opend_quote_transport.py / smoke_live.py / smoke_paper.py /
                 smoke_reconnect.py)
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

## Primary L1 equity-quote selection (DoD item 2)

Distinct from the `LiveObservationalRuntime` ingest path above: the
broker-neutral `EquityQuoteProvider` contract (`providers/contracts.py`,
ADR-PROV-001) has its own request/response quote-source selection, used by
the $0 no-additional-cost stack (see
[`us-equity-provider-stack-selection.json`](../../artifacts/ftep-v1-002/us-equity-provider-stack-selection.json)).
The locked decision for that stack: **Primary L1 = Moomoo OpenD
observational**.

- `providers/adapters/moomoo_opend_equity_quote.py` — `MoomooOpenDEquityQuoteProvider`
  (`moomoo.opend.observational`, capability `US_EQUITY_L1`). Loopback-only
  (`127.0.0.1`/`localhost`/`::1`); a non-loopback `IMP_MOOMOO_HOST` fails
  closed with `OPEND_NON_LOOPBACK_BLOCKED` without attempting a connection.
  Reachability is a live TCP probe evaluated inside `fetch_quote` (never
  cached at composition time). Unreachable → `OPEND_UNAVAILABLE`. Reachable
  OpenD then uses the quote-only vendor transport in
  `tools/moomoo/opend_quote_transport.py` (`OpenQuoteContext.get_market_snapshot`
  only; the `moomoo-api` SDK is still not a dependency of this package).
  Missing SDK → `MOOMOO_SDK_MISSING`. Auth failure (`qot_logined` false) →
  `MOOMOO_AUTH_FAILURE`. Protocol/SDK exception or non-`RET_OK` →
  `MOOMOO_PROTOCOL_ERROR`. A vendor row without `last_price` or without a
  parseable `update_time`/`time` fails closed (`MOOMOO_LAST_PRICE_MISSING` /
  `MISSING_TIMESTAMP`) — the adapter never fills `last_price` from
  bid/ask/close/session fields. A real tick requires operator OpenD **and**
  the vendor SDK; CI without a daemon stays `OPEND_UNAVAILABLE` with zero
  events. `status="available"` is returned only when the vendor row itself
  carries `last_price`.
- `providers/adapters/yahoo_delayed_equity_quote.py` — `YahooDelayedEquityQuoteProvider`
  (`yahoo.finance.delayed`, capability `US_EQUITY_SNAPSHOT`, `timeliness="DELAYED"`).
  A distinctly-identified, cloud-reachable **overlay** — never the primary L1
  slot, never labeled `REAL_TIME`, and never usable for ES/futures symbols
  (`ES=F`, `/ES`, `MES`, … fail closed with
  `ES_FUTURES_NOT_SUPPORTED_BY_DELAYED_EQUITY_OVERLAY` before any HTTP call).
  Overlay events stamp `capability=US_EQUITY_SNAPSHOT` (not `US_EQUITY_L1`).
  G7 does **not** register Yahoo for `OBSERVATIONAL_L1`; selecting
  `yahoo.finance.delayed` as hop L1 is `UNKNOWN_PROVIDER`.
- `providers/moomoo_opend_capability.py` — G7 `ProviderRegistry` identity
  `moomoo.opend.observational` with implemented `US_EQUITY_L1`.
  `RuntimeCapabilityRegistry` auto-registers it. Default runtime health is
  `DOWN` (fail closed) until a hop stamps `HEALTHY` after an admitted OpenD
  fetch. Lane `OBSERVATIONAL_L1` resolves per provider (`US_EQUITY_L1` on
  OpenD, `IBKR_L1` on IBKR) so a hop with that `provider_id` is not
  `UNKNOWN_PROVIDER`.
- `providers/equity_quote_selection.py` — `primary_equity_quote_provider()`
  always returns the Moomoo OpenD adapter; `opend_readiness()` is a
  diagnostic-only reachability snapshot that never changes which provider is
  primary; `delayed_cloud_overlay_provider()` returns the Yahoo overlay under
  its own identity.
- `providers/equity_quote_discovery.py` — `discover_equity_quote_stack()`
  reports OpenD identity, classification, and reachability. OpenD down does
  **not** select Yahoo as the hop `quote_provider`; Yahoo is listed as
  `overlay_provider_id` only.
- Path A hop CLI (`tools/path_a_prospective_run.py`) takes
  `quote_provider` from `primary_equity_quote_provider()`, not from the
  discovery provider tuple. Before quote fetch the hop calls
  `diagnose_opend(start=True)` so an installed-but-down Windows OpenD
  (`%APPDATA%\\moomoo_OpenD\\moomoo_OpenD.exe`) is started via
  `tools/moomoo/check_live_environment.py --start-opend`. If it is still
  down, the hop fail-closes (`PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE`)
  and does **not** swap Yahoo into L1. Persist CLI, catalog invoke, and
  Live argparse refusal are unchanged. Honest outcome with OpenD down:
  `PROVIDER_UNAVAILABLE` / `OPEND_UNAVAILABLE` (or
  `MOOMOO_SDK_MISSING` if loopback TCP answers but the vendor SDK is
  absent). FTEP is not `EMPIRICAL_ACTIVE`. Live stays off. A real OpenD
  tick still requires an operator daemon **and** `moomoo-api` in the
  **same** IMP interpreter (`python tools/imp.py env install-opend`); this
  increment wires the quote-only transport, it does not
  declare empirical L1.
- `providers/composition.py` — `with_moomoo_opend_primary_quote(composition)`
  wires the `equity_quote` slot to the OpenD adapter. Additive/opt-in: the
  default `ProviderComposition` keeps `UnconfiguredEquityQuoteProvider`
  (fail-closed `PROVIDER_NOT_CONFIGURED`) unless a caller opts in.
- Tests: `tests/providers/test_moomoo_opend_primary_l1.py` plus hop rewrites
  in `tests/intelligence/test_path_a_prospective.py`. The cloud CI/dev VM
  has no loopback OpenD daemon, so the "no OpenD → honest unavailable, no
  generated quotes" path is exercised unconditionally; a local loopback TCP
  listener (never a moomoo protocol/tick) proves the reachable-but-SDK-missing
  branch also fails closed (`MOOMOO_SDK_MISSING`). Injected vendor-row mapping
  is a contract test, not empirical evidence. G7 selection tests in
  `tests/providers/test_g7_runtime_capability.py` prove OpenD is a known
  hop-L1 identity, Yahoo overlay is not, and unstamped OpenD is
  `PROVIDER_DOWN`.

## SDK requirement

Optional extra on the IMP interpreter (not a `market_platform_foundation`
dependency; not installed by cloud/default bootstrap):

- CPython 3.11 IMP `.venv` (already has sklearn / intelligence BUILD deps)
- `python tools/imp.py env install-opend` → `moomoo-api==10.10.7008` matching OpenD `10.10.7008`

`import moomoo` must resolve to the vendor package (`OpenQuoteContext`). The
local `tools/moomoo` directory is never the SDK. Missing SDK fail-closes
(`MOOMOO_SDK_MISSING`) and never mocks a tick.

After that one-time extra, Path A hop is one interpreter:

```powershell
$imp = "<IMP root>"
Set-Location $imp
Remove-Item Env:IMP_PERSIST_STATE,Env:IMP_STATE_DIR,Env:IMP_MOOMOO_LIVE,Env:IMP_LIVE_OBSERVATIONAL,Env:IMP_LIVE_INTERNAL_SIMULATION,Env:IMP_PAPER_EXECUTION -ErrorAction SilentlyContinue
$env:PYTHONPATH = "src"
& .\.venv\Scripts\python.exe tools\path_a_prospective_run.py --symbol AAPL --mode paper
```

Do not append `%USERPROFILE%\moomoo-api-test\.venv\Lib\site-packages` to
`PYTHONPATH` and do not run the hop with that sibling venv's python.

## Security boundary

Forbidden in this package: `unlock_trade`, place/modify/cancel orders, fund transfers,
OpenTradeContext, paid entitlement purchases, Hermes modification, WAN exposure of OpenD.

## How to probe

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tools/moomoo/probe.py `
  --output evidence/market_data/moomoo/capability-report.json `
  --subscribe-seconds 8
```

Bounded recorder:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tools/moomoo/record.py `
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
