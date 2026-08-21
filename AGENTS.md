# Validation cadence

Use the manifest-driven validation ladder for implementation work:

```text
after each edit            -> python tools/validate.py changed
domain milestone           -> python tools/validate.py domain <domain>
major/final checkpoint     -> python tools/validate.py full
live provider modified     -> python tools/validate.py live <provider>
```

Do not run FULL after every intermediate edit. Run it once at the final major checkpoint. A passing CHANGED result is not a substitute for FULL when it reports `full_suite_required=true`.

Run LIVE only for the provider whose live boundary changed, after the applicable offline validation. FULL must remain offline and must never select live suites.

See `docs/engineering/VALIDATION_ARCHITECTURE.md` for selectors, domains, snapshots, safety classes, and result interpretation.
