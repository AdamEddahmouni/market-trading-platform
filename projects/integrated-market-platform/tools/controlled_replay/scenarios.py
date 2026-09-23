"""Controlled-replay scenario pack (real ingest path; ~5 scenarios).

Scenarios post through ``POST /intelligence/ingest/news`` (and optional
enrichment) — never into UI state. Evidence remains CONTROLLED_REPLAY.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Deterministic controlled clocks. Stale rows use retrieved_time a few minutes
# before as_of so OE freshness is STALE while still inside news admit TTL
# (RECENCY_EXCEEDS_TTL is ~3 days from server receive).
T_STALE_PUBLISHED = "2026-09-22T13:59:00Z"
T_STALE_RETRIEVED = "2026-09-22T14:00:00Z"
T_FRESH_PUBLISHED = "2026-09-22T14:05:00Z"
T_FRESH_RETRIEVED = "2026-09-22T14:05:08Z"
T_ZERO_PUBLISHED = "2026-09-22T14:04:00Z"
T_ZERO_RETRIEVED = "2026-09-22T14:04:30Z"

DEFAULT_API_BASE = "http://127.0.0.1:8766"
NEWS_INGEST_ROUTE = "/intelligence/ingest/news"
ENRICHMENT_INGEST_ROUTE = "/intelligence/ingest/enrichment"
CLOCK_ROUTE = "/controlled-replay/advance-clock"


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    scenario_id: str
    title: str
    description: str
    expected_qualifying: bool


SCENARIO_SPECS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="clean",
        title="Clean opportunity",
        description="Valid instrument, fresh evidence, clear catalyst, Watch/Dismiss eligible.",
        expected_qualifying=True,
    ),
    ScenarioSpec(
        scenario_id="stale",
        title="Stale but surfaced",
        description="Freshness=STALE remains STALE; eligibility independent (PR #389).",
        expected_qualifying=True,
    ),
    ScenarioSpec(
        scenario_id="linkage_warning",
        title="Provider linkage warning",
        description="Real backend provider_linkage_warnings (uncorroborated / contextual concern).",
        expected_qualifying=True,
    ),
    ScenarioSpec(
        scenario_id="contradicted_enrichment",
        title="Contradicted enrichment",
        description="Observed support vs CONTRADICTION enrichment; inference not flattened to fact.",
        expected_qualifying=True,
    ),
    ScenarioSpec(
        scenario_id="zero_qualifying",
        title="Zero qualifying",
        description="Non-catalyst headline admits nothing; empty radar is a valid result.",
        expected_qualifying=False,
    ),
)


def _article(
    *,
    headline: str,
    tickers: list[str],
    provider_native_id: str,
    published_time: str,
    retrieved_time: str,
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "headline": headline,
        "published_time": published_time,
        "retrieved_time": retrieved_time,
        "url": url if url is not None else f"https://example.com/controlled-replay/{provider_native_id}",
        "tickers": tickers,
        "publisher_source": "ControlledReplayWire",
        "provider_native_id": provider_native_id,
    }


def build_news_ingest_body() -> dict[str, Any]:
    """Articles for the default pack (qualifying + zero in one POST)."""

    return {
        "retrieved_time": T_FRESH_RETRIEVED,
        "articles": [
            _article(
                headline="AAPL reports quarterly earnings beat estimates",
                tickers=["AAPL"],
                provider_native_id="cr-clean-aapl",
                published_time=T_FRESH_PUBLISHED,
                retrieved_time=T_FRESH_RETRIEVED,
            ),
            _article(
                headline="MSFT reports quarterly earnings guidance raise",
                tickers=["MSFT"],
                provider_native_id="cr-stale-msft",
                published_time=T_STALE_PUBLISHED,
                retrieved_time=T_STALE_RETRIEVED,
            ),
            _article(
                headline="MillerKnoll reports quarterly earnings beat",
                tickers=["NVDA"],
                provider_native_id="cr-warn-nvda",
                published_time=T_FRESH_PUBLISHED,
                retrieved_time=T_FRESH_RETRIEVED,
                url="",
            ),
            _article(
                headline="AMD reports quarterly earnings and data-center demand update",
                tickers=["AMD"],
                provider_native_id="cr-conflict-amd",
                published_time=T_FRESH_PUBLISHED,
                retrieved_time=T_FRESH_RETRIEVED,
            ),
            _article(
                headline="Example Corp beats estimates in quiet session",
                tickers=["ZZZZ"],
                provider_native_id="cr-zero-zzzz",
                published_time=T_ZERO_PUBLISHED,
                retrieved_time=T_ZERO_RETRIEVED,
            ),
        ],
    }


def build_enrichment_bodies(opportunity_id: str) -> list[dict[str, Any]]:
    """SUPPORTING (observed-like) + CONTRADICTION enrichment for one opportunity."""

    support_id = f"aer-cr-support-{opportunity_id[:16]}"
    return [
        {
            "record_id": support_id,
            "schema_version": "1",
            "opportunity_id": opportunity_id,
            "retrieved_at": "2026-09-22T14:10:00+00:00",
            "agent_id": "controlled.replay.sentinel.v1",
            "bot_role": "SENTINEL",
            "skill": {"skill_id": "imp.controlled_replay.verify", "version": "1.0.0"},
            "claim_type": "SUPPORTING_EVIDENCE",
            "confidence": 0.55,
            "expires_at": "2099-01-01T00:00:00+00:00",
            "provenance": {
                "ingest_plane": "controlled_replay",
                "epistemic_class": "OBSERVED_SOURCE_CLAIM",
                "worker_id": "controlled-replay-pack",
            },
            "operation": "ATTACH_EVIDENCE",
            "claim_body": {
                "summary": "Wire headline observed; catalyst keywords matched.",
                "epistemic_class": "OBSERVED",
            },
            "metadata": {"controlled_replay": True, "evidence_class": "CONTROLLED_REPLAY"},
        },
        {
            "record_id": f"aer-cr-contradict-{opportunity_id[:16]}",
            "schema_version": "1",
            "opportunity_id": opportunity_id,
            "retrieved_at": "2026-09-22T14:11:00+00:00",
            "agent_id": "controlled.replay.challenger.v1",
            "bot_role": "SENTINEL",
            "skill": {"skill_id": "imp.controlled_replay.challenge", "version": "1.0.0"},
            "claim_type": "CONTRADICTION",
            "confidence": 0.4,
            "expires_at": "2099-01-01T00:00:00+00:00",
            "provenance": {
                "ingest_plane": "controlled_replay",
                "epistemic_class": "INFERENCE",
                "worker_id": "controlled-replay-pack",
            },
            "operation": "ATTACH_CONTRADICTION",
            "claim_body": {
                "summary": "Inferred conflict: guidance language may not match demand narrative.",
                "epistemic_class": "INFERENCE",
            },
            "contradiction_refs": [support_id],
            "hypothesis_suggestion": "Treat demand update as unverified inference until primary filing.",
            "metadata": {"controlled_replay": True, "evidence_class": "CONTROLLED_REPLAY"},
        },
    ]


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = {"User-Agent": "imp-controlled-replay/1.0"}
    data = None
    if method.upper() != "GET":
        data = payload
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    request = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            return int(response.status), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        return int(exc.code), parsed


def load_scenarios(*, api_base: str = DEFAULT_API_BASE) -> dict[str, Any]:
    """POST scenario pack through the real news (+ enrichment) ingress."""

    base = api_base.rstrip("/")
    try:
        status, ingest = _http_json(
            "POST",
            f"{base}{NEWS_INGEST_ROUTE}",
            body=build_news_ingest_body(),
            timeout=120.0,
        )
    except Exception as exc:  # noqa: BLE001 — surface transport failures to CLI
        return {
            "ok": False,
            "stage": "news_ingest_transport",
            "status": None,
            "payload": {"error": type(exc).__name__, "detail": str(exc)},
        }
    if status != 200:
        return {"ok": False, "stage": "news_ingest", "status": status, "payload": ingest}

    clock_status, clock_payload = _http_json(
        "POST",
        f"{base}{CLOCK_ROUTE}",
        body={"as_of_time": T_FRESH_RETRIEVED},
    )

    opportunity_ids = list(ingest.get("opportunity_ids") or [])
    enrichment_results: list[dict[str, Any]] = []
    summary_status, summary = _http_json("GET", f"{base}/opportunities/summary")
    conflict_host = None
    if summary_status == 200:
        for item in summary.get("items") or []:
            headline = str(item.get("headline") or "")
            symbol = str(item.get("instrument_id") or item.get("symbol") or "")
            if "AMD" in symbol.upper() or (
                "AMD" in headline.upper() and "earnings" in headline.lower()
            ):
                conflict_host = str(item.get("opportunity_id") or item.get("summary_id") or "")
                break
    if conflict_host:
        for body in build_enrichment_bodies(conflict_host):
            estatus, epayload = _http_json("POST", f"{base}{ENRICHMENT_INGEST_ROUTE}", body=body)
            enrichment_results.append({"status": estatus, "payload": epayload})

    return {
        "ok": True,
        "evidence_class": "CONTROLLED_REPLAY",
        "scenarios": [spec.scenario_id for spec in SCENARIO_SPECS],
        "ingest": ingest,
        "admitted_count": ingest.get("admitted_count"),
        "opportunity_count": ingest.get("opportunity_ids") and len(ingest.get("opportunity_ids") or []),
        "zero_qualifying_count": ingest.get("zero_qualifying_count"),
        "opportunity_ids": opportunity_ids,
        "enrichment": enrichment_results,
        "clock_advance": {"status": clock_status, "payload": clock_payload},
        "summary_status": summary_status,
        "summary_item_count": len((summary or {}).get("items") or []) if summary_status == 200 else None,
    }



def list_scenario_catalog() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": spec.scenario_id,
            "title": spec.title,
            "description": spec.description,
            "expected_qualifying": spec.expected_qualifying,
        }
        for spec in SCENARIO_SPECS
    ]


__all__ = [
    "SCENARIO_SPECS",
    "T_FRESH_RETRIEVED",
    "build_enrichment_bodies",
    "build_news_ingest_body",
    "list_scenario_catalog",
    "load_scenarios",
]
