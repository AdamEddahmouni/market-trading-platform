# Integration API Contract

API version: `1.0.0`

Schema version: `batch14.integration.v1`

The generated manifest is available at `GET /api/v1/integration/manifest`; the sanitized
fixture is `apps/research_screener/demo_data/integration_manifest_v1.json`.

Stable routes:

- `GET /health`, `GET /ready`;
- `GET /api/health`, `GET /api/readiness`, `GET /api/providers`;
- `GET /api/frozen/candidates`, `GET /api/frozen/candidate/<symbol>`;
- `GET /api/current/candidates`, `GET /api/current/candidate/<symbol>`;
- `POST /api/current/refresh`, `POST /api/discovery/refresh`;
- `GET /api/methodologies`, `GET /api/methodologies/<symbol>`;
- `GET|POST /api/export`;
- `GET /api/v1/integration/manifest`.

Envelope:

```json
{
  "api_version": "1.0.0",
  "schema_version": "batch14.integration.v1",
  "mode": "CLOUD_PROVIDER_MODE",
  "as_of": "2026-07-25T23:00:00Z",
  "data": {},
  "status": "OK",
  "missingness": [],
  "provenance": {
    "application": "short-squeeze-research-screener",
    "predictive_validation": "NOT_COMPLETED"
  }
}
```

Methodology results contain explicit nullable `pressure` and `ignition`, coverage,
known/missing inputs, supporting evidence, blocking/conflict reasons, calculation/as-of
times, experimental status, and predictive-validation status. Missing values are null,
never zero. Legacy compatibility aliases retain prior top-level fields alongside the
versioned `data` copy.

Classification enums: `PRIME`, `SUBPRIME`, `WATCH`, `NOT_QUALIFIED`, `UNEVALUABLE`,
`CONFLICTED`, and `REFERENCE_DEFINITION_INCOMPLETE`. Trend enums: `ASCENDING`,
`DESCENDING`, `FLAT`, and `INSUFFICIENT_HISTORY`.

The API exposes no token, cookie, password, private path, authenticated URL, account
identifier, order method, trading method, probability, expected return, target, or stop.
