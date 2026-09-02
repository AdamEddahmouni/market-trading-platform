# OF-02 known limitations

These are OF-02-scoped limitations, not broader platform limitations.

1. Native attribution is disabled by default (`IMP_OF02_ENABLED` plus per-adapter flags).
2. Real provider smoke is not executed in this acceptance; fixture/NOT_EXECUTED only.
3. Training/research/promotion/drift adapters record existing domain identities; they do not invoke BUILD 17–24 engines inside OF-02 tests.
4. Retrospective indexing covers file-backed JSON sources. Mongo is never authority.
5. Native `validate.py` attribution is best-effort when enabled without a configured ledger writer.
6. Multiple domain identities on one request currently attach the first identity as an OF provenance reference; remaining IDs stay in adapter extras.
