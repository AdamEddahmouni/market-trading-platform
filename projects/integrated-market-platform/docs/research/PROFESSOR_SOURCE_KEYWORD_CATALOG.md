# Professor source and keyword catalog (Lane D)

**Status:** `RESEARCH_ONLY` — structured characterization for professor sequencing and FTEP
news/catalyst planning. Does **not** authorize procurement, credentials, or runtime
provider selection changes.

**Machine-readable catalog:** [`PROFESSOR_SOURCE_KEYWORD_CATALOG.json`](./PROFESSOR_SOURCE_KEYWORD_CATALOG.json)  
**JSON Schema (documentation):** [`PROFESSOR_SOURCE_KEYWORD_CATALOG.schema.json`](./PROFESSOR_SOURCE_KEYWORD_CATALOG.schema.json)

## Relationship to existing IMP docs

| Document | Role |
|----------|------|
| [PROVIDER_CANDIDATE_CATALOG_2026-09-11.md](./PROVIDER_CANDIDATE_CATALOG_2026-09-11.md) | Broad vendor universe (external research) |
| [PROVIDER_AND_DATA_RESEARCH_MATRIX.md](./PROVIDER_AND_DATA_RESEARCH_MATRIX.md) | Selection economics and sparse planning rows |
| [NEWS_EVENT_FOUNDATION.md](../architecture/NEWS_EVENT_FOUNDATION.md) | Runtime news/event contract and trust catalog semantics |
| [NEWS_SOURCES.md](../providers/NEWS_SOURCES.md) | NewsAPI/Finnhub/Finviz operator wiring |
| [PROVIDER_READINESS.md](../engineering/PROVIDER_READINESS.md) | Local gates and probes |
| `news/sources.py` / `news/catalysts.py` | In-code `CONFIGURED` vs `OPERATIONAL` and keyword registry |
| `artifacts/wave-a-findings/news-data-inventory.json` | Wave A configured_not_operational headline vendors |

## Frozen runtime policy (Lane D)

- G7, OpenD primary L1, Yahoo overlay-only honesty, Finviz hop gating, and Path A
  boundaries are unchanged.
- Seven professor-named headline sources remain **`CONFIGURED`** in
  `SourceTrustCatalog` until a separate activation increment wires adapters.
- Every catalog row sets `access_in_imp_claimed` explicitly; **false** means
  documentation or adapter existence does not assert operator access on this machine.

## Catalyst taxonomy

The JSON `catalyst_taxonomy` section maps professor-requested categories to
`DEFAULT_CATALYST_REGISTRY` entries in `news/catalysts.py` and flags gaps
(buybacks, dividends, litigation, geopolitical, unusual volume, short squeeze,
options activity) as **research extensions only** — no registry code change in
this lane.

## Project store mirror

User-facing narrative and tables for the IMP Project live at the Project Agent
Store `docs/professor-source-keyword-catalog.md` (maintained in Lane D receipt
`internal/lane-d-sources.md`).
