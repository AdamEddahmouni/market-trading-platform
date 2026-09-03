# OF-02 Agent Operating Rules

| Field | Value |
|---|---|
| Document ID | `AGENT-RULES-OF02` |
| System | `IMP-OF-02` |

Agents MUST NOT:

- fabricate historical provenance
- backdate OF records
- promote `LEGACY_PARTIAL` to complete without evidence
- rewrite historical evidence
- write SQLite directly
- bypass the OF-01 writer
- regenerate retry IDs
- treat Mongo as authority
- hide C3/C4 attribution failures
- create future-information leakage
- change domain results merely for attribution convenience

Agents MUST use `OF02.OP.*` capabilities and typed adapter APIs. Domain IDs
remain domain IDs. OF `recorded_at` is writer-allocated contemporaneous time.
