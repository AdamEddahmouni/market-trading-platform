# Dependencies

**Status:** Strategic direct dependencies only.

## Foundation constraint

`phase0-dependency-lock.json` — CPython 3.11 **stdlib only** for `market_platform_foundation`. Exception: intelligence BUILD dev deps (numpy, pymongo, scikit-learn) via cloud install script — not in foundation imports.

## Frontend (`ui/package.json`)

| Package | Purpose | Notes |
|---------|---------|-------|
| react / react-dom | UI framework | Stay on 18.x until planned upgrade |
| react-router-dom | Routing, handoff state | v6 |
| @tanstack/react-query | Server state/cache | Central `queryKeys` |
| zod | Runtime API validation | Mirror backend contracts |
| lightweight-charts | Price charts | Bundle-sensitive — lazy where possible |
| recharts | Secondary charts | Heavier — avoid entry path |

### Adding frontend libraries

1. Can existing stack solve it?
2. Bundle impact (`npm run build` budget)
3. License, maintenance, types
4. Document here

## Backend

| Component | Purpose |
|-----------|---------|
| CPython 3.11 stdlib | Entire foundation |
| tzdata (Windows venv) | `zoneinfo` data only |

## Provider SDKs

Moomoo SDK via separate venv (`%USERPROFILE%\moomoo-api-test\.venv`) when present — not in foundation package.

## Library selection rules

Before adding any dependency:

1. Existing dependency or stdlib/platform API?
2. Maintenance status and license
3. Security history (`npm audit`)
4. Bundle size (frontend) / lock impact (backend)
5. Type quality and API stability
6. Necessity — document in PR/work log

## Replacement threshold

Replace when: unmaintained, critical CVE without fix, blocks bundle budget, duplicates existing capability.

## Audit commands

```powershell
cd ui && npm audit
cd ui && npm outdated    # informational
```

See [DEPENDENCY_UPDATE.md](sops/DEPENDENCY_UPDATE.md).
