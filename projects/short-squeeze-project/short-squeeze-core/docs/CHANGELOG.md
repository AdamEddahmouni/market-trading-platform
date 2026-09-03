# Changelog

## 0.16.0

- Evidence-gated scoring floor aligned to Finviz-supported weight (65%) so
  LOW_COVERAGE no longer forces UNEVALUABLE when both dimensions score.
- Correctness: SEC catalyst age uses filing `filed_at`; Finviz mapping conflicts
  are withheld; estimated DTC / Finviz day-change stay display-only.
- Borrow availability % float becomes research-admissible when both IBKR and
  Finviz legs are eligible.
- Opt-in security prep: `CSRF_PROTECTION` and `LOCK_SENSITIVE_API` (default off).
- Documentation system refreshed (Diátaxis index, Getting Started, how-to guides,
  reproducibility, CLI reference; ports and Phase 3E product wording clarified).

## 0.15.0

- Centralized runtime and provider configuration with deterministic precedence.
- Added provider enable/disable states and a redacted configuration doctor.
- Replaced public academic terminology with organization-neutral labels while
  retaining stable machine identifiers.
- Added privacy and credential release auditing with reviewed allowlisting.
- Added an allowlisted release builder, release metadata, checksums, and ZIP output.
- Added professional architecture, configuration, API, provider, deployment,
  testing, security, integration, methodology, and limitation documentation.

## 0.14.0

- Added deployable runtime modes, methodology comparison, frozen demonstration,
  cloud-safe environment provider configuration, and integration schema
  `batch14.integration.v1`.
