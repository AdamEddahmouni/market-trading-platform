# OF-01 Agent Operating Rules

| Field | Value |
|---|---|
| Document ID | `AGENT-RULES-OF01` |
| Version | `1.0-draft` |
| Status | `NORMATIVE_RUNTIME_DRAFT` |
| Applies to | Cursor, Codex, OpenCode, research/operations/workflow/ADAPT/AI agents, and unattended automation |

These rules apply equally to deterministic automation and AI. An agent's
ability to invoke a tool does not grant authority to use it. `MUST`, `MUST NOT`,
`SHOULD`, and `MAY` are normative.

## Preconditions for consequential action

Before maintenance, recovery, migration, destructive CAS work, or an
authority-affecting workflow, an agent MUST read:

1. the controlling OF-01 specification and relevant SOP/workflow;
2. structured `OF01.OP.STATUS` including ledger authority, schema/profiles,
   mode, readiness, integrity, latest commit, CAS and projection state;
3. its granted role/capabilities and explicit authorization reference; and
4. current operation evidence and unresolved findings.

If any required state cannot be proven, the agent MUST stop and surface
`STOP_VERIFY_REQUIRED`. It MUST NOT infer success or safety from absence of an
error message.

## Rule A — Inspect before acting

Agents MUST compare the intended target authority, source/tool version,
schema/profile compatibility, service mode, readiness, and required
authorization before consequential action. Stale status MUST be refreshed at
the action boundary.

## Rule B — Typed interfaces only

Agents MUST use approved typed command, read, integrity, and operation
capabilities. Agents MUST NOT issue arbitrary SQL, import internal SQLite
connections, fabricate CAS metadata, choose CAS paths, or use Mongo/projections
as a reverse mutation channel.

## Rule C — Stable command identity

An agent MUST allocate `command_id` and every new domain ID before first
submission and preserve them plus the canonical semantic content/hash across
retries. After timeout or connection loss it MUST query the command receipt
before resubmission. Generating new IDs creates a new command and MUST NOT be
described as retry.

## Rule D — No fabricated success

An authoritative command succeeds only when a matching receipt proves the
commit. Backup, restore, integrity, projection, migration, GC, startup, and
shutdown success require their structured verification evidence. An agent MUST
NOT turn `unknown`, `incomplete`, `unverified`, an exit timeout, or optimistic
log text into success.

## Rule E — No hidden repair

Agents MUST surface record/commit/CAS/integrity mismatches and stop writes as
specified. They MUST NOT recompute stored hashes, update/delete rows, remove
evidence, invent missing bytes, suppress findings, or silently change schemas.

## Rule F — Preserve evidence

Before destructive remediation an agent MUST preserve the incident handoff
fields in the runbook. It MUST NOT clean, truncate, overwrite, or relocate
original DB/WAL/SHM/CAS/log evidence unless an authorized procedure explicitly
does so after capture and verification.

## Rule G — No secret persistence

Agents MUST reject credentials, tokens, private keys, raw cookies, arbitrary
environment dumps, and other prohibited secrets before commands/artifacts/logs.
They MUST use approved non-secret provider/reference identities. They MUST NOT
hash low-entropy secrets as redaction or include secrets in operation evidence.

## Rule H — No authority escalation

Agents MUST NOT grant themselves typed-command, maintenance, recovery,
destructive, migration, activation, broker, risk, release, promotion, or
execution authority. They MAY prepare plans/dry runs under read authority, but
must obtain consequence-appropriate authorization for execution.

## Rule I — No projection as truth

Agents MUST treat Mongo and current-state materializations as derived. On
divergence they MUST compare against SQLite authority and repair the projection
by resume/rebuild. They MUST NOT edit ledger history to make it match a view.

## Rule J — No history rewrite

Agents MUST use new typed outcome, disposition, transition, relationship, or
correction records. They MUST NOT update/delete authoritative history, reuse an
ID for different content, or describe a mutable projection as the authoritative
record.

## Rule K — No unsupported topology

Agents MUST NOT place or activate SQLite authority on SMB, NFS, another network
filesystem, or an unproven filesystem. They MUST NOT start a second writer,
activate two restored copies, simulate multi-primary failover, or merge
divergent ledgers.

## Rule L — No autonomous destructive maintenance

Agents MUST NOT autonomously execute CAS deletion, backup pruning, database
replacement, restore activation, migration, authority reinitialization, or
destructive break-glass repair. Dry runs MAY be produced when scoped. Execution
requires explicit authorization bound to exact target/input manifest and a
human/recovery role where the authority matrix requires it.

## Rule M — Surface uncertainty

Agents MUST report uncertainty with exact missing evidence and safest next
verification. They MUST NOT guess that a commit, backup, restore, projection,
migration, integrity check, or shutdown completed. Repeated failure is a reason
to diagnose and hand off, not to create retry storms or weaken safeguards.

## Human handoff requirements

An agent MUST stop and request human/recovery direction when:

- a fatal integrity finding, suspected fork, or custody conflict exists;
- restore activation, authority identity change, schema migration, database
  replacement, backup pruning, or destructive GC is proposed;
- required authorization does not exactly match the current target/manifest;
- the procedure would exceed the agent's granted role;
- secrets may have entered durable authority; or
- the controlling docs/runtime disagree on consequential behavior.

The handoff includes proposed action, why it is required, exact target
authority/operation IDs, current mode/readiness, evidence references, risk,
reversibility, and the specific authorization needed.

## Prohibited shortcuts

Agents and humans MUST NOT use:

```text
manual INSERT/UPDATE/DELETE; "fix the hash"; "delete the bad row";
raw copy of an active DB/WAL folder as backup; age-based CAS deletion;
new retry IDs after timeout; projection-to-SQLite mutation;
network-share authority; hidden schema upcast; automatic corruption repair;
unverified backup/restore success; silent failure suppression
```

## Required negative tests

Runtime acceptance MUST prove that an agent-facing capability cannot:

- obtain arbitrary SQL mutation;
- treat same command ID/different hash as retry;
- present new IDs as the same operation;
- execute destructive GC/activation/migration without exact authorization;
- report backup/restore/integrity/projection success without verification;
- elevate Mongo/current state to authority;
- rewrite or delete corrupt history; or
- persist a prohibited secret through any supported command/artifact interface.

## Allowed examples

An authorized scoped agent MAY inspect status, stream granted records, submit a
typed command under its domain grant, resolve its own ambiguous receipt, run a
non-destructive CAS orphan scan, inspect projection lag, prepare a GC dry run,
or draft incident evidence. These permissions do not imply authority to perform
the next destructive or domain-governed step.
