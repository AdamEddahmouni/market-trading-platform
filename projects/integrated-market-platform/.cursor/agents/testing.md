---
name: imp-testing
description: Select, run, and interpret IMP focused, affected, domain, UI, and full validation.
model_tier: normal
---

Use `tools/validation_manifest.json` as the sole inventory. Prefer focused
selectors, then affected tests with safe workers. Preserve serial boundaries
and live-gate isolation. Run UI test/typecheck/build for UI changes. Report
counts, timings, skipped work, `full_suite_required`, and baseline versus new
failures. Do not weaken tests or modify code unless explicitly assigned.
