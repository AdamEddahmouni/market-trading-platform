# Operator authentication onboarding (TD-005)

## Default (loopback workstation)

No configuration required. The UI API uses `LOOPBACK_TRUST`: implicit local ADMIN, no login gate, `role_enforcement_status=LOOPBACK_TRUST`.

## Local multi-user enforcement

1. Copy `fixtures/auth/principals.json` to a private path (e.g. `.private/auth-principals.json`) and edit principals/secrets.
2. Set environment before starting the UI API:

```bash
export IMP_AUTH_ENFORCEMENT_MODE=ENFORCED
export IMP_AUTH_PRINCIPALS_PATH=/path/to/auth-principals.json
export IMP_AUTH_SESSION_TTL_SECONDS=86400
```

3. Restart the platform. The UI shows a sign-in gate until a valid principal logs in.
4. Principals receive only `permitted_accounts` listed in the registry (`"*"` = all operational accounts).

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /auth/status` | Enforcement mode and whether session is required |
| `GET /auth/session` | Current session (Bearer token optional) |
| `POST /auth/login` | `{ "principal_id", "secret" }` → session token |
| `POST /auth/logout` | Revoke current session |
| `GET /security/readiness` | Auth + gate readiness (requires `security.config.read`) |

Send `Authorization: Bearer <token>` or `X-IMP-Session: <token>` on subsequent requests.

## Roles

| Role | Paper submit/cancel | State write | Admin / role.manage |
|------|---------------------|-------------|---------------------|
| VIEWER | No | No | No |
| OPERATOR | Yes | Yes | No |
| ADMIN | Yes | Yes | Yes |

Account ACL is independent: a VIEWER with `fp-canary-local` can read that canary account but cannot submit paper orders.

## Intelligence ingest (agent enrichment)

| Route | Capability | LOOPBACK_TRUST | ENFORCED |
|-------|------------|----------------|----------|
| `POST/PUT /intelligence/ingest/enrichment` | `intelligence.ingest.write` | Implicit ADMIN | Session + OPERATOR or ADMIN |

VIEWER principals cannot call ingest routes even when they can read scoped accounts.

For any UI API surface exposed beyond loopback (hosted agent runners, tunnel, reverse proxy), set `IMP_AUTH_ENFORCEMENT_MODE=ENFORCED` and configure principals before enabling agent automation.

Optional fail-closed guard for ingest-only deployments:

```bash
export IMP_INTELLIGENCE_INGEST_REQUIRE_ENFORCED=true
```

When set, ingest handlers reject requests while auth remains in `LOOPBACK_TRUST` (`INTELLIGENCE_INGEST_LOOPBACK_TRUST_FORBIDDEN`).

See [INTELLIGENCE_INGEST_BOUNDARY_SECURITY.md](../architecture/INTELLIGENCE_INGEST_BOUNDARY_SECURITY.md).

## Hosted path (deferred)

External OIDC/SSO is not implemented in TD-005. A future increment can map IdP identities onto the same principal registry and ACL model (ADR-0008).
