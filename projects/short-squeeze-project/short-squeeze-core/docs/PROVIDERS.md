# Providers

## Provider capabilities

| Provider | Capabilities used by this app | Account, plan, or entitlement condition | Cloud |
|---|---|---|---|
| [Finviz Elite](https://elite.finviz.com/help/faq) | Scanner fields, Float, Short Float (SI %), Short Ratio (DTC), Relative Volume, Shares Outstanding, and news export | Active Elite subscription and valid export/API access. The current advertised plans are a 7-day trial, $39.50 monthly, or $299.50 annually; all paid Elite plans expose the same feature set. | Yes |
| [NewsAPI](https://newsapi.org/pricing) | Timestamped symbol-associated display news | API key. The free Developer plan is strictly for development/testing, has a 24-hour article delay and 100 requests/day, and may not be used in staging or production (including internal production). Production requires a paid plan. | Yes |
| [Finnhub Company News](https://finnhub.io/docs/api/company-news) | Current quote fallback and company news | API key. The documented Free tier includes one year of Company News and new updates for North American companies. An actual 403 is reported as account/request access denial, not inferred as a plan requirement. | Yes |
| [SEC EDGAR](https://www.sec.gov/about/developer-resources) | Public filings and filing metadata (`filed_at` for catalyst age) | No API key. A descriptive `SEC_USER_AGENT` is required for automated access; requests must comply with SEC fair-access guidance (currently no more than 10 requests/second). | Yes |
| [ProsusAI FinBERT](https://huggingface.co/ProsusAI/finbert) | Local per-headline financial sentiment | Local model deployment with the optional `torch`/`transformers` dependencies. Model labels are positive, negative, and neutral. The application may report `MIXED` only as an aggregate outcome across multiple headlines. | No |
| [IBKR API](https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/) | Read-only market data, bars, scanner, shortability, shortable shares, and halted status | Open IBKR Pro account, Market Data API acknowledgement, applicable exchange subscriptions, and normally at least $500 account equity plus subscription costs. Entitlements vary by field and exchange. | Remote Gateway only |
| IBKR Borrow Fee | No live retrieval currently | The adapter is a placeholder. It does not claim a generic tick or a specific entitlement until the correct API mechanism is verified against the target IBKR session. | No |

## Evidence admissibility

Fields carry a `research_admissibility` tag:

- `RESEARCH_ADMISSIBLE`: Meets unit, time-basis, provenance, and freshness requirements for methodology evaluation.
- `RESEARCH_INADMISSIBLE`: Display or supplemental; a matching provider field name does not imply semantic compatibility.
- `DISPLAY_ONLY`: Rendered but never enters a methodology or rule.

### Research-admissible fields (current pipeline)

| Field | Provider | Admissibility |
|---|---|---|
| `float_shares` | Finviz Elite | `RESEARCH_ADMISSIBLE` |
| `published_short_interest` (SI %) | Finviz Elite | `RESEARCH_ADMISSIBLE` |
| `days_to_cover` | Finviz Elite Short Ratio | `RESEARCH_ADMISSIBLE` |
| `relative_volume` | Finviz Elite | `RESEARCH_ADMISSIBLE` |
| `percentage_change` | IBKR canonical return | `RESEARCH_ADMISSIBLE` |
| `completed_bar_acceleration` | IBKR (computed) | `RESEARCH_ADMISSIBLE` |
| `catalyst_age_hours` | Computed (news + SEC `filed_at`) | `RESEARCH_ADMISSIBLE` |
| `borrow_availability_pct_float` | IBKR + Finviz (both legs required) | `RESEARCH_ADMISSIBLE` |
| `borrow_fee` | IBKR (secondary) | `RESEARCH_ADMISSIBLE` |

Display-only / research-inadmissible proxies (shown, not scored): estimated DTC from
Short Float / Avg Volume, and Finviz day-change when IBKR `PERCENTAGE_RETURN` is
missing. Conflicting Finviz field mappings are withheld from scoring.

## Configuration

Each credential-bearing provider has an `*_ENABLED` switch. Disabled providers
report `DISABLED`. Enabled providers without required credentials report
`NOT_CONFIGURED`.

Providers retain last-good cached results where implemented and surface failures
without converting stale data into fresh evidence. Rate limits, licenses, plans,
and entitlements remain the provider account owner's responsibility and must be
revalidated before a production deployment.

Setup recipes: [how-to-guides.md](how-to-guides.md#enable-providers-ibkr--finviz--news--sec).
Variable reference: [CONFIGURATION.md](CONFIGURATION.md).
