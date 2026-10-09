"""Explicitly install official smaller Qwen GGUF pins without changing the 4B manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from tools.news.setup_local_synthesis import _runtime
from market_platform_foundation.intelligence.inference.local_models import MODELS, DEFAULT_MODEL_ID, manifest_relative, model_manifest
from market_platform_foundation.intelligence.inference.local_runtime import RUNTIME_VERSION, ARCHIVE_HASH, verify_artifacts
from market_platform_foundation.local_state.external_cache import imp_cache_dir, write_json_atomic


def install(model_id, *, offline=False):
    if os.name != 'nt':
        raise ValueError('LOCAL_PINNED_RUNTIME_PLATFORM_UNSUPPORTED')
    pin = MODELS[model_id]
    if model_id == DEFAULT_MODEL_ID:
        raise ValueError('USE_EXISTING_4B_SETUP')
    root = imp_cache_dir()
    server = _runtime(root, offline=offline)
    target = root / 'models' / 'weights' / pin.revision / pin.filename
    if not target.exists():
        if offline:
            raise ValueError('LOCAL_MODEL_FILE_NOT_FOUND')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.download')
        owned = False
        # Exclusive staging avoids partial artifacts becoming installed or overlapping writers.
        try:
            with temporary.open('xb') as stream:
                owned = True
                url = f'https://huggingface.co/{pin.repository}/resolve/{pin.revision}/{pin.filename}'
                with urlopen(Request(url, headers={'User-Agent':'IMP-model-setup/1.0'}), timeout=120) as response:
                    for block in iter(lambda: response.read(1024*1024), b''):
                        stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            with temporary.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != pin.sha256 or temporary.stat().st_size != pin.weight_bytes:
                raise ValueError('MODEL_CHECKSUM_FAILED')
            temporary.replace(target)
        finally:
            # Delete only staging owned by this invocation; a preexisting staging file is retained.
            if owned:
                temporary.unlink(missing_ok=True)
    with target.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != pin.sha256 or target.stat().st_size != pin.weight_bytes:
            raise ValueError('MODEL_CHECKSUM_FAILED')
    payload = {'schema_version':'imp-local-model/1.0.0', 'model_id':pin.model_id,
        'revision':pin.revision, 'model_sha256':pin.sha256, 'model_bytes':pin.weight_bytes,
        'source_repository':pin.repository, 'quantization':pin.quantization, 'license':pin.license,
        'runtime_version':RUNTIME_VERSION, 'runtime_sha256_archive':ARCHIVE_HASH,
        'cache_relative_paths':True, 'runtime_path':str(server.relative_to(root)),
        'model_path':str(target.relative_to(root)), 'execution_profile':pin.profile,
        'context':4096, 'batch':128, 'ubatch':64, 'threads':4, 'gpu_layers':0,
        'verified_at':datetime.now(UTC).isoformat(), 'operational_activation':'OFF',
        'quantization_basis':'Official repository exposes Q8_0 only; preferred Q4_K_M unavailable.'}
    destination = root / manifest_relative(model_id)
    # Check the complete runtime file set before making the new manifest discoverable.
    from market_platform_foundation.intelligence.inference.local_provider import LocalModelManifest
    manifest = LocalModelManifest.from_dict({**payload, 'model_path':str(target), 'runtime_path':str(server)})
    reason = verify_artifacts(manifest)
    if reason:
        raise ValueError(reason)
    if not offline:
        write_json_atomic(destination, payload)
    else:
        saved = model_manifest(root, model_id)
        if saved is None:
            raise ValueError('LOCAL_MODEL_MANIFEST_MISSING')
        from market_platform_foundation.intelligence.inference.local_runtime import profile_reason
        reason = verify_artifacts(saved) or profile_reason(saved)
        if reason:
            raise ValueError(reason)
    return {'model_id':pin.model_id, 'revision':pin.revision, 'sha256':pin.sha256,
        'bytes':target.stat().st_size, 'manifest':str(destination), 'artifact_verified':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=tuple(k for k in MODELS if k != DEFAULT_MODEL_ID), required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.model, offline=args.check), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
