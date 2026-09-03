"""Shadow/forward-validation infrastructure (Platformization P6).

Shadow observation is NOT execution: this package records predictions,
labels outcomes after the fact, and computes post-hoc metrics over
fixture/replay data only. It has no execution path and performs no
network I/O. See docs/superpowers/specs/
2026-08-22-platform-p6-shadow-forward-validation-design.md — fixture results
are infrastructure proofs, never forward-validation evidence.
"""
