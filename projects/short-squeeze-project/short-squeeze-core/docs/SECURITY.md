# Security

## Credential boundary

Credentials are runtime configuration, not source. `.env`, `.private`, tokens,
cookies, authenticated URLs, and provider caches are prohibited from the handoff
release. `.env.example` contains placeholders only. The repository gitignores
`.env` and `.env.*` while keeping `.env.example` tracked.

## Runtime boundary

| Mode | Private file | Local IBKR probe | Bind |
|---|---|---|---|
| `FROZEN_DEMO` | Not loaded | No | Loopback |
| `CLOUD_PROVIDER_MODE` | Not loaded | No local probe | `0.0.0.0:$PORT` |
| `LOCAL_FULL` | Allowed | Optional | Loopback |

The application exposes no account, position, order, execution, or trading
capability.

## Output boundary

Public API errors and release tools omit secret values, private absolute paths,
tracebacks, and personal identifiers. The release audit reports category, relative
path, line number, and counts while withholding matched content.

## Opt-in API hardening (default off)

These flags keep a public demo URL usable until operators intentionally enable
them. Set via process environment or platform secrets (see `.env.example`).

| Variable | Default | Effect |
|---|---|---|
| `CSRF_PROTECTION` | off | When `1`/`true`, state-changing requests require `X-CSRF-Token` matching the `squeeze_csrf` cookie from `GET /api/csrf-token` |
| `LOCK_SENSITIVE_API` | off | When `1`/`true`, cloud mode rejects unauthenticated `/api/export`, `/api/logs/*`, and `/api/collectors/*` unless a valid CSRF cookie/header pair is present. `LOCAL_FULL` remains open |

If a CSRF cookie is already present, mutating requests validate it even when
`CSRF_PROTECTION` is off (soft-gate for local UI adoption without redeploy secrets).

Enable only after clients can obtain and send the token pair. Recipe:
[how-to-guides.md](how-to-guides.md#enable-optional-security-locks).

## Deploy mirror integrity

Before Railway upload, run `python tools/check_railway_mirror.py` (or
`make check-railway-mirror`) so `.railway-deploy/` matches `apps/`, `src/`,
`scripts/`, `tools/`, and `pyproject.toml`. The check does not modify files.

## Operator responsibilities

- Store credentials in the deployment platform's secret manager.
- Use a unique read-only IBKR client identifier.
- Apply provider rate limits and entitlements.
- Run the release audit and an independent secret scanner before distribution.
- Rotate any credential found in tracked content; the application does not rotate
  credentials automatically.
- Do not commit `.env` or `.private/providers.env`.
