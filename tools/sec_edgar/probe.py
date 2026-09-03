"""Small Fair Access probe: submissions + optional companyfacts. No bulk crawl."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.sec_edgar.documents import hash_document
from market_platform_foundation.sec_edgar.health import health_from_transport
from market_platform_foundation.sec_edgar.live import (
    fetch_companyfacts,
    fetch_primary_document,
    fetch_submissions,
    transport_from_env,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="SEC EDGAR capability probe")
    parser.add_argument("--cik", default="0000320193")
    parser.add_argument("--output", default="evidence/sec_edgar/capability-report.json")
    parser.add_argument("--fetch-document", action="store_true")
    args = parser.parse_args()

    transport = transport_from_env()
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filings = fetch_submissions(transport, args.cik)
    facts: list[dict[str, object]] = []
    try:
        xbrl = fetch_companyfacts(transport, args.cik, as_of=observed, tag="Assets")
        facts = [{"accession": row.accession, "value": row.value, "filed": row.filed} for row in xbrl[:3]]
    except OSError as exc:
        facts = [{"error": str(exc)}]
    document_hash = ""
    if args.fetch_document and filings:
        body = fetch_primary_document(transport, filings[0])
        document_hash = hash_document(body)
    health = health_from_transport(
        transport,
        last_filing_observation=filings[0].normalized_accession if filings else "",
    )
    report = {
        "source": "sec_edgar",
        "tested_at": observed,
        "cik": args.cik,
        "interfaces": {
            "submissions": {"status": "OBSERVED" if filings else "UNTESTED", "filing_count": len(filings)},
            "companyfacts": {"status": "OBSERVED" if facts and "error" not in facts[0] else "UNTESTED"},
            "companyconcept": {"status": "PLANNED"},
            "frames": {"status": "PLANNED"},
            "filing_documents": {"status": "OBSERVED" if document_hash else "UNTESTED"},
            "rss": {"status": "IMPLEMENTED_PARSER"},
            "bulk": {"status": "PLANNED"},
        },
        "forms": sorted({row.form_type for row in filings[:40]}),
        "rate_policy": {
            "max_requests_per_second": 5,
            "sec_policy_ceiling_rps": 10,
            "request_count": health.request_count,
        },
        "timestamp_semantics": {
            "acceptance_time": "acceptanceDateTime",
            "available_time": "observed_time for metadata; document fetch for content",
        },
        "pit_semantics": {
            "amendments_do_not_rewrite_history": True,
            "companyfacts_filtered_by_filed": True,
        },
        "quality_findings": {
            "reachable": health.reachable,
            "last_status": health.last_status,
            "error_count": health.error_count,
        },
        "sample_accessions": [row.normalized_accession for row in filings[:5]],
        "sample_facts": facts,
        "document_hash": document_hash,
        "limitations": [
            "Live observation is not an admitted dataset",
            "13F is delayed holdings",
            "Form type is not trade direction",
        ],
        "user_agent_configured": bool(os.environ.get("SEC_USER_AGENT", "").strip()),
    }
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    write_canonical_json(out, report)
    print(json.dumps({"output": str(out), "filings": len(filings), "requests": health.request_count}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
