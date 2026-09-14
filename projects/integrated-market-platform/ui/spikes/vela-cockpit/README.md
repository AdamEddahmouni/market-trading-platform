# Lane G — Vela charting spike (isolated)

**Not wired into IMP `ui/` production entry.** Run only from this folder.

## License boundary

| Package | Role in spike | License |
|---------|----------------|---------|
| `@luxalgo/vela` | Chart renderer + native indicators | Apache-2.0 |
| `@luxalgo/vela-pinets` / `pinets` | **Not installed** — Pine Script / PineTS | AGPL-3.0 |

IMP retains bar identity (`bar_id`, `source_time_ns`, `instrument_id`) and semantic markers in TypeScript; Vela receives OHLCV projections and drawing placements only.

## Run

```powershell
cd projects/integrated-market-platform/ui/spikes/vela-cockpit
npm install
npm run dev
```

## Measure bundle (lazy-load impact proxy)

```powershell
npm run measure
```

Decision memo: `artifacts/spikes/vela-cockpit/LANE_G_VELA_CHARTING_DECISION.md`
