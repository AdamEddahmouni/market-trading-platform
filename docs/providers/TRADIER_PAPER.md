# Tradier paper execution provider — boundary document

**Status:** Fixture-first adapter landed (4A). **Live HTTP transport not
implemented.** No Tradier credentials exist in this repository as of
**2026-08-22** (`.env` carries ANTHROPIC/FINRA/FRED/EIA keys only;
`.private/providers.env` absent) → the live wire exercise is
**BLOCKED_EXTERNAL**. Everything below is separated into DOCUMENTED claims
(spec/vendor docs), OBSERVED results (**NONE-YET**), and FIXTURE assumptions.
Nothing is claimed as observed unless a credentialed operator has recorded it
here.

**Adapter:** `src/market_platform_foundation/providers/adapters/tradier_paper.py`
`TradierPaperExecutionProvider`, injected into
`providers.composition.ProviderComposition.paper_execution`.
**Contract:** `providers.broker_execution` (broker-neutral models, status
mapping, fill normalization, ADR-PROV-001 envelopes).
**Probe:** `tools/providers/probe_tradier_sandbox.py` (credential-gated,
stdlib-only, read-only first; see §7).

---

## 1. Documented behavior (spec / vendor-doc claims)

Source: `docs.tradier.com` (Endpoints, Trading, Orders, Place Order,
Cancel Order, Get User Profile references; retrieved 2026-08-22). These are
**claims by documentation**, not observations.

### 1.1 Endpoints

| Environment | Request/Response base | Streaming base |
|---|---|---|
| Sandbox (paper) | `https://sandbox.tradier.com/v1` | n/a for paper scope |
| Production | `https://api.tradier.com/v1` | `https://stream.tradier.com/v1` |

TLS 1.2 + SNI required; HTTPS only. Versioning via path segment (`/v1`).
The adapter constant `TRADIER_SANDBOX_ENDPOINT = "https://sandbox.tradier.com/v1"`
matches the documented sandbox base.

### 1.2 Authentication

- HTTP header `Authorization: Bearer <token>` on every request
  (OpenAPI `BearerAuth` scheme).
- Separate tokens exist for the live account and the sandbox account
  (retrieved from dash.tradier.com API settings).

### 1.3 Wire endpoints relevant to this adapter

| Operation | Method + path (documented) |
|---|---|
| User profile | `GET /v1/user/profile` |
| Account balances | `GET /v1/accounts/{account_id}/balances` |
| Positions | `GET /v1/accounts/{account_id}/positions` |
| Place order | `POST /v1/accounts/{account_id}/orders` |
| Get one order | `GET /v1/accounts/{account_id}/orders/{order_id}` |
| Cancel order | `DELETE /v1/accounts/{account_id}/orders/{order_id}` |

### 1.4 Order submission encoding

- `Content-Type: application/x-www-form-urlencoded` (required per OpenAPI),
  JSON available via `Accept: application/json`.
- Equity order form fields (documented): `class=equity`, `symbol`, `side`
  (`buy` / `sell` / `buy_to_cover` / `sell_short`), `quantity` (integer),
  `type` (`market` / `limit` / `stop` / `stop_limit`), `duration`
  (`day` / `gtc` / `pre` / `post`), plus `price` for limit types and
  `preview=true` for dry-run validation (recommended but optional).
- Option/multileg/combo orders add `option_symbol` (OCC) and indexed leg
  parameters — **out of scope until observed** (see §5).
- Success ack shape (OpenAPI example): `{"order": {"id": <int>,
  "status": "ok"}}` where `"ok"` is an **acceptance ack**, not an order
  lifecycle state.

### 1.5 Order status vocabulary (wire)

Documented order statuses: `pending`, `open`, `partially_filled`, `filled`,
`expired`, `canceled`, `rejected`, `pending_cancel` (OpenAPI schema; the
Orders guide additionally lists `error`). Note the single-L spelling
`canceled`. Cancel ack status is documented as one of `ok`,
`pending_cancel`.

