"""Console alert formatting for momentum trading signals.

Pipeline role
-------------
Optional human-visible output when a decision fires — complements
``paper_trader`` JSON logs and ``telegram_notifier`` pushes. Called from the
main loop for high-signal BUY/SELL/REVIEW events.

``print_trade_alert`` is stdout-only (no state files). Run ``main()`` directly
to verify box formatting before a live session.

Merge notes: fully reusable for any CLI-driven trading agent; no options-specific logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict


def print_trade_alert(
    ticker: str,
    decision: str,
    score: float,
    label: str,
    confidence: str,
    source: str,
    headline: str,
    reason: str,
    social_signal: str,
    signal_since: str = "unknown",
    options_bias: str | None = None,
    options_score: float | None = None,
    action_probs: dict | None = None,
    lean: str | None = None,
    lean_pct: int | None = None,
    instrument_hint: str | None = None,
) -> None:
    """
    Print a loud human-readable console alert box.

    Inputs:
    - ticker, decision, score, label, confidence: core signal details.
    - source, headline, reason: news context for quick understanding.
    - social_signal: HIGH_ALERT / WATCH / IGNORE.
    - signal_since: optional time the social signal started.

    Output:
    - None. Prints formatted alert text.

    Why this exists:
    - Fast, clear visibility helps a human reviewer react quickly and
      audit why an action was suggested.
    """
    timestamp = datetime.now().strftime("%I:%M:%S %p")
    line_top = "╔" + "═" * 58 + "╗"
    line_bottom = "╚" + "═" * 58 + "╝"

    print(line_top)
    print(f"║  🚨 {decision} SIGNAL — ${ticker:<42}║")
    print(f"║  Score:    {score:+.2f} ({label}, {confidence} conf.){' ' * 17}║")
    print(f"║  Source:   {source} — {timestamp:<31}║")
    print(f"║  Headline: {headline[:44]:<44}║")
    print(f"║  Reason:   {reason[:44]:<44}║")
    print(f"║  Signal:   {social_signal} since {signal_since:<31}║")
    if options_bias is not None:
        options_text = f"{options_bias} ({options_score:.1f})" if options_score is not None else options_bias
        print(f"║  Options:  {options_text[:44]:<44}║")
    if lean:
        print(f"║  Lean:     {lean} {lean_pct or 0}%{' ' * 35}║")
    if action_probs:
        probs = " ".join(f"{k}:{float(v)*100:.0f}%" for k, v in action_probs.items())
        print(f"║  Probs:    {probs[:44]:<44}║")
    if instrument_hint:
        print(f"║  Instrument: {instrument_hint:<42}║")
    print(line_bottom)


def main() -> None:
    """
    Run a demo alert print for visual verification.

    Inputs:
    - None.

    Output:
    - None. Prints one alert box.

    Why this exists:
    - Quick direct execution confirms formatting before full pipeline use.
    """
    print_trade_alert(
        ticker="ASTC",
        decision="BUY",
        score=0.87,
        label="positive",
        confidence="high",
        source="PR Newswire",
        headline="Astrotech approves lunar initiative",
        reason="Small cap catalyst narrative appears strong",
        social_signal="HIGH_ALERT",
        signal_since="06:02 AM",
    )


if __name__ == "__main__":
    main()
