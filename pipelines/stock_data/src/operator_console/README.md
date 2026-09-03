# Stock Data Operator Console (CLI)

Rich terminal UI for the nested stock-data **collector pipeline** — not the canonical React workstation (`ui/`).

## Scope

- Pipeline progress dashboard (`LivePipelineDashboard`)
- Interactive filter/export menus for collector inventory
- Progress bars and timing for scraper stages

## Authority

The product workstation remains `ui/` + `ui_api/`. This package is **pipeline-local CLI tooling** only.

Renamed from `src/ui` (2026-09-01) to eliminate confusion with POST-BUILD35 duplicate-UI classification.
