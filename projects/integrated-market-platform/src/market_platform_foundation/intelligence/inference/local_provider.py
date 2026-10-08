"""Zero-cost local inference on the canonical ``InferenceProvider`` boundary.

``LocalChatInferenceProvider`` speaks the OpenAI-compatible ``/v1/chat/completions``
protocol that llama.cpp's ``llama-server``, Ollama, and LM Studio all serve. It only
ever talks to a loopback address: story text never leaves the workstation.

Two ways to point it at a model:

* ``IMP_LOCAL_LLM_BASE_URL`` + ``IMP_LOCAL_LLM_MODEL`` — an OpenAI-compatible server
  the operator already runs (process environment or ``.private/providers.env``);
* the manifest ``<IMP cache>/models/local-llm.json`` written by the explicit setup step
  ``tools/news/setup_local_synthesis.py`` — IMP then starts a pinned ``llama-server``
  on demand (first synthesis request only), bound to 127.0.0.1, and stops it after
  it has been idle, so the model uses no memory until an operator asks for synthesis.

Nothing here downloads. A missing runtime, missing weights, a busy port, or a crashed
server is an explicit state (``LOCAL_MODEL_UNAVAILABLE``), never a fabricated output.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceInputPacket, IntelligenceTaskType, ParsingStatus
from .errors import InferenceErrorCode
from .provider import ProviderInferenceResponse

LOCAL_PROVIDER_ID = "local.openai_compatible"
MANIFEST_RELATIVE = Path("models") / "local-llm.json"
BASE_URL_ENV, MODEL_ENV, PROVIDER_ENV = "IMP_LOCAL_LLM_BASE_URL", "IMP_LOCAL_LLM_MODEL", "IMP_SYNTHESIS_PROVIDER"
SERVER_ALIAS = "imp-local-synthesis"
DEFAULT_PORT = 18089
STARTUP_TIMEOUT_S = 180.0
IDLE_SHUTDOWN_S = 15 * 60
LOCAL_UNAVAILABLE = "LOCAL_MODEL_UNAVAILABLE"
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_CREATE_NO_WINDOW = 0x08000000


def is_loopback_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and (parts.hostname or "") in _LOOPBACK


Getter = Callable[[str, float], tuple[int, bytes]]
Poster = Callable[[str, bytes, float], tuple[int, bytes]]


def _http_get(url: str, timeout: float) -> tuple[int, bytes]:
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as response:
            return int(getattr(response, "status", 200)), response.read()
    except HTTPError as exc:
        return exc.code, b""


def _http_post(url: str, body: bytes, timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200)), response.read()
    except HTTPError as exc:
        return exc.code, b""


@dataclass(frozen=True, slots=True)
class LocalModelManifest:
    runtime_path: Path
    model_path: Path
    model_id: str
    revision: str
    runtime_version: str
    context: int = 8192
    gpu_layers: int = 99

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LocalModelManifest | None:
        try:
            return cls(Path(str(payload["runtime_path"])), Path(str(payload["model_path"])), str(payload["model_id"]),
                       str(payload.get("revision") or ""), str(payload.get("runtime_version") or ""),
                       int(payload.get("context") or 8192), int(payload.get("gpu_layers", 99)))
        except (KeyError, TypeError, ValueError):
            return None

    def missing(self) -> str | None:
        if not self.runtime_path.is_file():
            return "LOCAL_RUNTIME_NOT_FOUND"
        if not self.model_path.is_file():
            return "LOCAL_MODEL_FILE_NOT_FOUND"
        return None


class LocalLlamaServer:
    """On-demand ``llama-server`` bound to loopback; idle shutdown; one process per API process."""

    def __init__(self, manifest: LocalModelManifest, *, port: int = DEFAULT_PORT, log_path: Path | None = None,
                 getter: Getter = _http_get, spawn: Callable[..., Any] = subprocess.Popen,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 idle_shutdown_s: float = IDLE_SHUTDOWN_S, startup_timeout_s: float = STARTUP_TIMEOUT_S) -> None:
        self.manifest = manifest
        self.base_url = f"http://127.0.0.1:{port}"
        self._port = port
        self._log_path = log_path
        self._get = getter
        self._spawn = spawn
        self._clock = clock
        self._sleep = sleep
        self._idle_shutdown_s = idle_shutdown_s
        self._startup_timeout_s = startup_timeout_s
        self._lock = threading.Lock()
        self._process: Any = None
        self._last_used = 0.0
        self._watcher: threading.Thread | None = None
        self.starts = 0
        self.last_start_ms: float | None = None

    def _ours(self) -> bool | None:
        """True: our alias answers; False: something else holds the port; None: nothing answers."""

        try:
            status, body = self._get(f"{self.base_url}/v1/models", 2.0)
        except (URLError, OSError, ValueError):
            return None
        if status != 200:
            return False
        try:
            ids = {str(item.get("id")) for item in json.loads(body.decode("utf-8")).get("data", [])}
        except (ValueError, AttributeError):
            return False
        return SERVER_ALIAS in ids

    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def ensure_running(self) -> str | None:
        """None when the server answers as ours; otherwise a stable reason code."""

        with self._lock:
            self._last_used = self._clock()
            if self.running() and self._ours():
                return None
            missing = self.manifest.missing()
            if missing:
                return missing
            owner = self._ours()
            if owner is True:
                return None  # started by an earlier IMP process; reuse it
            if owner is False:
                return "LOCAL_MODEL_PORT_IN_USE"
            started = self._clock()
            args = [str(self.manifest.runtime_path), "-m", str(self.manifest.model_path), "--alias", SERVER_ALIAS,
                    "--host", "127.0.0.1", "--port", str(self._port), "-c", str(self.manifest.context),
                    "-ngl", str(self.manifest.gpu_layers), "-np", "1", "--jinja", "--reasoning", "off", "--no-webui"]
            log = open(self._log_path, "wb") if self._log_path else subprocess.DEVNULL  # noqa: SIM115
            try:
                self._process = self._spawn(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                            creationflags=_CREATE_NO_WINDOW if os.name == "nt" else 0)
            except OSError:
                return "LOCAL_RUNTIME_START_FAILED"
            finally:
                if log is not subprocess.DEVNULL:
                    log.close()
            self.starts += 1
            deadline = started + self._startup_timeout_s
            while self._clock() < deadline:
                if self._process.poll() is not None:
                    return "LOCAL_RUNTIME_EXITED"
                try:
                    status, _ = self._get(f"{self.base_url}/health", 2.0)
                except (URLError, OSError, ValueError):
                    status = 0
                if status == 200 and self._ours():
                    self.last_start_ms = round((self._clock() - started) * 1000)
                    self._start_watcher()
                    return None
                self._sleep(0.5)
            self._stop_locked()
            return "LOCAL_RUNTIME_START_TIMEOUT"

    def touch(self) -> None:
        self._last_used = self._clock()

    def _start_watcher(self) -> None:
        if self._watcher is not None and self._watcher.is_alive():
            return
        self._watcher = threading.Thread(target=self._watch, name="local-llm-idle", daemon=True)
        self._watcher.start()

    def _watch(self) -> None:
        while True:
            time.sleep(30)
            with self._lock:
                if not self.running():
                    return
                if self._clock() - self._last_used > self._idle_shutdown_s:
                    self._stop_locked()
                    return

    def _stop_locked(self) -> None:
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()


class LocalChatInferenceProvider:
    """OpenAI-compatible chat completions on a loopback server; temperature 0, JSON output."""

    provider_id = LOCAL_PROVIDER_ID
    runtime = "LOCAL_MODEL"

    def __init__(self, *, base_url: str, model_id: str, server: LocalLlamaServer | None = None,
                 request_model: str | None = None, poster: Poster = _http_post) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self._server = server
        self._request_model = request_model or model_id
        self._post = poster

    def _error(self, code: InferenceErrorCode, message: str, status: ParsingStatus, started: float) -> ProviderInferenceResponse:
        return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id, error_code=code,
                                         error_message=message, parsing_status=status,
                                         latency_ms=int((time.perf_counter() - started) * 1000))

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        started = time.perf_counter()
        if not is_loopback_url(self.base_url):
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, "LOCAL_ENDPOINT_NOT_LOOPBACK",
                               ParsingStatus.PROVIDER_ERROR, started)
        if self._server is not None:
            reason = self._server.ensure_running()
            if reason is not None:
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, reason, ParsingStatus.PROVIDER_ERROR, started)
        response_format: dict[str, Any] = {"type": "json_object"}
        if packet.task_type in (IntelligenceTaskType.NEWS_SCREENER_SYNTHESIS, IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, IntelligenceTaskType.SCREENER_ACTION_DECISION):
            from .schema_dispatch import schema_for_packet

            # Grammar-constrained structure (refs limited to the packet's story ids); content is still validated.
            response_format = {"type": "json_schema", "json_schema": {
                "name": "screener_synthesis", "strict": True,
                "schema": schema_for_packet(packet)}}
        body = {"model": self._request_model, "temperature": 0, "max_tokens": config.max_tokens,
                "response_format": response_format,
                # Qwen3-family reasoning models: answer directly; servers without the option ignore it.
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [{"role": "system", "content": "Return ONLY valid JSON matching the schema in the user prompt."},
                             {"role": "user", "content": rendered_prompt}]}
        try:
            status, raw = self._post(f"{self.base_url}/v1/chat/completions", json.dumps(body).encode("utf-8"),
                                     config.timeout_seconds)
        except TimeoutError:
            return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "LOCAL_MODEL_TIMEOUT", ParsingStatus.TIMEOUT, started)
        except (URLError, OSError) as exc:
            if "timed out" in str(exc).lower():
                return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "LOCAL_MODEL_TIMEOUT", ParsingStatus.TIMEOUT, started)
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, LOCAL_UNAVAILABLE, ParsingStatus.PROVIDER_ERROR, started)
        finally:
            if self._server is not None:
                self._server.touch()
        if status != 200:
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, f"LOCAL_MODEL_HTTP_{status}",
                               ParsingStatus.PROVIDER_ERROR, started)
        try:
            payload = json.loads(raw.decode("utf-8"))
            text = str(payload["choices"][0]["message"]["content"] or "")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "LOCAL_MODEL_RESPONSE_MALFORMED",
                               ParsingStatus.MALFORMED, started)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return ProviderInferenceResponse(raw_text=_THINK.sub("", text).strip(), provider_id=self.provider_id,
                                         model_id=self.model_id, tokens_input=usage.get("prompt_tokens"),
                                         tokens_output=usage.get("completion_tokens"),
                                         latency_ms=int((time.perf_counter() - started) * 1000),
                                         provider_response_id=str(payload.get("id") or ""))


@dataclass(frozen=True, slots=True)
class SynthesisSelection:
    provider: Any
    reason: str | None           # why no provider was selected
    runtime: str | None          # LOCAL_MODEL | PAID_API | None


def select_synthesis_provider(value: Callable[[str], str | None], *, cache_dir: Path,
                              anthropic_factory: Callable[[], Any] | None = None, engine: str | None = None,
                              model: str | None = None) -> SynthesisSelection:
    """Provider priority: the operator's ``engine`` (UI choice), else ``IMP_SYNTHESIS_PROVIDER``
    (local | anthropic | openai | gemini), else Anthropic when its key is configured, else a configured local model.
    A missing paid key never disables local synthesis in automatic mode. ``model`` must be in the engine's catalog
    (``synthesis_engines``). A Claude model outside the catalog selects no provider: it is never replaced by the
    default. For OpenAI and Gemini anything else still falls back to the engine's default."""

    from ...local_state.external_cache import read_manifest
    from .synthesis_engines import engine_models

    choice = (engine or value(PROVIDER_ENV) or "auto").strip().lower()
    has_key = bool((value("ANTHROPIC_API_KEY") or "").strip())
    if choice in ("auto", "anthropic") and has_key:
        if anthropic_factory is None:
            from .anthropic_synthesis import build_paid_provider

            offered = [item[0] for item in engine_models("anthropic", value)]
            if model and model not in offered:
                return SynthesisSelection(None, "SYNTHESIS_MODEL_NOT_IN_CATALOG", None)
            # Key from the same source that selected it (env or private provider file), behind the daily budget.
            # With no model chosen, the catalog's first entry: IMP_SYNTHESIS_ANTHROPIC_MODEL when set, else the default.
            return SynthesisSelection(build_paid_provider(value, cache_dir=cache_dir, model=model or offered[0]),
                                      None, "PAID_API")
        return SynthesisSelection(anthropic_factory(), None, "PAID_API")
    if choice == "anthropic":
        return SynthesisSelection(None, "ANTHROPIC_API_KEY_NOT_SET", None)
    if choice in ("openai", "gemini"):
        from .anthropic_synthesis import build_paid_provider
        from .hosted_synthesis import VENDORS, HostedChatSynthesisProvider
        from .synthesis_engines import ENGINE_SPECS

        credential_env = ENGINE_SPECS[choice].credential_env or ""
        credential = (value(credential_env) or "").strip()
        if not credential:
            return SynthesisSelection(None, f"{credential_env}_NOT_SET", None)
        offered = dict(engine_models(choice, value))
        chosen = model if model in offered else next(iter(offered))
        provider = HostedChatSynthesisProvider(vendor=VENDORS[choice], api_key=credential, model=chosen,
                                               reasoning_effort=offered[chosen])
        # One daily budget for every paid engine.
        return SynthesisSelection(build_paid_provider(value, cache_dir=cache_dir, provider=provider), None, "PAID_API")
    base_url, model = (value(BASE_URL_ENV) or "").strip(), (value(MODEL_ENV) or "").strip()
    if base_url:
        if not is_loopback_url(base_url):
            return SynthesisSelection(None, "LOCAL_ENDPOINT_NOT_LOOPBACK", None)
        if not model:
            return SynthesisSelection(None, f"{MODEL_ENV}_NOT_SET", None)
        return SynthesisSelection(LocalChatInferenceProvider(base_url=base_url, model_id=model), None, "LOCAL_MODEL")
    manifest = LocalModelManifest.from_dict(read_manifest(cache_dir / MANIFEST_RELATIVE) or {})
    if manifest is None:
        return SynthesisSelection(None, "NO_SYNTHESIS_PROVIDER_CONFIGURED", None)
    missing = manifest.missing()
    if missing:
        return SynthesisSelection(None, missing, None)
    server = _managed_server(manifest, cache_dir)
    return SynthesisSelection(LocalChatInferenceProvider(base_url=server.base_url, model_id=manifest.model_id,
                                                         server=server, request_model=SERVER_ALIAS), None, "LOCAL_MODEL")


_SERVERS: dict[tuple[str, str], LocalLlamaServer] = {}
_SERVERS_LOCK = threading.Lock()


def _managed_server(manifest: LocalModelManifest, cache_dir: Path) -> LocalLlamaServer:
    key = (str(manifest.runtime_path), str(manifest.model_path))
    with _SERVERS_LOCK:
        server = _SERVERS.get(key)
        if server is None:
            (cache_dir / "logs").mkdir(parents=True, exist_ok=True)
            server = LocalLlamaServer(manifest, log_path=cache_dir / "logs" / "llama-server.log")
            _SERVERS[key] = server
            atexit.register(server.stop)
        return server


__all__ = ["DEFAULT_PORT", "LOCAL_PROVIDER_ID", "LOCAL_UNAVAILABLE", "LocalChatInferenceProvider", "LocalLlamaServer",
           "LocalModelManifest", "MANIFEST_RELATIVE", "SERVER_ALIAS", "SynthesisSelection", "is_loopback_url",
           "select_synthesis_provider"]
