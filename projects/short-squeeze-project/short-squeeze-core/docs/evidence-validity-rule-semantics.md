# Evidence Validity Rule Semantics

Validity rules project Phase 2D coverage, conflict, and input-sufficiency results rather than
creating a second readiness engine. Domain absence, unavailability, unknown state, and conflict
remain distinct. Temporal differences already excluded by Phase 2D are not conflicts.

Point-in-time failures fail only the eligibility rule. Unit incompatibility and insufficient
history produce `INSUFFICIENT_DATA`. Explicit provider scope passes independently. Any detected
default substitution fails `NO_DEFAULT_SUBSTITUTION`; an honestly absent value is not a
substitution and remains missing/unknown in its own rule.

