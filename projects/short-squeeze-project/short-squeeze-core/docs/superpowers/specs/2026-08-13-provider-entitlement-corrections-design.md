# Provider Entitlement Corrections Design

## Goal

Correct provider capability, plan, entitlement, and licensing statements without expanding the screener's data sources or making it place trades.

## Approach

The implementation will keep runtime capabilities evidence-based. Provider documentation will distinguish an endpoint's functional support from the plan, account, market-data entitlement, or licensing condition needed to use it. Runtime text will remove unsupported claims and retain `NOT_CONFIGURED` or unavailable states until a successful provider response establishes availability.

## Components

- `docs/PROVIDERS.md` will become the source-backed matrix for the six live providers and local FinBERT, including plan and entitlement constraints.
- `docs/COLLECTORS.md` will document the restrictions for FINRA, yfinance, Polygon, Alpha Vantage, Reddit, Stocktwits, and RSS collectors.
- Finnhub's 403 handling will report an account-access denial without incorrectly asserting that Company News is premium-only.
- IBKR borrow-fee status will no longer assert an unverified generic tick or fundamental-ratios entitlement; the adapter remains unavailable until its request implementation and entitlement are verified.
- FinBERT documentation will distinguish the model's three per-headline classes from the application's aggregate `MIXED` outcome.

## Error Handling

Credential, plan, and entitlement failures remain non-fatal. They are displayed as provider-specific unavailable states, never converted into fresh evidence or inferred values.

## Testing

Regression tests will verify that a Finnhub 403 uses neutral account-access wording and that the borrow-fee status does not advertise generic tick 258. Documentation is validated by a focused source-link and claim scan plus the full test suite.

