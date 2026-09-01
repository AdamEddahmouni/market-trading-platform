# SOP: Release

Local/manual release process (no hosted deploy pipeline in repo).

## Pre-release

- [ ] Clean git tree (intentional changes only)
- [ ] `validate.py full` — offline
- [ ] `cd ui && npm test && npm run build`
- [ ] `tools/check_docs_links.py` if docs changed
- [ ] [PROJECT_STATUS.md](../../PROJECT_STATUS.md) updated if milestone

## Paper / Live safety

- [ ] Paper authority regression tests pass
- [ ] No Live execution paths introduced
- [ ] Env example accurate

## Build

- [ ] `npm run build` bundle within budget
- [ ] Record bundle metric in release notes / work log

## Config

- [ ] `.env.example` reflects required vars
- [ ] No secrets in tree

## Migration

- [ ] SQLite schema: document if `local_state` changed
- [ ] Backward compatible API projections

## Rollback

- [ ] Git tag or branch point recorded
- [ ] Known limitations documented

## Documentation

- [ ] WORK_LOG release entry
- [ ] Completion record if major

No `CHANGELOG.md` — use WORK_LOG + completion records unless formal versioning adopted.
