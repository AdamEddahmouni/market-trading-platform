# Historical As-Of Validation Semantics

How Phase 2V replays a historical moment without letting later knowledge leak in.

## 1. The rule

A replay at `as_of = T` may use only evidence whose availability, publication, and
receipt times are at or before `T`. This is not re-implemented in Phase 2V: it is
inherited wholesale from `squeeze_core.evidence.build_point_in_time_evidence`, which
already enforces it across every domain, together with corrections, cancellations,
revisions, and freshness.

`squeeze_core.validation.replay` orchestrates and records. It performs no filtering. A
test asserts the module contains no comparison of any observation timestamp against
`as_of`; if that test fails, a second point-in-time engine has begun to grow, and that is
the bug.

## 2. Bounded detection requires multiple replays

When detection time is a window rather than an instant, one replay is not enough — and
choosing which edge to replay would let the analyst pick the flattering answer.

`replay_boundaries()` therefore returns:

| Detection state | Replays |
| --- | --- |
| `EXACT_TIMESTAMP` | one, labelled `exact` |
| `BOUNDED_TIME_WINDOW` | two, labelled `earliest` and `latest` |
| `UNKNOWN` | none |

Both boundary replays are computed, both are anchored, and both are exported. Divergence
between them is a reported finding, not a problem to resolve: it quantifies how much the
conclusion depends on when precisely detection occurred.

For BIYA the window spans 2h31m (`2026-07-17T14:23:58Z` to `16:54:58Z`), and both
replays return no eligible evidence — because no observation for that symbol exists in
any domain. The empty result is the finding.

## 3. Why the window is not narrower

Two questions have different answers, and conflating them would overstate precision:

- *When was the candidate surfaced by the platform?* Bounded below by the screener run's
  start and above by its log's last write.
- *When was it observed on screen by a person?* An 8m43s interval inside that window.

Phase 2V resolves the **first**, because it validates a platform decision, not a
conversation. Using the meeting interval would claim roughly 17× more precision than the
evidence supports, and would describe when someone spoke rather than when the software
decided.

## 4. What bounds a detection event

An artifact contributes bounds only when `bounds_detection_event` is true. An artifact
can be real evidence about a case while bounding nothing about *this* candidate's
detection — an email that never names the symbol, or a design note written hours later.
Treating every artifact's mtime as a bound silently widens windows with irrelevant
timestamps, so bounding is opt-in per artifact rather than assumed from presence.

Within a bounding artifact:

- an **embedded event time** bounds both sides,
- a **creation time** bounds below — the event cannot precede the run that wrote the file,
- a **modification time** bounds above — the event had occurred by the time writing stopped.

## 5. Later evidence

A correction, cancellation, or revision that arrives after `T` is invisible at `T` and
visible in a later replay. That asymmetry is the point: it lets the same case be examined
as it appeared then and as it appears now, without the two contaminating each other.

It also means a replay's deterministic id changes when `as_of` changes even if the
underlying evidence set is identical, because `as_of` is part of the identity.

## 6. Relationship to outcome observation

Replay and outcome observation are separate models, built by separate functions, and are
never combined into a single "result."

Replay is strictly backward-looking from `as_of`. Outcome observation is explicitly
forward-looking from it. Keeping them apart is what prevents the most common failure in
this kind of study — letting knowledge of what happened next quietly influence the
reconstruction of what was knowable at the time.
