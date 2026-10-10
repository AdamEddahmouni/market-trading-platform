# Provider readiness

This document is the operator checklist for external providers. It records
credential presence and activation state without recording credential values.
Run the report after changing local configuration.

Wave B activation increment (capability matrix, gap engine, campaign readiness,
calibration semantics, ES/news gate table): [PROVIDER_ACTIVATION_INCREMENT.md](./PROVIDER_ACTIVATION_INCREMENT.md).

For UI HTTP read models and Wave A hook/gap inventory (not the in-repo capability matrix), see
[`artifacts/wave-a-findings/ux-hooks-audit.json`](../../artifacts/wave-a-findings/ux-hooks-audit.json).

```powershell
$env:PYTHONPATH = "src"
python tools/provider_readiness.py
python tools/provider_readiness.py --probe-local
python tools/provider_readiness.py --json
python tools/provider_readiness.py audit --json
python tools/provider_readiness.py gaps --profile FTEP-V1-001 --json
python tools/provider_readiness.py campaign-readiness FTEP-V1-001 --json
python tools/providers/capability_matrix.py
python tools/providers/capability_matrix.py --output artifacts/wave-a-findings/capability-matrix-snapshot.json
```

The capability-matrix command emits a deterministic, secret-free snapshot aligned to
[`MARKET_DATA_CAPABILITY_CONTRACT.md`](../architecture/MARKET_DATA_CAPABILITY_CONTRACT.md)
and Wave A inventory JSON under `artifacts/wave-a-findings/`. It merges value-blind
gate rows from `provider_readiness.py` by default; use `--skip-readiness` for
artifact-only output. Writing `--output` re-validates the payload with the capability
contract loader (same rules as `manifests/providers/schemas/capability_matrix_snapshot.schema.json`).

`provider_readiness.py` subcommands are read-only by default:

- `audit` — capability-matrix snapshot merged with gate rows (capability contract IDs, stale evidence as-of).
- `gaps` — deterministic Wave A / capability requirement disposition for a campaign profile (start with `FTEP-V1-001`).
- `campaign-readiness` — fail-closed composition of forward-test preflight plus gap engine output for an activation manifest slug.

Legacy flags `--audit`, `--gaps`, and `--campaign-readiness` remain aliases for JSON output.

`--probe-local` checks only loopback ports. It does not call external APIs,
place orders, or attempt logins.

## Selected market-data path

Moomoo/OpenD is the primary observational market-data provider. This matches
the existing live runtime and UI routing, and is the only integrated path
intended to provide depth-oriented observations. It requires:

- Moomoo OpenD listening on `127.0.0.1:11111`;
- an operator-authenticated Moomoo session with the required entitlements;
- the external SDK environment described in
  [MOOMOO_OBSERVATIONAL.md](../providers/MOOMOO_OBSERVATIONAL.md);
- `IMP_LIVE_OBSERVATIONAL=1` and `IMP_MOOMOO_LIVE=1`.

IBKR remains a secondary observational option for delayed quotes, history,
contract discovery, scanners, and portfolio reads. It requires the local
Client Portal Gateway and a manual authenticated brokerage session. It does
not replace Moomoo depth, and its captures remain observational and
non-admitted.

## Current wiring

Configured in the ignored local `.env`, but still opt-in:

- Anthropic: `ANTHROPIC_API_KEY`; set `IMP_ASSISTANT_PROVIDER=anthropic`.
- FINRA: `FINRA_CLIENT_ID` and `FINRA_CLIENT_SECRET`; set
  `IMP_FINRA_LIVE=1` for live short intelligence.
- FRED/ALFRED: `FRED_API_KEY`; set `IMP_FRED_LIVE=1`.
- U.S. Treasury Fiscal Data and daily rates (public, no credential): set
  `IMP_TREASURY_LIVE=1` for the Screener Bonds universe
  ([Screener S9](SCREENER_S9_BONDS.md)).
- EIA: `EIA_API_KEY`; set `IMP_EIA_LIVE=1`.

The repository must not print, commit, or copy those values into evidence.
Rotate any key that was exposed outside the ignored local secret store.

## SEC status

`SEC_USER_AGENT` is configured in the ignored local `.env`. Bounded live
probes passed for:

- EDGAR submissions/companyfacts for CIK `0000320193`;
- SEC fails-to-deliver archive discovery and the BIYA sample.

Probe reports were written under `.local/` so existing tracked evidence was
not overwritten. Future SEC runs still require the current PowerShell session
to export the same user-agent because the standalone SEC probe does not load
`.env` automatically.

## Provider-specific prerequisites

- SEC EDGAR and FTD use the configured descriptive `SEC_USER_AGENT`; they do
  not need an API key.
- Finviz discovery uses the configured Elite token or operator login recovery.
  MFA/CAPTCHA still requires operator action.
- NewsAPI and Finnhub require `NEWSAPI_API_KEY` and `FINNHUB_API_KEY` in the
  ignored private provider file. Configure them with
  `python tools/news/auth.py configure`, then enable their independent gates.
