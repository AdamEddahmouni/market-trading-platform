"""One experimental readiness contract. Candidate profiles carry no quality approval."""
from __future__ import annotations

import hashlib
import os
import threading
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .local_resources import GIB, MAX_PROCESS_BYTES, MIN_AVAILABLE_BYTES, memory_sample

MODEL_ID = 'Qwen/Qwen3-4B-GGUF:Q4_K_M'
MODEL_REVISION = 'bc640142c66e1fdd12af0bd68f40445458f3869b'
MODEL_HASH = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
MODEL_BYTES = 2497280256
RUNTIME_VERSION = 'b11269'
ARCHIVE_NAME = 'llama-b11269-bin-win-vulkan-x64.zip'
ARCHIVE_HASH = '34a27c239727047adc5aed80b656b13373ff136b27d28bd898a14b7b7283695a'
PROFILES = {
    'cpu-8192/1': (8192, 128, 64, 4, 0),
    'cpu-4096/1': (4096, 128, 64, 4, 0),
    # Dedicated-VRAM discrete GPU through the Vulkan device of the same pinned archive. Same model, runtime,
    # context, f16 KV, single slot and memory floors; batch/ubatch measured with the pinned llama-bench
    # (destination-tests/20261016-paper-ai-throughput/baseline). Never promoted on shared-memory claims.
    'vulkan-8192/1': (8192, 512, 512, 4, 99),
    # A mixture-of-experts model larger than the card: every layer on the GPU except the expert weights of the
    # first PROFILE_CPU_MOE layers, which stay in system RAM (llama.cpp --n-cpu-moe). More threads, because those
    # experts run on the CPU.
    'vulkan-8192/1-moe': (8192, 512, 512, 8, 99),
}
# llama.cpp device per profile; profiles not listed run on the CPU only.
PROFILE_DEVICES = {'vulkan-8192/1': 'Vulkan0', 'vulkan-8192/1-moe': 'Vulkan0'}
# Layers whose expert weights stay on the CPU. Qwen3-30B-A3B: 48 layers of 0.34 GiB experts each; 38 on the CPU
# leaves 10 layers' experts (3.4 GiB) plus the 0.93 GiB of shared weights and the KV cache on the card.
PROFILE_CPU_MOE = {'vulkan-8192/1-moe': 38}
# A GPU profile that cannot start falls back, visibly, to the CPU profile with the same context. The MoE profile
# has none: the whole model in system RAM is far over the CPU process limit, so it stays refused instead.
CPU_FALLBACK = {'vulkan-8192/1': 'cpu-8192/1'}
# What the 8 GiB RTX 2070 Super may hold for one model: about 1 GiB stays with the Windows desktop and driver.
GPU_VRAM_BUDGET_BYTES = 7 * GIB
# Vulkan compute buffers at batch/ubatch 512 and the device context, on top of weights and KV.
GPU_OVERHEAD_BYTES = 1 * GIB
# Host allocations of a GPU profile besides the weights kept on the CPU: runtime, graph and staging buffers.
HOST_ALLOWANCE_BYTES = 2 * GIB


def profile_device(name):
    return PROFILE_DEVICES.get(name, 'none')


def memory_plan(pin, manifest):
    """Where the weights and KV cache go for this profile, in bytes. Pure arithmetic; starts nothing.

    CPU profile: everything in host RAM (full weights + f16 KV + 2 GiB), under the 6 GiB process limit.
    GPU profile: the offloaded weights, the KV cache and 1 GiB of buffers on the card, within its budget; the
    host keeps the CPU-side weights + 2 GiB. A memory-mapped file's pages may stay in the process working set after
    upload, so the GPU process limit also allows the offloaded weights; they are file-backed and reclaimable."""
    kv = pin.layers * pin.kv_heads * pin.head_dim * 4 * manifest.context
    if profile_device(manifest.execution_profile) == 'none':
        host = pin.weight_bytes + kv + HOST_ALLOWANCE_BYTES
        return {'device': 'none', 'gpu_bytes': 0, 'host_bytes': host, 'kv_bytes': kv,
                'process_limit_bytes': MAX_PROCESS_BYTES, 'cpu_weight_bytes': pin.weight_bytes}
    cpu_layers = min(pin.layers, PROFILE_CPU_MOE.get(manifest.execution_profile, 0)) if pin.expert_bytes else 0
    cpu_weights = pin.expert_bytes * cpu_layers // pin.layers
    gpu = pin.weight_bytes - cpu_weights + kv + GPU_OVERHEAD_BYTES
    host = cpu_weights + HOST_ALLOWANCE_BYTES
    return {'device': profile_device(manifest.execution_profile), 'gpu_bytes': gpu, 'host_bytes': host,
            'kv_bytes': kv, 'cpu_moe_layers': cpu_layers, 'cpu_weight_bytes': cpu_weights,
            'process_limit_bytes': max(MAX_PROCESS_BYTES, host + pin.weight_bytes - cpu_weights)}


