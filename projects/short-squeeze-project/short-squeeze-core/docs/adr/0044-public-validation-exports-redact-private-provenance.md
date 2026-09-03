# ADR 0044: Public validation exports redact private provenance

## Status

Accepted (Phase 2V).

## Context

Phase 2V produces a publicly deployable research demonstration. Its inputs include
material that must never be published: an application log containing a live provider API
credential, meeting transcripts and correspondence naming a real individual, and
workspace paths describing the operator's filesystem.

The obvious approach — serialize the internal case, then strip the sensitive parts — has
a failure mode that only shows up later. It is safe exactly once. The next field added to
the internal model is published by default, and stays published until someone remembers
it needs redacting. The failure is silent and the feedback loop is a leak.

## Decision

The public export is built by **whitelist projection**. `PublicValidationCase` is
constructed field by field from named sources; a `ValidationCase` is never copied and
stripped. A field added to the internal model is therefore **absent from the export by
default**, and appears only when someone deliberately adds it to the projection.

Three further guards, in depth:

1. `ValidationArtifact` rejects at construction any artifact that is both `sensitive` and
   `included_in_public_demo`, and `public_artifacts()` requires the positive flag *and*
   the absence of the sensitive flag.
2. `relative_path` rejects drive-rooted, UNC, and POSIX-absolute paths, so a local path
   cannot enter canonical bytes — and therefore cannot enter a hash or an export.
   `public_artifact_summary()` omits the path entirely: even a workspace-relative path
   describes the operator's layout and is unnecessary for judging evidence weight.
3. `assert_export_is_clean()` re-scans the rendered bytes for absolute paths, credentials
   in query strings, API keys, tokens, and email addresses, raising `PublicExportError`
   before anything is written. The CLI calls it on every export.

Internal artifact manifests may reference workspace-relative paths; public exports may
not reference paths at all. Each withheld artifact produces a
`VALIDATION_PUBLIC_EXPORT_REDACTED` diagnostic, so redaction is auditable rather than
invisible.

## Consequences

The public payload is deliberately thin: for the BIYA case, two of five artifacts appear,
identified only by id, type, and reliability class. A reader can assess evidential weight
without seeing the evidence, which is the intended trade.

Adding a field to the demonstration requires an explicit projection change and a
deliberate judgement that it is publishable. That friction is the point.

The credential found in the archived application log is out of scope for this phase to
rotate, but it is recorded in the artifact inventory and flagged, because a credential in
a committed archive remains exposed regardless of what this export does.
