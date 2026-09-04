---
name: imp-debugging
description: Reproduce and isolate IMP failures while preserving safety and temporal semantics.
model_tier: normal
---

Start with evidence, not a patch. Reproduce with the narrowest selector or
command, inspect the owning source and manifest, distinguish environment or
dirty-baseline failures, and add a regression test before fixing. Never enable
live gates, fabricate fixtures, or bypass authority checks. Return root cause,
reproduction, fix scope, and verification evidence.
