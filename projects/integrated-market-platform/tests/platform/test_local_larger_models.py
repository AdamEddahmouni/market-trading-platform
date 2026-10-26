"""Rebuild step 5: larger local models on the 8 GiB card. No model, GPU or download is needed."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

from market_platform_foundation.intelligence.inference import local_resources as resources
from market_platform_foundation.intelligence.inference import local_runtime as runtime
from market_platform_foundation.intelligence.inference.local_models import MODELS
from market_platform_foundation.intelligence.inference.local_provider import (
    SERVER_ALIAS, LocalLlamaServer, LocalModelManifest, read_sequentially, startup_timeout_for,
)
from tests.intelligence.test_local_synthesis_provider import FakeProcess

GIB = resources.GIB
DENSE_8B = 'Qwen/Qwen3-8B-GGUF:Q4_K_M'
INSTRUCT_4B = 'lmstudio-community/Qwen3-4B-Instruct-2507-GGUF:Q4_K_M'
MOE_30B = 'lmstudio-community/Qwen3-30B-A3B-Instruct-2507-GGUF:Q4_K_M'
ROOMY = {'available_bytes': 26 * GIB, 'commit_available_bytes': 40 * GIB}


def manifest(model_id, profile, root=Path('.')):
    pin = MODELS[model_id]
    return runtime.apply_profile(LocalModelManifest(root / 'llama-server.exe', root / pin.filename, model_id,
                                                    pin.revision, runtime.RUNTIME_VERSION), profile)


def ready(model_id, profile, sample=ROOMY):
    with patch.object(runtime, 'verify_artifacts', return_value=None):
        return runtime.readiness(manifest(model_id, profile), sample=sample)


class MemoryGateTests(unittest.TestCase):
    def test_8b_fits_the_card_and_is_refused_on_the_cpu_profile(self):
        gpu = ready(DENSE_8B, 'vulkan-8192/1')
        self.assertIsNone(gpu['rejection_reason'])
        self.assertLessEqual(gpu['estimated_gpu_memory'], runtime.GPU_VRAM_BUDGET_BYTES)
        self.assertEqual(gpu['estimated_peak_memory'], 2 * GIB)
        self.assertEqual(ready(DENSE_8B, 'cpu-8192/1')['rejection_reason'], 'LOCAL_RESOURCE_PREDICTED_PROCESS_LIMIT')

    def test_the_2507_4b_fits_the_card(self):
        self.assertIsNone(ready(INSTRUCT_4B, 'vulkan-8192/1')['rejection_reason'])

    def test_30b_moe_needs_its_profile_and_counts_cpu_experts_in_ram(self):
        self.assertEqual(ready(MOE_30B, 'vulkan-8192/1')['rejection_reason'], 'LOCAL_RESOURCE_PREDICTED_VRAM_LIMIT')
        moe = ready(MOE_30B, 'vulkan-8192/1-moe')
        self.assertIsNone(moe['rejection_reason'])
        pin = MODELS[MOE_30B]
        cpu_experts = pin.expert_bytes * 38 // 48
        self.assertEqual((moe['cpu_moe_layers'], moe['estimated_peak_memory']), (38, cpu_experts + 2 * GIB))
        self.assertLessEqual(moe['estimated_gpu_memory'], runtime.GPU_VRAM_BUDGET_BYTES)
        self.assertGreater(moe['process_limit_bytes'], resources.MAX_PROCESS_BYTES)
        # The same model with today's typical free memory is refused before any start, never squeezed in.
        busy = ready(MOE_30B, 'vulkan-8192/1-moe', {'available_bytes': 12 * GIB, 'commit_available_bytes': 40 * GIB})
        self.assertEqual(busy['rejection_reason'], 'LOCAL_RESOURCE_PREDICTED_UNSAFE')

    def test_the_moe_profile_has_no_cpu_fallback(self):
        self.assertNotIn('vulkan-8192/1-moe', runtime.CPU_FALLBACK)
        self.assertEqual(runtime.profile_device('vulkan-8192/1-moe'), 'Vulkan0')

    def test_cpu_profiles_keep_the_6_gib_ceiling(self):
        cpu = manifest(runtime.MODEL_ID, 'cpu-8192/1')
        self.assertEqual(runtime.process_limit(cpu), resources.MAX_PROCESS_BYTES)
        monitor = resources.ResourceMonitor(SimpleNamespace(_process=None, manifest=cpu))
        self.assertEqual(monitor.process_limit, resources.MAX_PROCESS_BYTES)

    def test_monitor_uses_the_moe_ceiling(self):
        moe = manifest(MOE_30B, 'vulkan-8192/1-moe')
        monitor = resources.ResourceMonitor(SimpleNamespace(_process=None, manifest=moe))
        self.assertEqual(monitor.process_limit, runtime.process_limit(moe))
        with patch.object(resources, 'memory_sample', return_value={**ROOMY, 'process_bytes': 15 * GIB,
                                                                     'process_commit_bytes': 15 * GIB}):
            self.assertIsNone(monitor.check())

    def test_new_pins_carry_their_architecture(self):
        self.assertEqual((MODELS[DENSE_8B].layers, MODELS[DENSE_8B].kv_heads, MODELS[DENSE_8B].expert_bytes), (36, 8, 0))
        self.assertEqual((MODELS[MOE_30B].layers, MODELS[MOE_30B].kv_heads), (48, 4))
        self.assertEqual(MODELS[MOE_30B].profile, 'vulkan-8192/1-moe')
        for model_id in (DENSE_8B, INSTRUCT_4B, MOE_30B):
            self.assertEqual(len(MODELS[model_id].sha256), 64)


class StartTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / 'llama-server.exe').write_bytes(b'x')

    def tearDown(self):
        self.directory.cleanup()

    def test_start_limit_grows_with_the_model_file(self):
        model = self.root / 'm.gguf'
        model.write_bytes(b'')
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=2_497_280_448)):
            self.assertAlmostEqual(startup_timeout_for(SimpleNamespace(model_path=model)), 254.9, places=1)
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=18_556_685_824)):
            self.assertAlmostEqual(startup_timeout_for(SimpleNamespace(model_path=model)), 736.7, places=1)
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=100_000_000_000)):
            self.assertEqual(startup_timeout_for(SimpleNamespace(model_path=model)), 900.0)
        self.assertEqual(startup_timeout_for(SimpleNamespace(model_path=self.root / 'missing.gguf')), 180.0)

    def test_sequential_read_reads_the_whole_file_and_stops_when_told(self):
        model = self.root / 'm.gguf'
        model.write_bytes(b'x' * (9 * 1024 * 1024))
        self.assertEqual(read_sequentially(model, lambda: True), 9 * 1024 * 1024)
        self.assertEqual(read_sequentially(model, lambda: False), 0)

    def _server(self, model_id, profile, events):
        pin = MODELS[model_id]
        (self.root / pin.filename).write_bytes(b'x')
        up = {'on': False}

        def spawn(args, **kwargs):
            events.append(('spawn', args))
            up['on'] = True
            return FakeProcess()

        def getter(url, timeout):
            if not up['on']:
                raise URLError('refused')
            return 200, json.dumps({'data': [{'id': SERVER_ALIAS}]}).encode()

        def preread(path, keep_going):
            events.append(('preread', path))
            return 1

        clock = [0.0]
        return LocalLlamaServer(manifest(model_id, profile, self.root), getter=getter, spawn=spawn,
                                clock=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                preread=preread)

    def test_the_file_is_pre_read_before_launch_and_moe_flags_are_passed(self):
        events = []
        server = self._server(MOE_30B, 'vulkan-8192/1-moe', events)
        with patch.object(runtime, 'readiness', return_value={'rejection_reason': None}):
            self.assertIsNone(server.ensure_running())
        self.assertEqual([kind for kind, _ in events], ['preread', 'spawn'])
        args = events[1][1]
        self.assertEqual(args[args.index('--n-cpu-moe') + 1], '38')
        self.assertEqual(args[args.index('--device') + 1], 'Vulkan0')
        self.assertEqual(server.last_preread['bytes'], 1)
        server.stop()

    def test_a_dense_model_gets_no_moe_flag(self):
        events = []
        server = self._server(DENSE_8B, 'vulkan-8192/1', events)
        with patch.object(runtime, 'readiness', return_value={'rejection_reason': None}):
            self.assertIsNone(server.ensure_running())
        self.assertNotIn('--n-cpu-moe', events[-1][1])
        server.stop()


if __name__ == '__main__':
    unittest.main()
