# PineTS isolated research bridge (AGPL boundary)

This directory is **not** part of the IMP production dependency graph.

- npm package: [`pinets`](https://www.npmjs.com/package/pinets) (`AGPL-3.0-only`, LuxAlgo/PineTS)
- `@luxalgo/vela` in `ui/package.json` is chart rendering only — **no** `@luxalgo/vela-pinets` / `pinets` in UI deps
- Install PineTS here only after explicit license review:

```bash
cd research/pinets_research_bridge
npm install pinets@0.9.31
export IMP_PINETS_NODE_MODULES="$PWD/node_modules"
```

Python probes this path via `IMP_PINETS_NODE_MODULES` or the sibling bridge under
`strategy/source_runtime/pinets_research_bridge/` (scripts only; no bundled `node_modules`).

Lane E gate 1 does **not** claim FTEP eligibility or research approval for imported Pine scripts.
