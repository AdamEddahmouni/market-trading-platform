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
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
_GPU_START_FAILURES = frozenset({"LOCAL_RUNTIME_EXITED", "LOCAL_RUNTIME_START_FAILED", "LOCAL_RUNTIME_START_TIMEOUT"})
GPU_FALLBACK_COOLDOWN_S = 30 * 60


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
    threads: int = 4
    execution_profile: str = 'cpu-8192/1'
    batch: int = 128
    ubatch: int = 64

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LocalModelManifest | None:
        try:
            return cls(Path(str(payload["runtime_path"])), Path(str(payload["model_path"])), str(payload["model_id"]),
                       str(payload.get("revision") or ""), str(payload.get("runtime_version") or ""),
                       int(payload.get("context") or 8192), int(payload.get("gpu_layers", 99)), int(payload.get("threads", 4)),
                       str(payload.get('execution_profile') or 'cpu-8192/1'), int(payload.get('batch',128)), int(payload.get('ubatch',64)))
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
        from .local_models import MODELS
        self.enforce_admission = manifest.model_id in MODELS
        self.last_readiness = None
        self.should_stop = lambda: False
        self._runtime_lease = None
        self.gpu_fallback: dict[str, Any] | None = None  # last GPU start failure; receipts carry it
        self._preferred: tuple[LocalModelManifest, float] | None = None

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
        """None when the server answers as ours; otherwise a stable reason code.

        A GPU profile that cannot start (exit, start failure or start timeout) is recorded in
        ``gpu_fallback`` and retried once on its CPU profile; the GPU is tried again after the cooldown."""

        with self._lock:
            self._last_used = self._clock()
            if self.should_stop():return 'STOPPED_BY_OPERATOR'
            self._restore_preferred_locked()
            reason = self._ensure_locked()
            if reason in _GPU_START_FAILURES and self._fallback_locked(reason):
                reason = self._ensure_locked()
            return reason

    def _fallback_locked(self, reason: str) -> bool:
        from .local_runtime import CPU_FALLBACK, apply_profile, profile_device
        profile = self.manifest.execution_profile
        if not self.enforce_admission or profile_device(profile) == 'none' or profile not in CPU_FALLBACK:
            return False
        self.gpu_fallback = {'from_profile': profile, 'to_profile': CPU_FALLBACK[profile], 'reason': reason,
                             'at': datetime.now(UTC).isoformat(), 'cooldown_s': GPU_FALLBACK_COOLDOWN_S}
        self._preferred = (self.manifest, self._clock() + GPU_FALLBACK_COOLDOWN_S)
        self.manifest = apply_profile(self.manifest, CPU_FALLBACK[profile])
        return True

    def _restore_preferred_locked(self) -> None:
        if self._preferred is not None and not self.running() and self._clock() >= self._preferred[1]:
            self.manifest, self._preferred = self._preferred[0], None

    def _ensure_locked(self) -> str | None:
        if self.enforce_admission:
            from .local_runtime import readiness
            self.last_readiness=readiness(self.manifest,process=self._process)
            if self.last_readiness['rejection_reason']:return self.last_readiness['rejection_reason']
        if self.running() and self._ours():
            return None
        if self._process is not None:
            self._stop_locked()  # never overwrite an unreaped owned instance
        missing = self.manifest.missing()
        if missing:
            return missing
        owner = self._ours()
        if owner is True:
            if self.enforce_admission:return 'LOCAL_QUALIFICATION_REQUIRES_OWNED_PINNED_RUNTIME'
            return None  # started by an earlier IMP process; reuse it
        if owner is False:
            return "LOCAL_MODEL_PORT_IN_USE"
        started = self._clock()
        args = [str(self.manifest.runtime_path), "-m", str(self.manifest.model_path), "--alias", SERVER_ALIAS,
                "--host", "127.0.0.1", "--port", str(self._port), "-c", str(self.manifest.context),
                "-ngl", str(self.manifest.gpu_layers), "-np", "1", "--jinja", "--reasoning", "off", "--no-webui", "-t", str(self.manifest.threads)]
        if self.enforce_admission:
            from .local_runtime import profile_device
            device = profile_device(self.manifest.execution_profile)
            # A CPU profile keeps every allocation in host RAM; a GPU profile names its one device explicitly.
            args += ['--device',device] + (['--no-kv-offload','--no-op-offload'] if device == 'none' else [])
            args += ['--fit','off',
                     '--batch-size',str(self.manifest.batch),'--ubatch-size',str(self.manifest.ubatch),
                     '--cache-type-k','f16','--cache-type-v','f16','--load-mode','mmap','--threads-batch',str(self.manifest.threads),
                     # b11269 defaults to 8 GiB of extra host prompt snapshots. Saving a
                     # warm slot can exceed the process ceiling before cache eviction.
                     '--cache-ram','0']
            lease=self.manifest.runtime_path.parent/'imp-local-runtime.lock'
            try:
                with lease.open('x',encoding='utf-8') as stream:
                    stream.write(json.dumps({'owner_pid':os.getpid(),'profile':self.manifest.execution_profile}))
            except FileExistsError:
                return 'LOCAL_RUNTIME_ALREADY_OWNED_OR_INTERRUPTED'
            except OSError:
                return 'LOCAL_RUNTIME_OWNERSHIP_UNAVAILABLE'
            self._runtime_lease=lease
        log = open(self._log_path, "wb") if self._log_path else subprocess.DEVNULL  # noqa: SIM115
        try:
            self._process = self._spawn(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        creationflags=_CREATE_NO_WINDOW if os.name == "nt" else 0,
                                        env={k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_ARG_','GGML_'))})
        except OSError:
            self._stop_locked()
            return "LOCAL_RUNTIME_START_FAILED"
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        self.starts += 1
        deadline = started + self._startup_timeout_s
        while self._clock() < deadline:
            if self.should_stop():
                self._stop_locked()
                return 'STOPPED_BY_OPERATOR'
            if self._process.poll() is not None:
                self._stop_locked()
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
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        self._process = None  # ownership ends only after confirmed exit
        if self._runtime_lease is not None:
            self._runtime_lease.unlink(missing_ok=True)
            self._runtime_lease=None

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()


class LocalChatInferenceProvider:
    """OpenAI-compatible chat completions on a loopback server; temperature 0, JSON output."""

    provider_id = LOCAL_PROVIDER_ID
    runtime = "LOCAL_MODEL"
    candidate_schema_contract = 'canonical-parser-bounds/1'

    def __init__(self, *, base_url: str, model_id: str, server: LocalLlamaServer | None = None,
                 request_model: str | None = None, poster: Poster = _http_post) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self._server = server
        self._request_model = request_model or model_id
        self._post = poster

    def _error(self, code: InferenceErrorCode, message: str, status: ParsingStatus, started: float, *, dispatched: bool = False) -> ProviderInferenceResponse:
        return ProviderInferenceResponse(raw_text="", provider_id=self.provider_id, model_id=self.model_id, error_code=code,
                                         error_message=message, parsing_status=status, inference_dispatched=dispatched,
                                         latency_ms=int((time.perf_counter() - started) * 1000))

    def infer(self, packet: IntelligenceInputPacket, *, rendered_prompt: str,
              config: IntelligenceInferenceConfig) -> ProviderInferenceResponse:
        return self._run(packet, rendered_prompt=rendered_prompt, config=config)

    def preflight(self, packet, *, rendered_prompt, config):
        """Count the full chat template under the same local admission controls; never generate."""
        response = self._run(packet, rendered_prompt=rendered_prompt, config=config, preflight_only=True)
        window = getattr(getattr(self._server, 'manifest', None), 'context', None)
        return {'accepted': response.error_code is None, 'input_tokens': response.tokens_input,
                'context_window': window, 'context_fit': False if response.error_message == 'LOCAL_CONTEXT_EXCEEDED'
                else True if response.error_code is None else None, 'reason': response.error_message or None}

    def _run(self, packet, *, rendered_prompt, config, preflight_only=False):
        started, cpu = time.perf_counter(), time.thread_time()
        diagnostics = {'started_at': datetime.now(UTC).isoformat(), 'http': [],
                       'generation_timeout_seconds': config.timeout_seconds, 'preflight_only': preflight_only}
        if packet.task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION:
            diagnostics['candidate_schema_contract'] = self.candidate_schema_contract
        response = self._run_owned(packet, rendered_prompt=rendered_prompt, config=config,
                                   preflight_only=preflight_only, diagnostics=diagnostics)
        diagnostics.update(ended_at=datetime.now(UTC).isoformat(), elapsed_ms=round((time.perf_counter()-started)*1000, 3),
                           thread_cpu_ms=round((time.thread_time()-cpu)*1000, 3),
                           cancelled=bool(getattr(packet, 'should_stop', lambda: False)()))
        return replace(response, diagnostics=diagnostics)

    def _run_owned(self, packet, *, rendered_prompt, config, preflight_only=False, diagnostics=None):
        from .local_resources import ADMISSION, SLOT, ResourceMonitor
        started = time.perf_counter()
        stop = getattr(packet, 'should_stop', lambda: False)
        if stop():
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, 'STOPPED_BY_OPERATOR', ParsingStatus.PROVIDER_ERROR, started)
        if not ADMISSION.acquire(blocking=False):
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, 'LOCAL_INFERENCE_QUEUE_FULL', ParsingStatus.PROVIDER_ERROR, started)
        deadline = time.monotonic() + config.timeout_seconds
        while not SLOT.acquire(timeout=min(.25, max(0, deadline-time.monotonic()))):
            if stop() or time.monotonic() >= deadline:
                ADMISSION.release()
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE,
                    'STOPPED_BY_OPERATOR' if stop() else 'LOCAL_INFERENCE_BUSY', ParsingStatus.PROVIDER_ERROR, started)
        diagnostics = diagnostics if diagnostics is not None else {}
        diagnostics['slot_wait_ms'] = round((time.perf_counter()-started)*1000, 3)
        qualification = packet.task_type == IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION
        managed = isinstance(self._server,LocalLlamaServer) and self._server.enforce_admission
        monitor = ResourceMonitor(self._server, stop, time.monotonic()+STARTUP_TIMEOUT_S+config.timeout_seconds) if (qualification or managed) and self._server is not None else None
        self.last_resource_sample = {}
        self.last_context_sample = None
        response = None
        try:
            if isinstance(self._server, LocalLlamaServer):
                # SLOT is held: no other inference can still be using an owned prior model.
                _stop_other_managed_servers(self._server)
            if qualification and getattr(packet, 'should_stop', lambda: False)():
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, 'STOPPED_BY_OPERATOR', ParsingStatus.PROVIDER_ERROR, started)
            if (qualification or managed) and isinstance(self._server, LocalLlamaServer):
                self._server.enforce_admission=True
                self._server.should_stop=stop
                from .local_runtime import readiness
                self._server.last_readiness=readiness(self._server.manifest,process=self._server._process)
                if self._server.last_readiness['rejection_reason']:
                    return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE,self._server.last_readiness['rejection_reason'],ParsingStatus.PROVIDER_ERROR,started)
            if monitor and monitor.check():
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, monitor.failure, ParsingStatus.PROVIDER_ERROR, started)
            if preflight_only:
                response=self._infer_locked(packet, rendered_prompt=rendered_prompt, config=config, monitor=monitor, preflight_only=True, diagnostics=diagnostics)
            else:
                response=self._infer_locked(packet, rendered_prompt=rendered_prompt, config=config, monitor=monitor, diagnostics=diagnostics)
            if monitor:
                monitor.close()
                if monitor.failure:
                    response=self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE,monitor.failure,ParsingStatus.PROVIDER_ERROR,started,
                                         dispatched=bool(response.inference_dispatched))
            return response
        finally:
            try:
                if monitor:
                    monitor.close()
                    self.last_resource_sample = {"peak_process_bytes": monitor.peak_bytes or None,
                        'peak_commit_bytes':monitor.peak_commit_bytes or None,"failure": monitor.failure,
                        'samples':monitor.samples,'final_sample':monitor.last_sample,'readiness':getattr(self._server,'last_readiness',None),
                        'startup_ms':getattr(self._server,'last_start_ms',None),
                        'execution_profile':getattr(getattr(self._server,'manifest',None),'execution_profile',None),
                        'gpu_fallback':getattr(self._server,'gpu_fallback',None)}
                    diagnostics['resources'] = self.last_resource_sample
                    # A count refusal dispatched no generation and leaves the owned runtime healthy.
                    # All operational/resource failures still stop and reap it.
                    oversize_count = (response is not None and response.error_message == 'LOCAL_CONTEXT_EXCEEDED'
                                      and response.inference_dispatched is False)
                    # A reply that used its whole allowance completed normally on a healthy runtime.
                    output_limit = response is not None and response.error_message == 'LOCAL_OUTPUT_LIMIT_REACHED'
                    if response is None or (response.error_code and not (oversize_count or output_limit)) or monitor.failure or stop():
                        self._server.stop()
            finally:
                if isinstance(self._server,LocalLlamaServer):self._server.should_stop=lambda:False
                SLOT.release()
                ADMISSION.release()

    def _infer_locked(self, packet, *, rendered_prompt, config, monitor=None, preflight_only=False, diagnostics=None):
        started = time.perf_counter()
        diagnostics = diagnostics if diagnostics is not None else {}
        def post(stage, url, body):
            begin = time.perf_counter()
            record = {'stage': stage, 'started_at': datetime.now(UTC).isoformat()}
            try:
                return self._post(url, body, config.timeout_seconds)
            finally:
                record.update(ended_at=datetime.now(UTC).isoformat(), elapsed_ms=round((time.perf_counter()-begin)*1000, 3))
                diagnostics.setdefault('http', []).append(record)
        if not is_loopback_url(self.base_url):
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, "LOCAL_ENDPOINT_NOT_LOOPBACK",
                               ParsingStatus.PROVIDER_ERROR, started)
        if packet.task_type == IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION:
            if self._server is None or (not self._server.running() and self._server._ours() is True):
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, 'LOCAL_QUALIFICATION_REQUIRES_OWNED_PINNED_RUNTIME', ParsingStatus.PROVIDER_ERROR, started)
        if monitor: monitor.start()
        if self._server is not None:
            startup = time.perf_counter()
            reason = self._server.ensure_running()
            diagnostics['ensure_runtime_ms'] = round((time.perf_counter()-startup)*1000, 3)
            if reason is not None:
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, reason, ParsingStatus.PROVIDER_ERROR, started)
        if monitor:
            if monitor.failure:
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, monitor.failure, ParsingStatus.PROVIDER_ERROR, started)
        response_format: dict[str, Any] = {"type": "json_object"}
        if packet.task_type in (IntelligenceTaskType.NEWS_SCREENER_SYNTHESIS, IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, IntelligenceTaskType.SCREENER_ACTION_DECISION, IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION):
            from .schema_dispatch import schema_for_packet

            # Grammar-constrained structure (refs limited to the packet's story ids); content is still validated.
            schema = schema_for_packet(packet)
            if packet.task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION:
                schema = _bounded_candidate_schema(schema, len(getattr(packet, 'candidates', ())))
            response_format = {"type": "json_schema", "json_schema": {
                "name": "screener_synthesis", "strict": True,
                "schema": schema}}
        body = {"model": self._request_model, "temperature": 0, "max_tokens": config.max_tokens,
                "response_format": response_format,
                # Qwen3-family reasoning models: answer directly; servers without the option ignore it.
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [{"role": "system", "content": "Return ONLY valid JSON matching the schema in the user prompt."},
                             {"role": "user", "content": rendered_prompt}]}
        if preflight_only or packet.task_type in (IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,
                IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, IntelligenceTaskType.SCREENER_ACTION_DECISION):
            try:
                window = getattr(getattr(self._server, 'manifest', None), 'context', None)
                if type(window) is not int or window <= 0:
                    raise ValueError('LOCAL_CONTEXT_UNAVAILABLE')
                status, templated = post('CHAT_TEMPLATE', f"{self.base_url}/apply-template",
                    json.dumps({"messages":body["messages"],"chat_template_kwargs":body["chat_template_kwargs"]}).encode("utf-8"))
                prompt=json.loads(templated)["prompt"] if status==200 else None
                if not isinstance(prompt,str) or not prompt: raise ValueError("LOCAL_TEMPLATE_UNAVAILABLE")
                if monitor and monitor.check():
                    return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, monitor.failure, ParsingStatus.PROVIDER_ERROR, started)
                status, tokenized=post('EXACT_TOKEN_COUNT', f"{self.base_url}/tokenize",json.dumps({"content":prompt,"add_special":True}).encode("utf-8"))
                tokens=json.loads(tokenized)["tokens"] if status==200 else None
                if not isinstance(tokens,list) or not tokens or any(type(token) is not int or token < 0 for token in tokens):
                    raise ValueError("LOCAL_TOKENIZER_UNAVAILABLE")
                # The output allowance is what the window leaves, never more than the task's configured maximum,
                # and the request is refused intact when that is under the measured floor. A reply that reaches
                # the allowance is refused as LOCAL_OUTPUT_LIMIT_REACHED, never parsed or truncated into acceptance.
                floor=output_floor(packet,config)
                allowance=min(int(config.max_tokens),window-len(tokens))
                self.last_context_sample={"input_tokens":len(tokens),"output_allowance":allowance,"output_floor":floor,
                                          "configured_max_tokens":int(config.max_tokens),"context_window":window}
                diagnostics['context']=dict(self.last_context_sample)
                if monitor and monitor.check():
                    return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, monitor.failure, ParsingStatus.PROVIDER_ERROR, started)
                if allowance<floor:
                    return replace(self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE,"LOCAL_CONTEXT_EXCEEDED",ParsingStatus.PROVIDER_ERROR,started), tokens_input=len(tokens))
                body["max_tokens"]=allowance
            except (ValueError,KeyError,TypeError,OSError,URLError):
                return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE,"LOCAL_CONTEXT_PREFLIGHT_FAILED",ParsingStatus.PROVIDER_ERROR,started)
        if getattr(packet, 'should_stop', lambda: False)():
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, 'STOPPED_BY_OPERATOR', ParsingStatus.PROVIDER_ERROR, started)
        if preflight_only:
            return ProviderInferenceResponse(raw_text='', provider_id=self.provider_id, model_id=self.model_id,
                                             tokens_input=len(tokens), inference_dispatched=False)
        try:
            status, raw = post('GENERATION', f"{self.base_url}/v1/chat/completions", json.dumps(body).encode("utf-8"))
        except TimeoutError:
            return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "LOCAL_MODEL_TIMEOUT", ParsingStatus.TIMEOUT, started, dispatched=True)
        except (URLError, OSError) as exc:
            if "timed out" in str(exc).lower():
                return self._error(InferenceErrorCode.PROVIDER_TIMEOUT, "LOCAL_MODEL_TIMEOUT", ParsingStatus.TIMEOUT, started, dispatched=True)
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, LOCAL_UNAVAILABLE, ParsingStatus.PROVIDER_ERROR, started, dispatched=True)
        finally:
            if self._server is not None:
                self._server.touch()
        if monitor and monitor.failure:
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, monitor.failure, ParsingStatus.PROVIDER_ERROR, started, dispatched=True)
        if status != 200:
            return self._error(InferenceErrorCode.PROVIDER_UNAVAILABLE, f"LOCAL_MODEL_HTTP_{status}",
                               ParsingStatus.PROVIDER_ERROR, started, dispatched=True)
        try:
            payload = json.loads(raw.decode("utf-8"))
            text = str(payload["choices"][0]["message"]["content"] or "")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, "LOCAL_MODEL_RESPONSE_MALFORMED",
                               ParsingStatus.MALFORMED, started, dispatched=True)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        diagnostics['finish_reason'] = payload['choices'][0].get('finish_reason')
        diagnostics['runtime_timings'] = {key: value for key, value in (payload.get('timings') or {}).items()
            if key in ('prompt_n', 'prompt_ms', 'prompt_per_second', 'predicted_n', 'predicted_ms', 'predicted_per_second', 'cache_n')
            and type(value) in (int, float)} if isinstance(payload.get('timings'), dict) else {}
        if diagnostics['finish_reason'] == 'length':
            return replace(self._error(InferenceErrorCode.PROVIDER_RESPONSE_MALFORMED, 'LOCAL_OUTPUT_LIMIT_REACHED',
                                       ParsingStatus.MALFORMED, started, dispatched=True),
                           tokens_input=usage.get("prompt_tokens"), tokens_output=usage.get("completion_tokens"))
        return ProviderInferenceResponse(raw_text=text if packet.task_type == IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION else _THINK.sub("", text).strip(), provider_id=self.provider_id,
                                         model_id=self.model_id, tokens_input=usage.get("prompt_tokens"),
                                         tokens_output=usage.get("completion_tokens"),
                                         latency_ms=int((time.perf_counter() - started) * 1000),
                                         provider_response_id=str(payload.get("id") or ""),inference_dispatched=True)


