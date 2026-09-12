# FTEP-V1 activation split — merge stack

Supersedes monolithic draft PR **#19** (`work/ftep-v1-activation`). Pathway **B**, empirical locks, SIGNAL_ONLY sessions, and Live remain **out of scope** for this stack.

**Stack status (2026-09-12 wave 15):** PR **#24** calibration head @ `64c03de3`. **#25** rebased onto `#24` → `c47f1662` (was **CONFLICTING** vs stale base `ee94af67`; now **MERGEABLE**). Cascade rebases: **#26** → `1f5be74e`, **#27** → `f61a669a` onto new stack tips; **#28** rebased onto `#27` head (tip SHA after push). **#29** FTEP-V1-002 @ `7c562f74` **MERGEABLE** CI green. **#22–#27, #29** **MERGEABLE** on last poll; poll **#25–#28** CI after cascade.

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

## Stack reconciliation (wave 8 — 2026-09-12)

Recorded after wave 7 closure; **do not merge** unless owner/governance in activation docs authorizes stack landing.

| PR | Head SHA | Base | IMP Validation (latest observed) | Merge-ready |
|----|----------|------|----------------------------------|-------------|
| [#22](https://github.com/AdamEddahmouni/market-trading-platform/pull/22) | `854b0d94` | `main` | validate-python + validate-python-changed + docs + ui — **pass** | Yes (slice 1) |
| [#23](https://github.com/AdamEddahmouni/market-trading-platform/pull/23) | `6a153722` | `main` | full suite — **pass** | Yes (slice 2) |
| [#24](https://github.com/AdamEddahmouni/market-trading-platform/pull/24) | `e7dcdadb` | `#23` branch | guardrails only on last push (stacked PR) | Yes after #23 merge |
| [#25](https://github.com/AdamEddahmouni/market-trading-platform/pull/25) | `3a1d3dd8` | `#24` branch | full suite — **pass** | Yes after upstream stack |
| [#26](https://github.com/AdamEddahmouni/market-trading-platform/pull/26) | `e4b79a44` | `#25` branch | full suite — **pass** | Yes after upstream stack |
| [#27](https://github.com/AdamEddahmouni/market-trading-platform/pull/27) | `9b86e634` | `#26` branch | full suite — **pass** | Yes after upstream stack |
| [#28](https://github.com/AdamEddahmouni/market-trading-platform/pull/28) | `95e662bc` | `#27` branch | prior run failed `validate-python-changed`; fixed @ `95e662bc` (protocol ref SHA); **re-run IMP Validation pending** on tip | **Conditional** — merge-ready after green full suite on `95e662bc` |

**Recommendation:** Merge **#22 → #23** to `main` first (parallel-safe if conflict-free), then rebase #24–#28 sequentially. Hold **#28** until IMP Validation reports green on `95e662bc`. Parallel product track **FTEP-V1-002** lives on PR **#29** (`543bc912`); not part of this stack merge order.

**Governance:** No stack merge and no governed SIGNAL_ONLY session without owner authorization receipts and RTH calendar gates (see `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md` on #29).
