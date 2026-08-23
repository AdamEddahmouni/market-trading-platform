# Tradier paper execution provider (Platformization P4 / sub-milestone 4A)

**Status:** Fixture-first adapter landed (4A). **Live HTTP transport not yet
implemented** — the sandbox wire contract must be verified and recorded here
before any network path is added.
**Adapter:** `src/market_platform_foundation/providers/adapters/tradier_paper.py`
`TradierPaperExecutionProvider`, injected into
`providers.composition.ProviderComposition.paper_execution`.
**Contract:** `providers.broker_execution` (broker-neutral models, status
mapping, fill normalization, ADR-PROV-001 envelopes).

## What this adapter does

- Implements the `PaperExecutionProvider` contract (`place_order`) plus
  adapter-local `cancel_order` / `fetch_order` / `fetch_account` /
  `fetch_positions`.
- Is **fixture-first**: CI exercises the adapter against recorded sandbox
  responses in `tests/fixtures/providers/tradier_sandbox_orders.json` (no
  network), mirroring the `IMP_LIVE_FIXTURE_FEED` philosophy from
  PLATFORM-DATA-001.
- Without a matching fixture record the adapter **fails closed**
  (`BROKER_TRANSPORT_NOT_IMPLEMENTED`). There is deliberately **no live HTTP
  path** until the sandbox wire contract is verified and the mapping (Tradier
  statuses → canonical broker statuses, order/account payloads) is documented
  here.

## Fail-closed gates (P4-SAFE-001)

All must be set for any broker request; none are set in CI:

| Variable | Default | Effect |
|---|---|---|
| `IMP_TRADIER_PAPER=1` | unset | Tradier paper adapter disabled |
| `IMP_BROKER_PAPER_EXECUTION=1` | unset | `BROKER_PAPER` execution authority (`PAPER_ONLY`) |
| `IMP_TRADIER_TOKEN` | unset | sandbox bearer token |
| `IMP_TRADIER_ENDPOINT` | sandbox URL | blocked if changed to a production endpoint |
| `IMP_TRADIER_ACCOUNT_ID` | unset | sandbox account |

The legacy `EXECUTION_ENABLE` gate used by `DisabledPaperExecutionProvider` is
being reconciled/deprecated so the composition slot has one explicit gate.

## Entry points

- `submit_broker_paper_order` / `cancel_broker_paper_order`
  (`paper/broker_paper.py`) — dedicated broker-paper entry points, kept out of
  `paper/execution.py` so the `INTERNAL_SIMULATION` path never references a
  broker trade verb. The `submit_interactive_order` guard is **not** loosened
  (P4-SAFE-003).
- Submission is idempotent (`idempotency_key`); an `OrderSubmitted`-class
  record is written to the ledger **before** any broker call; an ambiguous
  broker outcome is never blind-retried (P4-IDEM-001 / P4-AMB-001).
- In `BROKER_PAPER` mode the broker is authoritative for lifecycle **and
  fills**; fills are normalized into the shared `apply_fill` shape so the
  ledger, positions, and cash all derive from one source (P4-FILL-001).

## Sandbox limits (verified)

- Free account: API token + paper sandbox.
- Sandbox market data is **15-minute delayed**, Level 1 only, no delayed
  streaming. Not a CVD/Level-2 source and not a fill-quality source.
- Supports US equities/options orders, chains, and delayed quote testing.
- Real-time data requires a brokerage account and is out of scope.

## Wire contract (pending verification in 4A +)

The following must be recorded here from a real sandbox exercise before a live
transport is added: order submit/cancel endpoints and payload shapes, broker
order-id provenance, and the mapping of Tradier statuses to the canonical
`broker_execution` statuses (`accepted` / `working` / `partially_filled` /
`filled` / `rejected` / `cancelled` / `expired` / `ambiguous`).

## Authority

Tradier exercises the execution contract. It does not provide research data;
broker fills are authoritative only for the `BROKER_PAPER` ledger and are not
admitted research fixtures.