LOCAL_OUTPUT_FLOOR_BASE = 512
LOCAL_OUTPUT_FLOOR_PER_CANDIDATE = 256


def output_floor(packet, config) -> int:
    """Smallest output allowance a local request is sent with, never above the task's configured maximum.

    Measured local candidate replies were 42-173 tokens for one candidate (October 14-16 receipts): the floor
    is 768 tokens for one candidate and grows 256 per further candidate. It is an admission threshold; the
    allowance actually sent is everything the window leaves, up to the configured maximum. Tasks configured
    below the floor keep their configured maximum."""
    count = len(getattr(packet, 'candidates', ()) or ()) if packet.task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION else 1
    return min(int(config.max_tokens), LOCAL_OUTPUT_FLOOR_BASE + LOCAL_OUTPUT_FLOOR_PER_CANDIDATE * max(1, count))


def _bounded_candidate_schema(shared_schema, candidate_count):
    """Give llama.cpp only bounds already enforced by the canonical candidate parser.

    Keep the shared schema untouched: hosted strict-schema dialects have different support.
    An unbounded local string can repeat past the parser's 1,200-character rejection bound
    until the HTTP deadline, even when its short prefix already expressed an abstention.
    """
    from .candidate_reduction import MAX_SELECTED
    schema = deepcopy(shared_schema)
    def bound(node):
        if isinstance(node, dict):
            if node.get('type') == 'string':
                node['maxLength'] = 1200
            elif node.get('type') == 'array':
                node['maxItems'] = 12
            for value in node.values():
                bound(value)
        elif isinstance(node, list):
            for value in node:
                bound(value)
    bound(schema)
    candidates = schema.get('properties', {}).get('candidates')
    if isinstance(candidates, dict):
        candidates['maxItems'] = min(MAX_SELECTED, candidate_count)
    return schema


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
    try:
        server = _managed_server(manifest, cache_dir)
    except ValueError as exc:
        return SynthesisSelection(None,str(exc),None)
    return SynthesisSelection(LocalChatInferenceProvider(base_url=server.base_url, model_id=manifest.model_id,
                                                         server=server, request_model=SERVER_ALIAS), None, "LOCAL_MODEL")


