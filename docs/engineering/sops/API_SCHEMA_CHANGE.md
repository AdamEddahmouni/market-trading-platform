# SOP: API / Schema Change

## 1. Identify canonical contract

Backend type, JSON schema (`manifests/ui1/schemas/`), frontend Zod (`ui/src/api/schemas.ts`).

## 2. Backend type

Add optional fields with defaults in `contracts/` or domain module.

## 3. Request parser

Validate and reject oversize/malformed input; fail closed on mutations.

## 4. Service mapping

Map to domain objects; preserve legacy records without new fields.

## 5. Projection

Include optional fields when present; omit when absent.

## 6. Frontend schema

Update Zod; treat new fields as optional.

## 7. Client / hook

`api/endpoints.ts` + `hooks.ts` if new query; use `queryKeys`.

## 8. Fixtures

Update admitted fixtures and test payloads (old + new shapes).

## 9. Tests

Backend unittest + vitest for parsing/display.

## 10. Backward compatibility

Optional-only unless migration authorized. Old clients must not break.

## 11. Docs

Update [DATA_CONTRACTS.md](../../architecture/DATA_CONTRACTS.md) if semantic.

## 12. Validation

`validate.py changed` + `cd ui && npm test` + build if UI touched.

### Timestamp checklist

- [ ] Epoch unit documented (ns preferred for new fields)
- [ ] Frontend formatter handles ns and legacy ms
- [ ] Never conflate `source_time` and `created_time`

### Versioning

Coordinate deploy: backend tolerant of missing fields; frontend tolerant of absent response fields.

See [checklists/API_CHANGE.md](../checklists/API_CHANGE.md).
