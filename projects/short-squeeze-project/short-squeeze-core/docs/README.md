# Documentation index

Version **0.16.0**. This index maps **current-truth** product documentation for the
Short Squeeze Research Screener.

The product is a **read-only research screener**. It does not place orders, access
brokerage accounts, recommend trades, or claim predictive validation.

## Start here

| Audience | Document |
|---|---|
| New engineer or integrator | [Getting Started](getting-started.md) |
| Package overview | [../README.md](../README.md) |
| Integration handoff | [../HANDOFF_README.md](../HANDOFF_README.md) |
| What the product does not do | [LIMITATIONS.md](LIMITATIONS.md) |

## Tutorials (learning-oriented)

| Document | Outcome |
|---|---|
| [Getting Started](getting-started.md) | Clone → Python 3.12 venv → install → configure → run frozen demo → verify `/health` |

## How-to guides (task-oriented)

| Document | Task |
|---|---|
| [How-to guides](how-to-guides.md) | Cloud/Railway, providers, frozen demo, collectors, deploy-sync, morning checks, security locks |
| [Collectors](COLLECTORS.md) | Enable and operate supplemental evidence collectors |
| [Deployment](DEPLOYMENT.md) | Docker and Railway deploy boundary |
| [Railway IB Gateway](railway-ib-gateway.md) | Optional IBKR sidecar on Railway (private network) |
| [Integration](INTEGRATION.md) | Swap providers and run acceptance checks |

## Reference (information-oriented)

| Document | Contents |
|---|---|
| [CONFIGURATION.md](CONFIGURATION.md) | Precedence, environment variables, doctor |
| [API.md](API.md) | HTTP routes and integration contract |
| [openapi.json](openapi.json) | Static OpenAPI 3 description |
| [PROVIDERS.md](PROVIDERS.md) | Provider capabilities and admissibility |
| [METHODOLOGIES.md](METHODOLOGIES.md) | Scoring dimensions, thresholds, labels |
| [TESTING.md](TESTING.md) | Offline test commands |
| [SECURITY.md](SECURITY.md) | Credential boundary and opt-in API locks |
| [CLI and Make](CLI.md) | Entrypoints and Makefile targets |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [../.env.example](../.env.example) | Environment template (placeholders only) |

## Explanation (understanding-oriented)

| Document | Topic |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Surfaces, runtime, evidence pipeline, release boundary |
| [Reproducibility](reproducibility.md) | Frozen/offline vs live credentials; research vs live app |
| [LIMITATIONS.md](LIMITATIONS.md) | Explicit non-goals and incomplete validation |

## Ports and modes (quick facts)

| Fact | Value |
|---|---|
| Default local port | `8787` (`PORT`, binds `127.0.0.1` in local/frozen) |
| Docker Compose host URL | `http://127.0.0.1:8787/` (maps host `8787` → container `8080`) |
| Container / Railway listen | `0.0.0.0:$PORT` (Compose sets `PORT=8080` inside the container) |
| Modes | `LOCAL_FULL`, `CLOUD_PROVIDER_MODE`, `FROZEN_DEMO` |

## Architecture decisions

Product behavior constraints live in [adr/](adr/). Release and privacy audit notes are
in [release/](release/).
