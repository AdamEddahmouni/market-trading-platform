# Research UI — separate frontend subject

React + TypeScript + Vite frontend for the stdlib API. Started as the
replay-only UI-001 subject; Platformization P0–P3.3 added live
observational, internal paper execution, discovery, and operator
surfaces on top of the replay surfaces.

Requires the stdlib API:

```bash
python tools/ui1/run_ui_api.py --serve --port 8766
```

Code changes are not picked up until that process is restarted. For
live observational / paper flags (`IMP_LIVE_OBSERVATIONAL`,
`IMP_MOOMOO_LIVE` observational-only, `IMP_PAPER_EXECUTION`,
`IMP_LIVE_INTERNAL_SIMULATION`, `IMP_PERSIST_STATE`):

```powershell
powershell -File tools/ui1/restart_ui_api.ps1
```

Then:

```bash
cd ui
npm install
npm run dev
```

## Stack

- React + TypeScript + Vite
- TanStack Query + Zod
- Lightweight Charts (ADR-UX-002 UX-015)

## Surfaces

- `/` — NOW command center with reason codes
- `/explore` — instrument + capability discovery, live subscribe flow
- `/workspace[/:symbol]` — unified live decision cockpit: live
  quote/tape/CVD/L2, What Matters Now, lane evidence drawer
  (squeeze / order-flow / order-book / futures / catalyst / fund-ETF /
  options / large-transactions / disclosure / institutional-flow),
  manual paper OrderTicket + execution trace panel
- `/discover` — Finviz screening candidates (`INVESTIGATE` only, no orders)
- `/portfolio` — paper account, positions, orders, fills, execution trace
- `/settings` — operator settings (watchlist, recents, workspace, provider prefs)
- `/diagnostics/provider` — provider health (channel health, generation, quota)
- `/research` — Model Lab / Simulation Lab (UI-002)
- `/assistant/history` — assistant conversation history

## Gating

Live and paper surfaces render according to the API's operating
context (`data_mode` / `execution_mode` / `execution_authority`); order
submission is never reachable without the backend env gates. Vitest:
`npm run test` (frontend boundary only — see
[docs/engineering/VALIDATION_ARCHITECTURE.md](../docs/engineering/VALIDATION_ARCHITECTURE.md)).
