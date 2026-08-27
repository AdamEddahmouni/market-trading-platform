# IMP-REBASE-01 known limitations

These are current program limitations, not a general technical-debt inventory.
None weakens the integrity of the REBASE-01 canonical documentation layer.

1. EVIDENCE-01C has not been operationally accepted; EVIDENCE-01B remains the
   latest implemented evidence milestone.
2. Production live broker transport is absent, autonomous live execution is
   disabled, human session and per-order gates remain mandatory, and automatic
   broker failover remains disabled.
3. Universal run attribution, append-only attempt preservation, and a global
   artifact index are incomplete pending REBASE-02 and OF-01.
4. End-to-end causal tracing and measured latency budgets are incomplete;
   current performance benchmark provenance is insufficient for an event-bus,
   persistence, or native-hot-path redesign.
5. AI live-inference attribution does not yet freeze the complete prompt,
   evidence pack, settings, tool, request/response, code, configuration, and
   run identity required by AI-01.
6. The IMP Operating Fabric is not universal, and a workflow/capability/SOP
   registry does not yet exist.
7. A universal Cross-Asset identity and relationship kernel and admitted
   sovereign-rates vertical are not implemented.
8. The REBASE-00 inventory hash was recorded for a CRLF materialization. Git's
   normalized LF checkout has a different byte hash, while CRLF reconstruction
   exactly reproduces the recorded byte count and SHA-256. REBASE-00 remains
   unchanged; consumers must account for the repository's line-ending rule.
