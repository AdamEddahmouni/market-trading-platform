# Reproducibility

What you can reproduce from the repository alone, and what requires live
credentials or operator infrastructure.

## Paths

| Path | Credentials | Network | Deterministic? |
|---|---|---|---|
| `FROZEN_DEMO` app + frozen API | None | None (after install) | Yes — 13 candidates, fixed rule outcomes |
| Offline pytest suite | None | None (synthetic fakes) | Yes |
| `tools/integration_acceptance.py --mode frozen` | None | None | Yes |
| Canonical / Phase research scripts on bundled fixtures | Usually none | None | Yes when inputs are frozen files |
| `CLOUD_PROVIDER_MODE` live screen | Cloud provider keys | Yes | No — depends on upstream data |
| `LOCAL_FULL` live screen | Local/private providers + optional IBKR | Yes | No |
| Phase 3E stage-2 outcome acquisition | IBKR (historical) at acquisition time | Yes at capture time | Captured artifacts are fixed; re-fetch needs IBKR |
| Railway production | Platform secrets | Yes | No |

## Frozen and offline

- Bundled frozen demonstration data ships with the app; it is sanitized and
  provider-independent.
- Normal tests must not call Finviz, NewsAPI, Finnhub, SEC, IBKR, or Railway.
- Integration acceptance in `--mode frozen` checks versions, frozen totals,
  methodologies, and absence of trading/account endpoints.

## Live credentials

Required only when you enable the corresponding provider or collector:

- Finviz Elite export token → `FINVIZ_API_KEY`
- NewsAPI → `NEWSAPI_KEY`
- Finnhub → `FINNHUB_KEY`
- SEC EDGAR → descriptive `SEC_USER_AGENT` (public API; still identify your client)
- IBKR Gateway → host/port/client id; login user/password for containerized Gateway
- Optional collectors → see [COLLECTORS.md](COLLECTORS.md)

Never commit `.env` or `.private/`. Use `.env.example` placeholders only.

## Research tooling vs live app

| Concern | Live research screener | Research / phase tooling |
|---|---|---|
| Purpose | Current candidates, methodologies, provider health | Point-in-time evidence, rule outcomes, cohort analyses |
| Entry | `apps.research_screener`, `start_local.py`, `start_cloud.py` | Scripts under `scripts/` and documented phase reports |
| Phase 3D | Consumes verified acquisition packages as descriptive foundation | Packages remain integrity-preserving evidence |
| Phase 3E | Not part of the live scoring loop | Stage-2 outcome acquisition for the pilot cohort is recorded in historical docs; it does not imply predictive validation of the product |

## Admissibility (short)

Provider fields are tagged `RESEARCH_ADMISSIBLE`, `RESEARCH_INADMISSIBLE`, or
`DISPLAY_ONLY`. Methodologies score only admissible evidence. Missing or
conflicted inputs stay `UNKNOWN` / withheld rather than coerced to zero.

Product rules that affect reproducibility of scores (0.16.0):

- Evidence-gated scoring floor uses Finviz-supported weight (**65%**); low coverage
  alone does not force `UNEVALUABLE` when both dimensions score.
- SEC catalyst age uses filing `filed_at`.
- Finviz mapping conflicts are withheld from scoring.
- Estimated DTC and Finviz day-change remain display-only.
- Borrow availability % float is research-admissible when **both** IBKR and Finviz
  legs are eligible.

See [METHODOLOGIES.md](METHODOLOGIES.md) and [PROVIDERS.md](PROVIDERS.md).
