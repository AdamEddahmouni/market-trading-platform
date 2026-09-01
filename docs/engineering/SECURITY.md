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
