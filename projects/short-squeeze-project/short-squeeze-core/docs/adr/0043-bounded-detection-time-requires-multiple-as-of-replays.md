# ADR 0043: Bounded detection time requires multiple as-of replays

## Status

Accepted (Phase 2V).

## Context

Reconstructing a historical decision needs an `as_of`. For the BIYA case no artifact
records a platform event time: the only direct platform record carries no timestamps at
all, so both bounds rest on filesystem metadata.

Manufacturing a point estimate would make replay simpler and would be indefensible — it
would present a chosen instant as a recorded fact. But replaying at a single edge of the
window is barely better: it invites, and cannot detect, choosing the edge that produces
the more favourable result.

A related question arose over which window to use. The recording filename
`20260717_124615.mp4` gives a precise 8m43s interval during which the candidate was
discussed on screen. It is tempting because it is narrow. But it bounds when a person
*spoke*, not when the platform *decided* — and the log shows the candidate appearing at
file line 4, essentially at screener startup, well before.

## Decision

Detection time is classified as exactly one of `EXACT_TIMESTAMP`, `BOUNDED_TIME_WINDOW`,
or `UNKNOWN`. There is deliberately no `APPROXIMATE` or `ESTIMATED` member: an
approximate time is a bounded window.

`EXACT_TIMESTAMP` requires an embedded event time on a `DIRECT_PLATFORM_RECORD`.
Filesystem metadata never qualifies, and a `VALIDATION_DETECTION_TIME_FILESYSTEM_ONLY`
diagnostic records when metadata is doing the bounding.

**A bounded window is replayed at both edges.** `replay_boundaries()` returns `earliest`
and `latest`; both are computed, anchored, and exported. Selecting one is not expressible
through the API. Divergence between them is a reported finding that quantifies how much
the conclusion depends on precisely when detection occurred.

Conflicting direct records **widen** the window to span every claim, with a
`VALIDATION_DETECTION_TIME_CONFLICTED` diagnostic — a disagreement is evidence about
uncertainty, not a tie to be broken.

The window resolved is the one bounding the **platform's decision**, not human
observation of it. For BIYA that is `2026-07-17T14:23:58Z`–`16:54:58Z` (2h31m). The
narrower meeting interval is recorded as corroboration; substituting it would claim
roughly 17× more precision than the evidence supports.

Only artifacts with `bounds_detection_event` contribute bounds. An artifact can be
genuine case evidence while bounding nothing about a particular candidate's detection —
an email that never names the symbol, or a note written hours later. Without this,
irrelevant modification times silently widen windows; it was added after the advisor
email pushed the BIYA window a full day past the log's last write.

## Consequences

Every bounded case carries at least two replays, so anchors, exports, and the demo all
handle replay collections rather than a single result.

Wide windows are visible rather than hidden. A 2h31m window is less satisfying than a
timestamp, and it is what the evidence supports.

Narrowing the window is a concrete, high-value acquisition target: a single screenshot or
a recalled time would tighten it substantially, which is why it leads the questions in
the advisor meeting brief.