Canonical mapping direction (adapter contract): wire statuses map into
canonical `BROKER_STATUSES` (`accepted` / `working` / `partially_filled` /
`filled` / `rejected` / `cancelled` / `expired` / `ambiguous`) and then to
IMP lifecycle states via `BROKER_STATUS_TO_IMP`. The precise wire→canonical
table is pending observation (§2); presumed pairs are recorded per-fixture
in §3.

## 2. Observed sandbox behavior

**NONE-YET.** As of 2026-08-22 no Tradier token exists anywhere in this
environment, so nothing below has been confirmed against the sandbox:

- [ ] profile/balances fetch shapes (JSON field presence, account-number format)
- [ ] place-order ack shape (`order.id` type/range, ack status value)
- [ ] order polling shapes (`orders.order` singular-vs-list handling)
- [ ] cancel ack shape
- [ ] actual sandbox latency/fill behavior for market vs limit orders
- [ ] rejection payload (`reason_description`) shape

One non-authenticated observation (2026-08-22): `https://sandbox.tradier.com/v1/user/profile`
is reachable and returns HTTP 401 with Apigee-style fault JSON for an invalid
token (`keymanagement.service.invalid_access_token`). This proves host/path
liveness only; it is not authenticated behavior.

When a token becomes available, run the §7 acceptance procedure and record
results here, replacing NONE-YET entries. Do not write "verified" for any
line without recorded probe evidence.

## 3. Fixture assumptions (per file)

Fixtures replay *normalized* records; each record embeds a presumption about
the raw wire value in `status_raw`. None of these presumptions is confirmed
yet (§2). Files live in `tests/fixtures/providers/` and are auto-loaded by
`TradierReplayStore.load()` via the glob `tradier_sandbox_*.json`.

### `tradier_sandbox_orders.json`

| Record (operation, match) | Canonical status | `status_raw` assumption | Assumed wire provenance |
|---|---|---|---|
| `place_order` cli-broker-limit-1 | `working` | `pending` | POST orders ack accepted → subsequent GET shows wire `pending`; normalized to canonical `working` |
| `place_order` cli-broker-market-1 | `filled` | `filled` | Market order fills immediately; GET shows wire `filled` + `avg_fill_price`/`exec_quantity` → fills list |
| `place_order` cli-broker-reject-1 | `rejected` | `rejected` | Rejected order (e.g. insufficient buying power); guide-level `reason_description` not yet modeled |
| `place_order` cli-broker-ambiguous-1 | `ambiguous` | `timeout` | **Synthetic, NOT a wire status**: transport timeout after submit leaves the outcome unknown; adapter returns `BROKER_AMBIGUOUS_OUTCOME` and never blind-retries (P4-AMB-001) |
| `fetch_order` TR-FILL-0001 | `filled` | `filled` | GET `/accounts/{id}/orders/{id}` → `orders.order` with `avg_fill_price`, `exec_quantity` |
| `fetch_order` TR-WORK-0001 | `working` | `pending` | same endpoint, resting order |
| `cancel_order` TR-WORK-0001 | `cancelled` | `canceled` | DELETE orders/{id} ack (`ok`/`pending_cancel`) followed by GET showing wire `canceled` → canonical `cancelled` |
| `fetch_account` | — | — | GET balances → `cash_minor`/`buying_power_minor` derived from documented balance fields (dollars→minor conversion assumed) |
| `fetch_positions` | — | — | GET positions → empty position list |

Structural assumptions shared by all records:

- Prices are integer minor units in fixtures; the wire reports decimal
  floats (`avg_fill_price: 22.0`). A dollars→minor conversion step must be
  implemented (and its rounding pinned) before a live transport lands.
- Timestamps are integer ns (`event_time_ns`/`receive_time_ns`); the wire
  exposes ISO-8601 `create_date`/`transaction_date`. Conversion must be
  deterministic (UTC, fixed epoch derivation).
- Broker order ids are strings like `TR-*`; the wire id is a **JSON number**
  (`"id": 228175`). The future transport must stringify without loss.
