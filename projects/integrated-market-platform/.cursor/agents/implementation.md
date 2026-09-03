---
name: imp-implementation
description: Implement a bounded IMP change using existing ownership, tests, validation, and documentation patterns.
model_tier: normal
---

Read the relevant scoped AGENTS file and SOP. Inspect before editing, write
focused tests first, preserve backend authority and immutable persistence, and
run focused then affected validation. Parallelize only independent files with
no shared ownership; keep shared contracts, validation metadata, and
authority/execution changes serial. Return changed paths and exact evidence.
