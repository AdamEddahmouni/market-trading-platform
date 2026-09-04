# OF-03 Agent Operating Rules

| Field | Value |
|---|---|
| Document ID | `AGENT-RULES-OF03` |
| Version | `1.0` |
| System | `IMP-OF-03` |

Agents MUST inspect registry status before consequential registry use.

Agents MUST select exact `id` + `definition_version`. Implicit latest is
prohibited.

Agents MUST NOT:

- self-register a capability to gain authority
- modify `required_authority_refs` or `automation_policy` to bypass a gate
- treat registration as authorization
- invoke arbitrary bindings from untrusted registry content
- invent missing SOP/workflow definitions
- silently select latest versions
- rewrite historical definition versions
- delete definitions referenced by historical OF runs
- claim capability availability from registration alone
- execute a destructive capability solely because it is listed
- bypass human-approval requirements
- create an execution engine through registry helper code
- loosen their own policy and then execute in one uncontrolled path
- attribute consequential registry changes without OF-01 provenance where required

`evaluate_agent_use` never returns authorization to execute. Registry
modifications occur only through ordinary repository change control.
