"""Secure setup for NewsAPI, Finnhub, and paid AI synthesis (Anthropic, OpenAI, Gemini) credentials."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def provider_env_path() -> Path:
    override = os.environ.get("IMP_PROVIDER_ENV", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return ROOT / ".private" / "providers.env"


def write_provider_values(values: dict[str, str], *, path: Path | None = None) -> bool:
    destination = path or provider_env_path()
    try:
        existing = destination.read_text(encoding="utf-8") if destination.is_file() else ""
        lines = existing.splitlines()
        remaining = dict(values)
        output: list[str] = []
        for line in lines:
            key, separator, _ = line.partition("=")
            normalized = key.strip()
            if separator and normalized in remaining:
                output.append(f"{normalized}={remaining.pop(normalized)}")
            else:
                output.append(line)
        output.extend(f"{key}={value}" for key, value in remaining.items())
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return True
    except OSError:
        return False


def configured_values(newsapi_key: str, finnhub_key: str, anthropic_key: str = "", *, openai_key: str = "",
                      gemini_key: str = "") -> dict[str, str]:
    """Private-file values for the keys entered; storing a key is the operator's opt-in for that provider.

    AI keys need no live flag: storing one only makes that engine selectable in the Screener. Synthesis runs on
    the engine the operator picks, only on an explicit request, behind the shared daily budget
    (IMP_SYNTHESIS_DAILY_REQUESTS / IMP_SYNTHESIS_DAILY_TOKENS)."""

    values: dict[str, str] = {}
    if newsapi_key:
        values.update(NEWSAPI_API_KEY=newsapi_key, IMP_NEWSAPI_LIVE="1")
    if finnhub_key:
        values.update(FINNHUB_API_KEY=finnhub_key, IMP_FINNHUB_LIVE="1")
    if anthropic_key:
        values.update(ANTHROPIC_API_KEY=anthropic_key)
    if openai_key:
        values.update(OPENAI_API_KEY=openai_key)
    if gemini_key:
        values.update(GEMINI_API_KEY=gemini_key)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure read-only news providers")
    parser.add_argument(
        "command",
        choices=("configure",),
        help="Store NewsAPI (Developer), Finnhub, and/or AI synthesis keys in the private provider file",
    )
    args = parser.parse_args(argv)
    if args.command != "configure":
        return 2

    # Input is hidden; leave a prompt blank to skip that provider. Values are never printed or logged.
    newsapi_key = getpass.getpass("NewsAPI Developer key (blank to skip): ").strip()
    finnhub_key = getpass.getpass("Finnhub key (blank to skip): ").strip()
    anthropic_key = getpass.getpass("Anthropic API key for AI synthesis (blank to skip): ").strip()
    openai_key = getpass.getpass("OpenAI API key for AI synthesis (blank to skip): ").strip()
    gemini_key = getpass.getpass("Google Gemini API key for AI synthesis (blank to skip): ").strip()
    values = configured_values(newsapi_key, finnhub_key, anthropic_key, openai_key=openai_key, gemini_key=gemini_key)
    if not values:
        print("ERROR: no provider key entered")
        return 2
    if not write_provider_values(values):
        print("ERROR: failed to store provider keys")
        return 2
    stored = [name for name, key in (("NewsAPI", newsapi_key), ("Finnhub", finnhub_key), ("Anthropic", anthropic_key),
                                     ("OpenAI", openai_key), ("Gemini", gemini_key)) if key]
    print(f"Stored {', '.join(stored)} credentials in the private provider file; restart the platform API")
    if anthropic_key or openai_key or gemini_key:
        print("Pick the AI synthesis engine in the Screener (the engine menu beside Generate AI synthesis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