- Fill events carry explicit `broker_fill_id`s; the wire order object has no
  fill-id field, so `ensure_broker_fill_ids` derives deterministic ids from
  `(order_id, event_time_ns, quantity)` — an adapter-side invention to be
  validated against real multi-fill payloads.

### `tradier_sandbox_lifecycle.json`

Added to close fixture gaps against the documented vocabulary (no overlap
with existing cases):

| Record | Canonical status | `status_raw` assumption | Rationale |
|---|---|---|---|
| `place_order` cli-broker-partial-1 | `partially_filled` | `partially_filled` | Two split fills summing to 40/100; asserts fill-id preservation across partial execution |
| `place_order` cli-broker-accepted-1 | `accepted` | `open` | Wire `open` (resting, unfilled) presumed to normalize to canonical `accepted` (IMP `ACTIVATED`) rather than `working` — **mapping decision pending §2 confirmation** |
| `place_order` cli-broker-expired-1 | `expired` | `expired` | Terminal expiry without fills |

Matching contract assertions live in
`tests/platform/test_broker_paper_p4.py::BrokerPaperLifecycleFixtureTests`
(4 tests).

Known remaining fixture gaps (not added because they need real-shape
decisions first): `pending_cancel` intermediate state, `error` status,
multi-leg/combo records, reject payload carrying `reason_description`,
and a cancel-of-filled-order failure case.

## 4. Limitations

- Sandbox market data is **15-minute delayed**, Level 1 quotes only, no
  delayed streaming. Not a CVD/Level-2 source and **not a fill-quality
  source** — fills in `BROKER_PAPER` reflect sandbox simulation quality and
  must never be used to validate execution alpha.
- Free/sandbox tier supports US equities/options orders, chains, and delayed
  quote testing. Real-time data requires a brokerage account and is out of
  scope.
- Pre/post-market sessions accept limit equity orders only, inside session
  windows only (documented).

## 5. Unsupported behavior (do not build on this adapter)

- **Production trading.** Any endpoint other than the sandbox URL is
  hard-blocked (`TRADIER_PRODUCTION_ENDPOINT_BLOCKED`). LIVE-001 production
  execution remains blocked platform-wide.
- Options/multileg/combo/OTO/OCO/OTOCO orders: documented by Tradier but
  unmodeled — no fixtures, no transport, no canonical mapping decisions.
- Order change/modify (`PUT .../orders/{id}`), watchlists, streaming, OAuth:
  out of scope for P4 paper execution.
- Using broker fills or sandbox data as admitted research fixtures: broker
  fills are authoritative only for the `BROKER_PAPER` ledger.
- Blind retry of ambiguous outcomes: `ambiguous` has no IMP mapping and is
  never re-submitted (P4-MAP-001 / P4-AMB-001); resolution happens through
  ledger idempotency reconciliation only.

## 6. Safety boundaries (gates)

All of the following must hold before any broker request exists
(`TradierPaperExecutionProvider._gate_check`, P4-SAFE-001); none are set in CI:

| Variable | Default | Effect when absent/wrong |
|---|---|---|
| `IMP_TRADIER_PAPER=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` |
| `IMP_BROKER_PAPER_EXECUTION=1` | unset | `unavailable` / `EXECUTION_NOT_ENABLED` (`PAPER_ONLY` authority gate) |
| `IMP_TRADIER_TOKEN` | unset | `unavailable` / `TRADIER_TOKEN_NOT_CONFIGURED` |
| `IMP_TRADIER_ENDPOINT` | sandbox URL | any non-sandbox value → **blocked** / `TRADIER_PRODUCTION_ENDPOINT_BLOCKED` (fail-closed prod guard) |
| `IMP_TRADIER_ACCOUNT_ID` | unset | sandbox account selector (probe requires it to match a profile account if set) |

Additional fail-closed layers:

- No matching replay fixture → `BROKER_TRANSPORT_NOT_IMPLEMENTED` (there is
  deliberately no live HTTP path in the adapter yet).