- Moomoo needs the OpenD install, login, and entitlements above. No API key is
  read by the observational runtime.
- IBKR needs Client Portal Gateway and manual login. A private provider file
  can hold documented login material, but the session still needs to be
  authenticated locally.
- Tradier needs a sandbox token only for sandbox lifecycle work. The adapter
  is currently fixture-only; credentials do not enable live HTTP submission.
- Moomoo paper execution needs simulated-environment credentials only if that
  feature is explicitly scoped. Its adapter is also fixture-only.
- MongoDB needs `IMP_MONGODB_URI` only when shared operational persistence is
  required.
- Enforced local multi-user auth needs a private principals file and
  `IMP_AUTH_ENFORCEMENT_MODE=ENFORCED`. The committed principals fixture is
  for development shape only and must not be used as a shared production
  credential store.

## Public providers

These paths need no secret, though each remains disabled until its live gate
is enabled:

- SEC EDGAR/FTD: the SEC user-agent is required.
- CFTC COT.
- Nasdaq, NYSE, FINRA OTC, and Cboe threshold sources.
- Cboe public options statistics.
- NOAA/NWS/CPC weather products.

Use the provider-specific documents under `docs/providers/` for rate limits,
point-in-time rules, licensing, and bounded probe commands.

## Additions worth considering

Do not add another provider merely to duplicate an existing source. The
following are genuine capability gaps:

- Borrow, cost-to-borrow, utilization, and locate data: add one licensed
  lending source or a broker shortability feed. FINRA, SEC, and threshold
  lists do not provide this.
- Consolidated real-time equities/options: evaluate a licensed feed such as
  Databento, Polygon/Massive, or an equivalent vendor. Moomoo depth and IBKR
  delayed data do not provide the same consolidated entitlement or historical
  contract.
- Production-grade news: evaluate a licensed feed such as Benzinga or an
  equivalent source if catalyst workflows eventually require stronger
  redistribution rights, latency, or historical coverage than the free-tier
  NewsAPI/Finnhub/Finviz paths provide.
- Alerts: add an outbound webhook, email, Slack, or Teams adapter only when
  the workstation has an alerting requirement. None exists today.
- Hosted identity: add OIDC/SSO through the chosen hosting identity provider
  when the platform leaves the loopback workstation. Local principal/session
  auth is already implemented.
- Billing: add Stripe only if the product will charge customers; it is not
  needed for the current research and paper-trading scope.

Every new provider needs an explicit adapter boundary, secret redaction,
rate-limit policy, licensing review, point-in-time availability semantics,
fixture coverage, and an opt-in live probe. Production order execution
remains blocked regardless of provider choice.

## Offline resilience tokens (software)

Backend-owned status tokens for operator explanation live in
`providers/resilience.py`. Fixtures under `tests/fixtures/providers/resilience/`
cover OpenD unavailable, delayed data, partial staleness, source disagreement,
reconnect, timeout, empty payload, malformed response, temporary network
failure, restart recovery, and Yahoo-as-hop-L1 fallback blocked. These tests
are SOFTWARE-class; they do not collect Item 9, calibrate, or enable Live.
OpenD down does not promote Yahoo delayed overlay into hop L1.

## Portable workstation replay and read-only snapshots

Controlled replay refuses current-market `/screener` and `/discover` routes
(including configuration and AI reevaluation mutations) before provider access.
The UI waits for a fresh `/context` result before mounting the Screener and
removes its rows when authority becomes unavailable. Replay provider health is
`NOT_APPLICABLE`; it does not construct or probe live runtimes. Finviz credential
validation, recovery, cache access and HTTP/login sinks refuse controlled replay
even if live flags are also present.

Finviz health audit admits only enumerated public authentication/source/error
values and nonnegative integer generation/recovery counters. Tokens, arbitrary
strings under those names and generic auth fields still fail secret auditing.

The IBKR TWS socket adapter requests delayed snapshot data, waits up to its
configured timeout for a finite positive price, and always cancels the request.
Each snapshot uses a distinct contract object to avoid retained ticker prices.
`market_data_type` distinguishes realtime (1), frozen (2), delayed (3) and
delayed frozen (4); a populated delayed price does not certify realtime
entitlement. Gateway installation or a listening port alone does not establish
authentication or a current capability certificate.

Offline validation must remove inherited operator `IMP_*` settings. In
particular, `IMP_STATE_DIR` enables persistence regardless of `IMP_PERSIST_STATE`;
ordinary unit runs leave it unset and persistence tests choose their own
temporary directories. Preserve operational state independently of test state.

Portable launcher state version 2 binds each service to its process creation
time and absolute checkout/runtime command. Legacy or unverifiable records
never authorize termination. Stop/rollback retain unresolved records, and
restart/update refuse to proceed after partial cleanup. Broker applications
remain external sessions. Windows termination verifies creation time while
holding a process handle; generic command substrings alone are insufficient.
