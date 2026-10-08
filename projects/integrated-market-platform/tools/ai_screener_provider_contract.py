"""Receipt for the AI Screener provider contract: the compact wire, the prompt, and each Claude model's request.

Offline by default: it builds the controlled 50-candidate packet, the production request for every selectable
Claude model, a controlled valid round trip and the invalid-output matrix, and writes the receipt.

``--probe`` adds bounded provider diagnostics with the configured key, per model:
  * the token-count endpoint on the exact production request (bills nothing, generates nothing);
  * a grammar probe: the exact production tool schema and tool choice with a one-line message and no output
    (``max_tokens`` 0, or 1 where the model's forced tool call does not accept 0). It bills a few thousand input
    tokens and produces no candidates. Only a generation request compiles a strict schema's grammar.
Two control schemas the provider is known to refuse show that each probe can fail, and the request shape used
before requests were model-aware is offered to each model that the table says rejects it. No market data is read,
no workflow runs, and nothing is written but the receipt.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference import anthropic_synthesis  # noqa: E402
from market_platform_foundation.intelligence.inference.anthropic_models import (  # noqa: E402
    CLAUDE_MODELS, TOOL_NAME, contract_status, count_request,
)
from market_platform_foundation.intelligence.inference.anthropic_synthesis import (  # noqa: E402
    COUNT_TOKENS_URL, DEFAULT_MODEL, AnthropicSynthesisProvider, rejection_reason,
)
from market_platform_foundation.intelligence.inference.candidate_reduction import (  # noqa: E402
    MAX_INTAKE, MAX_PACKET_BYTES, MAX_SELECTED, PROMPT_ID, SCHEMA_VERSION, WIRE_SCHEMA_VERSION, CandidateReducer,
    ScreenerEvidencePacket, output_schema, parse_reduction, reference_ids, rejection_stage,
)
from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType  # noqa: E402
from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict  # noqa: E402
from market_platform_foundation.intelligence.inference.provider import ANTHROPIC_API_URL  # noqa: E402
from market_platform_foundation.intelligence.inference.synthesis_engines import ENGINE_SPECS  # noqa: E402

RECEIPT = ROOT / "artifacts" / "ai-screener-provider-contract-closure.json"
REDUCTION = IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION
OCTOBER_7_MODEL = "claude-haiku-4-5-20251001"
PROBE_MESSAGE = "Schema compatibility probe. There is no evidence packet; record nothing."


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def legacy_branching_schema(candidates: list[dict], *, array_const: bool) -> dict:
    """The per-instrument schema this wire replaced, as a control the provider refuses. Never sent for generation."""

    choices = []
    for c in candidates:
        evidence = (*c["current_market_evidence"], *c["reference_evidence"])
        refs = {"type": "array", "items": {"type": "string", "enum": [e["evidence_id"] for e in evidence]}}
        weak = sorted(e["evidence_id"] for e in evidence if e["weak_reasons"])
        missing = sorted({x["capability"] for x in c["missing"]})
        fixed = ((lambda v: {"type": "array", "items": {"type": "string"}, "const": v}) if array_const
                 else (lambda v: {"type": "string", "const": json.dumps(v)}))
        properties = {"instrument_id": {"type": "string", "enum": [c["instrument"]["instrument_id"]]},
                      "rank": {"type": "integer", "enum": list(range(1, MAX_SELECTED + 1))}, "rationale": {"type": "string"},
                      "supporting_refs": refs, "conflicting_refs": refs, "weak_refs": fixed(weak),
                      "missing_capabilities": fixed(missing), "uncertainties": {"type": "array", "items": {"type": "string"}}}
        choices.append({"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties})
    return {"type": "object", "additionalProperties": False, "required": ["schema_version", "candidates", "limitations"],
            "properties": {"schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
                           "candidates": {"type": "array", "items": {"anyOf": choices}},
                           "limitations": {"type": "array", "items": {"type": "string"}}}}


def post(provider: AnthropicSynthesisProvider, url: str, body: dict) -> dict:
    """One diagnostic request. Keeps the status, the stable class and the provider's own validation sentence."""

    try:
        status, raw = anthropic_synthesis._http_post(url, json.dumps(body).encode("utf-8"), provider._headers(), 60)
    except OSError as exc:
        return {"http_status": None, "accepted": False, "classification": "ANTHROPIC_UNREACHABLE", "detail": type(exc).__name__}
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except ValueError:
        payload = {}
    if status != 200:
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        return {"http_status": status, "accepted": False, "classification": rejection_reason(status, payload),
                "provider_error_type": error.get("type"), "provider_message": str(error.get("message") or "")[:240]}
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    return {"http_status": 200, "accepted": True, "classification": None, "input_tokens": payload.get("input_tokens", usage.get("input_tokens")),
            "output_tokens": usage.get("output_tokens"), "stop_reason": payload.get("stop_reason")}


