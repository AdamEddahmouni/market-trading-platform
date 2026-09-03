from collections import Counter

from .models import AcquisitionBatch


_INTERPRETATION = (
    "Phase 3D builds controlled historical acquisition infrastructure.",
    "Curated cases are not proof of predictive validity.",
    "Inclusion is based on preregistered criteria, not later outcome.",
    "Detection boundaries are frozen before retrospective outcome capture.",
    "Missing historical evidence is retained as missing.",
    "Current provider data is not silently treated as historical evidence.",
    "Excluded and blocked attempts remain visible.",
    "Repeated boundaries for one symbol are dependent observations.",
    "Synthetic fixtures test software behavior only.",
    "No Phase 3A threshold was changed.",
    "No Phase 3B policy was optimized.",
    "No scoring, ranking, recommendation, alert, backtest, P&L, or trading simulation was performed.",
)


def render_acquisition_report(batch: AcquisitionBatch) -> bytes:
    statuses = Counter(item.curation_status.value for item in batch.bundles)
    classifications = Counter(item.fixture_classification for item in batch.bundles)
    lines = [
        "# Phase 3D Acquisition Curation Report", "",
        "## Acquisition plan", "",
        f"- Plan ID: `{batch.acquisition_plan.acquisition_plan_id}`",
        f"- Status: `{batch.acquisition_plan.plan_status.value}`",
        f"- Outcome blinding: `{batch.acquisition_plan.outcome_blinding_state}`", "",
        "## Case ledger", "",
        f"- Attempted cases: {len(batch.ledger.attempts)}",
    ]
    lines.extend(f"- {name}: {count}" for name, count in sorted(statuses.items()))
    lines.extend(["", "## Fixture classifications", ""])
    lines.extend(f"- {name}: {count}" for name, count in sorted(classifications.items()))
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {statement}" for statement in _INTERPRETATION)
    lines.extend(["", "## Limitations", "",
                  "This batch performs infrastructure curation only and does not establish predictive validity.", ""])
    return "\n".join(lines).encode("utf-8")


__all__ = ["render_acquisition_report"]
