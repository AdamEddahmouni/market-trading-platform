"""Operator-selectable engines and models for Screener news synthesis.

The catalog names every engine the Screener can run synthesis on — the free local model
and the paid Anthropic, OpenAI, and Gemini APIs — with the models offered for each. The
operator's choice (engine + model) is saved in the IMP cache
(``settings/synthesis-engine.json``) and wins over ``IMP_SYNTHESIS_PROVIDER``; with
neither, selection stays automatic (Anthropic when its key is set, else local).

Only catalog models are accepted, so a UI request cannot name an arbitrary model. A
model set in ``IMP_SYNTHESIS_<ENGINE>_MODEL`` joins its engine's list as the default.
Listing options only reads configuration: it never calls a model or starts a process.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ENGINE_SETTINGS_RELATIVE = Path("settings") / "synthesis-engine.json"
AUTO = "auto"
OPTIONS_TTL_S = 5.0


@dataclass(frozen=True, slots=True)
class EngineSpec:
    engine: str
    label: str
    runtime: str                         # LOCAL_MODEL | PAID_API
    credential_env: str | None           # the env var holding the API key (paid engines)
    model_env: str | None
    models: tuple[tuple[str, str | None], ...] = ()   # (model id, reasoning_effort); first is the default
    default_effort: str | None = None    # for an env-supplied model outside the list


ENGINE_SPECS: dict[str, EngineSpec] = {spec.engine: spec for spec in (
    EngineSpec("local", "Local model", "LOCAL_MODEL", None, None),
    EngineSpec("anthropic", "Anthropic Claude", "PAID_API", "ANTHROPIC_API_KEY", "IMP_SYNTHESIS_ANTHROPIC_MODEL",
               (("claude-sonnet-5-5", None), ("claude-haiku-4-5-20251001", None), ("claude-opus-5-5", None))),
    # GPT-6 Luna accepts reasoning_effort "none" (and so temperature 0); Sol and Astra start at "low".
    EngineSpec("openai", "OpenAI", "PAID_API", "OPENAI_API_KEY", "IMP_SYNTHESIS_OPENAI_MODEL",
               (("gpt-6-luna", "none"), ("gpt-6.1-sol", "low"), ("gpt-6-astra", "low")), default_effort="low"),
    # Gemini 3 cannot turn thinking off; "low" keeps it short.
    EngineSpec("gemini", "Google Gemini", "PAID_API", "GEMINI_API_KEY", "IMP_SYNTHESIS_GEMINI_MODEL",
               (("gemini-3.8-flash", "low"), ("gemini-3.5-flash-lite", "low")), default_effort="low"),
)}
ENGINES = tuple(ENGINE_SPECS)

Value = Callable[[str], str | None]


def engine_models(engine: str, value: Value) -> list[tuple[str, str | None]]:
    """(model id, reasoning_effort) offered for a paid engine; an env-configured model first."""

    spec = ENGINE_SPECS[engine]
    models = list(spec.models)
    override = (value(spec.model_env) or "").strip() if spec.model_env else ""
    if override:
        known = dict(models)
        models = [(override, known.get(override, spec.default_effort))] + [item for item in models if item[0] != override]
    return models


def local_model(value: Value, cache_dir: Path) -> tuple[str | None, str | None]:
    """(model id, None) for a configured local model, else (None, reason). Starts nothing."""

    from ...local_state.external_cache import read_manifest
    from .local_provider import BASE_URL_ENV, MANIFEST_RELATIVE, MODEL_ENV, LocalModelManifest, is_loopback_url

    base_url, model = (value(BASE_URL_ENV) or "").strip(), (value(MODEL_ENV) or "").strip()
    if base_url:
        if not is_loopback_url(base_url):
            return None, "LOCAL_ENDPOINT_NOT_LOOPBACK"
        return (model, None) if model else (None, f"{MODEL_ENV}_NOT_SET")
    manifest = LocalModelManifest.from_dict(read_manifest(cache_dir / MANIFEST_RELATIVE) or {})
    if manifest is None:
        return None, "NO_SYNTHESIS_PROVIDER_CONFIGURED"
    missing = manifest.missing()
    return (None, missing) if missing else (manifest.model_id, None)


def local_context_window(value: Value, cache_dir: Path) -> int | None:
    """The context window the managed local model is started with; None for an operator-run endpoint. Starts nothing."""

    from ...local_state.external_cache import read_manifest
    from .local_provider import BASE_URL_ENV, MANIFEST_RELATIVE, LocalModelManifest

    if (value(BASE_URL_ENV) or "").strip():
        return None
    manifest = LocalModelManifest.from_dict(read_manifest(cache_dir / MANIFEST_RELATIVE) or {})
    return manifest.context if manifest is not None else None


def engine_options(value: Value, cache_dir: Path) -> list[dict[str, Any]]:
    """Every engine with its models and whether it can run now (never calls a model)."""

    options: list[dict[str, Any]] = []
    for spec in ENGINE_SPECS.values():
        # A context window is stated only where IMP sets it (the managed local model). None means "not recorded",
        # never "unlimited".
        context = None
        if spec.engine == "local":
            model, reason = local_model(value, cache_dir)
            models = [model] if model else []
            context = local_context_window(value, cache_dir) if model else None
        else:
            models = [model for model, _ in engine_models(spec.engine, value)]
            configured = bool((value(spec.credential_env or "") or "").strip())
            reason = None if configured else f"{spec.credential_env}_NOT_SET"
        options.append({"id": spec.engine, "label": spec.label, "runtime": spec.runtime, "models": models,
                        "default_model": models[0] if models else None, "context_window": context,
                        "state": "AVAILABLE" if reason is None else "NOT_CONFIGURED", "reason": reason})
    return options


class SynthesisSettings:
    """The saved engine choice, its catalog validation, and the provider it selects."""

    def __init__(self, value: Value, cache_dir: Path, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._value = value
        self._cache_dir = cache_dir
        self._clock = clock
        self._lock = threading.Lock()
        self._options: tuple[float, list[dict[str, Any]]] | None = None

    @property
    def path(self) -> Path:
        return self._cache_dir / ENGINE_SETTINGS_RELATIVE

    def saved(self) -> tuple[str, str | None] | None:
        from ...local_state.external_cache import read_manifest

        payload = read_manifest(self.path) or {}
        engine, model = payload.get("engine"), payload.get("model")
        if engine not in ENGINE_SPECS:
            return None
        return engine, model if isinstance(model, str) and model else None

    def current(self) -> dict[str, Any]:
        """The operator's choice: saved, else ``IMP_SYNTHESIS_PROVIDER``, else automatic."""

        saved = self.saved()
        if saved is not None:
            return {"engine": saved[0], "model": saved[1], "source": "OPERATOR"}
        from .local_provider import PROVIDER_ENV

        env_choice = (self._value(PROVIDER_ENV) or "").strip().lower()
        if env_choice in ENGINE_SPECS:
            return {"engine": env_choice, "model": None, "source": "ENVIRONMENT"}
        return {"engine": AUTO, "model": None, "source": "AUTOMATIC"}

    def options(self) -> list[dict[str, Any]]:
        # Reads the provider files several times; the status payload asks often, so hold it briefly.
        with self._lock:
            if self._options is not None and self._clock() - self._options[0] < OPTIONS_TTL_S:
                return self._options[1]
        options = engine_options(self._value, self._cache_dir)
        with self._lock:
            self._options = (self._clock(), options)
        return options

    def select(self, engine: str, model: str | None) -> None:
        """Save an engine (and model) from the catalog; raises ValueError for anything else."""

        from ...local_state.external_cache import write_json_atomic

        if not isinstance(engine, str) or engine not in ENGINE_SPECS:
            raise ValueError("SYNTHESIS_ENGINE_INVALID")
        if model is not None and not isinstance(model, str):
            raise ValueError("SYNTHESIS_MODEL_INVALID")
        if model:
            allowed = (engine_options(self._value, self._cache_dir)[ENGINES.index(engine)]["models"])
            if model not in allowed:
                raise ValueError("SYNTHESIS_MODEL_INVALID")
        write_json_atomic(self.path, {"engine": engine, "model": model or None})
        with self._lock:
            self._options = None

    def build(self) -> Any:
        """The ``SynthesisSelection`` for the current choice."""

        from .local_provider import select_synthesis_provider

        choice = self.current()
        engine = None if choice["engine"] == AUTO else choice["engine"]
        return select_synthesis_provider(self._value, cache_dir=self._cache_dir, engine=engine, model=choice["model"])


__all__ = ["AUTO", "ENGINES", "ENGINE_SETTINGS_RELATIVE", "ENGINE_SPECS", "EngineSpec", "SynthesisSettings",
           "engine_models", "engine_options", "local_context_window", "local_model"]
