# Integrated Market Platform — Agent Instructions

**Mission:** Governed local market operating workstation (Demo replay, Paper simulation, Live observational). Safety and source-backed data are non-negotiable.

## Required first reads

1. [docs/README.md](docs/README.md) — documentation map and authority hierarchy
2. [docs/architecture/MODE_AUTHORITY.md](docs/architecture/MODE_AUTHORITY.md) — **safety invariants**
3. [docs/engineering/ENGINEERING_HANDBOOK.md](docs/engineering/ENGINEERING_HANDBOOK.md)
4. [docs/engineering/WORK_LOG.md](docs/engineering/WORK_LOG.md) — recent changes (newest first)

Scoped guides: [ui/AGENTS.md](ui/AGENTS.md), [paper/AGENTS.md](src/market_platform_foundation/paper/AGENTS.md)

## Critical safety invariants

- **No Live production execution** — LIVE-001 blocked; Live mode is read-only
- **Paper** requires backend `INTERNAL_SIMULATION` + `PAPER_ONLY` + env gates — frontend `canUsePaperActions` is UX only
- **Workspace** is the canonical Paper submit boundary — Paper Command hands off, does not submit
- **Fail closed** on authority loss, stale preview, schema mismatch on write
- **Never fabricate** market data, authority, or API shapes — inspect schemas
- **Backward compatibility** — optional fields by default; legacy records stay valid

## Inspect before inventing

Search existing `Mode*Route`, `*Observability`, `paper/`, `queryKeys` before new abstractions.

## Query-key rule

Same React Query key ⇒ same fetch semantics and response shape. Add keys to `ui/src/api/hooks.ts` `queryKeys`. See [ADR-0004](docs/architecture/adr/0004-react-query-key-invariants.md).

## Validation minimums

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed    # after each edit
cd ui && npm test && npm run build                    # UI changes
.venv\Scripts\python.exe tools\validate.py full       # major checkpoint / Paper safety
```

CI runs `fast` + `changed` only. Details: [VALIDATION.md](docs/engineering/VALIDATION.md), [VALIDATION_ARCHITECTURE.md](docs/engineering/VALIDATION_ARCHITECTURE.md).

| Change | Minimum validation |
|--------|-------------------|
| Docs only | `tools/check_docs_links.py` if links changed |
| UI | vitest + build + validate changed |
| Backend | validate changed |
| Paper safety | full + vitest + build |

## Work logging (required)

After substantive work, append to [WORK_LOG.md](docs/engineering/WORK_LOG.md) **before ending the turn** — template at top of file. Enforced by `.cursor/rules/work-logging.mdc`.

Large features: completion record under `docs/superpowers/plans/`.

## Local environment (Windows)

CPython **3.11** in `.venv` (not system Python):

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
```

Setup: [LOCAL_DEVELOPMENT.md](docs/engineering/LOCAL_DEVELOPMENT.md)

## Cursor Cloud

```bash
bash .cursor/install-cloud-deps.sh
export PYTHONPATH=src
python tools/validate.py changed
```

See [CURSOR_CLOUD_ENVIRONMENT.md](docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md).

## SOPs (when applicable)

- API/schema: [API_SCHEMA_CHANGE.md](docs/engineering/sops/API_SCHEMA_CHANGE.md)
- Paper execution: [PAPER_EXECUTION_CHANGE.md](docs/engineering/sops/PAPER_EXECUTION_CHANGE.md)
- Debugging: [DEBUGGING.md](docs/engineering/sops/DEBUGGING.md)

## AI workflow

[AI_AGENT_GUIDE.md](docs/engineering/AI_AGENT_GUIDE.md) · [AI_MODEL_STRATEGY.md](docs/engineering/AI_MODEL_STRATEGY.md)

## Definition of done

[DEFINITION_OF_DONE.md](docs/engineering/DEFINITION_OF_DONE.md)
