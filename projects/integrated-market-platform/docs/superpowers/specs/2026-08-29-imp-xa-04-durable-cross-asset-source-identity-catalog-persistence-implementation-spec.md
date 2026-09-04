> **Permanent constraint (Mongo/persistence):** Design for Mongo compatibility now, but **no paid Mongo/cloud database usage** until the user explicitly authorizes it after reviewing pricing, limits, expected usage, monthly cost, and billing-control options.

XA-03 is sufficiently closed to proceed. This milestone implements the report recommendation:

```text
IMP-XA-04 — Durable Cross-Asset Source & Identity Catalog Persistence
```

Use **Cursor Composer 2.5**.

---

# CURSOR COMPOSER 2.5
# IMP-XA-04 — Durable Cross-Asset Source & Identity Catalog Persistence
## Audit → Persistence Contract → In-Memory + Mongo → Restart/Conflict Proof → Operations → Acceptance

You are implementing:

# `IMP-XA-04 — Durable Cross-Asset Source & Identity Catalog Persistence`

for the Integrated Market Platform.

This is a **full implementation and acceptance campaign**, not design-only.

The cross-asset sequence now has:

```text
XA-01
canonical instrument identity/domain kernel
        ↓
XA-02
FRED scalar macro/rates admission
        ↓
XA-03
CFTC structured positioning admission
        ↓
XA-04
durable source + identity catalog persistence
```

XA-04 must make the proven cross-asset identity/admission state durable **without changing its semantics**.

The central rule is:

> **Persistence stores canonical XA truth; it must not become a second identity authority, a market-data history database, or a place where conflicting records are silently overwritten.**

---

# 1. Canonical base

Repository:

```text
C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
```

Start exactly from:

```text
ed4baff27c6f23f089153ee59b906c0a0a458aa4
```

Expected recent lineage:

```text
44e266e  XA-01
   ↓
f8a3634  XA-02
   ↓
eb700a4  XA-03 source-neutral envelope
   ↓
ad7f221  CFTC vertical
   ↓
1f2a842  XA-03 tests
   ↓
58192a4  XA-03 registration
   ↓
ed4baff  XA-03 closure
```

Reported latest validation:

```text
3195 tests
3153 passed
42 skipped
0 failures
0 errors
```

Verify Git truth before editing.

---

# 2. Composer execution mode

Use short verified loops:

```text
audit
→ reuse existing repository pattern
→ implement one repository slice
→ focused tests
→ inspect diff
→ continue
```

Do not:

```text
redesign XA identities
change FRED/CFTC semantics
create a generic database framework
persist every market tick
migrate all historical provider data
make Mongo mandatory
silently overwrite conflicting records
stop after writing a spec
```

Prefer existing repository/storage abstractions.

---

# 3. Isolated worktree

Recover:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git log -25 --oneline --decorate
git worktree list
git branch --all
```

Preserve all existing worktrees and dirty state.

Create:

```text
branch:
build/imp-xa-04-durable-catalog

