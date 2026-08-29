# OF-03 known limitations

These are OF-03-scoped limitations, not broader platform limitations.

1. Twenty-five `OF01.OP.*` capabilities remain `UNBOUND` because OF-01 still exposes them as operator stubs. The registry reports that truthfully and does not fake availability.
2. OF-02 adapter capabilities are `DISABLED` while `IMP_OF02_ENABLED` / per-adapter flags remain off. `provider_smoke` additionally requires `IMP_LIVE_PROVIDER_AVAILABLE` before it can become `AVAILABLE`. Binding verification does not execute provider smoke.
3. BUILD 21–23 operational surfaces without stable OF operator IDs are deferred, not invented.
4. SOP document integrity uses identifier headings and whitespace-normalized section hashes, not semantic prose comparison.
5. Workflow execution, scheduling, and agent orchestration remain intentionally out of scope (architectural boundary).
