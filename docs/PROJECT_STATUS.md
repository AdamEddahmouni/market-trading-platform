# IMP Project Status

**Status:** Authoritative current snapshot. Update when major milestones complete.  
**Last updated:** 2026-09-01 (operational hardening pass)

## What IMP is today

A governed CPython 3.11 (stdlib-only foundation) + React/Vite market operating workstation with:

- **Demo** — fixture replay exploration (read-only)
- **Paper** — internal simulated execution under explicit env gates
- **Live** — broker-observed read-only data, canary/reconciliation surfaces

Phases 0–16, UI-001/002, MRA-001/002, Platform P0–P4-4C, and mode-specific UI surfaces are **implemented** on admitted fixtures with documented limitations.

**Live production execution (`LIVE-001`) is blocked** — requires separate authorization.

---

## Completed major systems

| System | Status | Reference |
|--------|--------|-----------|
| Governed foundation (Phases 0–8) | PASS | [README](../README.md) phase table |
| Research UI (UI-001/002) | PASS | [ui/README](../ui/README.md) |
| Platformization P0–P4-4C | COMPLETE_WITH_LIMITATIONS | [platformization roadmap](research/PLATFORMIZATION_ROADMAP.md) |
| Mode launcher & session | Complete | [mode launcher completion](superpowers/plans/2026-08-26-mode-launcher-implementation.md) |
| Mode-specific surfaces (Now/Portfolio/Workspace/Explore/Research/Discover) | Complete | [completion](superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| Workspace lane mode content (10 lanes) | Complete | [completion](superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md) |
| Paper workspace decision cockpit | Complete | [completion](superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md) |
| Paper Command → Workspace handoff | Complete | [completion](superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md) |
| Paper Portfolio decision history | Complete | [completion](superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md) |
| Paper decision-source snapshot | Complete | [completion](superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md) |
| Paper decision source_time | Complete | [completion](superpowers/plans/2026-09-01-paper-decision-source-time-completion.md) |
| UI completion & productization | Complete | [completion](superpowers/plans/2026-09-01-ui-completion-productization-completion.md) |
| Project operating system / governance docs | Complete | [completion](superpowers/plans/2026-09-01-project-operating-system-completion.md) |
| Operational hardening (lane provenance, CI, consolidation) | Complete | [completion](superpowers/plans/2026-09-01-operational-hardening-completion.md) |
| Manifest-driven validation | Active | [VALIDATION_ARCHITECTURE](engineering/VALIDATION_ARCHITECTURE.md) |
| Intelligence BUILD 01–35 | PASS (fixture scope) | [BUILD specs](engineering/) |

---

## Current work

**P6 Shadow Run 1** — forward-validation evidence collection **IN PROGRESS** (protocol preregistered 2026-09-01; 4 ACTUAL_FORWARD abstentions on default-store run `SHRUN-00C5…`; stopping rule not met — see [P6 protocol](engineering/P6_SHADOW_RUN_1_PROTOCOL.md)).

---

## Recently completed

- TD-005 operator auth and account-scoped authorization (2026-09-01)
- TD-003 multi-account snapshot architecture (2026-09-01)

---

## Next likely work (not committed)

- Complete P6 Shadow Run 1 forward observation window when Moomoo/OpenD available
- TD-004 Moomoo OpenD real-wire when connectivity available
- Hosted deployment (P5 hosted/OIDC — local auth enforcement complete)

---

## Deferred / blocked

| Item | Reason |
|------|--------|
| ES-session acceptance | ADR-DATA-001 — lawful ES bytes not procured |
| LIVE-001 production execution | Blocked pending separate authorization |
| Crypto / prediction-market expansion | Planning only — not authorized |
| P4-4C Moomoo paper real-wire | Fixture-proven; OpenD TCP protocol |
| Auth / multi-user enforcement | TD-005 closed — `LOOPBACK_TRUST` default; `ENFORCED` via `IMP_AUTH_ENFORCEMENT_MODE` + principals registry (ADR-0008); hosted OIDC/SSO deferred |
| P6 forward validation | Protocol preregistered; observational Moomoo path blocked — [P6 protocol](engineering/P6_SHADOW_RUN_1_PROTOCOL.md) |

---

## Intentionally out of scope (current repo)

- On-chain ingestion, live social APIs, AI-trading
- Non-stdlib Python in foundation (locked per `phase0-dependency-lock.json`)
- Retroactive Finviz screen reconstruction

---

## Validation snapshot (2026-09-01)

Recorded at TD-003 multi-account snapshot increment; re-run before release:

| Gate | Last recorded |
|------|---------------|
| Vitest | 421 passed |
| UI typecheck | Pass (`tsconfig.typecheck.json`) |
| `validate.py changed` | 874 passed, 0 failures, 0 errors |
| `validate.py full` | 2984 passed, 0 failures, 0 errors |
| `test_repository_closure` | OK |
| Initial bundle | 200.00 KiB gzip (budget 201 KiB) |

Do not treat counts as permanent — verify with [VALIDATION.md](engineering/VALIDATION.md).
