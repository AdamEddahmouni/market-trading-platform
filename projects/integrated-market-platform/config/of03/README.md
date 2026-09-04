# OF-03 registry (canonical machine-readable configuration)

These JSON files are the identity/version/policy authority for OF-03.

- `manifest.json` — schema version, active-version pointers, optional snapshot pin
- `capabilities.json` — capability definitions
- `sops.json` — SOP metadata (procedure text remains in `docs/operations/`)
- `workflows.json` — workflow graphs (not execution history)

Runtime loader: `market_platform_foundation.of03`.
