# GridIQ donor notes

These notes describe an external, immutable donor snapshot. Revision 3 is the
authority if this summary conflicts with it. Nothing here authorizes donor
execution, network access, data copying, AI-provider use, or a phase transition.

## Identity and inspection boundary

- Logical root: `PROTO-GRIDIQ-001`
- Observed collection-relative path:
  `DS-440-CAPSTONE-GridIQ-main/DS-440-CAPSTONE-GridIQ-main`
- Git state: `UNAVAILABLE_NO_GIT_METADATA`; neither nested snapshot level
  contains usable `.git` metadata.
- Purpose: a football analytics dashboard and chat application.
- Inspection was offline and read-only. No backend, frontend, migration,
  package manager, database mutation, remote request, or Gemini call ran.

The backend uses FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL and SQLite
configuration, JWT/password libraries, nfl-data-py, pandas-style transformations,
and Google Generative AI. The frontend uses React, TypeScript, Vite, Axios,
TanStack React Query, Zod, Zustand, Recharts, and Tailwind.

## Representative code inspected

- Dataset acquisition/projection: `gridiq-backend/app/nflverse_parquet.py`
- Schedule acquisition/cache: `gridiq-backend/app/nflverse_schedules.py`
- play-by-play store/cache: `gridiq-backend/app/nflverse_pbp_store.py`
- chat context: `gridiq-backend/app/nflverse_chat_context.py` and
  `gridiq-backend/app/nflverse_chat_pbp.py`
- API routing and DTO transformation:
  `gridiq-backend/app/api/routes/nflverse_dashboard.py`, `games.py`, `chat.py`,
  `auth.py`, `users.py`, and `cache.py`
- persistence: `gridiq-backend/app/models/conversation.py`, `user.py`,
  `game.py`, and `cache.py`
- schemas: `gridiq-backend/app/schemas/*.py`
- query and runtime validation: `gridiq-frontend/src/lib/api/endpoints.ts`
  and `src/pages/Chat.tsx`, `Dashboard.tsx`
- authentication state: `gridiq-frontend/src/stores/auth.ts`
- charts: `gridiq-frontend/src/pages/DashboardCharts.tsx`

## Dataset and cache findings

The Parquet path downloads a whole remote object into memory before parsing,
projects optional columns, and fills absent columns with missing values. This is
useful as a small prototype pattern but is not an immutable dataset contract.
The full-object load lacks byte limits and content-addressed identity; silently
materializing missing columns can hide schema drift.

The schedule path is remote-first with a fixed disk fallback/cache location.
No content hash, source version, invalidation policy, or explicit point-in-time
availability boundary was observed. The play-by-play in-memory cache is bounded
by season count rather than bytes and may downcast `float64` columns to
`float32`, creating memory and precision tradeoffs that are not represented in
dataset identity. The generic SQL TTL cache is mutable application cache, not a
canonical dataset store.

Canonical adaptation therefore requires immutable source/version/hash identity,
schema contracts, explicit missing-column policy, maximum object and cache byte
limits, deterministic invalidation, precision policy, and offline replay with
no hidden network fallback.

## API, UI, and AI findings

FastAPI routers, Pydantic DTOs, SQLAlchemy conversation persistence, model and
token accounting, React Query lifecycle handling, Zod response validation,
Zustand state, and chart composition are useful patterns. They remain donor
patterns, not canonical contracts.

The chat path is directly coupled to Gemini configuration and invocation. A
future platform assistant must instead use a provider-neutral adapter, cite
canonical evidence, expose uncertainty, and possess no authority to mutate
orders, positions, risk, execution, or accounting. Authentication tokens and
user objects are persisted in browser `localStorage`; that pattern requires an
independent security decision and must not be adopted by default.

## Private SQLite artifact

The bundled `gridiq-backend/gridiq.db` is 196,608 bytes. A schema/count-only
inspection observed 3 user rows, 12 conversation rows, 44 message rows, and zero
rows in game, play, and cache tables. No values were inspected.

The database is private donor state. Password hashes, users, account fields,
conversation/message content, and identifiers are excluded from copying,
fixtures, evidence publication, and canonical ingestion. Preservation evidence
represents the database only through opaque metadata.

## Dependency, test, and licensing state

- `gridiq-backend/requirements.txt` pins most entries but leaves
  `email-validator` unpinned.
- The README requires `pyarrow`, while `requirements.txt` omits it.
- No automated backend or frontend tests were observed.
- No root `LICENSE` exists even though the root README refers to one.
- `gridiq-frontend/LICENSE` contains only the title and copyright line; it lacks
  the permission grant, conditions, and disclaimer required to support an MIT
  license claim.
- The UI describes nflverse data as CC BY 4.0, but that claim was not
  independently verified in this offline task.

These facts require conservative treatment: no direct copying, no license claim,
and separate review of repository code, dependencies, nflverse data, and the
bundled database.

## Reuse classification

`PORT_ADAPT` means independently reimplement behind canonical interfaces after
rights, phase, and tests; it never means copy donor code.

| Component | Class | Canonical destination | Earliest phase | Preconditions and verification |
|---|---|---|---|---|
| Parquet column projection | `PORT_ADAPT` | dataset reader adapter | Phase 5R | Immutable dataset manifest; schema/version/hash checks; byte limits |
| Missing-column fill | `CONCEPT_ONLY` | schema-evolution policy | Phase 5R | Explicit optional-field registry; unknown drift fails closed |
| Schedule disk cache | `CONCEPT_ONLY` | disposable dataset cache | Phase 5R | Content addressing, invalidation, offline determinism |
| PBP memory cache | `CONCEPT_ONLY` | bounded cache interface | Phase 5R | Byte/entry bounds, precision policy, deterministic eviction |
| SQL TTL cache | `CONCEPT_ONLY` | application cache only | Later UI/API phase | Never used as canonical dataset identity |
| FastAPI routers and DTO transforms | `PORT_ADAPT` | future read-only research API | Later UI/API phase | Canonical contracts first; provider DTO isolation; error tests |
| Conversation persistence and accounting | `PORT_ADAPT` | research-assistant audit store | Later AI phase | Privacy retention, model/provider provenance, immutable citations |
| React Query, Zod, Zustand, charts | `PORT_ADAPT` | future research UI | Later UI phase | Accessibility, failure states, runtime validation, no trade authority |
| Gemini invocation | `DO_NOT_USE` | none as written | Never | Direct provider coupling and no canonical citation/authority boundary |
| Browser token storage | `DO_NOT_USE` | none as written | Never | Independent threat model and accepted auth ADR required |
| Incomplete frontend license | `DO_NOT_USE` | none | Never | Not sufficient evidence of MIT permission |
| Bundled SQLite database | `DO_NOT_USE` | none | Never | Private state and unresolved rights |

## Required future tests

- object-size, cache-byte, eviction, precision, and corrupt-cache tests;
- schema drift, optional-column, and incompatible-column tests;
- immutable hash/version identity and offline no-network replay;
- DTO/domain separation and stable error contracts;
- query cancellation, stale/error/empty UI states, and accessibility;
- prompt-injection, citation resolution, unsupported-claim, and no-authority tests;
- privacy deletion/retention and secret-container checks.

The authoritative cross-donor disposition is in
[DONOR_REUSE_MATRIX.md](DONOR_REUSE_MATRIX.md). Rights states are recorded in
`docs/superpowers/governance/2026-08-14-donor-code-permissions.json`.
