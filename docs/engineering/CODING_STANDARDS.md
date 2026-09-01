# Coding Standards

**Status:** Project-specific conventions beyond linter defaults.

## TypeScript / React

- Prefer explicit types on public exports
- Colocate pure helpers as `build*`, `parse*`, `resolve*`, `derive*`
- Components focus on composition; avoid 500+ line pages — extract panels
- Use `queryKeys` from `hooks.ts` for React Query
- Mode checks via `modeAuthority.ts` — not ad-hoc string compares scattered widely
- Optional API fields: `?:` + handle `undefined` in display

## Python

- Stdlib only in `market_platform_foundation` (per dependency lock)
- Type hints on public functions
- Optional fields with `None` default for backward compatibility
- Epoch **nanoseconds** for new timestamps
- No secrets in logs or error messages

## Naming

- Mode pages: `{Demo|Paper|Live}{Surface}Page`
- Mode routes: `Mode{Surface}Route`
- Observability: `{Surface}Observability` or `{Lane}WorkspaceObservability`
- CSS: `{mode}-{surface}.css`

## Imports

- Frontend: relative within feature folders; `api/` for client layer
- Avoid circular imports between paper-workspace and paper-portfolio — shared logic in `paper/`

## Tests

- `describe`/`it` name behavior, not implementation
- Fixtures mirror admitted shapes — no fabricated live prices
- Paper tests must set authority context explicitly

## Comments

- Explain **why** for business rules (authority, immutability, timestamp semantics)
- Do not restate obvious code

## Magic strings

Use canonical mappings (`LANE_MODULE_IDS`, mode union types, provenance parsers) instead of raw strings in multiple places.

## Error handling

- UI: degraded display for bad optional fields
- Backend: fail closed on mutations; structured errors
- Never weaken tests to pass
