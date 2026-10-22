"""Official artifact registry. Selection is explicit; runtime never downloads weights."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelPin:
    model_id: str
    revision: str
    filename: str
    sha256: str
    weight_bytes: int
    parameter_count: int
    quantization: str
    layers: int
    kv_heads: int
    profile: str
    license: str = 'Apache-2.0'
    model_family: str = 'Qwen3'
    head_dim: int = 128
    context_limit: int = 32768

    @property
    def repository(self):
        return self.model_id.split(':')[0]


MODELS = {pin.model_id: pin for pin in (
    ModelPin('Qwen/Qwen3-0.6B-GGUF:Q8_0', '23749fefcc72300e3a2ad315e1317431b06b590a',
        'Qwen3-0.6B-Q8_0.gguf', '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031',
        639446688, 600000000, 'Q8_0', 28, 8, 'cpu-4096/1'),
    ModelPin('Qwen/Qwen3-1.7B-GGUF:Q8_0', '90862c4b9d2787eaed51d12237eafdfe7c5f6077',
        'Qwen3-1.7B-Q8_0.gguf', '061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a',
        1834426016, 1700000000, 'Q8_0', 28, 8, 'cpu-4096/1'),
    ModelPin('Qwen/Qwen3-4B-GGUF:Q4_K_M', 'bc640142c66e1fdd12af0bd68f40445458f3869b',
        'Qwen3-4B-Q4_K_M.gguf', '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5',
        2497280256, 4000000000, 'Q4_K_M', 36, 8, 'cpu-8192/1', context_limit=40960),
)}
DEFAULT_MODEL_ID = 'Qwen/Qwen3-4B-GGUF:Q4_K_M'


def manifest_relative(model_id):
    if model_id not in MODELS:
        raise ValueError('LOCAL_MODEL_NOT_IN_REGISTRY')
    if model_id == DEFAULT_MODEL_ID:
        return Path('models/local-llm.json')
    return Path('models') / (MODELS[model_id].filename.removesuffix('.gguf') + '.json')


def model_manifest(cache_dir, model_id=None):
    from .local_provider import LocalModelManifest
    from ...local_state.external_cache import read_manifest
    chosen = model_id or DEFAULT_MODEL_ID
    payload = read_manifest(cache_dir / manifest_relative(chosen)) or {}
    if payload.get('model_id') != chosen:
        return None
    if payload.get('cache_relative_paths'):
        payload = dict(payload)
        for key in ('model_path', 'runtime_path'):
            path = (cache_dir / str(payload.get(key, ''))).resolve()
            if not path.is_relative_to(cache_dir.resolve()):
                return None
            payload[key] = str(path)
    return LocalModelManifest.from_dict(payload)


def model_options(cache_dir):
    from .local_runtime import readiness, apply_profile
    from .local_qualification import METHOD_VERSION
    from ...local_state.external_cache import read_manifest
    options = []
    for pin in MODELS.values():
        manifest = model_manifest(cache_dir, pin.model_id)
        if manifest:
            try:
                manifest = apply_profile(manifest, manifest.execution_profile)
            except ValueError:
                pass
        status = readiness(manifest)
        # Observations are external append-only benchmark receipts, never an approval flag.
        observation = read_manifest(cache_dir / 'benchmarks' / 'local-model-observations' /
            (pin.filename + '.json'))
        if observation and (observation.get('model_hash') != pin.sha256 or
                observation.get('revision') != pin.revision):
            observation = None
        options.append({**status, 'model_id': pin.model_id, 'model_family': pin.model_family,
            'parameter_count': pin.parameter_count, 'quantization': pin.quantization,
            'artifact_revision': pin.revision, 'artifact_sha256': pin.sha256, 'license': pin.license,
            'runtime_version': 'b11269', 'context_limit': pin.context_limit,
            'execution_profile': manifest.execution_profile if manifest else pin.profile,
            'installed': bool(manifest and not manifest.missing()),
            'estimated_memory': status['estimated_peak_memory'], 'observed_memory':
                observation.get('observed_peak_memory') if observation else None,
            'qualification_method_version': METHOD_VERSION,
            'benchmark_status': observation.get('quality', {}).get('quality_status', 'NOT_RUN') if observation else 'NOT_RUN',
            'performance_observations': observation, 'experimental': True, 'operational_activation': 'OFF',
            'last_inference_error': observation.get('rejection_reason') if observation else None})
    return options
