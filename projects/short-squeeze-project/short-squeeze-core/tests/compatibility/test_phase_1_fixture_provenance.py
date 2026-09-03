"""Fixture-provenance and sensitive-content guards for every Phase 1 fixture family.

Every provider fixture family must declare exactly one allowed provenance class. Two honest
shapes exist in the repository and both are accepted:

* Phase 1C+ providers carry a ``fixture_metadata.json`` with a ``families`` list, each entry
  declaring an ``origin``.
* Phase 1B (IBKR) carries provenance inline per case as ``metadata.origin`` inside the case
  files. This stylistic difference is documented in the fixture-provenance report as intentional
  and is asserted here directly rather than being reclassified.

No fixture may contain credentials, account identifiers, emails, or live/routable URLs. All
sample URLs use the reserved non-routable ``.invalid`` TLD.
"""

import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROVIDERS = FIXTURES / "providers"

ALLOWED_ORIGINS = {
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
}

METADATA_PROVIDERS = ["finra", "finviz", "halts", "market_bars", "news", "sec", "trades_quotes"]

SECRET_PATTERN = re.compile(
    rb"(?i)(api[_-]?key|secret|password|bearer|authorization|account[_-]?id)\s*[:=]\s*[^,}\s\"]+"
)
URL_PATTERN = re.compile(rb"https?://([^/\"'\s]+)")


def _all_fixture_files():
    return sorted(p for p in FIXTURES.rglob("*") if p.is_file())


def _declared_origins(document) -> set[str]:
    """Extract declared provenance classes, tolerant of the two metadata shapes in the repo.

    Phase 1C+ providers either use a ``families`` list (each with an ``origin``) or a top-level
    ``allowed_origins`` list. Both are honest; this helper normalizes them.
    """
    origins: set[str] = set()
    if isinstance(document.get("families"), list):
        origins.update(str(f["origin"]) for f in document["families"] if "origin" in f)
    if isinstance(document.get("allowed_origins"), list):
        origins.update(str(o) for o in document["allowed_origins"])
    return origins


def _collect_origin_values(value) -> set[str]:
    """Recursively collect every value stored under an ``origin`` key in a JSON document."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "origin" and isinstance(item, str):
                found.add(item)
            found |= _collect_origin_values(item)
    elif isinstance(value, list):
        for item in value:
            found |= _collect_origin_values(item)
    return found


def test_every_metadata_provider_declares_allowed_origins() -> None:
    for provider in METADATA_PROVIDERS:
        path = PROVIDERS / provider / "fixture_metadata.json"
        assert path.exists(), f"missing fixture_metadata.json for {provider}"
        document = json.loads(path.read_text(encoding="utf-8"))
        origins = _declared_origins(document)
        assert origins, f"{provider} declares no provenance origins"
        assert origins <= ALLOWED_ORIGINS, f"{provider} declares invalid origins: {origins - ALLOWED_ORIGINS}"
        if "contains_credentials" in document:
            assert document["contains_credentials"] is False
        for family in document.get("families", []):
            if "contains_credentials" in family:
                assert family["contains_credentials"] is False


def test_no_fixture_declares_a_provenance_class_outside_allowed_set() -> None:
    """Every inline ``origin`` value across all JSON fixtures must be an allowed class."""
    offenders = {}
    for path in _all_fixture_files():
        if path.suffix != ".json":
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        bad = _collect_origin_values(document) - ALLOWED_ORIGINS
        if bad:
            offenders[str(path.relative_to(FIXTURES))] = sorted(bad)
    assert offenders == {}, f"disallowed provenance classes: {offenders}"


def test_ibkr_cases_declare_allowed_inline_provenance() -> None:
    for name in ("representative_cases.json", "edge_cases.json"):
        document = json.loads((PROVIDERS / "ibkr" / name).read_text(encoding="utf-8"))
        cases = document["cases"]
        assert cases
        for case in cases:
            meta = case["metadata"]
            assert meta["origin"] in ALLOWED_ORIGINS
            assert meta["contains_credentials"] is False
            assert meta["contains_real_account_data"] is False


def test_no_fixture_contains_secret_like_values() -> None:
    offenders = []
    for path in _all_fixture_files():
        if SECRET_PATTERN.search(path.read_bytes()):
            offenders.append(str(path.relative_to(FIXTURES)))
    assert offenders == [], f"secret-like values in fixtures: {offenders}"


def test_no_fixture_contains_email_addresses() -> None:
    email = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    offenders = [
        str(p.relative_to(FIXTURES)) for p in _all_fixture_files() if email.search(p.read_bytes())
    ]
    assert offenders == [], f"email addresses in fixtures: {offenders}"


def test_all_fixture_urls_are_non_routable() -> None:
    offenders = {}
    for path in _all_fixture_files():
        for host in URL_PATTERN.findall(path.read_bytes()):
            host_text = host.decode("utf-8")
            bare = host_text.split(":")[0]
            if not (bare.endswith(".invalid") or bare == "localhost.invalid"):
                offenders.setdefault(str(path.relative_to(FIXTURES)), set()).add(host_text)
    offenders = {k: sorted(v) for k, v in offenders.items()}
    assert offenders == {}, f"routable/live URLs in fixtures: {offenders}"


def test_no_environment_specific_absolute_paths_in_fixtures() -> None:
    patterns = (rb"C:\\\\Users", rb"C:/Users", rb"/home/", rb"/Users/")
    offenders = []
    for path in _all_fixture_files():
        raw = path.read_bytes()
        if any(re.search(pat, raw) for pat in patterns):
            offenders.append(str(path.relative_to(FIXTURES)))
    assert offenders == [], f"environment-specific absolute paths in fixtures: {offenders}"
