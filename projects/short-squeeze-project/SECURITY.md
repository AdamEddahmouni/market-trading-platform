# Security Policy

## Reporting a vulnerability

If you discover a security issue, please **do not** open a public GitHub issue with
exploit details. Instead, report it privately to the repository owner via GitHub
Security Advisories or direct contact.

Include:

- A description of the issue and its potential impact
- Steps to reproduce (if applicable)
- Suggested remediation (optional)

## Credential safety

This repository is designed so that **no API keys, passwords, or tokens are required**
to run the default `FROZEN_DEMO` mode. Credentials belong in local environment files
(`.env`, `.private/providers.env`) that are gitignored and must never be committed.

For full credential boundaries, opt-in API locks, and operator responsibilities, see
[short-squeeze-core/docs/SECURITY.md](short-squeeze-core/docs/SECURITY.md).

## Before going public (operators)

If this repository was ever private with real credentials in use, rotate all provider
keys (NewsAPI, Finviz, Finnhub, Schwab, IBKR, MongoDB) at their respective dashboards
before or immediately after making the repository public. Keys that appeared in git
history should be treated as compromised even after redaction.
