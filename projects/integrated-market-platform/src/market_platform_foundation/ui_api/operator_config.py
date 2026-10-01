"""Provider setup registry: which operator settings IMP accepts, where they live, and value-blind status.

This is the only allowlist of settings the UI (and ``tools/news/auth.py``) may write. It is not a
generic environment editor: a write names a registered provider and only that provider's settings.

Storage and precedence (highest first):

1. The API's process environment as it was before IMP loaded any file ("ENVIRONMENT"). Read-only
   here: the UI refuses to write a setting the environment already sets, so there is no shadow value.
2. ``.private/providers.env`` (or ``IMP_PROVIDER_ENV``), the private file the UI and CLI write
   ("PRIVATE_FILE").
3. The repository ``.env`` ("ENV_FILE"), loaded by the API launcher.

Most provider code reads ``os.environ``. At API start :func:`bootstrap_process_environment` copies
registered settings from the private file into the process environment without overriding it, and
every UI write updates that copy, so a saved value reaches the next request without a restart. The
``applies`` field says honestly when a provider still needs one (it built its client at startup).

Secret values never leave this module except into the private file and the process environment:
status payloads carry ``configured``/``source`` only, and the non-secret SEC contact is reduced to
its email domain.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping

REPO_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_ENV = ".private/providers.env"
SCHEMA_VERSION = "operator-config/1.1"
PLACEHOLDERS = frozenset({"CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})

# Where a setting's effective value comes from.
SOURCE_ENVIRONMENT = "ENVIRONMENT"
SOURCE_PRIVATE_FILE = "PRIVATE_FILE"
SOURCE_ENV_FILE = "ENV_FILE"
SOURCE_NONE = "NONE"


class ConfigError(ValueError):
    """A rejected write. ``str()`` is ``CODE`` or ``CODE:SETTING``; never a value."""

    def __init__(self, code: str, setting: str | None = None) -> None:
        super().__init__(f"{code}:{setting}" if setting else code)
        self.code = code
        self.setting = setting


# ------------------------------------------------------------------ validation
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"[^\s@<>()]+@[^\s@<>()]+\.[A-Za-z]{2,}")
_WORD = re.compile(r"[A-Za-z]{2,}")


def _base(value: str, setting: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise ConfigError("INVALID_VALUE", setting)
    text = value.strip()
    if not text:
        raise ConfigError("VALUE_REQUIRED", setting)
    if _CONTROL.search(text):
        raise ConfigError("VALUE_HAS_CONTROL_CHARACTERS", setting)
    if len(text) > limit:
        raise ConfigError("VALUE_TOO_LONG", setting)
    if text[0] in "\"'" or text[-1] in "\"'":
        # The env-file reader strips surrounding quotes, so a quoted value would not round-trip.
        raise ConfigError("VALUE_QUOTED", setting)
    if text.upper() in PLACEHOLDERS:
        raise ConfigError("VALUE_IS_PLACEHOLDER", setting)
    return text


def opaque_value(value: str, setting: str) -> str:
    """Keys, tokens, secrets, and ids: one printable run. Provider formats are not guessed at."""

    text = _base(value, setting, limit=512)
    if any(character.isspace() for character in text):
        raise ConfigError("VALUE_HAS_WHITESPACE", setting)
    return text


def sec_contact_identity(value: str, setting: str = "SEC_USER_AGENT") -> str:
    """SEC Fair Access User-Agent: who is asking (a name or organization) and a contact email.

    Uses the same rule the SEC transport enforces, plus a real email shape and a readable name,
    so a value the UI accepts is one every SEC client will send."""

    from ..sec_edgar.transport import require_user_agent

    text = _base(value, setting, limit=200)
    if not text.isascii():
        raise ConfigError("SEC_USER_AGENT_NOT_ASCII", setting)   # sent as an HTTP header
    try:
        require_user_agent(text)
    except ValueError as exc:
        raise ConfigError(str(exc), setting) from None
    email = _EMAIL.search(text)
    if email is None:
        raise ConfigError("SEC_USER_AGENT_MUST_IDENTIFY_CONTACT", setting)
    if not _WORD.search(text[: email.start()] + text[email.end():]):
        raise ConfigError("SEC_USER_AGENT_NEEDS_NAME", setting)
    return " ".join(text.split())


# ------------------------------------------------------------------ registry
@dataclass(frozen=True)
class Setting:
    name: str
    label: str
    kind: str          # API_KEY | TOKEN | CLIENT_ID | CLIENT_SECRET | ACCOUNT_ID | CONTACT_IDENTITY
    secret: bool
    validate: Callable[[str, str], str] = opaque_value
    required: bool = True
    help: str = ""
    example: str = ""  # non-secret settings only


@dataclass(frozen=True)
class ProviderSetup:
    provider: str
    label: str
    group: str         # REGULATORY | NEWS | MARKET_DATA | AI | BROKERAGE | LOCAL
    access: str        # FREE | FREE_ACCOUNT | PAID_API | SUBSCRIPTION | PAPER_SANDBOX
    about: str
    unlocks: tuple[str, ...]
    settings: tuple[Setting, ...] = ()
    # Observational read gates switched on when the provider becomes fully configured. Never an
    # execution, billing, or broker gate.
    live_gates: tuple[str, ...] = ()
    applies: str = "NEXT_REQUEST"  # NEXT_REQUEST | RESTART
    applies_note: str = ""
    # Services to refresh after a change so the next request uses the new value.
    refresh: tuple[str, ...] = ()
    # Providers configured outside IMP (native login, local process, legal attestation).
    external_setup: str = ""

    @property
    def configurable(self) -> bool:
        return bool(self.settings)


_KEY_HELP = "IMP never shows a saved key again."

PROVIDERS: tuple[ProviderSetup, ...] = (
    ProviderSetup(
        "sec", "SEC EDGAR", "REGULATORY", "FREE",
        "The SEC's Fair Access policy requires every automated request to say who is asking and how to "
        "reach them. No account or key: just your name (or firm) and a contact email.",
        ("SEC filings in News", "SEC press releases", "13F institutional ownership",
         "Fail-to-deliver data (Short Squeeze)", "Automatic Senate eFD downloads (also needs the attested folder)"),
        (Setting("SEC_USER_AGENT", "Contact identity", "CONTACT_IDENTITY", False, sec_contact_identity,
                 help="Your name or firm and a contact email. Sent as the User-Agent to SEC EDGAR, and to the "
                      "Senate eFD site when automatic Senate downloads are on. Never sent anywhere else.",
                 example="IMP Screener Jane Doe jane@example.com"),),
        live_gates=("IMP_EDGAR_LIVE", "IMP_SEC_FTD_LIVE"),
        refresh=("news", "participants"),
    ),
    ProviderSetup(
        "newsapi", "NewsAPI", "NEWS", "FREE_ACCOUNT",
        "Headline search. The free Developer plan is limited to 100 requests a day and delayed articles.",
        ("NewsAPI headlines in News",),
        (Setting("NEWSAPI_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        live_gates=("IMP_NEWSAPI_LIVE",), refresh=("news",),
    ),
    ProviderSetup(
        "finnhub", "Finnhub", "NEWS", "FREE_ACCOUNT",
        "Company news for US equities. The free account key is rate limited.",
        ("Finnhub company news in News",),
        (Setting("FINNHUB_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        live_gates=("IMP_FINNHUB_LIVE",), refresh=("news",),
    ),
    ProviderSetup(
        "finra", "FINRA API", "MARKET_DATA", "FREE_ACCOUNT",
        "FINRA Query API credentials from a free FINRA API console account.",
        ("Short interest and short-sale volume (Short Squeeze)", "FINRA short intelligence"),
        (Setting("FINRA_CLIENT_ID", "Client ID", "CLIENT_ID", False),
         Setting("FINRA_CLIENT_SECRET", "Client secret", "CLIENT_SECRET", True, help=_KEY_HELP)),
        live_gates=("IMP_FINRA_LIVE",),
    ),
    ProviderSetup(
        "fred", "FRED", "MARKET_DATA", "FREE_ACCOUNT",
        "Federal Reserve Economic Data. A free key from the St. Louis Fed.",
        ("Macro and rates context from FRED",),
        (Setting("FRED_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        live_gates=("IMP_FRED_LIVE",),
    ),
    ProviderSetup(
        "eia", "EIA", "MARKET_DATA", "FREE_ACCOUNT",
        "U.S. Energy Information Administration open data. A free key.",
        ("Energy inventory and production context",),
        (Setting("EIA_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        live_gates=("IMP_EIA_LIVE",),
    ),
    ProviderSetup(
        "openfigi", "OpenFIGI", "MARKET_DATA", "FREE",
        "Bond identifier lookups work without a key; a free key raises the rate limit.",
        ("Higher OpenFIGI lookup limit (Bonds)",),
        (Setting("OPENFIGI_API_KEY", "API key (optional)", "API_KEY", True, required=False, help=_KEY_HELP),),
    ),
    ProviderSetup(
        "noaa", "NOAA Climate Data Online", "MARKET_DATA", "FREE_ACCOUNT",
        "Weather forecasts work without a token; a free CDO token adds historical climate data.",
        ("Historical climate data (Weather)",),
        (Setting("NOAA_CDO_TOKEN", "CDO token (optional)", "TOKEN", True, required=False, help=_KEY_HELP),),
    ),
    ProviderSetup(
        "finviz", "Finviz Elite", "MARKET_DATA", "SUBSCRIPTION",
        "Your existing Finviz Elite subscription's API token. IMP does not sell or start a subscription.",
        ("Finviz discovery screens", "Finviz news and fundamentals"),
        (Setting("FINVIZ_API_KEY", "Elite API token", "TOKEN", True, help=_KEY_HELP),),
        applies="RESTART", applies_note="Finviz reads its token when the API starts.",
    ),
    ProviderSetup(
        "anthropic", "Anthropic Claude", "AI", "PAID_API",
        "Paid API billed by Anthropic. Saving a key calls no model and switches nothing to it: it only makes "
        "Claude selectable in the AI engine menu. Synthesis runs only when you ask, within the daily budget.",
        ("Claude as an AI synthesis engine",),
        (Setting("ANTHROPIC_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        refresh=("news",),
    ),
    ProviderSetup(
        "openai", "OpenAI", "AI", "PAID_API",
        "Paid API billed by OpenAI. Saving a key calls no model: synthesis runs only when you ask, "
        "within the daily synthesis budget.",
        ("OpenAI as an AI synthesis engine",),
        (Setting("OPENAI_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        refresh=("news",),
    ),
    ProviderSetup(
        "gemini", "Google Gemini", "AI", "PAID_API",
        "Paid API billed by Google (a free tier may apply). Saving a key calls no model: synthesis runs "
        "only when you ask, within the daily synthesis budget.",
        ("Gemini as an AI synthesis engine",),
        (Setting("GEMINI_API_KEY", "API key", "API_KEY", True, help=_KEY_HELP),),
        refresh=("news",),
    ),
    ProviderSetup(
        "tradier", "Tradier paper sandbox", "BROKERAGE", "PAPER_SANDBOX",
        "Sandbox paper account only. Saving a token enables nothing: paper order routing stays off until "
        "IMP_TRADIER_PAPER and IMP_BROKER_PAPER_EXECUTION are set, and production endpoints stay blocked.",
        ("Tradier sandbox paper account (when paper routing is separately enabled)",),
        (Setting("IMP_TRADIER_TOKEN", "Sandbox token", "TOKEN", True, help=_KEY_HELP),
         Setting("IMP_TRADIER_ACCOUNT_ID", "Sandbox account ID", "ACCOUNT_ID", False)),
        applies="RESTART", applies_note="The paper adapter reads its token when the API starts.",
    ),
    ProviderSetup(
        "opend", "moomoo OpenD", "LOCAL", "FREE",
        "A local gateway process, not a key. Log in inside OpenD; IMP can start the installed program.",
        ("ETF and Futures catalogs", "Live quotes"),
        external_setup="No API key. Start OpenD from the Setup checklist and log in inside OpenD.",
    ),
    ProviderSetup(
        "ibkr", "Interactive Brokers", "BROKERAGE", "ACCOUNT",
        "IBKR sign-in happens in IB Gateway or TWS with IBKR's own two-factor login.",
        ("IBKR observational market data",),
        external_setup="Sign in through IB Gateway or TWS. IMP never stores IBKR passwords or two-factor secrets.",
    ),
    ProviderSetup(
        "senate_efd", "Senate eFD", "REGULATORY", "FREE",
        "Senate disclosures require accepting the eFD terms. IMP downloads only into a folder holding your "
        "own ACCESS_ATTESTATION.json with automated_access: true.",
        ("Senate periodic transaction reports",),
        external_setup="Set IMP_SENATE_EFD_IMPORT_DIR to a folder with your attestation file. Terms are not "
                       "accepted from this form. It also uses the SEC contact identity above.",
    ),
)

PROVIDERS_BY_ID: dict[str, ProviderSetup] = {entry.provider: entry for entry in PROVIDERS}


def managed_names() -> frozenset[str]:
    """Every setting and gate name the registry may write. Nothing outside this set is touched."""

    names: set[str] = set()
    for entry in PROVIDERS:
        names.update(setting.name for setting in entry.settings)
        names.update(entry.live_gates)
    return frozenset(names)


def process_names() -> frozenset[str]:
    """Names mirrored into the API's process environment.

    Paid-API keys are not: AI synthesis reads them from the private file itself, and a key in the
    process environment would silently switch the Assistant to a paid provider
    (``assistant.inference_factory``). Storing a paid key must only make an engine selectable."""

    return managed_names() - frozenset(
        setting.name for entry in PROVIDERS if entry.access == "PAID_API" for setting in entry.settings)


# ------------------------------------------------------------------ file I/O
def provider_env_path(*, root: Path | None = None) -> Path:
    override = os.environ.get("IMP_PROVIDER_ENV", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (root or REPO_ROOT) / PRIVATE_ENV


def _read_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _present(value: str | None) -> bool:
    text = (value or "").strip()
    return bool(text) and text.upper() not in PLACEHOLDERS


def _rewrite(path: Path, updates: Mapping[str, str | None]) -> None:
    """Atomically set (str) or delete (None) exactly these lines; every other line is kept as written."""

    destination = path.resolve()
    existing = destination.read_text(encoding="utf-8") if destination.is_file() else ""
    pending = dict(updates)
    output: list[str] = []
    for line in existing.splitlines():
        name, separator, _ = line.partition("=")
        normalized = name.strip()
        if separator and normalized in updates:
            value = pending.pop(normalized, None) if normalized in pending else None
            if value is not None:
                output.append(f"{normalized}={value}")
            continue  # deleted, or a duplicate line for a name already written
        output.append(line)
    output.extend(f"{name}={value}" for name, value in pending.items() if value is not None)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(output) + ("\n" if output else ""))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


# ------------------------------------------------------------------ the store
@dataclass
class ProviderConfigStore:
    """Reads and writes registered settings with the documented precedence.

    ``external`` is the set of registered names the process environment held before IMP loaded any
    file; it is captured once and never changes, so a value IMP copies into ``environ`` is never
    mistaken for an operator's environment override."""

    private_path: Path
    env_file_path: Path | None = None
    environ: MutableMapping[str, str] = field(default_factory=lambda: os.environ)
    external: frozenset[str] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _external(self) -> frozenset[str]:
        if self.external is None:
            self.external = frozenset(name for name in managed_names() if _present(self.environ.get(name)))
        return self.external

    def _env_file(self) -> dict[str, str]:
        return _read_values(self.env_file_path) if self.env_file_path is not None else {}

    def bootstrap(self) -> None:
        """Copy registered private-file values into the process environment without overriding it."""

        with self._lock:
            external = self._external()
            for name, value in _read_values(self.private_path).items():
                if name in process_names() and name not in external and _present(value):
                    self.environ[name] = value

    def source(self, name: str, private: Mapping[str, str], env_file: Mapping[str, str]) -> str:
        if name in self._external():
            return SOURCE_ENVIRONMENT
        if _present(private.get(name)):
            return SOURCE_PRIVATE_FILE
        if _present(env_file.get(name)):
            return SOURCE_ENV_FILE
        return SOURCE_NONE

    def _effective(self, name: str, private: Mapping[str, str], env_file: Mapping[str, str]) -> str | None:
        if name in self._external():
            return self.environ.get(name)
        for layer in (private, env_file):
            if _present(layer.get(name)):
                return layer[name]
        return None

    def _sync(self, names: set[str], private: Mapping[str, str], env_file: Mapping[str, str]) -> None:
        """Make the process environment match the files for these names (never an external or paid one)."""

        for name in (names & process_names()) - self._external():
            value = self._effective(name, private, env_file)
            if value is None:
                self.environ.pop(name, None)
            else:
                self.environ[name] = value

    # -------------------------------------------------------------- status
    def payload(self) -> dict[str, Any]:
        private, env_file = _read_values(self.private_path), self._env_file()
        return {
            "schema_version": SCHEMA_VERSION,
            "providers": [self._provider_status(entry, private, env_file) for entry in PROVIDERS],
            "precedence": [SOURCE_ENVIRONMENT, SOURCE_PRIVATE_FILE, SOURCE_ENV_FILE],
            "secrets_included": False,
        }

    def _provider_status(self, entry: ProviderSetup, private: Mapping[str, str], env_file: Mapping[str, str]) -> dict[str, Any]:
        fields = [self._field_status(setting, private, env_file) for setting in entry.settings]
        required = [item for item in fields if item["required"]]
        if not entry.configurable:
            state = "EXTERNAL"
        elif required and all(item["configured"] for item in required):
            state = "CONFIGURED"
        elif not required and any(item["configured"] for item in fields):
            state = "CONFIGURED"
        elif any(item["configured"] for item in fields):
            state = "PARTIAL"
        else:
            state = "OPTIONAL" if not required else "NEEDS_SETUP"
        gates = []
        for gate in entry.live_gates:
            value = self._effective(gate, private, env_file) or ""
            gates.append({"name": gate, "enabled": value.strip().lower() in {"1", "true", "yes"},
                          "source": self.source(gate, private, env_file)})
        return {
            "provider": entry.provider,
            "label": entry.label,
            "group": entry.group,
            "access": entry.access,
            "about": entry.about,
            "unlocks": list(entry.unlocks),
            "configurable": entry.configurable,
            "external_setup": entry.external_setup or None,
            "state": state,
            "live_gates": gates,
            "applies": entry.applies,
            "applies_note": entry.applies_note or None,
            # No provider is probed on save: a paid key must not spend money to prove itself.
            "verification": "ON_FIRST_USE",
            "fields": fields,
        }

    def _field_status(self, setting: Setting, private: Mapping[str, str], env_file: Mapping[str, str]) -> dict[str, Any]:
        source = self.source(setting.name, private, env_file)
        hint = None
        if not setting.secret and setting.kind == "CONTACT_IDENTITY" and source != SOURCE_NONE:
            email = _EMAIL.search(self._effective(setting.name, private, env_file) or "")
            hint = f"contact at @{email.group(0).split('@', 1)[1]}" if email else None
        return {
            "key": setting.name,
            "label": setting.label,
            "kind": setting.kind,
            "sensitive": setting.secret,
            "required": setting.required,
            "configured": source != SOURCE_NONE,
            "source": source,
            "editable": source != SOURCE_ENVIRONMENT,
            "removable": source == SOURCE_PRIVATE_FILE,
            "help": setting.help or None,
            "example": setting.example or None,
            "hint": hint,
        }

    # -------------------------------------------------------------- writes
    def write(self, provider: str, values: Mapping[str, Any] | None = None,
              clear: list[Any] | tuple[Any, ...] | None = None) -> dict[str, Any]:
        """Validate, persist, and apply one provider's settings. Returns names only, never values.

        Blank values are ignored (the UI's "leave blank to keep"). A setting the process environment
        sets is refused, not shadowed. When the provider becomes fully configured its observational
        gates are switched on in the private file; when its required settings are all removed those
        private gate lines go too."""

        entry = PROVIDERS_BY_ID.get(str(provider or "").strip().lower())
        if entry is None or not entry.configurable:
            raise ConfigError("PROVIDER_NOT_SUPPORTED")
        allowed = {setting.name: setting for setting in entry.settings}
        values = dict(values or {})
        clear_names = [str(name) for name in (clear or [])]
        for name in list(values) + clear_names:
            if name not in allowed:
                raise ConfigError("PROVIDER_FIELD_NOT_ALLOWED")
        updates: dict[str, str | None] = {}
        for name, raw in values.items():
            if not isinstance(raw, str):
                raise ConfigError("INVALID_VALUE", name)
            if not raw.strip():
                continue
            if name in clear_names:
                raise ConfigError("SET_AND_CLEAR_CONFLICT", name)
            updates[name] = allowed[name].validate(raw, name)
        for name in clear_names:
            updates[name] = None
        if not updates:
            raise ConfigError("NO_CHANGES")
        overridden = sorted(name for name in updates if name in self._external())
        if overridden:
            raise ConfigError("SETTING_OVERRIDDEN_BY_ENVIRONMENT", overridden[0])

        with self._lock:
            private = _read_values(self.private_path)
            after = {**private, **{name: value for name, value in updates.items() if value is not None}}
            for name, value in updates.items():
                if value is None:
                    after.pop(name, None)
            env_file = self._env_file()
            required = [setting.name for setting in entry.settings if setting.required]
            complete = bool(required) and all(self._effective(name, after, env_file) for name in required)
            gates_on: list[str] = []
            gates_off: list[str] = []
            if entry.live_gates and complete:
                gates_on = [gate for gate in entry.live_gates if private.get(gate) != "1"]
                updates.update({gate: "1" for gate in gates_on})
            elif entry.live_gates and required and not any(self._effective(name, after, env_file) for name in required):
                gates_off = [gate for gate in entry.live_gates if gate in private]
                updates.update({gate: None for gate in gates_off})
            _rewrite(self.private_path, updates)
            self._sync(set(updates), _read_values(self.private_path), env_file)

        return {
            "provider": entry.provider,
            "saved": sorted(name for name, value in updates.items() if value is not None and name in allowed),
            "cleared": sorted(name for name, value in updates.items() if value is None and name in allowed),
            "gates_enabled": sorted(gates_on),
            "gates_removed": sorted(gates_off),
            "applies": entry.applies,
            "verification": "ON_FIRST_USE",
            "refresh": list(entry.refresh),
        }


