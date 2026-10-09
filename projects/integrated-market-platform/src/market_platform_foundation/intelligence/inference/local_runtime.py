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
}
_VERIFIED = {}
_VERIFY_LOCK = threading.Lock()


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
    return None if actual == PROFILES[manifest.execution_profile] else 'LOCAL_RUNTIME_PROFILE_MISMATCH'


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_artifacts(manifest):
    """Trust anchored in pinned archive, including adjacent executables and DLLs.

    Success is cached only for unchanged file identities. Failures are not cached.
    Never executes or downloads an artifact to verify it.
    """
    if not manifest or (manifest.model_id, manifest.revision, manifest.runtime_version) != (
            MODEL_ID, MODEL_REVISION, RUNTIME_VERSION):
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
        key = tuple((str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns) for p in paths)
        with _VERIFY_LOCK:
            if key in _VERIFIED:
                return None
            if manifest.model_path.stat().st_size != MODEL_BYTES or _digest(manifest.model_path) != MODEL_HASH:
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
            if current!=key:return 'LOCAL_ARTIFACT_CHANGED_DURING_VERIFICATION'
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
    # f16 K+V: pinned Qwen3 36 layers, 8 KV heads, head dim 128.
    # Count the FULL weight artifact even with mmap, plus conservative uncalibrated
    # 1.5 GiB runtime/graph/buffer reserve; shared GPU budgets never add capacity.
    kv = 36 * 8 * 128 * 4 * manifest.context if manifest else None
    peak = MODEL_BYTES + kv + 3*GIB//2 if kv is not None else None
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
        elif peak > MAX_PROCESS_BYTES:
            reason = 'LOCAL_RESOURCE_PREDICTED_PROCESS_LIMIT'
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
        'model_hash':MODEL_HASH if manifest and not verify_identity_reason(manifest) else None,
        'artifact_verified':not bool(artifact_reason),
        'runtime_version':manifest.runtime_version if manifest else None,
        'execution_profile':manifest.execution_profile if manifest else None,
        'profile_validation':'CANDIDATE_NOT_EMPIRICALLY_VALIDATED',
        'context_configuration':{'context':manifest.context if manifest else None,
                                 'batch':manifest.batch if manifest else None, 'ubatch':manifest.ubatch if manifest else None,
                                 'kv_type':'f16', 'parallel_slots':1, 'mmap':True},
        'context_window':manifest.context if manifest else None,
        'available_memory':available, 'available_memory_bytes':available,
        'required_memory':required, 'minimum_available_bytes':MIN_AVAILABLE_BYTES,
        'estimated_peak_memory':peak, 'estimated_kv_bytes':kv,
        'estimate_basis':'FULL_WEIGHT_BYTES_PLUS_F16_KV_PLUS_1_5_GIB_UNCALIBRATED_RESERVE',
        'observed_peak_memory':sample.get('process_peak_bytes'), 'resource_sample':sample,
        'readiness_status':status, 'state':{'LOCAL_RUNTIME_READY':'READY',
            'LOCAL_RUNTIME_RESOURCE_BLOCKED':'RESOURCE_BLOCKED'}.get(status,'UNAVAILABLE'),
        'rejection_reason':reason, 'reason':reason, 'measurement_timestamp':datetime.now(UTC).isoformat(),
        'runtime_launched':process is not None and process.poll() is None,
        'inference_occurred':False, 'results_produced':False, 'premium_generation_attempted':False,
        'quality_status':'LOCAL_QUALITY_NOT_PROVEN', 'retry_requires_fresh_resource_measurement':True,
    }


def verify_identity_reason(manifest):
    return (manifest.model_id,manifest.revision,manifest.runtime_version) != (MODEL_ID,MODEL_REVISION,RUNTIME_VERSION)
