# Security

**Status:** IMP-specific security baseline.

## Never commit

- API keys, broker tokens, `ANTHROPIC_API_KEY`, `FINVIZ_API_KEY`, `FRED_API_KEY`, etc.
- Real account identifiers if sensitive
- `.env` with real values (use `.env.example` as template)
- `.private/` provider credential files

## Environment variables

Sensitive vars listed in [CONFIGURATION.md](CONFIGURATION.md). Store locally or Cursor Cloud Secrets — never in repo.

## Logs

- Redact tokens in validation worker output (manifest enforces conservative patterns on evidence changes)
- Do not log full provider auth responses

## Execution boundaries

- **Live production execution blocked** (LIVE-001)
- Paper requires env gates + backend authority
- Broker paper: sandbox endpoint + explicit gates only
- Frontend gating is not a security control

## Paper / Live confusion

Mode-specific pages + backend operating context. Test Demo/Paper/Live separation on safety changes.

## Arbitrary metadata

`decision_source_snapshot` is bounded — reject oversize or malformed payloads on write.

## Fixtures

Use admitted/synthetic fixtures — no real operator PII or live account data in committed tests.

## Dependency vulnerabilities

Run `npm audit` on UI updates. Foundation stdlib lock reduces Python supply-chain surface.

## Security-sensitive review

Flag changes affecting: credentials, authority, execution, persistence, account identity.

Additional checklist: [checklists/PAPER_SAFETY.md](checklists/PAPER_SAFETY.md) for Paper; full [PAPER_EXECUTION_CHANGE.md](sops/PAPER_EXECUTION_CHANGE.md).

## `.gitignore`

Verify secrets paths remain ignored: `.env`, `.private/`, `.local/` state, venv.

## Loopback browser requests (AUD-001 / AUD-039)

The UI API checks browser origins before reading bodies or dispatching handlers. Only
`http://127.0.0.1:5173` and `http://localhost:5173` are admitted by default; the
API-only `IMP_UI_ALLOWED_ORIGINS` variable adds explicit origins for isolated UI runs.
Foreign or malformed origins and cross-site Fetch Metadata are refused. Browser
mutations require JSON. CORS reflects only an admitted origin; it never uses `*`.
The lifecycle service independently enforces the default UI origins before actions.
The UI dev server uses a strict port to preserve this contract.

Requests without browser markers retain the existing capability checks. Default
`LOOPBACK_TRUST` still trusts local processes; use the existing `ENFORCED` mode for
principal authentication. This remediation does not change the deployment's auth mode.
Unmapped mutations fail closed. Explicit POST reads (preview, stored evaluation
reproduction, bounded viewport demand) remain declared separately from writes.
Paper submit and replace retain account scope and order authority.

Forward-test session, decision, lock, observation and evaluation mutations are
account-scoped to the active Paper ledger. A viewer cannot mutate them and an
operator authorized for another account is refused. Read-view query parameters
cannot substitute a different account for mutation authorization (AUD-039).
