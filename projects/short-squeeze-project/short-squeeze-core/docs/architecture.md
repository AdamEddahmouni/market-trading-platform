# Architecture

Explanation of how the research screener is structured. For tasks, see
[how-to-guides.md](how-to-guides.md). For contracts, see [API.md](API.md).

## What this system is

A read-only HTTP application that:

1. Collects provider evidence into typed field values with provenance.
2. Projects candidates through independent methodologies.
3. Exposes Scanner and Advanced Research UIs plus a versioned integration API.

It does not trade, hold account state, or assert predictive validity.

## Application surfaces

| Surface | Paths | Role |
|---|---|---|
| Scanner | `/` | Default table: price, change, pressure, ignition, coverage, classification, news, sentiment |
| Advanced Research | `/advanced`, `/index.html`, `/research` | Canonical Phase 3A rules, diagnostics, methodologies, frozen research, manifest |

Both surfaces share one backend API and methodology engine.

## Runtime modes

| Mode | Bind | Private `.private` file | IBKR local probe | Typical use |
|---|---|---|---|---|
| `FROZEN_DEMO` | `127.0.0.1` | Never | No | Evaluation, offline demos |
| `LOCAL_FULL` | `127.0.0.1` | Allowed | Optional | Operator workstation |
| `CLOUD_PROVIDER_MODE` | `0.0.0.0:$PORT` | Never | No local probe | Containers, Railway |

Default native port is **8787**. Docker Compose publishes host **8787** to container
**8080** (`PORT=8080` inside the image). Railway uses the platform `PORT`.

## Runtime layout

`apps/research_screener` is the product package:

- `server.py` — HTTP routes, static assets, optional CSRF / sensitive-API gates
- `session_state.py` — discovery, refresh cadence, row projection
- `config.py` / `credentials.py` — immutable resolved settings; imports never load private files
- `methodologies/` — legacy, peer-reference, Evidence-Gated Prime projections
- `collectors/` — optional supplemental evidence schedulers
- `squeeze_core` (under `src/`) — canonical evaluation, metrics, research policies

## Evidence pipeline

```
Provider / collector data
  → FieldValue (unit, times, freshness, admissibility, provenance)
  → session row / evidence_from_row()
  → EvidenceInputs
  → evaluate_adam() (Evidence-Gated Prime)
  → Pressure / Ignition / Classification on the row
```

Canonical Phase 3A evaluation remains in `squeeze_core` and is independent of the
live Prime projection. Missing evidence stays `UNKNOWN`; display-only fields do
not satisfy research rules by label similarity alone.

## Provider refresh

Per-symbol refresh uses a round-robin slice with IBKR pacing constraints.
External providers (Finviz, NewsAPI, Finnhub, SEC, borrow fee) refresh alongside
that cycle. Caches retain last-good data and surface staleness explicitly.

## Phase flags (product vs research)

| Phase | Product meaning |
|---|---|
| Phase 3A | Preregistered canonical rule evaluation; `UNKNOWN` ≠ fail |
| Phase 3B / 3C | Research publication and descriptive analysis tooling |
| Phase 3D | Verified point-in-time acquisition packages used as integrity foundation |
| Phase 3E | Outcome-oriented research acquisition exists as **offline tooling and historical reports** for a pilot cohort; it is **not** wired into the live screener scoring loop and does **not** complete predictive validation |

Historical `phase-*.md` / `batch-*.md` files record work; [README.md](README.md)
marks them as archive relative to current-truth docs.

## Release boundary

`release-files.json` allowlists distribution contents.
`tools/build_handoff_release.py` stages files, writes checksums, runs
`tools/release_audit.py`, and builds a ZIP. Private config, Git history, and raw
provider caches stay outside the release.

Version is read from `pyproject.toml` (currently **0.16.0**).

## Related reading

- [Reproducibility](reproducibility.md)
- [PROVIDERS.md](PROVIDERS.md)
- [METHODOLOGIES.md](METHODOLOGIES.md)
- [SECURITY.md](SECURITY.md)