def grammar_probe(provider: AnthropicSynthesisProvider, body: dict) -> dict:
    """Send the request's exact tools and tool choice with no evidence and no output room."""

    probe = {**body, "messages": [{"role": "user", "content": PROBE_MESSAGE}], "max_tokens": 0}
    result = post(provider, ANTHROPIC_API_URL, probe)
    if not result["accepted"] and "max_tokens" in str(result.get("provider_message", "")).lower():
        result = post(provider, ANTHROPIC_API_URL, {**probe, "max_tokens": 1})
        result["max_tokens"] = 1
    else:
        result["max_tokens"] = 0
    return result


def build(probe: bool) -> dict:
    from tests.intelligence.test_ai_screener_provider_contract import (
        CLOCK, NEWS_ISO, Claude, packed, packet_bytes, reduce_with, wire_output, wire_pick,
    )

    raw, _ = packed(fit=False)
    candidates, _ = packed()
    schema = output_schema(candidates)
    reducer = CandidateReducer(clock=lambda: CLOCK)
    digest, rendered, prompt, size = reducer._prepare({}, candidates, NEWS_ISO)
    packet = ScreenerEvidencePacket(REDUCTION, "receipt", digest, NEWS_ISO, {}, candidates, schema)
    selectable = [model for model, _ in ENGINE_SPECS["anthropic"].models]

    key = ""
    if probe:
        from market_platform_foundation.news.config import configured_value
        key = (configured_value("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not configured; run without --probe for the offline receipt.")

    matrix, requests, preflight = [], {}, {}
    for model in selectable:
        capabilities = CLAUDE_MODELS[model]
        status = contract_status(model, REDUCTION)
        provider = AnthropicSynthesisProvider(api_key=key or "offline", model=model)
        body = provider.request_body(packet, rendered_prompt=rendered, config=reducer.config)
        requests[model] = {"fields": list(body), "max_tokens": body["max_tokens"], "temperature": body.get("temperature", "OMITTED"),
                           "tool_choice": body["tool_choice"], "strict": body["tools"][0].get("strict", False),
                           "system_names_the_tool_call": TOOL_NAME in body["system"],
                           "count_request_fields": list(count_request(body))}
        row = {"MODEL": model, "REQUEST_SHAPE_SUPPORTED": status["supported"], "STRICT_SCHEMA_SUPPORTED": capabilities.strict_tools,
               "FORCED_TOOL_CHOICE_SUPPORTED": capabilities.forced_tool_choice, "TEMPERATURE_SUPPORTED": capabilities.temperature,
               "COUNT_TOKENS_SUPPORTED": capabilities.count_tokens, "REASONS_BY_DEFAULT": capabilities.thinks_by_default,
               "CONTEXT_WINDOW": capabilities.context_window, "AI_SCREENER_COMPATIBLE": status["supported"],
               "REASON_IF_NOT": status["reason"], "SOURCE": "capability table"}
        if probe:
            counted = provider.preflight(packet, rendered_prompt=rendered, config=reducer.config)
            compiled = grammar_probe(provider, body)
            preflight[model] = {
                "token_count": counted, "grammar_probe": compiled,
                "CONTEXT_FIT": "PASS" if counted["context_fit"] else "FAIL",
                "SCHEMA_PROVIDER_ACCEPTED": "PASS" if counted["accepted"] else "FAIL",
                "GRAMMAR_COMPILES": "PASS" if compiled["accepted"] else "FAIL",
            }
            if not capabilities.forced_tool_choice:
                # The pre-model-aware shape, one parameter at a time. A refusal is a 400: nothing is billed.
                forced = {**count_request(body), "messages": [{"role": "user", "content": PROBE_MESSAGE}],
                          "tool_choice": {"type": "tool", "name": TOOL_NAME}}
                preflight[model]["legacy_forced_tool_choice"] = post(provider, COUNT_TOKENS_URL, forced)
            if not capabilities.temperature:
                preflight[model]["legacy_temperature"] = grammar_probe(provider, {**body, "temperature": 0})
            row["AI_SCREENER_COMPATIBLE"] = bool(status["supported"] and counted["accepted"] and counted["context_fit"] and compiled["accepted"])
            row["REASON_IF_NOT"] = None if row["AI_SCREENER_COMPATIBLE"] else (counted["reason"] or compiled["classification"])
            row["SOURCE"] = "capability table, confirmed by provider probe"
        matrix.append(row)

    controls = {}
    if probe:
        provider = AnthropicSynthesisProvider(api_key=key, model=OCTOBER_7_MODEL)
        for name, array_const in (("legacy_array_constants", True), ("legacy_per_instrument_branches", False)):
            legacy = ScreenerEvidencePacket(REDUCTION, "control", digest, NEWS_ISO, {}, candidates,
                                            legacy_branching_schema(candidates, array_const=array_const))
            body = provider.request_body(legacy, rendered_prompt=PROBE_MESSAGE, config=reducer.config)
            controls[name] = {"schema_bytes": len(json.dumps(legacy.output_schema)),
                              "token_count": post(provider, COUNT_TOKENS_URL, count_request(body)),
                              "grammar_probe": grammar_probe(provider, body)}

    keys = [41, 7, 0, 49, 23]
    valid, _ = reduce_with(OCTOBER_7_MODEL, Claude(wire_output(candidates, keys)), candidates)
    smallest = min(range(MAX_INTAKE), key=lambda i: len(reference_ids(candidates[i])))
    largest = max(range(MAX_INTAKE), key=lambda i: len(reference_ids(candidates[i])))
    own = len(reference_ids(candidates[0]))

    def bad(key=0, **change):
        return {**wire_pick(candidates, key, 1), **change}
    invalid = {
        "negative_index": bad(supporting_refs=[0, -1]),
        "out_of_range_index": bad(supporting_refs=[0, own]),
        "index_valid_only_for_another_candidate": bad(smallest, supporting_refs=[0, len(reference_ids(candidates[largest])) - 1]),
        "evidence_omitted_during_packing": bad(smallest, conflicting_refs=[len(reference_ids(raw[smallest])) - 1]),
        "duplicate_reference": bad(supporting_refs=[0, 1, 1]),
        "unknown_candidate_key": bad(candidate_key=MAX_INTAKE),
        "symbol_in_place_of_key": bad(candidate_key="X0"),
        "malformed_binding": bad(candidate_key={"index": 0}),
        "restated_missing_list": bad(missing_capabilities=[]),
    }
    invalid_results = {}
    for name, pick in invalid.items():
        answer = {"schema_version": SCHEMA_VERSION, "candidates": [pick], "limitations": ["x"]}
        _, reason = parse_reduction(json.dumps(answer), candidates)
        stored, _ = reduce_with(OCTOBER_7_MODEL, Claude(answer), candidates)
        invalid_results[name] = {"reason": reason, "stage": rejection_stage(reason), "state": stored["state"],
                                 "selected": len(stored["candidates"])}

    billed = [p[name] for p in (*preflight.values(), *controls.values()) for name in ("grammar_probe", "legacy_temperature")
              if p.get(name, {}).get("accepted")]
    return {
        "receipt": "ai-screener-provider-contract-closure",
        "base_sha": git("merge-base", "HEAD", "origin/main"),
        "implementation_sha": git("rev-parse", "HEAD"),
        "wire_schema_version": WIRE_SCHEMA_VERSION,
        "wire_schema_hash": input_hash_from_dict(schema),
        "wire_schema_bytes": len(json.dumps(schema)),
        "stored_schema_version": SCHEMA_VERSION,
        "prompt_id": PROMPT_ID, "prompt_version": prompt.version, "prompt_hash": prompt.content_hash,
        "method": {"max_intake": MAX_INTAKE, "max_selected": MAX_SELECTED, "max_packet_bytes": MAX_PACKET_BYTES},
        "default_model": DEFAULT_MODEL, "october_7_model": OCTOBER_7_MODEL,
        "model_capability_matrix": matrix,
        "request_construction": requests,
        "packet": {"fixture": "50 controlled candidates: current quote and technicals each, three long stories each before fitting",
                   "candidates": len(candidates), "raw_bytes_before_fitting": packet_bytes(raw), "bytes": size,
                   "within_cap": size <= MAX_PACKET_BYTES, "rendered_prompt_chars": len(rendered),
                   "stories_before_fitting": sum(c["news"]["story_count"] for c in raw),
                   "stories_after_fitting": sum(c["news"]["story_count"] for c in candidates)},
        "provider_probes_run": probe,
        "provider_preflight": preflight or None,
        "provider_controls": controls or None,
        "controlled_decode": {"model": OCTOBER_7_MODEL, "selected_keys": keys, "state": valid["state"], "reason": valid["reason"],
                              "selected": [c["instrument_id"] for c in valid["candidates"]],
                              "stored_fields": sorted(valid["candidates"][0]) if valid["candidates"] else []},
        "invalid_output_checks": invalid_results,
        "paid_generation_calls": 0,
        "probe_requests_that_returned_output_tokens": sum(1 for p in billed if p.get("output_tokens")),
        "billed_grammar_probe_requests": len(billed),
        "billed_grammar_probe_input_tokens": sum(int(p.get("input_tokens") or 0) for p in billed),
        "billed_grammar_probe_output_tokens": sum(int(p.get("output_tokens") or 0) for p in billed),
        "known_unresolved": [
            "50-row intake is NOT closure of the full-universe blind-spot issue.",
            "No end-to-end paid generation was run on any model under this contract.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", action="store_true", help="also run the bounded provider diagnostics with the configured key")
    parser.add_argument("--out", type=Path, default=RECEIPT)
    args = parser.parse_args()
    receipt = build(args.probe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: receipt[k] for k in ("wire_schema_hash", "prompt_version", "provider_probes_run", "paid_generation_calls")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
