# Portfolio contract map — UIR-01G

> Landed increment: `ui/operator-redesign-portfolio` (UIR-01G). This is the
> authoritative current-contract map for `/portfolio`. The older page spec
> ([pages/portfolio.md](pages/portfolio.md)) remains *design guidance*. Where
> that plan assumed NAV, daily P&L, concentration dollars, or a frontend risk
> score, **this map wins**. Rule: current contracts are authoritative; do not
> invent missing financial metrics.

## What Portfolio is for

Portfolio answers: **what I hold; what the backend says it is worth now; risk
and concentration that the contract actually reports; what changed in this
session; which positions need attention; the safe next action; and whether this
is Paper/simulated vs observational/live market data.**

Portfolio is **not**: the Paper submit cockpit (Workspace), a second Command
desk, Live execution, or a place to compute NAV / daily P&L / dollar
concentration in the browser.

Capital honesty: Paper and Demo figures are **simulated**. Live figures are
**broker-observed / observational**. Never present Paper P&L as real-money P&L.

## Backend contract inventory (verified against `ui/src/api/schemas.ts`
## and `ui/src/api/endpoints.ts`)

### 1. Paper/Demo account — `GET /paper/portfolio?view_mode=PAPER|DEMO`

Schema: `PaperPortfolioResponseSchema`.

#### Account (required)

| Field | Type | Operator use | Notes |
|---|---|---|---|
| `account.paper_account_id` | string | Account identity | CopyableIdentifier |
| `account.session_id` | string | Session identity | CopyableIdentifier |
| `account.currency` | string | Format buying power / starting cash | Required for `Intl` currency |
| `account.cash_display` | string | Cash (backend-formatted) | Prefer over recomputing from `cash_minor` |
| `account.cash_minor` | number | L4 audit | Do not invent a second cash figure |
| `account.buying_power_minor` | number | Buying power | Format with currency; **never** substitute `cash_display` |
| `account.initial_cash_minor` | number | Starting cash | Format with currency |
| `account.realized_pnl_display` | string | Realized P&L fallback | Paper/simulated |
| `account.realized_pnl_minor` | number | L4 | |
| `account.data_mode` | string | Honesty (replay vs observational) | Semantic `session` / data-mode tables |
| `account.data_provider` | string | Provenance | |
| `account.execution_mode` | string | Authority gating | `canUsePaperActions` |
| `account.execution_authority` | string | Authority gating | Semantic `executionAuthority` |
| `account.execution_provider` | string | Provenance | |

#### Positions

| Field | Type | Operator use |
|---|---|---|
| `instrument_id` | string | Workspace handoff (`/workspace/:id`) |
| `symbol` | string | Primary label |
| `quantity` | number | Size (shares/contracts as backend emits) |
| `side` | string | LONG/SHORT — semantic `portfolio` humanize if unmapped |
| `average_fill_display` | string? | Avg fill if present |
| `mark_display` | string? | Mark if present; else Unavailable |
| `mark_quality` | string? | Freshness word (`CURRENT`/`STALE`/…) |
| `mark_as_of_ns` | number? | Freshness as-of (ns) |
| `mark_provider` / `mark_source` | string? | L3 provenance |
| `unrealized_pnl_display` | string? | Position P&L; never invented |

No contract field for dollar market value, weight %, or NAV contribution. Do
**not** multiply qty × mark in the UI.

#### P&L block (optional)

`pnl.realized_display`, `pnl.unrealized_display` (nullable), `pnl.total_display`.
When absent, realized falls back to `account.realized_pnl_display`; unrealized
stays **Unavailable**. There is **no** daily P&L field.

#### Exposure (optional)

`exposure.gross_shares`, `exposure.net_shares`. Share counts only — not dollar
exposure. Omit the section when the object is absent; when present, `0` is a
real zero.

#### Risk (required)

| Field | Operator use |
|---|---|
| `risk.kill_switch_active` | Attention (critical when true) |
| `risk.open_order_count` | vs `limits.max_open_orders` |
| `risk.reconciliation_status` | Honesty |
| `risk.limits.max_order_shares` / `max_position_shares` / `max_open_orders` | Utilization of **share** limits (already used on Command risk ribbon) |
| `risk.last_decision` | Attention when decision is not PASS/ALLOW/APPROVE/RESIZE |

Share-limit utilization is a presentation of contract limits, not a new risk
score. No VaR, buying-power %, or frontend composite.

#### Data health / session / context

`data_health.state` + optional `detail` / `simulation_model`.
Optional `session` (`session_id`, `paper_account_id`, `execution_mode`,
`execution_authority`, `starting_cash_minor`).
`as_of_context`, `authority_boundary`, `reconciliation_status`,
`active_instrument` (+ source). Orders/fills are passthrough records.

### 2. Session list — `GET /paper/sessions` (raw fetch)

Not Zod-gated. Observed: `sessions[]` with `session_id`, `status`,
`created_at`, `closed_at`, `data_mode`, `execution_mode`. Stale after
archive/new until refetch (keyed on current session id). Manual refresh is
honest; do not invent a second session store.

### 3. Session mutations (Paper, gated)

`POST /paper/sessions` (open) and `/paper/sessions/close` via existing React
Query mutations. **Not** order submit. Gating: `canUsePaperActions`.

### 4. Order history — `GET /paper/order-history` (infinite)

Existing `PaperOrderHistory` surface. Portfolio may host it; Workspace remains
the only submit boundary. No UI call site for `/paper/orders/cancel` — do not
add one.

### 5. Strategy profitability — `GET /paper/strategy-profitability`

Existing sidecar. Non-authoritative cumulative attribution. Params stay as
today (no transport change).

### 6. Live — canary snapshot + reconciliation

`liveCanarySnapshot("portfolio")` + `liveCanaryReconciliation`. Broker-reported
positions/open orders, program caps, block reasons, reconciliation health.
Read-only. No Paper cash/P&L overlay. No execution controls.

## Explicitly not on this surface

| Tempting metric | Why omitted |
|---|---|
| NAV | No contract field; summing cash + mark×qty is frontend accounting |
| Daily P&L | No contract field |
| Dollar exposure / allocation % | Exposure is shares only |
| Frontend risk score | Forbidden |
| In-page `OrderTicket` | Workspace is the Paper submit boundary |

## Safe next actions (contract-backed)

- Inspect a position in Workspace (`instrument_id` present).
- Open Workspace with no draft when empty.
- Archive / new Paper session when `canUsePaperActions`.
- View execution trace for an order with `intent_id` / `order_id`.
- Open Control / Live Canary for degraded Live or data-health issues.

## Attention (no invented alerts)

Reuse `derivePaperExceptions` (Command/Paper-Now): kill switch, non-healthy
data health, non-reconciled status, non-healthy last risk decision, problem
order states, non-healthy mark quality. Cap 5. No extra synthetic alerts.
