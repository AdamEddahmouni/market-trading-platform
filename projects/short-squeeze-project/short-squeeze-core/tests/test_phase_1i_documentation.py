from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_phase_1i_required_documentation_exists_and_states_objective_boundaries():
    required = {
        "docs/adr/0026-trade-quote-availability.md": ("publication", "receipt", "event time"),
        "docs/adr/0027-sequence-scope-and-out-of-order-evidence.md": ("sequence scope", "out-of-order", "arrival"),
        "docs/adr/0028-crossed-and-locked-quotes-without-signals.md": ("CROSSED", "LOCKED", "without"),
        "docs/providers/trades-quotes-offline.md": ("local", "provider-neutral", "one-sided"),
        "docs/trade-quote-availability-semantics.md": ("effective", "publication", "received"),
        "docs/trade-quote-sequence-and-lifecycle-timeline.md": ("ORIGINAL", "CORRECTED", "CANCELLED"),
    }
    for relative, phrases in required.items():
        path = ROOT / relative
        assert path.exists(), relative
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase.lower() in text.lower(), f"{relative}: {phrase}"


def test_phase_1i_public_docs_name_compatibility_fixture_and_analytics_exclusions():
    paths = [
        ROOT / "README.md",
        ROOT / "docs/architecture.md",
        ROOT / "docs/adapter-contract.md",
        ROOT / "docs/observation-contract.md",
        ROOT / "docs/field-semantics.md",
        ROOT / "docs/cross-source-evidence.md",
        ROOT / "docs/point-in-time-evidence-policy.md",
        ROOT / "docs/TESTING.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    for phrase in (
        "phase 1i", "trades-quotes", "sequence scope", "market scope",
        "missing versus zero", "synthetic nbbo", "aggressor side",
        "spread", "order-flow", "schema `1.0.0`",
    ):
        assert phrase in combined
