# Integration

## Stable contracts

- API version: `1.0.0`
- Integration schema: `batch14.integration.v1`
- Health path: `/health`
- Readiness path: `/ready`
- Manifest path: `/api/v1/integration/manifest`
- Product version: `0.16.0` (`pyproject.toml`)

New response fields are additive. Integrations must tolerate explicit nulls and
unknown enum values. A missing value is never equivalent to zero.

## Acceptance

```bash
python tools/integration_acceptance.py --mode frozen
python tools/integration_acceptance.py --url http://127.0.0.1:8787 --json
```

Acceptance verifies versions, frozen totals, providers, methodologies, manifest,
exports, and the absence of trading/account endpoints.

## Provider swap

Change the provider environment value, restart, run the doctor, then verify
`GET /api/providers`. No source edit is required. Disable unused providers
explicitly with `*_ENABLED=false`.

## Security boundary

Integrators receive source and safe demonstration data, not existing provider
credentials, private raw evidence, account data, or Git history.

Optional hardening (`CSRF_PROTECTION`, `LOCK_SENSITIVE_API`) defaults off. See
[SECURITY.md](SECURITY.md) before enabling on a shared URL.

## Further reading

- [Getting Started](getting-started.md)
- [API.md](API.md)
- [CONFIGURATION.md](CONFIGURATION.md)
- [../INTEGRATION_CHECKLIST.md](../INTEGRATION_CHECKLIST.md)
