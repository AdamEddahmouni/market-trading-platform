# MATLAB research tree — agent instructions

Parent: [AGENTS.md](../../AGENTS.md)

This directory is **research-only**. `MODE_AUTHORITY` here is `NONE`.

## Allowed

- Read Research Export v1 packages and admitted fixtures
- Record toolbox honesty (`environment/toolbox_manifest.json` locally)
- MATLAB scripts under this tree **when MATLAB actually exists**

## Denied (fail closed)

- `ui/`
- Path A hop CLI, OpenD transport, Alpaca adapter
- FTEP session start and campaign-manifest mutation
- Mongo / canonical repository writes
- Broker credentials, Paper submit, Live, `LIVE-001`
- Datafeed Toolbox / Database Toolbox as IMP ingest
- Stamping `metadata.pit_status=PIT-PASS` on fixture exports
- Wave 1 `--allow-oos` on `NON_EMPIRICAL_FIXTURE` or `EXTERNAL_RESEARCH_DATA`
- Mixing `EXTERNAL_RESEARCH_DATA` with canonical IMP export rows

MATLAB findings never become production behavior. Promotion, if ever, is
independent Python under BUILD 19/20 — not this tree.