worktree:
.worktrees/imp-xa-04
```

from exactly:

```text
ed4baff27c6f23f089153ee59b906c0a0a458aa4
```

Never use:

```text
git reset --hard
git clean
broad stash
force push
```

---

# 4. Read controlling architecture

Read current:

```text
docs/platform/MASTER_ARCHITECTURE.md
docs/platform/PROGRAM_STATUS.md
docs/platform/MASTER_ROADMAP.md
docs/platform/CANONICAL_TRUTH_MAP.md
docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md
```

Read and inspect:

```text
XA-01 spec + src/.../xa01/
XA-02 spec + src/.../xa02/
XA-03 spec + src/.../xa03/
```

Then audit existing repository implementations, especially:

```text
InMemory repository patterns
Mongo repository patterns
schema validators
index creation
idempotent insert logic
content-hash/conflict logic
BSON time conversion
repository protocols
```

Reuse established IMP persistence conventions rather than inventing another style.

---

# 5. Preserve proven XA semantics

Required final state:

```text
XA-01 identity semantics changed: NO
XA-02 FRED semantics changed: NO
XA-03 CFTC semantics changed: NO
```

Persistence must store those records.

It must not redefine them.

Also preserve:

```text
OF-01 Invariants 1–75
OF-02 attribution semantics
OF-03 authority semantics
RT-01 tracing
EVIDENCE
prediction/settlement
risk/execution
```

---

# 5A. HARD COST / CLOUD DATABASE GUARDRAIL

**The user has not authorized any paid MongoDB service, paid cloud database, or usage that could incur MongoDB Atlas/cloud charges.**

Until the user explicitly gives separate approval after reviewing pricing, limits, architecture, and expected usage:

```text
PAID_MONGODB_AUTHORIZED: NO
PAID_MONGODB_ATLAS_AUTHORIZED: NO
PAID_CLOUD_DATABASE_AUTHORIZED: NO
AUTO-UPGRADE_TO_PAID_TIER: PROHIBITED
```

This is a hard acceptance boundary.

XA-04 must be fully developable, testable, and usable locally **without paying for MongoDB**.

Preferred development/acceptance modes:

```text
1. InMemory repository
2. Local self-hosted MongoDB Community Edition if already available / safely installable
3. Deterministic repository-contract fixtures/mocks where appropriate
4. Mongo integration tests skipped when a local Mongo instance is unavailable
```

Do **not** require MongoDB Atlas for XA-04 acceptance.

Do **not** create an Atlas cluster, organization, project, billing account, paid database, or cloud resource.

Do **not** enter payment information.

Do **not** activate a trial that may automatically convert to paid usage.

Do **not** enable paid backups, search, vector search, data federation, serverless resources, dedicated clusters, paid monitoring, or other billable MongoDB/cloud features.

Do **not** assume a free tier is acceptable merely because it is currently advertised as free. Cloud pricing, limits, suspension behavior, upgrade behavior, and billing rules can change.

If any implementation step would require:

```text
credit card
billing profile
paid tier
trial with possible conversion
usage-based charges
cloud resource creation
```

STOP that step and classify it:

```text
REQUIRES_USER_COST_APPROVAL
```

Do not proceed with it.

The user must first be given a clear explanation of:

```text
what service would be used
why it is needed
whether a local/free alternative exists
exact current pricing model
free-tier limits
storage limits
compute limits
network/egress costs if applicable
backup costs
expected IMP usage
estimated monthly cost
conditions that could increase cost
how billing can be capped or prevented
how the service can be shut down
```

Only after the user explicitly approves may any paid/cloud MongoDB dependency be introduced.

---

# 6. First task — persistence-surface audit

Before implementing anything, inventory exactly what XA currently keeps only in memory.

Build an internal matrix:

| Record family | Current owner | Identity | Mutable? | Needs durability? | Existing storage? | XA-04 action |
|---|---|---|---|---:|---|---|

Audit at least:

```text
XA-01 canonical instruments
aliases / external identifiers
domain participation
instrument relationships

XA-02 admitted source definitions/observations
source provenance
cross-asset reference relationships

XA-03 AdmissionEnvelope
CFTC source/report identities
PositioningPayload observations
bounded source catalog
```

Also identify anything that should explicitly **not** be persisted by XA-04.

---

# 7. Persistence scope

XA-04 should persist canonical low/moderate-frequency catalog truth such as:

```text
instrument definitions
aliases/external identifiers
domain memberships
typed relationships

source definitions
admission envelopes
admitted observations
source provenance
source→XA reference relationships
```

Do **not** turn XA-04 into storage for:

```text
tick history
quotes
trades
order book
dense feature telemetry
RT-01 spans
positions/orders
prediction ledger
OF run history
```

Those retain their existing authorities.

---

# 8. One repository abstraction — local/free-first

Implement one coherent backend-independent XA catalog repository contract.

Conceptually:

```text
CrossAssetCatalogRepository
```

or repository-equivalent naming.

It should support typed operations for the actual XA record families.

Do not expose raw Mongo concepts to domain code.

Required implementations:

```text
InMemory
Mongo-compatible repository
```

But the Mongo implementation must **not require a paid Mongo service**.

Acceptance must work with:

```text
InMemory
+
repository contract tests
```

and, where available:

```text
local MongoDB Community Edition
```

Mongo integration tests must skip cleanly if no local Mongo instance exists.

A remote MongoDB Atlas/database instance is **not** an XA-04 acceptance requirement.

Domain code must remain backend-independent so a deployment backend can be selected later after cost/security/operational review.

---

# 9. Repository authority

The repository stores canonical XA records.

It does not generate identity.

Identity remains defined by XA-01/02/03 contracts.

Expected flow:

```text
domain creates canonical record
        ↓