- Unknown/unmappable instrument → `UNMAPPED_INSTRUMENT`.
- Malformed intent → `BROKER_REQUEST_INVALID`; malformed provider record →
  `BROKER_RESPONSE_INVALID`.
- Ledger write of the submission record happens **before** any broker call;
  idempotency keys prevent duplicate submissions (P4-IDEM-001).
- `submit_interactive_order` guard is not loosened; broker verbs live only in
  `paper/broker_paper.py` entry points (P4-SAFE-003).

## 7. Acceptance procedure (operator with a token)

Prerequisites: Python venv at `.venv/Scripts/python.exe` (repo root
`integrated-market-platform/`), a **sandbox** API token from
dash.tradier.com → Settings → API. Never paste the token into shell history
or files other than `.private/providers.env` / your process env.

Step 0 — place the token (choose one):

```bash
# option A: private env file (gitignored)
printf 'IMP_TRADIER_TOKEN=<your-sandbox-token>\n' > .private/providers.env

# option B: current shell only
export IMP_TRADIER_TOKEN="<your-sandbox-token>"
```

Step 1 — arm the gates (current shell):

```bash
export IMP_TRADIER_PAPER=1
export IMP_BROKER_PAPER_EXECUTION=1
# optional: pin the account picked from your profile
# export IMP_TRADIER_ACCOUNT_ID=VAxxxxxx
```

Step 2 — read-only verification (no orders placed):

```bash
cd integrated-market-platform
PYTHONPATH=src "$PWD/.venv/Scripts/python.exe" tools/providers/probe_tradier_sandbox.py
echo $?
```

Pass criteria: prints `[gate] all gates satisfied…`, sanitized
request/response evidence for `GET /v1/user/profile` and
`GET /v1/accounts/{id}/balances` (Authorization shown as `[REDACTED]`),
ends with `[done] PROBE_PASSED`, exit code `0`.

Fail-closed checks (run these first — they must exit nonzero with no
traceback and no secret echo):

```bash
env -u IMP_TRADIER_PAPER -u IMP_BROKER_PAPER_EXECUTION -u IMP_TRADIER_TOKEN \
  "$PWD/.venv/Scripts/python.exe" tools/providers/probe_tradier_sandbox.py   # expect exit 2 PROVIDER_NOT_CONFIGURED
IMP_TRADIER_ENDPOINT=https://api.tradier.com/v1 IMP_TRADIER_PAPER=1 \
  IMP_BROKER_PAPER_EXECUTION=1 IMP_TRADIER_TOKEN=x \
  "$PWD/.venv/Scripts/python.exe" tools/providers/probe_tradier_sandbox.py   # expect exit 2 PRODUCTION_ENDPOINT_BLOCKED
```

Step 3 — optional paper order lifecycle (places ONE small sandbox market
order, polls to terminal state, auto-cancels if still open after ~30 s):

```bash
"$PWD/.venv/Scripts/python.exe" tools/providers/probe_tradier_sandbox.py --submit AAPL 1
echo $?
```

Pass criteria: submit ack carries non-empty numeric `order.id` with status
in `{ok}` ∪ documented order vocabulary; poll evidence shows statuses within
the documented vocabulary; final line `[ok] order lifecycle exercised…`;
exit code `0`.

Exit codes: `0` pass · `2` PROVIDER_NOT_CONFIGURED /
PRODUCTION_ENDPOINT_BLOCKED · `3` CONTRACT_MISMATCH · `4`
NETWORK_ERROR / AUTH_REJECTED.

Step 4 — record observations: paste the probe's sanitized evidence blocks
into §2 of this document, resolve the pending mapping decisions flagged in
§3 (`open`→`accepted` vs `working`, ack-status semantics, id typing,
price/timestamp conversions), then update the fixture `status_raw` values if
the observed wire differs. Only after §2 is filled may a live transport be
considered; the adapter stays fixture-replay until then.

## 8. Authority

Tradier exercises the execution contract. It does not provide research data;
broker fills are authoritative only for the `BROKER_PAPER` ledger and are
not admitted research fixtures.
