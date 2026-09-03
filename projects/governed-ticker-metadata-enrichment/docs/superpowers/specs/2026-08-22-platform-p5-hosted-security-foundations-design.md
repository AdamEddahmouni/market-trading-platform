# Platformization P5 — Hosted Security Foundations (design spec)

**Status:** Implemented (foundations only — no hosting, no enforcement)
**Roadmap:** [PLATFORMIZATION_ROADMAP.md](../../research/PLATFORMIZATION_ROADMAP.md) milestone **P5** ("Hosted platform, security, PROVIDER-COMMERCIAL-001" — *Not started* → foundations seeded 2026-08-22)
**Scope guard:** offline/fixture/sandbox only. `LIVE-001` production execution stays blocked. No cloud-specific YAML, no deployment artifacts, no production service, **no hosted auth implemented**.
**Date:** 2026-08-22

## 1. Purpose and boundary

P5 as scoped here delivers **neutral, locally-executable prerequisites** for a
future hosting effort — not hosting itself. The platform today is a localhost
operator workstation: `ui_api/server.py` is a stdlib `BaseHTTPRequestHandler`
bound to loopback with no authentication (and `Access-Control-Allow-Origin: *`
on every response). That posture is correct for the current threat model and
is **unchanged** by this work.

Respecting the P0-locked architecture decision 6 (*"Local durable state … No
custom JWT, no hosted auth"*): nothing in this package implements auth,
sessions, or tokens. Where a future hosted variant would need an identity
model, this work records data and decision points instead of mechanisms
(§5, §7).

## 2. Threat model

| Horizon | Surface | Adversary / failure | Posture |
|---|---|---|---|
| **Today** | Loopback HTTP UI (`127.0.0.1`), local SQLite state, env-file credentials | Local malware reading `.env`/state DB; secrets leaking into logs, error payloads, committed evidence; accidental non-loopback rebind during refactors | Fail-closed defaults + redaction/audit utilities reduce blast radius; bind allowlist makes an accidental exposure a validation error, not a silent default |
| **LAN tomorrow** | Same server bound wider (e.g., tablet on desk) | Anyone on LAN can read portfolio/order state; CSRF-style POSTs from browser tabs; unbounded bodies | Config schema forces explicit opt-in + external TLS termination + rate limiting before any non-loopback bind is even *valid* |
| **Hosted later** | Multi-user hosted UI, PROVIDER-COMMERCIAL-001 broker credentials server-side | Credential exfiltration via logs/responses; privilege confusion between operators; readiness endpoints disclosing internals | Secret-leak audit gates payloads/log lines; roles model records who may do what; readiness payload is deterministic and gate-scoped |

Non-goals (explicitly out of scope): DDoS defense, WAF rules, tenant
isolation, key rotation services, audit-log tamper evidence at scale.

## 3. Incident-safe defaults

Every knob fails toward the safer state:

1. **Bind allowlist:** loopback-only (`127.0.0.1`, `::1`, `[::1]`,
   `localhost`). A non-loopback host is invalid unless `ALLOW_NON_LOOPBACK`
   is explicitly truthy **and** TLS termination is declared
   `TERMINATED_AT_REVERSE_PROXY` **and** rate limiting stays enabled.
2. **TLS assumption documented:** the process serves plain HTTP; any remote
   exposure must be terminated at a reverse proxy in front. The config
   carries the assumption rather than pretending the app can do TLS.
3. **Bounded bodies:** max request body size exists by default (1 MiB,
   ceiling 64 MiB) so a future write endpoint cannot inherit unbounded-read
   assumptions.
4. **Rate limiting present:** parameters validated and on for remote binds;
   disabling them remotely fails validation.
5. **Over-redaction:** secret-shaped keys are matched broadly (substring,
   case/separator-insensitive). False positives redact benign fields — safe;
   false negatives leak — unsafe.
6. **Fail-closed parsing:** malformed config values raise
   `SecurityConfigError`; nothing silently coerces to a weaker setting.
7. **Determinism:** readiness/log builders inject no wall clock; identical
   inputs give byte-identical output (replay-safe, snapshot-testable).

## 4. What is implemented vs deferred vs principal-decision

### Implemented now (pure additions, wired nowhere destructive)

Package `src/market_platform_foundation/platform/security/` (stdlib-only):

| Module | Surface |
|---|---|
| `config.py` | `HostingSecurityConfig` / `RateLimitParameters` frozen dataclasses; `validate() → tuple[str,…]` error codes; `validated()` raising `SecurityConfigError`; `parse_security_config(mapping)`; `load_security_config(env=None)`; `with_overrides()`; sentinels `LOOPBACK_BIND_HOSTS`, `TLS_TERMINATION_{NONE,EXTERNAL,MODES}`, `DEFAULT_BIND_HOST=127.0.0.1`, `DEFAULT_BIND_PORT=8766` (matches existing UI API port), body-size bounds. Env namespace `IMP_SEC_*`. |
| `redaction.py` | `REDACTED="<REDACTED>"`; `SECRET_KEY_MARKERS`; `normalize_key`; `is_secret_key`; recursive `redact_mapping` (dict/list/tuple preserving); `redact_log_line` (JSON/KV/header/query shapes); `build_log_line(event, *, level, fields, provenance)` → deterministic canonical JSON with redaction applied. |
| `leak_audit.py` | `SecretFinding` (path + reason + SHA-256 fingerprint prefix — never the value); `scan_snapshot` (config/env dicts, nested); `audit_text` (reuses governed `credential_audit.SECRET_SCAN_RULES` regexes verbatim); `assert_no_secrets_in_payload` raising `SecretLeakError`; `PLACEHOLDER_VALUES`. |
| `readiness.py` | `build_readiness_payload(*, gates, mode_context, checks, schema)` — pure, sorted, gate-derived `READY`/`NOT_READY` with `failing_gates`; `collect_default_gates(env)` mirrors the operator `safety` projection shape without importing UI internals; `render_readiness_json`. |
| `roles.py` | `OperatorRole` str-enum (`VIEWER`/`OPERATOR`/`ADMIN`); `CAPABILITIES`; monotone `ROLE_CAPABILITY_MATRIX` checked by `assert_matrix_invariants()` at import (fails loudly if edited into a non-order); `capabilities_for_role`, `role_allows`; `ROLE_ENFORCEMENT_STATUS = "MODEL_ONLY_NOT_ENFORCED"`. |

Tests: `tests/platform/test_security_foundations_p5.py` — 36 tests covering
the fail-closed config matrices, adversarial redaction casing/nesting,
structural + textual secret-leak assertions, readiness determinism/key-order
independence, and role-matrix invariants. All green:
`PYTHONPATH=src .venv/Scripts/python.exe -m unittest tests.platform.test_security_foundations_p5 -v`.

Zero behavior change to existing endpoints/modules: nothing imports the new
package except its own tests.

### Deliberately deferred (with why)

- **Wiring redaction into `ui_api/server.py` log/error paths.** server.py is
  owned by another worker mid-change; the helper is exported and ready
  (`from ...platform.security import redact_log_line, build_log_line`) but
  integration must be a coordinated follow-up to avoid colliding edits.
- **Any auth/session/token mechanism.** P0-locked decision; also genuinely
  premature without a chosen hosting topology.
- **Rate-limit/body-limit enforcement in the handler.** Enforcement without
  a real deployment target would be untested theater; the validated schema
  makes future enforcement mechanical.
- **Readiness HTTP endpoint.** Same ownership/timing reason as redaction
  wiring; the builder is the reusable part.
- **Cloud/deployment specifics (no YAML).** Roadmap names no target platform;
  inventing one would violate the neutral-foundations scope.

### Principal decision points (recorded, not decided)

1. **Amendment to roadmap decision 6?** A hosted multi-operator surface needs
   *some* identity model (SSO/OIDC against an IdP is the boring answer).
   Requires explicit principal approval to amend "no hosted auth"; nothing
   here presumes the outcome.
2. **Hosting topology & TLS owner** (which proxy terminates TLS, where
   `IMP_SEC_TLS_TERMINATION=TERMINATED_AT_REVERSE_PROXY` gets set).
3. **PROVIDER-COMMERCIAL-001 commercial terms**, including which provider
   credentials may live server-side and under what custody.
4. **Role matrix contents** — capability names and VIEWER/OPERATOR/ADMIN
   boundaries are a starting draft for operator review.
5. **Whether readiness/gates detail may leave loopback** (a public
   `/healthz` discloses internal gate names; today's shape assumes trusted
   readers).

## 5. Roles model (recorded, NOT enforced)

```
VIEWER ⊆ OPERATOR ⊆ ADMIN            (import-time invariant)
VIEWER   = {state.read, audit.read, security.config.read}
OPERATOR = VIEWER ∪ {state.write, paper.order.submit, paper.order.cancel}
ADMIN    = CAPABILITIES (all eight)
ROLE_ENFORCEMENT_STATUS = "MODEL_ONLY_NOT_ENFORCED"
```

No request path consults this matrix. Any consumer must surface the
enforcement-status sentinel so the data model cannot masquerade as a control.

## 6. Integration note for ui_api (follow-up)

When server.py ownership frees up, the minimal integration is:

```python
from ..platform.security import build_log_line, redact_log_line
# route print(...)-style diagnostics through build_log_line(...)
# run assert_no_secrets_in_payload(payload) before _send_json on debug paths
```

That change touches an owned file and is intentionally **not** part of this
delivery.

## 7. Verification

- `tests.platform.test_security_foundations_p5`: **36 tests OK** (run command
  above).
- Existing modules untouched (`git status` shows additions only from this
  worker's scope); no dependency changes; no workflow/YAML files touched; no
  live gates exercised.