repository validates
        ↓
repository stores exact immutable content
```

not:

```text
repository inserts data
        ↓
database invents canonical identity
```

---

# 10. Immutability / conflict semantics

For immutable canonical records:

```text
same canonical ID + same immutable content
→ IDEMPOTENT / EXISTING

same canonical ID + different immutable content
→ CONFLICT
```

Never:

```text
same ID + different content
→ UPDATE IN PLACE
```

unless an existing XA record is explicitly defined as mutable status state, which should be rare and separately justified.

Default XA-04 policy is immutable or append-only.

---

# 11. No update/delete convenience APIs

Do not add generic:

```text
update_record(...)
delete_record(...)
upsert_anything(...)
```

to canonical XA storage.

Where correction/evolution is required, use existing semantics such as:

```text
new revision identity
new observation
new alias validity row
new relationship version
supersession
```

according to the source/domain contract.

Do not rewrite historical truth.

---

# 12. Observation revisions

This is critical.

For FRED/CFTC admitted observations:

```text
later revision/correction
≠ overwrite original observation
```

The repository must preserve both when their source semantics identify them separately.

Historical cutoff selection must still be able to distinguish what was available when.

Persistence must not destroy PIT semantics.

---

# 13. Alias temporal validity

Where alias rows already carry:

```text
valid_from
valid_to
```

or equivalent temporal semantics, persist them exactly.

Do not guess missing historical periods.

Queries must not silently resolve a temporally invalid alias at an earlier/later cutoff.

If XA-01 currently lacks full historical alias validity, preserve that limitation rather than fabricating intervals.

---

# 14. Source-neutral persistence

Mongo collection structure must not hard-code:

```text
fred_only
cftc_only
```

as the fundamental admission architecture.

Source-specific typed payloads are allowed.

The persistence layer must preserve:

```text
common AdmissionEnvelope
+
typed payload
```

without collapsing payloads into unvalidated blobs.

---

# 15. Typed payload persistence

Persist enough type information to reconstruct exactly:

```text
ScalarMacroPayload
PositioningPayload
```

and future approved payload families.

Use explicit:

```text
schema_version
payload_kind
```

or existing equivalent.

Reject unknown unsupported payload kinds.

Do not deserialize arbitrary Python types dynamically.

---

# 16. Mongo storage strategy — no paid dependency

Design the Mongo backend so it is compatible with a normal MongoDB deployment, but validate it using **local MongoDB Community Edition where available**.

Hard requirements:

```text
no Atlas-specific runtime dependency
no paid Mongo feature dependency
no cloud-only feature dependency
no mandatory remote connection
no billing-required acceptance test
```

Use ordinary Mongo collections, validators, and indexes that work with the supported local/community deployment unless repository evidence requires otherwise.

Do not use time-series collections just because observations contain timestamps.

XA-04 records are canonical admitted records/reference metadata, not dense tick telemetry.

Prefer collections aligned to semantic families rather than one giant polymorphic collection if existing repository patterns favor typed collections.

Let the audit/spec determine the exact layout.

Do not use paid/cloud-only features for convenience.

Do not use:

```text
Atlas Search
Atlas Vector Search
Atlas Data Federation
Atlas-specific triggers/functions
dedicated-cluster-only features
paid backup services
cloud-only observability
```

in XA-04.

If a feature is not available in the permitted local/free environment, either:

```text
implement a backend-neutral alternative
```

or:

```text
defer it explicitly
```

rather than creating a paid dependency.

---

# 17. Required indexes

Define indexes from actual query/integrity needs.

Likely categories include:

```text
canonical identity uniqueness
source observation identity uniqueness
provider/source identifier lookup
alias scoped lookup
XA relationship lookup
indicator/source lookup
available_time / event-time selection where required
payload/source family lookup
```

Do not create speculative indexes.

---

# 18. Mongo validators

Use schema validators consistent with existing repository practice.

Validators should enforce key structural invariants, not duplicate every Python-domain check unnecessarily.

At minimum protect:

```text
identity
schema version
record type
required temporal fields
payload type
```

where appropriate.

---

# 19. Integer/time fidelity

Audit repository BSON conventions.

Preserve nanosecond/integer timestamps without floating-point conversion.

If existing storage uses BSON `Int64` for `*_time_ns`, reuse it.

Round trip must preserve exact values.

---

# 20. Deterministic serialization

Persistence round trip must not modify the semantic record.

Required:

```text
record
→ repository
→ read
→ equivalent canonical record
```

Canonical hash/identity must remain stable.

Do not let Mongo field ordering or BSON conversions alter identity.

---

# 21. First vertical slice

Before implementing every family, prove:

### XA-01

```text
GOLD instrument
+
GC family/relationship
+
aliases/domains
```

### XA-02

```text
one FRED admitted observation
```

### XA-03

```text
one CFTC positioning admitted observation
```

through:

```text
write
→ read
→ restart/new repository instance where backend supports it
→ resolve/query
→ exact semantic comparison
```

Run focused tests before expanding.

---

# 22. Restart durability

For Mongo durability tests, use a **local MongoDB Community Edition instance only if one is already available or can be used without any charge**.

Required semantic test when available:

```text
write records
→ destroy repository object
→ create new repository object
→ read records
→ exact semantic state preserved
```

If local Mongo is unavailable:

```text
Mongo integration:
SKIPPED_ENVIRONMENT_UNAVAILABLE
```

not failure and not fabricated success.

Repository-contract, serialization, identity, idempotency, and conflict behavior must still be completely testable without Mongo.

Do not create an Atlas instance merely to make these tests run.

Do not claim restart durability from the InMemory backend.

Never fake a Mongo result.

---

# 23. Query contract

Provide only queries required by current XA capabilities, such as:

```text
get instrument by canonical ID

