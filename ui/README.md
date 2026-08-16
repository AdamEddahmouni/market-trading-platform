# Research UI V1 — separate UI subject

Replay-only React frontend for UI-001. Requires the stdlib API:

```bash
python tools/ui1/run_ui_api.py --serve --port 8766
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
