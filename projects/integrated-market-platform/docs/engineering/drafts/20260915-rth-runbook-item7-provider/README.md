# Isolated drafts — P7 + P8 + P10 + Sept 16 PREP

**Classification:** `EXPERIMENTAL` diagnosis / operator drafts
**Truth class:** not `CURRENT_CANONICAL_TRUTH`
**Must not be treated as program-status or doctrine.**

| Field | Value |
|---|---|
| Branch | `diagnosis/rth-runbook-item7-provider-20260915` |
| Worktree | `.worktrees/diagnosis-rth-runbook-item7-provider-20260915` |
| Base | `origin/main` |
| Base SHA | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| Frozen RTH runtime | `.rth-operator-20260915` at the same SHA — **not edited** |
| Merge / push to `main` | **forbidden from this lane** |
| Canonical `PROGRAM_STATUS.md` / doctrine | **not updated** |

These notes record 2026-09-15 observational evidence and the software gaps
that evidence implies. They become canonical **only when the corresponding
software lands** and a later docs PR updates program-status against that
software — not ahead of it.

## Drafts in this folder

| File | Lane | Subject |
|---|---|---|
| [P7_PROVIDER_SESSION_RELIABILITY.md](P7_PROVIDER_SESSION_RELIABILITY.md) | P7 | Finviz gates, one-shot ingress, FTEP vs cockpit, OpenD quote vs kline, CallClose, history quota, poll #1 / #2 |
| [ITEM7_UPSTREAM_GAP_DIAGNOSIS.md](ITEM7_UPSTREAM_GAP_DIAGNOSIS.md) | P8 | Item 7 generating loop; stage classification; ordered work package. Refined copy of `diagnosis/item7-upstream-20260915` (that branch was not rewritten) |
| [P10_OPERATOR_RUNBOOK_DRAFT.md](P10_OPERATOR_RUNBOOK_DRAFT.md) | P10 | Correct launch, SPA `/`, IMP `.venv`, FTEP ≠ discovery, enrichment OFF, Item 9 outcomes, CallClose, UTF-8, evidence paths |
| [SEPT16_0830_ET_MACRO_WINDOW_CHECKLIST.md](SEPT16_0830_ET_MACRO_WINDOW_CHECKLIST.md) | PREP | 2026-09-16 08:30 ET checklist only — **do not execute from this lane** |

## Sister diagnosis branches (do not fight)

| Branch | Use |
|---|---|
| `diagnosis/item7-upstream-20260915` | Source Item 7 notes; copied/refined here |
| `diagnosis/item9-prospective-bar-20260915` | Session-day OpenD 1m kline software (not on this base SHA) |
| `diagnosis/launcher-routing-20260915` | SPA `/` vs `/discover`, stop auto-selecting `moomoo-api-test` |

Sister software must land **with** these drafts, not by declaring this folder
canonical first.

## Safety

- Live OFF. FTEP not `EMPIRICAL_ACTIVE`. No empirical locks. No Paper/Live orders.
- Enrichment worker OFF.
- No new providers.
- No fake Item 7 rows.
- No Sept 16 campaign execution from this lane.
