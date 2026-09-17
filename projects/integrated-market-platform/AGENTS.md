# Integrated Market Platform — agent router

IMP is a governed market workstation: Demo replay, Paper internal simulation,
and Live observational monitoring. This file routes agents; authoritative
details live in the linked architecture and engineering references.

## First reads

1. [docs/README.md](docs/README.md) — authority map
2. [docs/architecture/MODE_AUTHORITY.md](docs/architecture/MODE_AUTHORITY.md) —
   non-negotiable safety model
3. [docs/engineering/AGENT_OPERATING_SYSTEM.md](docs/engineering/AGENT_OPERATING_SYSTEM.md) —
   model, parallelism, worktree, evidence, and handoff control plane
4. [docs/engineering/DEVELOPER_OPERATING_SYSTEM.md](docs/engineering/DEVELOPER_OPERATING_SYSTEM.md) —
   command and validation contract
5. [docs/engineering/WORK_LOG.md](docs/engineering/WORK_LOG.md) — current history

Read [ui/AGENTS.md](ui/AGENTS.md) for UI work and
[paper/AGENTS.md](src/market_platform_foundation/paper/AGENTS.md) for Paper
backend work. Use the relevant SOP from `docs/engineering/sops/`.

## Safety invariants

- Demo mutations are prohibited; Live is observational only; `LIVE-001` remains
  blocked.
- Paper mutations require backend `INTERNAL_SIMULATION` + `PAPER_ONLY` authority
  and explicit environment gates. Frontend gating is UX, not security.
- Workspace is the canonical Paper submit boundary. Preserve preview
  revalidation, risk authority, execution controls, account isolation,
  source-time semantics, immutable provenance, persistence correctness, and
  offline network denial.
- Fail closed on authority loss, stale preview, schema mismatch, unknown
  identifiers, and unconfigured providers. Never fabricate data or API shapes.

## Canonical command path

Run from the repository root:

```powershell
python tools/imp.py env
python tools/imp.py format
python tools/imp.py lint
python tools/imp.py ci jobs
python tools/imp.py validate fast
python tools/imp.py test focused <selector>
python tools/imp.py test affected
python tools/imp.py validate changed
python tools/imp.py validate full
python tools/imp.py review
python tools/imp.py closure
```

Use the cheapest relevant stage: FAST → focused/affected → domain/changed →
FULL closure. `tools/validation_manifest.json` remains the sole test inventory;
`tools/validate.py` remains the Python validation authority.

## Canonical edit target

IMP's single edit target in **this** monorepo is
`projects/integrated-market-platform/`. Parent-root CI and the local
workflow run against this tree. Do **not** edit the leftover nested clone at
repo-root `integrated-market-platform/`.

`tools/validate.py changed` automatically normalizes the
`projects/integrated-market-platform/` prefix when run inside the monorepo.

## Working rules

- Inspect existing patterns, schemas, ownership metadata, and authoritative
  docs before editing. Extend established abstractions.
- Keep changes minimal and preserve unrelated dirty-tree work.
- Add regression tests for real bugs and do not weaken tests or safety gates.
- Substantive work updates `WORK_LOG.md`; behavior/architecture changes update
  the authoritative doc, not only a completion record.
- Use repo-local skills/subagents only for their declared scope. Default to
  one agent. Parallelize only independent read-only or isolated worktrees;
  keep authority, persistence, execution, evidence-sensitive, and shared-state
  changes serial. Start on Composer; never Fast models.

Detailed validation, closure, model routing, and delegation rules:
[Agent Operating System](docs/engineering/AGENT_OPERATING_SYSTEM.md) and
[Developer Operating System](docs/engineering/DEVELOPER_OPERATING_SYSTEM.md).
On this machine the uv-managed 3.11 interpreter is
`C:\Users\adame\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe`. uv-managed
interpreters are PEP 668 externally managed, so install `tzdata` into the venv, never into the managed
interpreter. `tzdata` is data-only (read by stdlib `zoneinfo` on Windows); the foundation itself imports no
third-party modules per the dependency lock. On Linux the system tz database satisfies `zoneinfo` without
`tzdata`.

## Cursor Cloud specific instructions

Cloud Agents run on Ubuntu using `.cursor/environment.json`. Install dependencies with:

```bash
bash .cursor/install-cloud-deps.sh
export PYTHONPATH=src
source .venv/bin/activate
```

Default cloud validation is the `python tools/imp.py` pyramid from current
`main` (FAST → focused/affected → domain/changed → FULL), not
`python -m unittest discover`. See
[Developer Operating System](docs/engineering/DEVELOPER_OPERATING_SYSTEM.md).

- **MongoDB**: optional. Unit tests use `InMemoryIntelligenceRepository`; Mongo integration tests skip without `IMP_TEST_MONGODB_URI`.
- **Moomoo OpenD / IBKR**: not available on cloud VM. IBKR TWS (`4001`) and Client Portal Gateway (`5000`) are two transports; neither is execution authority. Use fixtures, replay, and mock paths; keep live gates off. Do not claim IBKR is available now.
- **Landing branch**: `git fetch origin main` then use `origin/main` (see [PROGRAM_STATUS.md](docs/platform/PROGRAM_STATUS.md) Canonical SHA **field** for the mutable program tip; do not pin stale SHAs in agent docs). `cloud-handoff/full-state-2026-08-25` is historical.
- See `docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md` for secret names (values via Cursor Cloud Secrets only).

## Canonical program truth and change isolation

Before implementation work, recover repository truth: root, branch, HEAD,
upstream/ahead-behind state, worktrees, tracked modifications, untracked paths,
and recent lineage. Do not assume a clean checkout.

- Use [`docs/platform/`](docs/platform/README.md) for current program
  explanation, status, roadmap, boundaries, authority routing, terminology, and
  documentation governance.
- Executable schemas, policies, gates, registries, manifests, frozen policies,
  and implementation authorities control behavior within their scopes.
  Canonical prose must reference mutable values rather than shadow them.
- Preserve accepted BUILD, Phase, repository-closure, and EVIDENCE artifacts as
  historical truth at their recorded cutoffs. Current prose may route to them
  but may not rewrite them.
- Keep EVIDENCE-01/01A/01B semantics and records isolated. EVIDENCE-01C remains
  independent of REBASE, Operating Fabric, Real-Time, Cross-Asset, Narrative,
  and AI roadmap work unless a separately accepted authority changes that
  relationship.
- Information, research, prediction, narrative, LLM/agent output,
  qualification, release approval, provider connectivity, and mode flags do not
  grant broker authority. Preserve independent risk, live-safety, session
  authorization, per-order confirmation, broker, and reconciliation boundaries.
- When the current checkout contains unrelated work, use a clean dedicated
  worktree from the approved base. Do not reset, clean, broadly stash, stage,
  or copy the unrelated changes.
- Validate with the manifest-driven ladder above. Before committing, inspect
  `git status --short`, the complete diff, `git diff --check`, the exact staged
  path list, the complete staged diff, and `git diff --cached --check`. Stage
  explicit intended paths only.
- Future run-ledger, workflow-registry, documentation-automation, or capability
  registry requirements apply only after their owning milestones are
  implemented and accepted; do not require nonexistent systems.
