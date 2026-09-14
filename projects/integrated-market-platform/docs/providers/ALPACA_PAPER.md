# Alpaca Paper execution comparator — boundary document

**Status:** Stdlib urllib Paper-host adapter landed. Authenticated Paper
behavior is **NONE-YET** (no paper keys on this cloud VM). Item 9 stays
**PARTIAL** until an operator places free Paper keys in gitignored
`.private` (never commit secrets). Live `api.alpaca.markets` is unauthorized.
FTEP is **not** `EMPIRICAL_ACTIVE`. The Tradier `#41` fail-closed path is
**kept**.

**Adapter:** `src/market_platform_foundation/providers/adapters/alpaca_paper.py`
**Paper HTTP:** `providers/adapters/alpaca_paper_http.py` (stdlib `urllib` only;
do **not** `import alpaca`).
**Probe:** `tools/providers/probe_alpaca_paper.py` (credential-gated,
read-only `GET /v2/account` first).
**Calibration classifier:** `tools/providers/run_calibration_harness.py`.

---

## 1. Endpoints

| Environment | Origin | Status |
|---|---|---|
| Paper | `https://paper-api.alpaca.markets` | **AUTHORIZED** (exact origin only) |
| Live | `https://api.alpaca.markets` | **NOT AUTHORIZED** (`LIVE_FORBIDDEN` before `urlopen`) |

TLS/HTTPS only. First probe path: `GET /v2/account`.

### 1.1 Authentication

Header pair on every request (never logged):

- `APCA-API-KEY-ID`
- `APCA-API-SECRET-KEY`

Names may be supplied via process env or gitignored `.private/providers.env`.

### 1.2 Fail-closed gates

| Gate | Default | Missing keys / unset |
|---|---|---|
| `IMP_ALPACA_PAPER=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` |
| `IMP_BROKER_PAPER_EXECUTION=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` |
| `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY` | unset | `COMPARATOR_NOT_CONFIGURED`, `orders_placed=false`, `fabricated_fills=false` |
| `APCA_API_BASE_URL` | `https://paper-api.alpaca.markets` | live host → `LIVE_FORBIDDEN`; other hosts → `ALPACA_HOST_FORBIDDEN` |
| `IMP_ALPACA_PAPER_HTTP=1` | unset | fixture / `BROKER_TRANSPORT_NOT_IMPLEMENTED` |

Composition is xor with Tradier 4A and Moomoo 4C (`PAPER_EXECUTION_PROVIDER_CONFLICT`).

---

## 2. Observed Paper behavior

**NONE-YET.** No Paper keys on this VM. Do not write "verified" without probe
evidence. Equity Paper does not validate ES.

When keys exist:

```bash
export IMP_ALPACA_PAPER=1
export IMP_BROKER_PAPER_EXECUTION=1
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
# keys from env or .private/providers.env — never commit
PYTHONPATH=src python tools/providers/probe_alpaca_paper.py
```

Without keys the probe must exit `2` with `COMPARATOR_NOT_CONFIGURED` and no
network. A live origin must exit `LIVE_FORBIDDEN` before `urlopen`.

---

## 3. Authority

Alpaca Paper is a **comparator**, never market ground truth. Broker fills would
be authoritative only for a `BROKER_PAPER` ledger. Simulator
`BarConservativeSimulator` is **not** the comparator. Item 9 stays PARTIAL
until operator Paper keys exist. Not `CALIBRATED`. Not `EMPIRICAL_ACTIVE`.
Live stays off.