resolve scoped alias

list aliases for instrument

list domains

list relationships from/to instrument

get source definition

get observation by ID

list observations for source/indicator

list source relationships for XA subject

PIT observation selection where repository owns that query
```

Do not create a generic arbitrary query language.

---

# 24. PIT query correctness

If repository APIs support:

```text
as_of(decision_time)
```

they must enforce the existing temporal rules.

For admitted observations:

```text
available_time <= decision_time
```

must remain mandatory.

Latest-retrieved record must not automatically win if it was unavailable at the historical cutoff.

Add deterministic negative tests.

---

# 25. Duplicate/retry behavior

Mandatory tests:

```text
same exact insert twice
→ idempotent

same ID changed content
→ conflict

lost caller response then retry
→ no duplicate

same relationship twice
→ idempotent

same alias identity changed target
→ conflict

same observation with same immutable content
→ idempotent
```

Use the existing exception/result vocabulary where available.

---

# 26. Batch writes

If batch write support is necessary, define semantics explicitly.

Do not leave ambiguous whether partial batches are accepted.

Preferred behavior:

```text
validate entire batch
then commit according to repository transaction guarantees
```

if existing Mongo repository conventions support it.

Otherwise document and test precise partial-failure semantics.

Do not invent distributed transactions.

---

# 27. No cache-as-authority confusion

If an in-memory cache/index is added for performance:

```text
Mongo durable repository
→ authority
in-memory cache
→ derived acceleration
```

not the reverse.

Cache rebuild must come from the durable backend, never from stale cache state.

If cache and durable store disagree, durable store wins and cache is invalidated.

---

# 28. Domain wiring

Wire existing XA-01/02/03 domain services to the repository through explicit adapters.

Do not silently replace in-memory registries without an audited migration path.

Preserve current public behavior while adding durable persistence behind the same contracts.

---

# 29. OF integration

XA-04 persistence operations that run consequential catalog writes should integrate with OF-01 where repository conventions require ledgered runs.

Do not make OF-01 the identity authority for XA records.

---

# 30. OF-03 registration

Register durable catalog operator capabilities such as:

```text
XA04.OP.STATUS
XA04.OP.VALIDATE
XA04.OP.SHOW_RECORD
XA04.OP.LIST_CATALOG
```

Update:

```text
config/of03/manifest.json
config/of03/capabilities.json
config/of03/sops.json
docs/operations/xa-04/SOPS.md
```

Update registry snapshot hash per OF-03 convention.

---

# 31. RT-01 boundary

RT-01 spans remain non-authoritative telemetry.

Do not persist RT-01 trace payloads in the XA catalog repository.

---

# 32. EVIDENCE isolation

EVIDENCE admission semantics remain separate.

Do not retrofit EVIDENCE records into XA catalog storage in XA-04.

---

# 33. No trading authority

Catalog persistence must not introduce order, risk, broker, or execution authority.

---

# 34. Implementation spec

Maintain a compact controlling spec record in this same file path and update it as decisions are made during implementation.

Record audit matrix, collection layout, index/validator decisions, and known limitations.

---

# 35. Suggested Composer stages

```text
1. persistence-surface audit matrix
2. CrossAssetCatalogRepository contract
3. InMemory implementation + contract tests
4. vertical slice (GOLD + one FRED obs + one CFTC obs)
5. Mongo-compatible implementation (local/community only)
6. restart/idempotency/conflict/PIT tests
7. OF-03 registration + SOPS
8. acceptance artifacts + platform doc reconciliation
```

---

# 36. Mandatory repository-contract tests

Cover all required record families through InMemory backend:

```text
write → read → semantic equality
duplicate insert idempotency
conflict on changed immutable content
batch semantics (if implemented)
query contract surfaces
```

---

# 37. Mandatory serialization tests

Prove canonical identity/hash stability across:

```text
record → persist → read → record
```

including integer nanosecond temporal fields.

---

# 38. Mandatory temporal/PIT tests

Negative tests required when repository owns cutoff queries:

```text
future-available observation excluded at earlier cutoff
revision rows do not overwrite prior PIT truth
alias temporal validity honored when present
```

---

# 39. Mongo integration tests — local only

Mongo integration tests may run only against local MongoDB Community Edition when available.

If unavailable:

```text
SKIPPED_ENVIRONMENT_UNAVAILABLE
```

Never require Atlas.

Never fabricate pass.

---

# 40. Backward compatibility tests

Continuously prove:

```text
XA-01 behavior unchanged except durability path
XA-02 FRED admission unchanged
XA-03 CFTC admission unchanged
```

---

# 41. Repository registration

If adding:

```text
src/market_platform_foundation/xa04/
tests/xa04/
```

register immediately in:

```text
tools/validation_manifest.json
tests/validation/test_validation_manifest.py
artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json
```

---

# 42. Program status reconciliation

Update only as needed:

```text
docs/platform/PROGRAM_STATUS.md
docs/platform/MASTER_ARCHITECTURE.md
docs/platform/MASTER_ROADMAP.md
docs/platform/CANONICAL_TRUTH_MAP.md
```

Claim durable catalog persistence only after acceptance evidence exists.

---

# 43. Acceptance artifacts

Create:

```text
artifacts/imp-rebase/XA04/
```

with repository-conventional evidence such as:

```text
XA04_ACCEPTANCE_REPORT.json
XA04_PERSISTENCE_AUDIT.json
XA04_KNOWN_LIMITATIONS.json
XA04_FILE_HASHES.json
full_validation_output.txt
```

---

# 44. Acceptance artifact contents

Machine-readable evidence should show:

```text
record families persisted
backend implementations present
idempotency/conflict behavior
restart durability classification
PIT query behavior
fixture/live classification
validation result
```

---

# 45. Mongo / cost acceptance

The final report must explicitly state:

```text
Paid MongoDB service used:
NO

