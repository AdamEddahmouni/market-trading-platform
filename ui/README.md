# Research UI V1 — separate UI subject

Replay-only React frontend for UI-001. Requires the stdlib API:

```bash
python tools/ui1/run_ui_api.py --serve --port 8766
```

Code changes are not picked up until that process is restarted. For live observational flags (`IMP_LIVE_OBSERVATIONAL`, `IMP_MOOMOO_LIVE` observational-only, `IMP_PAPER_EXECUTION`, `IMP_LIVE_INTERNAL_SIMULATION`, `IMP_PERSIST_STATE`):

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

- NOW command center with reason codes
- WORKSPACE instrument cockpit with OHLCV chart
- Explanation drawer + Evidence Inspector
- RESEARCH / PORTFOLIO gated shells
