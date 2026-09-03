# ADR-0008: Operator Authentication and Account-Scoped Authorization

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-01 |

## Context

TD-005 required moving from `ROLE_ENFORCEMENT_STATUS=MODEL_ONLY_NOT_ENFORCED` to enforced authorization that maps authenticated operators to permitted `OperationalIdentity` contexts (ADR-0007).

P5 security foundations already provide:

- Operator role/capability matrix (`VIEWER` / `OPERATOR` / `ADMIN`)
- Hosting security config, redaction, secret-leak audit, readiness payloads

The localhost UI API historically bound to loopback without authentication (roadmap decision 6). TD-003 established operational account identity; TD-005 adds optional enforcement without breaking the loopback default.

## Decision

### Enforcement modes

| Mode | Env | Behavior |
|------|-----|----------|
| `LOOPBACK_TRUST` | default | Implicit local ADMIN principal; no session required; backward compatible |
| `ENFORCED` | `IMP_AUTH_ENFORCEMENT_MODE=ENFORCED` + `IMP_AUTH_PRINCIPALS_PATH` | Session required; roles and account ACL enforced |

`role_enforcement_status()` returns `LOOPBACK_TRUST` or `ENFORCED` accordingly.

### Principal registry

Configured principals file (`fixtures/auth/principals.json` pattern):

- `principal_id`, `display_name`, `role`, `secret`, `permitted_accounts` (`["*"]` or explicit account ids)

Secrets are SHA-256 digested at load; never returned by APIs.

### Session model

- Login: `POST /auth/login` with `principal_id` + `secret`
- Session token: `Authorization: Bearer <token>` or `X-IMP-Session`
- In-memory session store with TTL (`IMP_AUTH_SESSION_TTL_SECONDS`)
- Status: `GET /auth/status`, session: `GET /auth/session`, logout: `POST /auth/logout`

### Authorization boundary

Every ui_api route (except public auth status/login) resolves:

1. Authenticated principal (or `AUTH_REQUIRED`)
2. Route capability from `route_policy.py` (or `CAPABILITY_DENIED`)
3. Operational account scope when `account_id` / paper ledger / portfolio view applies (`ACCOUNT_ACCESS_DENIED`)

Canary admin commands require `role.manage` (ADMIN). Paper submit/cancel require operator capabilities on the paper ledger account.

### Security foundation wiring

- Response payloads pass `assert_no_secrets_in_payload` before send
- Structured logs use `build_log_line` redaction
- `GET /security/readiness` exposes auth enforcement state

### Frontend

- `AuthProvider` loads `/auth/status` and `/auth/session`
- `OperatorLoginGate` blocks workstation when enforcement requires login
- `fetchJson` / `postJson` propagate session token
- Paper action gates consult `permitsCapability("paper.order.submit")`

### P0 decision 6 amendment

Hosted multi-operator surfaces require identity. This ADR implements **local multi-user enforcement** via configured principals and does not implement external IdP/OIDC. A future hosted increment may add OIDC while retaining the same principal → role → account ACL model.

## Rejected alternatives

- **Global JWT/OIDC in this increment** — premature without hosting topology; principal registry suffices for local multi-user
- **Always-on auth on loopback** — breaks existing operator workstation default
- **Role enforcement without account ACL** — insufficient after TD-003 account isolation

## References

- ADR-0007 operational account identity
- `docs/superpowers/specs/2026-08-22-platform-p5-hosted-security-foundations-design.md`
- TD-005 goal scope
