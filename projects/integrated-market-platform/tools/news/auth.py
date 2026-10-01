"""Terminal fallback for provider setup: the SEC contact identity, news keys, and AI synthesis keys.

The Screener's Setup panel is the normal path; this writes the same private provider file with the
same validation. ``configure --provider <id>`` sets any provider in the Setup registry
(``market_platform_foundation.ui_api.operator_config``)."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.operator_config import (  # noqa: E402
    PROVIDERS,
    PROVIDERS_BY_ID,
    ConfigError,
    ProviderConfigStore,
    sec_contact_identity,
)

SEC_GATES = PROVIDERS_BY_ID["sec"].live_gates


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
        temporary.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, destination)
        return True
    except OSError:
        return False


def configured_values(newsapi_key: str, finnhub_key: str, anthropic_key: str = "", *, openai_key: str = "",
                      gemini_key: str = "", sec_user_agent: str = "") -> dict[str, str]:
    """Private-file values for what was entered; storing a key is the operator's opt-in for that provider.

    AI keys need no live flag: storing one only makes that engine selectable in the Screener. Synthesis runs on
    the engine the operator picks, only on an explicit request, behind the shared daily budget
    (IMP_SYNTHESIS_DAILY_REQUESTS / IMP_SYNTHESIS_DAILY_TOKENS). The SEC identity switches on the SEC reads
    it unlocks, exactly as saving it in Setup does."""

    values: dict[str, str] = {}
    if sec_user_agent:
        values.update(SEC_USER_AGENT=sec_user_agent, **{gate: "1" for gate in SEC_GATES})
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


def configure_provider(provider: str, *, path: Path | None = None, ask=input, ask_secret=getpass.getpass) -> int:
    """Prompt for one registered provider's settings and store them with the Setup panel's rules."""

    entry = PROVIDERS_BY_ID[provider]
    values: dict[str, str] = {}
    for setting in entry.settings:
        prompt = f"{entry.label} {setting.label} (blank to skip): "
        values[setting.name] = (ask_secret(prompt) if setting.secret else ask(prompt)).strip()
    # The CLI is not the API process: it writes the file and never edits its own environment.
    store = ProviderConfigStore(private_path=path or provider_env_path(), environ={}, external=frozenset())
    try:
        result = store.write(provider, values)
    except ConfigError as exc:
        print(f"ERROR: {exc.code}" + (f" ({exc.setting})" if exc.setting else ""))
        return 2
    except OSError:
        print("ERROR: failed to store provider settings")
        return 2
    print(f"Stored {', '.join(result['saved'])} for {entry.label} in the private provider file")
    if result["gates_enabled"]:
        print(f"Switched on {', '.join(result['gates_enabled'])}")
    print("Restart the platform API to apply" if result["applies"] == "RESTART"
          else "A running API applies it after a restart; a Setup-panel save applies at once")
    return 0


def main(argv: list[str] | None = None) -> int:
    configurable = [entry.provider for entry in PROVIDERS if entry.configurable]
    parser = argparse.ArgumentParser(description="Configure provider credentials (fallback for the Setup panel)")
    parser.add_argument(
        "command",
        choices=("configure",),
        help="Store the SEC contact identity, NewsAPI, Finnhub, and/or AI synthesis keys in the private provider file",
    )
    parser.add_argument("--provider", choices=configurable, help="Configure one Setup provider instead")
    args = parser.parse_args(argv)
    if args.command != "configure":
        return 2
    if args.provider:
        return configure_provider(args.provider)

    # The SEC identity is not secret and is shown as typed. Keys are hidden; values are never printed or logged.
    sec_user_agent = input("SEC contact identity, your name and email (blank to skip): ").strip()
    if sec_user_agent:
        try:
            sec_user_agent = sec_contact_identity(sec_user_agent)
        except ConfigError as exc:
            print(f"ERROR: {exc.code}: enter a name and a contact email, e.g. IMP Screener Jane Doe jane@example.com")
            return 2
    newsapi_key = getpass.getpass("NewsAPI Developer key (blank to skip): ").strip()
    finnhub_key = getpass.getpass("Finnhub key (blank to skip): ").strip()
    anthropic_key = getpass.getpass("Anthropic API key for AI synthesis (blank to skip): ").strip()
    openai_key = getpass.getpass("OpenAI API key for AI synthesis (blank to skip): ").strip()
    gemini_key = getpass.getpass("Google Gemini API key for AI synthesis (blank to skip): ").strip()
    values = configured_values(newsapi_key, finnhub_key, anthropic_key, openai_key=openai_key, gemini_key=gemini_key,
                               sec_user_agent=sec_user_agent)
    if not values:
        print("ERROR: nothing entered")
        return 2
    if not write_provider_values(values):
        print("ERROR: failed to store provider settings")
        return 2
    stored = [name for name, key in (("SEC identity", sec_user_agent), ("NewsAPI", newsapi_key), ("Finnhub", finnhub_key),
                                     ("Anthropic", anthropic_key), ("OpenAI", openai_key), ("Gemini", gemini_key)) if key]
    print(f"Stored {', '.join(stored)} in the private provider file; restart the platform API")
    if anthropic_key or openai_key or gemini_key:
        print("Pick the AI synthesis engine in the Screener (the engine menu beside Generate AI synthesis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
