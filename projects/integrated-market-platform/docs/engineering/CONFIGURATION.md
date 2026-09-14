# Configuration

**Status:** Environment variable reference.  
**Template:** [.env.example](../../.env.example) (never commit real values).

## Application

| Variable | Required | Sensitive | Notes |
|----------|----------|-----------|-------|
| `PYTHONPATH=src` | dev/test | no | Set for validation |
| `ANTHROPIC_API_KEY` | optional | **yes** | MRA-002 LLM |
| `IMP_ASSISTANT_PROVIDER` | optional | no | `anthropic` \| `grounded` |
| `IMP_ASSISTANT_STUB` | optional | no | Force abstaining stub |

## Paper execution

| Variable | Default | Notes |
|----------|---------|-------|
| `IMP_PAPER_EXECUTION` | off | Enable paper API |
| `IMP_LIVE_INTERNAL_SIMULATION` | off | Interactive simulation |
| `IMP_PERSIST_STATE` | off | SQLite local state |
| `IMP_STATE_DIR` | optional | State directory override |
| `IMP_CANONICAL_STATE_DIR` | optional | Primary-workstation `.local` path for `python tools/imp.py state-path` comparison (see [STATE_PATH_OPERATOR_CONVENTION.md](STATE_PATH_OPERATOR_CONVENTION.md)) |

## Live observational

| Variable | Default | Notes |
|----------|---------|-------|
| `IMP_LIVE_OBSERVATIONAL` | off | Live data mode |
| `IMP_MOOMOO_LIVE` | off | Observational only — not execution |
| `IMP_MOOMOO_HOST` | 127.0.0.1 | Loopback only |
| `IMP_MOOMOO_PORT` | 11111 | OpenD port |

## Providers (opt-in live)

Each provider has `IMP_*_LIVE=1` gate + credential vars. See `.env.example` and `docs/providers/`.

## Broker paper (P4 sandbox)

| Variable | Notes |
|----------|-------|
| `IMP_TRADIER_PAPER=1` | Enable adapter |
| `IMP_BROKER_PAPER_EXECUTION=1` | Broker paper authority |
| `IMP_TRADIER_TOKEN` | **Sensitive** — sandbox only |
| `IMP_TRADIER_ENDPOINT` | Must be sandbox URL |
| `IMP_ALPACA_PAPER=1` | Enable Alpaca Paper adapter (stdlib urllib; no SDK) |
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | **Sensitive** — Paper keys only; missing → `COMPARATOR_NOT_CONFIGURED` |
| `APCA_API_BASE_URL` | Must be `https://paper-api.alpaca.markets`; live host `LIVE_FORBIDDEN` |
| `IMP_ALPACA_PAPER_HTTP=1` | Opt-in Paper HTTPS (first probe `GET /v2/account`) |

## Testing / debug

| Variable | Notes |
|----------|-------|
| `IMP_TEST_MONGODB_URI` | Optional Mongo integration tests |
| `IMP_LIVE_FIXTURE_FEED` | Offline live-runtime testing |

## Restart after flag changes

API does not hot-reload env. Use `tools/ui1/restart_ui_api.ps1` or restart launcher.

Full provider-specific docs: [docs/providers/](../providers/).
