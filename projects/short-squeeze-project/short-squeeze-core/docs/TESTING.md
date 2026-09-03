# Testing

Tests require Python **3.12** and the `test` optional dependency.

```bash
python -m pip install -e ".[test]"
python -m pytest -p no:cacheprovider --basetemp .pytest-run
```

Normal tests are offline and deterministic. They use synthetic providers and must
not call Finviz, NewsAPI, Finnhub, SEC EDGAR, IBKR, or Railway.

## Focused checks

```bash
python -m pytest tests/app/test_batch15_config.py
python -m pytest tests/app/test_batch15_documentation.py
python -m pytest tests/app/test_batch15_release_audit.py
python -m pytest tests/app/test_batch15_release_builder.py
python -m pytest tests/app/test_audit_remediation.py
python tools/integration_acceptance.py --mode frozen
```

Quick Make smoke (import checks + small pytest subset):

```bash
make test-quick
```

## Authoritative run

Use a new writable base directory and JUnit path for an authoritative run. Parse
the XML for tests, passed, skipped, failures, errors, and duration.

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest-run --junitxml=test-results.xml
```

## Documentation contract tests

`tests/app/test_batch15_documentation.py` asserts that the professional handoff
doc set exists, that `.env.example` uses safe placeholders and expected names,
and that public docs omit personal/academic markers. Update that test when
intentionally expanding `.env.example` keys.

## Related

- [Reproducibility](reproducibility.md)
- [CLI.md](CLI.md)