MongoDB Atlas resource created:
NO

Payment/billing information required:
NO

Paid cloud feature introduced:
NO

XA-04 requires paid infrastructure:
NO

InMemory backend acceptance:
PASS / FAIL

Local Mongo Community integration:
PASS / NOT_EXECUTED

Remote Mongo integration:
NOT_REQUIRED

Estimated recurring infrastructure cost introduced by XA-04:
$0
```

If the final answer cannot truthfully state:

```text
Estimated recurring infrastructure cost introduced by XA-04:
$0
```

then XA-04 must not be accepted without explicit user approval.

---

# 46. Validation loop

After each major stage:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
```

At closure:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py full
```

Required:

```text
0 failures
0 errors
```

---

# 47. Required regression suites

Before closure run at least:

```text
tests/xa01
tests/xa02
tests/xa03
tests/xa04
tests/of01
tests/of02
tests/of03
tests/rt01
```

plus affected FRED/CFTC/futures suites.

---

# 48. Diff discipline

Inspect full diffs before every commit.

No blind `git add .`.

---

# 49. Protected boundaries

Final audit must report:

```text
XA-01 identity semantics changed: NO
XA-02 FRED semantics changed: NO
XA-03 CFTC semantics changed: NO
OF-01 Invariants 1–75 changed: NO
OF-02 attribution semantics changed: NO
OF-03 authority semantics changed: NO
RT-01 trace semantics changed: NO
EVIDENCE semantics changed: NO
prediction/settlement semantics changed: NO
risk/execution authority changed: NO
catalog became generic market-data database: NO
repository became identity authority: NO
```

---

# 50. Acceptance blockers

Do not accept XA-04 if:

```text
implementation requires MongoDB Atlas
implementation requires a paid Mongo tier
implementation requires entering billing information
a free trial was activated without explicit approval
a cloud resource capable of generating charges was created
Mongo-specific cloud features prevent local operation
tests require remote Mongo to pass
there is no fully usable InMemory/local development path
pricing assumptions are treated as permanent facts
same canonical ID + different immutable content silently overwrites
repository generates identity instead of storing domain identity
PIT availability semantics regress
FRED/CFTC revision semantics collapse into overwrite
unknown payload kinds deserialize without rejection
new executable paths remain unregistered
OF-03 registry invalid
canonical full validation red
Estimated recurring infrastructure cost introduced by XA-04 is not $0 without explicit user approval
```

---

# 51. Legitimate limitations

Possible nonblocking limitations include, only if observed:

```text
local Mongo Community integration not executed
only vertical-slice record families persisted initially
no historical backfill of all provider history
no multi-host replication topology
no cloud deployment backend selected
alias temporal validity limitations inherited from XA-01 preserved
```

---

# 52. Final status

Use exactly one:

```text
IMP_XA_04_COMPLETE
```

or:

```text
IMP_XA_04_COMPLETE_WITH_LIMITATIONS
```

or:

```text
IMP_XA_04_BLOCKED
```

---

# 53. Required final report

Return:

# IMP-XA-04 Durable Cross-Asset Source & Identity Catalog Persistence Report

Include persistence audit matrix, backend implementations, restart/idempotency/conflict proof, Mongo/cost acceptance block, validation results, commits, and limitations.

---

# 54. Final Composer directive

Proceed autonomously from:

```text
ed4baff27c6f23f089153ee59b906c0a0a458aa4
```

in a clean XA-04 worktree.

**Do not begin by coding.**

First complete the persistence-surface audit matrix.

Reuse existing repository patterns.

Prove one vertical slice before expanding.

Preserve all proven XA semantics.

Never turn the catalog into tick history or a second identity authority.

Run changed validation frequently and full validation at closure.

Commit coherent stages.

Do not push.

Do not merge.

> **Financial guardrail:** XA-04 must introduce **$0 of required recurring infrastructure cost**. Use InMemory and local MongoDB Community Edition only. Do not create MongoDB Atlas or any other billable cloud resource. Do not enter billing information or activate a trial that could become paid. If anything potentially billable becomes desirable, stop that portion of the work and report `REQUIRES_USER_COST_APPROVAL`; the user must first review the current pricing, free limits, expected usage, monthly cost, and billing-control options and explicitly approve it.

That is a permanent constraint for current Mongo/persistence work: **design for Mongo compatibility now, but no paid Mongo/cloud database usage until the user explicitly authorizes it after reviewing what it costs and how billing works.**

Finish only when IMP has demonstrated durable cross-asset catalog persistence with exact semantic preservation, proven idempotency/conflict behavior, and truthful local/free-first acceptance without paid infrastructure dependency.
</user_query>