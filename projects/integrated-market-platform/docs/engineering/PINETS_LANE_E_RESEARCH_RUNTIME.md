# Phase 5 Lane E — PineTS research runtime

Status: gate 1 (`PINETS_PARTIAL_PARITY_READY`). Not FTEP-eligible; PineTS is not canonical truth.

## License audit (exact)

| Artifact | Package / repo | License | IMP production graph |
| --- | --- | --- | --- |
| PineTS runtime | npm `pinets` ([LuxAlgo/PineTS](https://github.com/LuxAlgo/PineTS)) | **AGPL-3.0-only** (dual-licensed; commercial license separate) | **Excluded** — optional Node bridge only |
| Vela chart lab | npm `@luxalgo/vela` | per package (chart rendering) | UI lazy chunk; **no** `pinets` / `@luxalgo/vela-pinets` in `ui/package.json` |
| Lane E adapter | `imp.pinets_strategy_runtime` | IMP proprietary | Research/replay/parity adapter only |

Imported Pine scripts register as `UNTESTED` until explicitly promoted. Built-in reference fixtures ship as `PARTIAL_PARITY` (Python reference path only).

## Modes

`RESEARCH`, `REPLAY`, `PARITY` only. Paper/Live execution authority is rejected (`StrategyExecutionMode` + hold labels).

## Parity doctrine

Compare indicators, signal timestamps, warmup/NA semantics, and parameters — never a single final P&L match.

Failure codes: `UNSUPPORTED_PINE_FEATURE`, `NUMERICAL_MISMATCH`, `TIME_ALIGNMENT_MISMATCH`, `WARMUP_MISMATCH`, `RUNTIME_ERROR`.

## Optional engine install

See `research/pinets_research_bridge/README.md`. Set `IMP_PINETS_NODE_MODULES` after isolated `npm install pinets`.
