> **STALE.** Canonical PR template is repo-root `.github/pull_request_template.md`. This nested IMP copy is not the GitHub template for the monorepo.

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

<!-- Commands run and results -->

## Validation

- [ ] `python tools/imp.py test affected`
- [ ] `cd ui && npm test` (if UI)
- [ ] `cd ui && npm run build` (if UI)
- [ ] `python tools/imp.py validate full` (**only** if Paper safety or release)
- [ ] `python tools/imp.py closure` (**only** if Paper safety or release)

## Documentation

- [ ] WORK_LOG updated (if substantive)
- [ ] Authoritative doc updated (if behavior changed)

## Bundle impact

<!-- N/A or before/after gzip size -->

## Backward compatibility

<!-- API/schema legacy record impact -->

## Screenshots

<!-- If UI visual change -->
