## Summary

<!-- What changed and why -->

## Risk

- [ ] Low — docs/tests only
- [ ] Medium — UI or backend behavior
- [ ] High — Paper execution / authority / security

## Mode impact

- [ ] Demo
- [ ] Paper
- [ ] Live
- [ ] None

## Tests

<!-- Commands run and results. Docs/UI: affected + Vitest/link-check. FULL required for Paper-execution-path and release only. -->

## Validation

- [ ] `python tools/imp.py test affected`
- [ ] `python tools/check_docs_links.py` (if docs)
- [ ] `cd ui && npm test` (if UI)
- [ ] `cd ui && npm run build` (if UI)
- [ ] `python tools/imp.py validate full` (**only** if Paper-execution-path or release)
- [ ] `python tools/imp.py closure` (**only** if Paper-execution-path or release)

## Documentation

- [ ] WORK_LOG updated (if substantive)
- [ ] Authoritative doc updated (if behavior changed)
- [ ] Program truth: `docs/platform/PROGRAM_STATUS.md` (do not treat PROJECT_STATUS.md as current campaign state)

## Bundle impact

<!-- N/A or before/after gzip size -->

## Backward compatibility

<!-- API/schema legacy record impact -->

## Screenshots

<!-- If UI visual change -->
