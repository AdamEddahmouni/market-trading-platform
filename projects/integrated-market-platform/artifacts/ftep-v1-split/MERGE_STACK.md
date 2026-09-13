# FTEP-V1 activation split — merge stack

Supersedes monolithic draft PR **#19** (`work/ftep-v1-activation`). Pathway **B**, empirical locks, SIGNAL_ONLY sessions, and Live remain **out of scope** for this stack.

**Stack status (2026-09-12 wave 17):** Poll **#22–#29** — all **MERGEABLE**, all required CI checks **SUCCESS** (0 failures). Heads unchanged from wave 16 poll (**#22** `854b0d94` … **#28** `9c8ccef7`; **#29** advances on `work/ftep-v1-002-us-equity-news` after wave 17 commit). **MERGE_READY recommendation: YES** (strict merge order below). **Owner merge only** this wave — agent does **not** execute `gh pr merge` (same policy as wave 16).

**Owner stack merge (run from repo root after each step rebase if GitHub reports CONFLICTING):**

```powershell
gh pr merge 22 --merge --subject "feat(imp): FTEP-V1 activation preflight, manifest binding, and session policy"
gh pr merge 23 --merge --subject "feat(imp): Wave B provider capability matrix and coverage gap engine"
# Rebase #24 onto main if needed, then:
gh pr merge 24 --merge --subject "feat(imp): Wave B paper calibration comparator and bridge fixes"
gh pr merge 25 --merge --subject "feat(imp): Wave B closure evidence and reconciliation artifacts"
gh pr merge 26 --merge --subject "feat(imp): FTEP ES-news stack selection and provider diagnostics"
gh pr merge 27 --merge --subject "feat(imp): PIT export, observational ingress, and FTEP goal audit closure"
gh pr merge 28 --merge --subject "fix(imp): FTEP-V1 freeze and signal-only readiness reconciliation"
# Do NOT merge #29 until stack reconciliation goal explicitly includes V1-002 campaign branch.
gh run list --branch main --limit 3
python tools/imp.py ftep integrity-check FTEP-V1-001 --json  # fingerprint on main after #28
```

**Stack status (2026-09-12 wave 16):** Poll **#22–#29** — all **MERGEABLE**, all required CI checks **SUCCESS** (0 failures). Heads: **#22** `854b0d94`, **#23** `6a153722`, **#24** `64c03de3`, **#25** `c47f1662`, **#26** `1f5be74e`, **#27** `f61a669a`, **#28** `9c8ccef7`, **#29** FTEP-V1-002 @ `342c35ca`. **MERGE_READY recommendation: YES** (strict merge order below; **no owner-delegated merge** in this wave — documentation only).

**Stack status (2026-09-12 wave 15):** PR **#24** calibration head @ `64c03de3`. **#25** rebased onto `#24` → `c47f1662` (was **CONFLICTING** vs stale base `ee94af67`; now **MERGEABLE**). Cascade rebases: **#26** → `1f5be74e`, **#27** → `f61a669a` onto new stack tips; **#28** → `9c8ccef7` rebased onto `#27`. **#29** FTEP-V1-002 @ `7c562f74` **MERGEABLE** CI green. **#22–#27, #29** **MERGEABLE** on last poll; poll **#25–#28** CI after cascade.

## Merge order (strict)

| Step | PR | Branch | Base branch |
|------|-----|--------|-------------|
| 1 | [#22](https://github.com/AdamEddahmouni/market-trading-platform/pull/22) | `split/ftep-v1-activation-core` | `main` |
| 2 | [#23](https://github.com/AdamEddahmouni/market-trading-platform/pull/23) | `split/wave-b-provider-capability` | `main` |
| 3 | [#24](https://github.com/AdamEddahmouni/market-trading-platform/pull/24) | `split/wave-b-calibration` | `split/wave-b-provider-capability` → rebase to `main` after #23 merges |
| 4 | **#25** | `split/ftep-v1-wave-b-closure` | `split/wave-b-calibration` |
| 5 | **#26** | `split/ftep-v1-es-news-stack` | `split/ftep-v1-wave-b-closure` |
| 6 | **#27** | `split/ftep-v1-goal-audit` | `split/ftep-v1-es-news-stack` |
| 7 | **#28** | `split/ftep-v1-freeze-readiness` | `split/ftep-v1-goal-audit` |

After each merge to `main`, rebase the next open PR onto `main` (or merge via GitHub stack) before the following step.

**Parallelism:** #22 and #23 may merge in either order if conflict-free. Everything from #24 onward assumes Wave B provider + calibration land before closure evidence.

**CI note:** Slices **#23–#28** that call `campaign_readiness` / `paper_forward_bridge.preflight` must vendor `activation.py`, `preflight.py`, `protocol_ref.py`, and `campaign_binding.py` from **#22** until activation-core is on `main` (otherwise `validate-python-changed` fails phase0 import analysis + providers collection). Slices **#26–#28** import additional activation-bridge modules from **#22**; rebase or merge `split/ftep-v1-activation-core` before final stack merge if checks drift.

## Slice map

| Slice | PR | Scope |
|-------|-----|--------|
| 1 | #22 | Activation preflight, manifest binding, session policy |
| 2 | #23 | Provider capability matrix, coverage gap engine |
| 3 | #24 | Paper calibration comparator + bridge fixes |
| 4 | #25 | Wave B closure docs, reconciliation artifacts, snapshot compare |
| 5 | #26 | ES/news stack selection, provider diagnostics router |
| 6 | #27 | PIT export, observational ingress, goal audit closure |
| 7 | #28 | Pre-freeze readiness, **frozen** manifest (pathway A), signal-only gap reconciliation |

## Frozen campaign invariant

`FTEP-V1-001` manifest fingerprint must remain `69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C` across slice **#28** only; earlier slices must not alter the frozen manifest.

## Equivalence check

`split/ftep-v1-freeze-readiness` + merged #22–#27 ≡ `work/ftep-v1-activation` @ `099388f` for `projects/integrated-market-platform/` (validated after full stack merge simulation).
