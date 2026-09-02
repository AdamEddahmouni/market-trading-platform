# Integrated Market Platform — agent router

IMP is a governed market workstation: Demo replay, Paper internal simulation,
and Live observational monitoring. This file routes agents; authoritative
details live in the linked architecture and engineering references.

## First reads

1. [docs/README.md](docs/README.md) — authority map
2. [docs/architecture/MODE_AUTHORITY.md](docs/architecture/MODE_AUTHORITY.md) —
   non-negotiable safety model
3. [docs/engineering/DEVELOPER_OPERATING_SYSTEM.md](docs/engineering/DEVELOPER_OPERATING_SYSTEM.md) —
   command and delegation contract
4. [docs/engineering/WORK_LOG.md](docs/engineering/WORK_LOG.md) — current history

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

## Working rules

- Inspect existing patterns, schemas, ownership metadata, and authoritative
  docs before editing. Extend established abstractions.
- Keep changes minimal and preserve unrelated dirty-tree work.
- Add regression tests for real bugs and do not weaken tests or safety gates.
- Substantive work updates `WORK_LOG.md`; behavior/architecture changes update
  the authoritative doc, not only a completion record.
- Use repo-local skills/subagents only for their declared scope. Parallelize
  independent read-only or isolated validation work; keep authority,
  persistence, execution, and shared-state changes serial.

Detailed validation, closure, model routing, and delegation rules:
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

Intelligence BUILD 04.5–09 additionally requires `numpy`, `pymongo`, and `scikit-learn` (installed by the script above).

Validation in cloud:

```bash
python -m unittest discover -s tests/intelligence -q
python -m unittest tests.platform.test_shadow_p6 -q
python tools/validate.py changed
```

- **MongoDB**: optional. Unit tests use `InMemoryIntelligenceRepository`; Mongo integration tests skip without `IMP_TEST_MONGODB_URI`.
- **Moomoo OpenD / IBKR gateway**: not available on cloud VM. Use fixtures, replay, and mock paths; keep live gates off.
- **Handoff branch**: start from `cloud-handoff/full-state-2026-08-25` and verify against `artifacts/cloud-handoff/CLOUD_FILE_HASHES.json`.
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
