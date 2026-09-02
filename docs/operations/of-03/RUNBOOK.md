# OF-03 Runbook

| Field | Value |
|---|---|
| Document ID | `RUNBOOK-OF03` |
| Version | `1.0` |
| System | `IMP-OF-03` |

## Inspect

Run `OF03.OP.STATUS` with `--json`. Treat `valid=false` as not ready. Do not
infer health from prose.

## Change a definition

Edit `config/of03/*.json`. Bump `definition_version` for semantic changes. Point
`manifest.json` active maps only after validation. Commit through ordinary
change control. There is no runtime mutation API.

## Invalid registry

Do not drop malformed records. Restore last known valid commit. Use
`SOP-OF03-008`.

## Drift

`OF03.OP.CHECK_DRIFT` reports missing documents, broken anchors, and section
hash drift. Prose remains authoritative in SOP documents; the registry stores
references.
