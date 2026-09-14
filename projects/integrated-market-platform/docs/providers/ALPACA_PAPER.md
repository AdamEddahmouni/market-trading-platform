# Alpaca Paper execution comparator — boundary document

**Status:** Stdlib urllib Paper-host adapter landed. The weekday probe is
**GET-only** (`account` / `clock` / `positions`) on
`https://paper-api.alpaca.markets`. Missing keys stay
`COMPARATOR_NOT_CONFIGURED`. Live `api.alpaca.markets` is unauthorized
(`LIVE_FORBIDDEN` before `urlopen`). Item 9 stays **PARTIAL**. FTEP is
**not** `EMPIRICAL_ACTIVE`. Not `CALIBRATED`. The Tradier `#41` fail-closed
path is **kept**.

**Adapter:** `src/market_platform_foundation/providers/adapters/alpaca_paper.py`
**Paper HTTP:** `providers/adapters/alpaca_paper_http.py` (stdlib `urllib` only;
do **not** `import alpaca`).
**Probe:** `tools/providers/probe_alpaca_paper.py` (credential-gated,
GET-only `AlpacaPaperReadOnlyHttpTransport`).
**Calibration classifier:** `tools/providers/run_calibration_harness.py`.

---

## 1. Endpoints

| Environment | Origin | Status |
|---|---|---|
| Paper | `https://paper-api.alpaca.markets` | **AUTHORIZED** (exact origin only) |
| Live | `https://api.alpaca.markets` | **NOT AUTHORIZED** (`LIVE_FORBIDDEN` before `urlopen`) |

TLS/HTTPS only.

### 1.1 Read-only probe paths

The probe uses `AlpacaPaperReadOnlyHttpTransport`. Allowed methods/paths:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v2/account` | Account present / `status_raw` (no cash printed) |
| `GET` | `/v2/clock` | Legacy session clock (`is_open`, `next_open`, `next_close`) |
| `GET` | `/v2/positions` | Position count only |

`POST` / `DELETE` and `/v2/orders` fail closed as `ALPACA_READONLY_FORBIDDEN`
before `urlopen`. Probe output always includes `orders_placed=false` and
`fabricated_fills=false`, including `LIVE_FORBIDDEN`. Clock `is_open=true`
during cash RTH is **not** Item 9 PROVED and is **not** `CALIBRATED`.

### 1.2 Authentication

Header pair on every request (never logged):

- `APCA-API-KEY-ID`
- `APCA-API-SECRET-KEY`

Names may be supplied via process env or gitignored `.private` env files.

### 1.3 Fail-closed gates

| Gate | Default | Missing keys / unset |
|---|---|---|
| `IMP_ALPACA_PAPER=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` |
| `IMP_BROKER_PAPER_EXECUTION=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` |
| `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY` | unset | `COMPARATOR_NOT_CONFIGURED`, `orders_placed=false`, `fabricated_fills=false` |
| `APCA_API_BASE_URL` | `https://paper-api.alpaca.markets` | live host → `LIVE_FORBIDDEN`; other hosts → `ALPACA_HOST_FORBIDDEN` |
| `IMP_ALPACA_PAPER_HTTP=1` | unset | fixture / `BROKER_TRANSPORT_NOT_IMPLEMENTED` |

Composition is xor with Tradier 4A and Moomoo 4C (`PAPER_EXECUTION_PROVIDER_CONFLICT`).
The harness `--place-sandbox-orders` flag is ignored; `orders_placed` stays false.

---

## 2. Observed Paper behavior

Operator Paper keys are gitignored and are never committed. Do not write
"verified" / `CALIBRATED` / `EMPIRICAL_ACTIVE` from HTTP 200 or `is_open=true`.
Equity Paper does not validate ES.

When keys exist:

```bash
export IMP_ALPACA_PAPER=1
export IMP_BROKER_PAPER_EXECUTION=1
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
# keys from env or gitignored --env-file — never commit
PYTHONPATH=src python tools/providers/probe_alpaca_paper.py
```

Without keys the probe must exit `2` with `COMPARATOR_NOT_CONFIGURED` and no
network. A live origin must exit `LIVE_FORBIDDEN` before `urlopen`.

---

## 3. Authority

Alpaca Paper is a **comparator**, never market ground truth. Broker fills would
be authoritative only for a `BROKER_PAPER` ledger. Simulator
`BarConservativeSimulator` is **not** the comparator. Item 9 stays PARTIAL
until honest cash-RTH MATCHED pairs exist. Not `CALIBRATED`. Not
`EMPIRICAL_ACTIVE`. Live stays off.
