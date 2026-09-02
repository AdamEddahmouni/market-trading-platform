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