_SERVERS: dict[tuple[LocalModelManifest, str], LocalLlamaServer] = {}
_SERVERS_LOCK = threading.Lock()


def _stop_other_managed_servers(selected):
    with _SERVERS_LOCK:
        others = [server for server in _SERVERS.values() if server is not selected and server._port == selected._port]
    for server in others:
        # These are owned objects from this API process, never foreign port/PID discovery.
        server.stop()


def _managed_server(manifest: LocalModelManifest, cache_dir: Path) -> LocalLlamaServer:
    from .local_models import MODELS
    from .local_runtime import apply_profile
    if manifest.model_id in MODELS:
        manifest=apply_profile(manifest,manifest.execution_profile)
    key = (manifest, str(cache_dir))
    with _SERVERS_LOCK:
        server = _SERVERS.get(key)
        if server is None:
            (cache_dir / "logs").mkdir(parents=True, exist_ok=True)
            server = LocalLlamaServer(manifest, log_path=cache_dir / "logs" / "llama-server.log")
            _SERVERS[key] = server
            atexit.register(server.stop)
        return server


def registered_local_provider(cache_dir: Path, model_id: str | None = None):
    from .local_models import DEFAULT_MODEL_ID, model_manifest
    chosen = model_id or DEFAULT_MODEL_ID
    manifest = model_manifest(cache_dir, chosen)
    if manifest is None or manifest.model_id != chosen or manifest.missing():
        return None
    server = _managed_server(manifest, cache_dir)
    return LocalChatInferenceProvider(base_url=server.base_url, model_id=chosen,
        server=server, request_model=SERVER_ALIAS)


__all__ = ["DEFAULT_PORT", "LOCAL_PROVIDER_ID", "LOCAL_UNAVAILABLE", "LocalChatInferenceProvider", "LocalLlamaServer",
           "LocalModelManifest", "MANIFEST_RELATIVE", "SERVER_ALIAS", "SynthesisSelection", "is_loopback_url",
           "select_synthesis_provider", "registered_local_provider"]