def process_limit(manifest):
    """The working-set and commit ceiling the resource monitor enforces for this manifest's profile."""
    pin = model_pin(manifest)
    return memory_plan(pin, manifest)['process_limit_bytes'] if pin else MAX_PROCESS_BYTES
_VERIFIED = {}
_VERIFY_LOCK = threading.Lock()


def model_pin(manifest):
    from .local_models import MODELS
    pin = MODELS.get(manifest.model_id) if manifest else None
    if not pin or manifest.revision != pin.revision or manifest.runtime_version != RUNTIME_VERSION:
        return None
    # Preserve the existing 4B constants and verification contract.
    return replace(pin, weight_bytes=MODEL_BYTES, sha256=MODEL_HASH) if pin.model_id == MODEL_ID else pin


def apply_profile(manifest, name):
    if name not in PROFILES:
        raise ValueError('LOCAL_RUNTIME_PROFILE_INVALID')
    context, batch, ubatch, threads, layers = PROFILES[name]
    return replace(manifest, execution_profile=name, context=context, batch=batch,
                   ubatch=ubatch, threads=threads, gpu_layers=layers)


def profile_reason(manifest):
    if manifest.execution_profile not in PROFILES:
        return 'LOCAL_RUNTIME_PROFILE_INVALID'
    actual = (manifest.context, manifest.batch, manifest.ubatch, manifest.threads, manifest.gpu_layers)
    pin = model_pin(manifest)
    if pin and manifest.context > pin.context_limit:
        return 'LOCAL_RUNTIME_PROFILE_CONTEXT_LIMIT'
    return None if actual == PROFILES[manifest.execution_profile] else 'LOCAL_RUNTIME_PROFILE_MISMATCH'


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_artifacts(manifest):
    """Trust anchored in pinned archive, including adjacent executables and DLLs.

    Success is cached only for unchanged file identities. Failures are not cached.
    Never executes or downloads an artifact to verify it.
    """
    pin = model_pin(manifest)
    if not pin:
        return 'PINNED_LOCAL_MODEL_REQUIRED'
    if os.name != 'nt':
        return 'LOCAL_PINNED_RUNTIME_PLATFORM_UNSUPPORTED'
    if manifest.runtime_path.name != 'llama-server.exe':
        return 'LOCAL_RUNTIME_FILE_SET_MISMATCH'
    from ...local_state.external_cache import imp_cache_dir
    archive = imp_cache_dir() / 'downloads' / ARCHIVE_NAME
    try:
        files = sorted(p for p in manifest.runtime_path.parent.iterdir()
                       if p.suffix.lower() in ('.dll', '.exe'))
        paths = [manifest.model_path, archive, *files]
        file_key = tuple((str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns) for p in paths)
        key = (pin.model_id, pin.revision, pin.sha256, pin.weight_bytes, ARCHIVE_HASH, file_key)
        with _VERIFY_LOCK:
            if key in _VERIFIED:
                return None
            if manifest.model_path.stat().st_size != pin.weight_bytes or _digest(manifest.model_path) != pin.sha256:
                return 'MODEL_CHECKSUM_FAILED'
            if _digest(archive) != ARCHIVE_HASH:
                return 'LOCAL_RUNTIME_ARCHIVE_CHECKSUM_FAILED'
            with zipfile.ZipFile(archive) as bundle:
                entries = {Path(n).name: n for n in bundle.namelist() if Path(n).suffix.lower() in ('.dll', '.exe')}
                if manifest.runtime_path.name != 'llama-server.exe' or set(entries) != {p.name for p in files}:
                    return 'LOCAL_RUNTIME_FILE_SET_MISMATCH'
                for path in files:
                    with bundle.open(entries[path.name]) as stream:
                        expected = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if _digest(path) != expected:
                        return 'LOCAL_RUNTIME_CHECKSUM_FAILED'
            current=tuple((str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in paths)
            if current!=file_key:return 'LOCAL_ARTIFACT_CHANGED_DURING_VERIFICATION'
            if len(_VERIFIED) >= 16:
                _VERIFIED.clear()
            _VERIFIED[key] = True
    except (OSError, ValueError, zipfile.BadZipFile, KeyError):
        return 'LOCAL_ARTIFACT_VERIFICATION_UNAVAILABLE'
    return None


def readiness(manifest, *, sample=None, process=None):
    sample = memory_sample(process) if sample is None else sample
    artifact_reason = verify_artifacts(manifest)
    reason = artifact_reason
    if not reason:
        reason = profile_reason(manifest)
    pin = model_pin(manifest)
    # Model-specific f16 K+V dimensions from the official architecture.
    # CPU profile: count the FULL weight artifact even with mmap, plus conservative uncalibrated
    # 2 GiB runtime/repacking/graph/buffer allowance; b11269 repacks the pinned
    # 4B weights into 1683.28 MiB, already exceeding the old 1.5 GiB allowance.
    # GPU profile: weights and KV the card holds are checked against its own budget, and only what stays on the
    # CPU is counted in RAM (``memory_plan``). Extra host prompt snapshots are disabled; shared GPU memory adds
    # no capacity.
    plan = memory_plan(pin, manifest) if pin and not profile_reason(manifest) else None
    kv = plan['kv_bytes'] if plan else None
    peak = plan['host_bytes'] if plan else None
    resident = min(sample.get('process_bytes') or 0, sample.get('process_commit_bytes') or 0)
    additional = max(0, peak-resident) if peak is not None else None
    required = MIN_AVAILABLE_BYTES + additional if additional is not None else None
    available = sample.get('available_bytes')
    commit = sample.get('commit_available_bytes')
    if not reason:
        if available is None or commit is None:
            reason = 'LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE'
        elif available < MIN_AVAILABLE_BYTES:
            reason = 'LOCAL_RESOURCE_INSUFFICIENT_MEMORY'
        elif plan['device'] == 'none' and peak > MAX_PROCESS_BYTES:
            reason = 'LOCAL_RESOURCE_PREDICTED_PROCESS_LIMIT'
        elif plan['gpu_bytes'] > GPU_VRAM_BUDGET_BYTES:
            reason = 'LOCAL_RESOURCE_PREDICTED_VRAM_LIMIT'
        elif commit < required:
            reason = 'LOCAL_RESOURCE_COMMIT_HEADROOM'
        elif available < required:
            reason = 'LOCAL_RESOURCE_PREDICTED_UNSAFE'
    status = ('LOCAL_RUNTIME_RESOURCE_BLOCKED' if reason and reason.startswith('LOCAL_RESOURCE_') else
              'LOCAL_RUNTIME_UNAVAILABLE' if reason else 'LOCAL_RUNTIME_READY')
    return {
        'schema_version':'local-runtime-readiness/1.0.0',
        'model_id':manifest.model_id if manifest else None,
        'model_revision':manifest.revision if manifest else None, 'revision':manifest.revision if manifest else None,
        'model_hash':pin.sha256 if pin else None,
        'quantization':pin.quantization if pin else None,
        'model_weight_bytes':pin.weight_bytes if pin else None,
        'artifact_verified':not bool(artifact_reason),
        'runtime_version':manifest.runtime_version if manifest else None,
        'execution_profile':manifest.execution_profile if manifest else None,
        'profile_validation':'CANDIDATE_NOT_EMPIRICALLY_VALIDATED',
        'context_configuration':{'context':manifest.context if manifest else None,
                                 'batch':manifest.batch if manifest else None, 'ubatch':manifest.ubatch if manifest else None,
                                 'kv_type':'f16', 'parallel_slots':1, 'mmap':True, 'host_prompt_cache_bytes':0,
                                 'device':profile_device(manifest.execution_profile) if manifest else None},
        'context_window':manifest.context if manifest else None,
        'available_memory':available, 'available_memory_bytes':available,
        'required_memory':required, 'minimum_available_bytes':MIN_AVAILABLE_BYTES,
        'estimated_peak_memory':peak, 'estimated_kv_bytes':kv,
        'estimated_gpu_memory':plan['gpu_bytes'] if plan else None, 'gpu_memory_budget':GPU_VRAM_BUDGET_BYTES,
        'cpu_moe_layers':plan.get('cpu_moe_layers') if plan else None,
        'process_limit_bytes':plan['process_limit_bytes'] if plan else MAX_PROCESS_BYTES,
        'estimate_basis':('FULL_WEIGHT_BYTES_PLUS_F16_KV_PLUS_2_GIB_RUNTIME_ALLOWANCE' if not plan or plan['device'] == 'none'
                          else 'CPU_SIDE_WEIGHTS_PLUS_2_GIB_HOST__GPU_WEIGHTS_PLUS_F16_KV_PLUS_1_GIB_DEVICE'),
        'observed_peak_memory':sample.get('process_peak_bytes'), 'resource_sample':sample,
        'readiness_status':status, 'state':{'LOCAL_RUNTIME_READY':'READY',
            'LOCAL_RUNTIME_RESOURCE_BLOCKED':'RESOURCE_BLOCKED'}.get(status,'UNAVAILABLE'),
        'rejection_reason':reason, 'reason':reason, 'measurement_timestamp':datetime.now(UTC).isoformat(),
        'runtime_launched':process is not None and process.poll() is None,
        'inference_occurred':False, 'results_produced':False, 'premium_generation_attempted':False,
        'quality_status':'LOCAL_QUALITY_NOT_PROVEN', 'retry_requires_fresh_resource_measurement':True,
    }


def verify_identity_reason(manifest):
    return model_pin(manifest) is None
