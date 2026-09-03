# SOP: Paper Execution Change

**Safety-critical.** Complete every item.

## Authority & leakage

- [ ] No Demo mutation paths enabled
- [ ] No Live order submission introduced
- [ ] `canUsePaperActions` respected on all new controls
- [ ] Backend rejects without `PAPER_ONLY` authority
- [ ] Env gates documented if new

## Preview / submit

- [ ] Preview required before submit
- [ ] Stale preview → `REVALIDATION_REQUIRED`
- [ ] `confirmedRequestIsCurrent` honored
- [ ] Accepted preview does not bypass draft changes

## Session & account

- [ ] Correct mode session (Paper)
- [ ] Account context matches API

## Request contract

- [ ] `correlation_id` preserved
- [ ] `decision_source_snapshot` bounded and validated
- [ ] `source_time` immutable after handoff (if applicable)

## Persistence

- [ ] Intent event written
- [ ] Ledger append-only
- [ ] Projection includes new fields optionally

## Trace

- [ ] Execution trace shows provenance/snapshot

## Compatibility

- [ ] Legacy intents/orders without new fields still project

## Tests

- [ ] Authority loss coverage
- [ ] Stale preview coverage
- [ ] Backend mutation rejection without authority

## Validation

- [ ] `validate.py full`
- [ ] `cd ui && npm test && npm run build`

See [checklists/PAPER_SAFETY.md](../checklists/PAPER_SAFETY.md) and [MODE_AUTHORITY.md](../../architecture/MODE_AUTHORITY.md).
