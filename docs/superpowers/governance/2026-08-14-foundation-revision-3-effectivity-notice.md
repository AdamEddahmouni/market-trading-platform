# Revision 3 — Effectivity Notice

**Logical ID:** `foundation.canonical_specification.revision_3.effectivity_notice`

**Status:** `EFFECTIVE` — exact-hash principal approval recorded

**Date:** 2026-08-14 (approval); notice published 2026-08-26

## Active authority

| Field | Value |
|---|---|
| Specification | `docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md` |
| Logical ID | `foundation.canonical_specification.revision_3` |
| Approved SHA-256 | `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35` |
| Approval record | `docs/superpowers/governance/2026-08-14-foundation-revision-3-approval.json` |
| Authority manifest | `manifests/phase0/canonical-authority.json` (`status: EFFECTIVE`) |

Principal approval statement (exact form):

```text
I approve foundation.canonical_specification.revision_3 at SHA-256 7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35.
```

Offline verification: `resolve_canonical_authority(repository_root)` returns `status: PASS`.

## Effect

Upon this approval:

1. Revision 3 is the sole **forward-looking** canonical foundation authority.
2. Revision 2 remains incorporated and continues to control the authorized Phase 0 safety subject.
3. Revision 3 approval does **not** by itself authorize phase transitions, provider access, broker access, model implementation, whale ingestion, AI integration, paper orders, or live trading.

Later phases and platformization milestones require their own implementation-authorization records.

## Frozen specification header

The Revision 3 specification file still displays:

```text
Status: PROPOSED_PENDING_EXACT_HASH_APPROVAL
```

That line is **frozen inside the approved byte sequence** and must not be edited in place. Any change to the specification bytes invalidates the recorded approval and requires a new immutable revision with fresh exact-hash principal approval.

Use this notice (and `canonical-authority.json`) as the operational status source, not the frozen header inside the approved specification.

## Related artifacts

- [Revision 3 roadmap projection](../../roadmap/REVISION_3_ROADMAP.md)
- [Donor integration and evidence transition plan](../plans/2026-08-14-revision-3-donor-integration-and-evidence-transition.md)
