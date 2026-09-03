# MRA-002 — Anthropic LLM Assistant (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** MRA-002 — Anthropic Messages API behind `ProviderNeutralInferenceBoundary`  
**Prerequisites:** MRA-001 `PASS`, `ADR-LLM-001` `ACCEPTED`

## 1. Purpose

Authorize read-only Anthropic inference for the research assistant. Answers must be
grounded in the server-assembled evidence pack from MRA-001 context assembly.
Credentials are injected via environment variables only.

## 2. In scope

- `AnthropicInference` adapter (stdlib `urllib.request`, no third-party SDK)
- `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` env configuration
- `IMP_ASSISTANT_PROVIDER=anthropic|grounded|stub` selection
- Deterministic fallback to `grounded.evidence` on provider failure
- Citation extraction and validation against `allowed_citation_refs`
- `READ_ONLY_NO_EXECUTION` authority boundary unchanged

## 3. Out of scope

- Order placement, risk override, portfolio mutation
- Committed credentials or config files with secrets
- Offline test suites making live network calls

## 4. Runtime configuration

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (required for LLM mode) |
| `ANTHROPIC_MODEL` | Model id (default `claude-sonnet-4-20250514`) |
| `IMP_ASSISTANT_PROVIDER` | `anthropic`, `grounded`, or leave empty (auto: anthropic when key set) |
| `IMP_ASSISTANT_STUB` | `1` forces abstaining stub |

Start API **without** offline guard (`python tools/ui1/run_ui_api.py --serve`) so
inference can reach Anthropic.

## 5. Completion definition

MRA-002 is complete when Anthropic adapter tests pass with mocked HTTP, grounded
fallback is proven, and live inference works when `ANTHROPIC_API_KEY` is set.