# ------------------------------------------------------------------ process-wide store
_STORE: ProviderConfigStore | None = None
_STORE_LOCK = threading.Lock()


def default_store() -> ProviderConfigStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ProviderConfigStore(private_path=provider_env_path(), env_file_path=REPO_ROOT / ".env")
        return _STORE


def bootstrap_process_environment() -> None:
    """At API start, before ``.env`` is loaded: snapshot the real environment, then apply the private file."""

    default_store().bootstrap()


# ------------------------------------------------------------------ compatibility
def write_provider_values(provider: str, values: Mapping[str, str], *, path: Path | None = None) -> None:
    """Validated write of one provider's values to a private file (tests and tools)."""

    store = ProviderConfigStore(private_path=(path or provider_env_path()), environ={}, external=frozenset())
    store.write(provider, values)


def build_config_payload(
    *,
    path: Path | None = None,
    environment: Mapping[str, str] | None = None,
    environment_path: Path | None = None,
) -> dict[str, Any]:
    """Status for explicit files; ``environment`` stands for the API's own process environment."""

    environ = {str(key): str(value) for key, value in (environment or {}).items()}
    store = ProviderConfigStore(private_path=(path or provider_env_path()), env_file_path=environment_path,
                                environ=environ)
    return store.payload()


__all__ = [
    "ConfigError",
    "PROVIDERS",
    "PROVIDERS_BY_ID",
    "ProviderConfigStore",
    "SCHEMA_VERSION",
    "bootstrap_process_environment",
    "build_config_payload",
    "default_store",
    "managed_names",
    "provider_env_path",
    "sec_contact_identity",
    "write_provider_values",
]
