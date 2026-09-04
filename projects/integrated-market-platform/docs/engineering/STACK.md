# Technology Stack

**Status:** Strategic inventory — verify versions in manifests, not here.

| Layer | Technology | Config |
|-------|------------|--------|
| **Runtime** | CPython 3.11.15 | `.venv`, `phase0-dependency-lock.json` |
| **Frontend framework** | React 18 + TypeScript | `ui/package.json`, `ui/tsconfig.json` |
| **Build** | Vite 5 | `ui/vite.config.ts` |
| **Routing** | React Router 6 | `ui/src/App.tsx` |
| **Server state** | TanStack Query 5 | `ui/src/api/hooks.ts` |
| **Validation (FE)** | Zod 3 | `ui/src/api/schemas.ts` |
| **Charts** | Lightweight Charts, Recharts | lazy where possible |
| **FE tests** | Vitest 2 + Testing Library | `ui/vitest` config |
| **BE tests** | unittest | `tools/validation_manifest.json` |
| **Validation orchestrator** | `tools/validate.py` | manifest-driven |
| **UI API** | stdlib HTTP server | `tools/ui1/run_ui_api.py` |
| **Local state** | SQLite (optional) | `IMP_PERSIST_STATE` |
| **CI** | GitHub Actions | `.github/workflows/imp-validate.yml` |

## Constraints

- Foundation stdlib-only lock
- 200 KiB gzip initial bundle budget
- Loopback-only default bind (`127.0.0.1:8766`, `:5173`)

## AI / coding tools

Documented in [AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md) — vendor-agnostic workload guidance.
