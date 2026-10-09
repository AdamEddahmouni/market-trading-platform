"""Resource safety contracts; no paid generation, model or hardware required."""
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.intelligence.inference.local_provider import LocalModelManifest
from market_platform_foundation.intelligence.inference import local_resources as resources


class RuntimeAdmissionTests(unittest.TestCase):
    def test_artifact_hashes_are_anchored_in_the_archive_not_manifest_claims(self):
        import hashlib
        import tempfile
        import zipfile
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'downloads').mkdir();(root/'runtime').mkdir()
            archive=root/'downloads'/runtime.ARCHIVE_NAME
            exe=root/'runtime'/'llama-server.exe';dll=root/'runtime'/'llama.dll';model=root/'model.gguf'
            exe.write_bytes(b'trusted exe');dll.write_bytes(b'trusted dll');model.write_bytes(b'trusted model')
            with zipfile.ZipFile(archive,'w') as bundle:
                bundle.write(exe,exe.name);bundle.write(dll,dll.name)
            manifest=replace(self.manifest(),runtime_path=exe,model_path=model)
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.object(runtime,'os',SimpleNamespace(name='nt')),patch.object(runtime,'MODEL_BYTES',model.stat().st_size),\
                 patch.object(runtime,'MODEL_HASH',digest(model)),patch.object(runtime,'ARCHIVE_HASH',digest(archive)),\
                 patch('market_platform_foundation.local_state.external_cache.imp_cache_dir',return_value=root):
                runtime._VERIFIED.clear()
                self.assertIsNone(runtime.verify_artifacts(manifest))
                self.assertEqual(runtime.verify_artifacts(replace(manifest,runtime_path=dll)),'LOCAL_RUNTIME_FILE_SET_MISMATCH')
                dll.write_bytes(b'corrupt dll')
                self.assertEqual(runtime.verify_artifacts(manifest),'LOCAL_RUNTIME_CHECKSUM_FAILED')
                dll.write_bytes(b'trusted dll');model.write_bytes(b'corrupt model')
                self.assertEqual(runtime.verify_artifacts(manifest),'MODEL_CHECKSUM_FAILED')
                runtime._VERIFIED.clear()

    def manifest(self):
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        return runtime.apply_profile(LocalModelManifest(Path('server'), Path('model'), runtime.MODEL_ID,
                                  runtime.MODEL_REVISION, runtime.RUNTIME_VERSION), 'cpu-8192/1')

    def status(self, **overrides):
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        sample = {'available_bytes': 12*resources.GIB, 'commit_available_bytes': 12*resources.GIB}
        sample.update(overrides)
        with patch.object(runtime, 'verify_artifacts', return_value=None):
            return runtime.readiness(self.manifest(), sample=sample)

    def test_below_floor_has_precise_reason_and_no_quality_claim(self):
        value = self.status(available_bytes=2*resources.GIB)
        self.assertEqual(value['rejection_reason'], 'LOCAL_RESOURCE_INSUFFICIENT_MEMORY')
        self.assertEqual(value['readiness_status'], 'LOCAL_RUNTIME_RESOURCE_BLOCKED')
        self.assertEqual(value['minimum_available_bytes'], 4*resources.GIB)
        self.assertFalse(value['inference_occurred'])
        self.assertIsNone(value['observed_peak_memory'])

    def test_unknown_memory_fails_closed(self):
        self.assertEqual(self.status(available_bytes=None)['rejection_reason'], 'LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE')

    def test_commit_headroom_is_independent_of_physical_ram(self):
        self.assertEqual(self.status(commit_available_bytes=resources.GIB)['rejection_reason'], 'LOCAL_RESOURCE_COMMIT_HEADROOM')

    def test_predicts_reserve_above_the_unchanged_floor(self):
        value = self.status(available_bytes=5*resources.GIB)
        self.assertEqual(value['rejection_reason'], 'LOCAL_RESOURCE_PREDICTED_UNSAFE')
        self.assertGreater(value['required_memory'], value['minimum_available_bytes'])

    def test_profiles_preserve_identity_and_bound_allocations(self):
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        base = self.manifest()
        small = runtime.apply_profile(base, 'cpu-4096/1')
        self.assertEqual((small.context, small.batch, small.ubatch, small.threads, small.gpu_layers), (4096,128,64,4,0))
        self.assertEqual(small.model_id, base.model_id)
        with self.assertRaisesRegex(ValueError, 'LOCAL_RUNTIME_PROFILE_INVALID'):
            runtime.apply_profile(base, 'unknown')
        changed = replace(small, context=1024)
        self.assertEqual(runtime.profile_reason(changed), 'LOCAL_RUNTIME_PROFILE_MISMATCH')

    def test_wrong_identity_is_rejected_before_hashing(self):
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        self.assertEqual(runtime.verify_artifacts(replace(self.manifest(), revision='wrong')), 'PINNED_LOCAL_MODEL_REQUIRED')

    def test_pinned_runtime_is_always_bounded_including_synthesis(self):
        from market_platform_foundation.intelligence.inference.local_provider import LocalLlamaServer
        self.assertTrue(LocalLlamaServer(self.manifest()).enforce_admission)

    def test_monitor_checks_commit_even_when_resident_is_small(self):
        from types import SimpleNamespace
        monitor = resources.ResourceMonitor(SimpleNamespace(_process=None))
        with patch.object(resources, 'memory_sample', return_value={
            'available_bytes':12*resources.GIB, 'process_bytes':resources.GIB,
            'process_commit_bytes':7*resources.GIB, 'commit_available_bytes':12*resources.GIB}):
            self.assertEqual(monitor.check(), 'LOCAL_RESOURCE_COMMIT_LIMIT')

    def test_windows_query_returns_total_commit_and_pressure_fields(self):
        sample = resources.memory_sample()
        for field in ('total_bytes', 'commit_available_bytes', 'memory_load_percent', 'process_commit_bytes', 'process_peak_bytes'):
            self.assertIn(field, sample)

    def test_monitor_retains_os_high_water_between_poll_samples(self):
        from types import SimpleNamespace
        monitor=resources.ResourceMonitor(SimpleNamespace(_process=None))
        with patch.object(resources,'memory_sample',return_value={'available_bytes':12*resources.GIB,
            'commit_available_bytes':12*resources.GIB,'process_bytes':1,'process_peak_bytes':12345}):
            monitor.check()
        self.assertEqual(monitor.peak_bytes,12345)


class BenchmarkSafetyTests(unittest.TestCase):
    def test_corrupt_budget_preserves_attempt_without_resetting_ledger(self):
        import contextlib
        import io
        import tempfile
        from tools import local_runtime_benchmark as benchmark
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            state=root/'benchmarks'/'local-runtime-validation';state.mkdir(parents=True)
            path=state/'budget.json'
            for i,content in enumerate(('{}','{broken')):
                path.write_text(content,encoding='utf-8')
                with patch.object(benchmark,'imp_cache_dir',return_value=root),contextlib.redirect_stdout(io.StringIO()):
                    summary=benchmark.run(output=root/('attempt-'+str(i)))
                self.assertEqual(summary['rejection_reason'],'LOCAL_BENCHMARK_BUDGET_CORRUPT')
                self.assertEqual(path.read_text(encoding='utf-8'),content)
                self.assertEqual(summary['runtime_starts'],0)
                self.assertTrue((root/('attempt-'+str(i))/'summary.json').is_file())
    def test_nonfinite_or_negative_budget_never_admits(self):
        from tools.local_runtime_benchmark import reserve
        for used in (float('nan'),float('inf'),-1,True,'zero'):
            with self.assertRaisesRegex(ValueError,'LOCAL_BENCHMARK_BUDGET_CORRUPT'):
                reserve({'used_seconds':used},'next')
        with self.assertRaisesRegex(ValueError,'LOCAL_BENCHMARK_BUDGET_CORRUPT'):
            reserve({},'next')
    def test_zero_real_results_cannot_report_recall_or_savings(self):
        from tools.local_runtime_benchmark import quality_summary
        summary = quality_summary([], 52)
        self.assertIsNone(summary['recall'])
        self.assertEqual(summary['real_cases_completed'], 0)
        self.assertEqual(summary['cases_not_completed'], 52)
        self.assertEqual(summary['quality_status'], 'LOCAL_QUALITY_NOT_PROVEN')

    def test_failed_assessment_advances_but_is_not_valid_quality(self):
        from tools.local_runtime_benchmark import quality_summary
        records = [{'label':'POSITIVE','assessment':{'valid':False,'category':'UNCERTAIN',
            'inference_dispatched':True,'reason':'LOCAL_INVALID_REFERENCE','simulated':False}}]
        summary = quality_summary(records, 1)
        self.assertEqual(summary['failed'], 1)
        self.assertEqual(summary['false_exclusions'], 0)
        self.assertEqual(summary['operational_advancement_recall'], 1)
        self.assertEqual(summary['evidence_grounding_failures'], 1)
        self.assertIsNone(summary['qualification_accuracy'])

    def test_unexecuted_positive_is_not_removed_from_complete_recall(self):
        from tools.local_runtime_benchmark import quality_summary
        records=[{'label':'POSITIVE','assessment':{'valid':True,'category':'WARRANTS_REVIEW','inference_dispatched':True}},
                 {'label':'POSITIVE','assessment':{'valid':False,'category':'UNCERTAIN','inference_dispatched':False,'reason':'LOCAL_CONTEXT_EXCEEDED'}}]
        value=quality_summary(records,2)
        self.assertFalse(value['quality_complete'])
        self.assertEqual(value['cases_not_completed'],1)
        self.assertIsNone(value['recall'])

    def test_original_stale_exclusion_remains_separate(self):
        from tools.local_runtime_benchmark import quality_summary
        records=[{'label':'POSITIVE','assessment':{'valid':True,'category':'WARRANTS_REVIEW','inference_dispatched':True}},
                 {'label':'UNAVAILABLE','assessment':{'valid':False,'inference_dispatched':False,'reason':'LOCAL_EVIDENCE_EXPIRED'}}]
        value=quality_summary(records,2)
        self.assertTrue(value['quality_complete'])
        self.assertEqual(value['intentional_stale_exclusions'],1)
        self.assertEqual(value['recall'],1)

    def test_frozen_dataset_is_original_and_hash_checked(self):
        from tools.ai_screener_local_first_benchmark import load
        value = load()
        self.assertEqual(len(value['cases']), 52)
        self.assertEqual(sum(c['split']=='holdout' for c in value['cases']),26)

    def test_economic_projection_uses_offline_provider_accounting(self):
        from tools.local_runtime_benchmark import economic_plan
        from tools.ai_screener_local_first_benchmark import load
        frozen=load();case=frozen['cases'][0]
        record={'case_id':case['case_id'],'assessment':{'valid':True,'category':'WARRANTS_REVIEW','inference_dispatched':True}}
        value=economic_plan([record],frozen['cases'],frozen['cutoff'])
        self.assertEqual(value['paid_generations'],0)
        self.assertEqual(value['plans'][0]['proposed_premium_count'],1)
        self.assertGreater(value['plans'][0]['required']['tokens'],0)

    def test_concurrent_benchmark_and_unresolved_attempt_are_refused(self):
        import tempfile
        from tools.local_runtime_benchmark import exclusive_run, reserve
        with tempfile.TemporaryDirectory() as folder:
            with exclusive_run(Path(folder)):
                with self.assertRaisesRegex(ValueError,'LOCAL_BENCHMARK_ALREADY_RUNNING'):
                    with exclusive_run(Path(folder)):pass
            budget = {'used_seconds':0,'pending':{'case_id':'prior'}}
            with self.assertRaisesRegex(ValueError,'PRIOR_INFERENCE_OUTCOME_UNKNOWN'):
                reserve(budget,'next')
            with self.assertRaisesRegex(ValueError,'CUMULATIVE_TWO_HOUR_CEILING'):
                reserve({'used_seconds':7000},'next')


class ControlledLifecycleTests(unittest.TestCase):
    def test_context_overflow_preserves_input_and_never_dispatches_generation(self):
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        requests=[]
        def post(url,body,timeout):
            requests.append((url,body))
            return (200,json_bytes({'prompt':'COMPLETE EVIDENCE'})) if url.endswith('apply-template') else (200,json_bytes({'tokens':[1]*4096}))
        server=SimpleNamespace(manifest=SimpleNamespace(context=4096),running=lambda:True,ensure_running=lambda:None,touch=lambda:None)
        provider=LocalChatInferenceProvider(base_url='http://127.0.0.1:19999',model_id='fixture',server=server,poster=post)
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,'i','h','t',{},[],{})
        result=provider._infer_locked(packet,rendered_prompt='COMPLETE EVIDENCE',config=IntelligenceInferenceConfig(max_tokens=384))
        self.assertEqual(result.error_message,'LOCAL_CONTEXT_EXCEEDED')
        self.assertFalse(result.inference_dispatched)
        self.assertFalse(any(url.endswith('chat/completions') for url,_ in requests))
        self.assertIn(b'COMPLETE EVIDENCE',requests[0][1])
    def setUp(self):
        from tests.intelligence.test_local_synthesis_provider import ServerLifecycleTests
        self.harness=ServerLifecycleTests()
        self.harness.setUp()

    def tearDown(self):
        self.harness.tearDown()

    def test_admission_refusal_never_spawns(self):
        spawn=unittest.mock.Mock()
        server=self.harness.server(lambda *a: (0,b''),spawn)
        server.enforce_admission=True
        with patch('market_platform_foundation.intelligence.inference.local_runtime.readiness',return_value={
            'rejection_reason':'LOCAL_RESOURCE_INSUFFICIENT_MEMORY'}):
            self.assertEqual(server.ensure_running(),'LOCAL_RESOURCE_INSUFFICIENT_MEMORY')
        spawn.assert_not_called()

    def test_operator_stop_during_startup_reaps_owned_process(self):
        from tests.intelligence.test_local_synthesis_provider import FakeProcess
        process=FakeProcess()
        server=self.harness.server(lambda *a:(503,b''),lambda *a,**kw:process)
        server._ours=lambda:None
        server.should_stop=lambda:self.harness.clock[0]>=.5
        self.assertEqual(server.ensure_running(),'STOPPED_BY_OPERATOR')
        self.assertTrue(process.terminated)
        self.assertFalse(server.running())

    def test_owned_timeout_terminates_then_waits_after_kill(self):
        import subprocess
        process=unittest.mock.Mock()
        process.poll.return_value=None
        process.wait.side_effect=[subprocess.TimeoutExpired('owned',10),0]
        server=self.harness.server(lambda *a:(0,b''),lambda *a,**kw:process)
        server._process=process
        server.stop()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count,2)

    def test_profile_flags_disable_automatic_context_fitting_and_gpu(self):
        from tests.intelligence.test_local_synthesis_provider import FakeProcess
        process=FakeProcess();args=[]
        server=self.harness.server(lambda *a:(503,b''),lambda command,**kw:(args.extend(command) or process))
        server._ours=lambda:None
        server.enforce_admission=True
        with patch('market_platform_foundation.intelligence.inference.local_runtime.readiness',return_value={'rejection_reason':None}):
            self.assertEqual(server.ensure_running(),'LOCAL_RUNTIME_START_TIMEOUT')
        self.assertIn('--load-mode',args)
        self.assertEqual(args[args.index('--fit')+1],'off')
        self.assertEqual(args[args.index('--device')+1],'none')
        self.assertEqual(args[args.index('--ubatch-size')+1],'64')
        self.assertTrue(process.terminated)

    def test_foreign_alias_is_not_reused_or_killed(self):
        from market_platform_foundation.intelligence.inference.local_provider import SERVER_ALIAS
        server=self.harness.server(lambda *a:(200,json_bytes({'data':[{'id':SERVER_ALIAS}]})),unittest.mock.Mock())
        server.enforce_admission=True
        with patch('market_platform_foundation.intelligence.inference.local_runtime.readiness',return_value={'rejection_reason':None}):
            self.assertEqual(server.ensure_running(),'LOCAL_QUALIFICATION_REQUIRES_OWNED_PINNED_RUNTIME')
        server._spawn.assert_not_called()

    def test_final_monitor_failure_rejects_successful_response(self):
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
        server=SimpleNamespace(stop=unittest.mock.Mock())
        monitor=SimpleNamespace(failure=None,peak_bytes=0,peak_commit_bytes=0,samples=[],last_sample={},check=lambda:None)
        def close():monitor.failure='LOCAL_RESOURCE_COMMIT_LIMIT'
        monitor.close=close
        provider=LocalChatInferenceProvider(base_url='http://127.0.0.1:19999',model_id='fixture',server=server)
        provider._infer_locked=lambda *a,**kw:ProviderInferenceResponse('{}',provider.provider_id,'fixture',inference_dispatched=True)
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,'i','h','t',{},[],{})
        with patch.object(resources,'ResourceMonitor',return_value=monitor):
            value=provider.infer(packet,rendered_prompt='complete',config=IntelligenceInferenceConfig())
        self.assertEqual(value.error_message,'LOCAL_RESOURCE_COMMIT_LIMIT')
        self.assertTrue(value.inference_dispatched)
        server.stop.assert_called_once()

    def test_failed_cleanup_retains_ownership_and_releases_inference_slots(self):
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        server=SimpleNamespace(stop=unittest.mock.Mock(side_effect=OSError('owned cleanup denied')))
        monitor=SimpleNamespace(failure='LOCAL_RESOURCE_COMMIT_LIMIT',peak_bytes=0,peak_commit_bytes=0,
            samples=[],last_sample={},check=lambda:'LOCAL_RESOURCE_COMMIT_LIMIT',close=lambda:None)
        provider=LocalChatInferenceProvider(base_url='http://127.0.0.1:19999',model_id='fixture',server=server)
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,'i','h','t',{},[],{})
        with patch.object(resources,'ResourceMonitor',return_value=monitor):
            with self.assertRaises(OSError):provider.infer(packet,rendered_prompt='data',config=IntelligenceInferenceConfig())
        self.assertTrue(resources.SLOT.acquire(blocking=False));resources.SLOT.release()
        self.assertTrue(resources.ADMISSION.acquire(blocking=False));resources.ADMISSION.release()
        process=unittest.mock.Mock();process.poll.return_value=None;process.terminate.side_effect=OSError('denied')
        owned=self.harness.server(lambda *a:(0,b''),lambda *a,**kw:process);owned._process=process
        with self.assertRaises(OSError):owned.stop()
        self.assertIs(owned._process,process)

    def test_duplicate_runtime_lease_refuses_without_spawning(self):
        spawn=unittest.mock.Mock()
        server=self.harness.server(lambda *a:(0,b''),spawn)
        server._ours=lambda:None;server.enforce_admission=True
        lease=self.harness.manifest.runtime_path.parent/'imp-local-runtime.lock'
        lease.write_text('another owner',encoding='utf-8')
        with patch('market_platform_foundation.intelligence.inference.local_runtime.readiness',return_value={'rejection_reason':None}):
            self.assertEqual(server.ensure_running(),'LOCAL_RUNTIME_ALREADY_OWNED_OR_INTERRUPTED')
        server.stop()
        self.assertEqual(lease.read_text(encoding='utf-8'),'another owner')
        spawn.assert_not_called()


def json_bytes(value):
    import json
    return json.dumps(value).encode()


class LaptopModelTests(unittest.TestCase):
    def test_offline_check_validates_the_persisted_manifest_revision(self):
        import hashlib
        import json
        import os
        import tempfile
        from types import SimpleNamespace
        from tools.news import setup_laptop_models as setup
        from market_platform_foundation.intelligence.inference.local_models import manifest_relative
        chosen = 'Qwen/Qwen3-0.6B-GGUF:Q8_0'
        pin = replace(setup.MODELS[chosen], weight_bytes=4, sha256=hashlib.sha256(b'GGUF').hexdigest())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'models'/'weights'/pin.revision/pin.filename
            target.parent.mkdir(parents=True)
            target.write_bytes(b'GGUF')
            (root/manifest_relative(chosen)).write_text(json.dumps({'model_id':chosen,
                'revision':'tampered', 'model_path':str(target), 'runtime_path':str(root/'llama-server.exe')}), encoding='utf-8')
            with patch.object(setup, 'os', SimpleNamespace(name='nt', fsync=os.fsync)), \
                 patch.object(setup, 'MODELS', {chosen:pin}), patch.object(setup, 'imp_cache_dir', return_value=root), \
                 patch.object(setup, '_runtime', return_value=root/'llama-server.exe'), \
                 patch.object(setup, 'verify_artifacts', side_effect=lambda m: 'PINNED_LOCAL_MODEL_REQUIRED' if m.revision != pin.revision else None):
                with self.assertRaisesRegex(ValueError, 'PINNED_LOCAL_MODEL_REQUIRED'):
                    setup.install(chosen, offline=True)

    def test_verification_retains_distinct_models_and_rejects_changed_files(self):
        import hashlib
        import tempfile
        import zipfile
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference import local_models as models, local_runtime as runtime
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'downloads').mkdir()
            (root/'runtime').mkdir()
            exe = root/'runtime'/'llama-server.exe'
            exe.write_bytes(b'fixture exe')
            archive = root/'downloads'/runtime.ARCHIVE_NAME
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.write(exe, exe.name)
            pins, manifests = {}, []
            for i, original in enumerate(list(models.MODELS.values())[:2]):
                path = root/f'{i}.gguf'
                path.write_bytes(b'GGUF'+bytes([i]))
                pin = replace(original, weight_bytes=5, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                pins[pin.model_id] = pin
                manifests.append(LocalModelManifest(exe, path, pin.model_id, pin.revision, runtime.RUNTIME_VERSION))
            with patch.object(models, 'MODELS', pins), patch.object(runtime, 'os', SimpleNamespace(name='nt')), \
                 patch.object(runtime, 'ARCHIVE_HASH', hashlib.sha256(archive.read_bytes()).hexdigest()), \
                 patch('market_platform_foundation.local_state.external_cache.imp_cache_dir', return_value=root):
                runtime._VERIFIED.clear()
                for manifest in manifests:
                    self.assertIsNone(runtime.verify_artifacts(manifest))
                self.assertEqual(len(runtime._VERIFIED), 2)
                manifests[0].model_path.write_bytes(b'WRONG')
                self.assertEqual(runtime.verify_artifacts(manifests[0]), 'MODEL_CHECKSUM_FAILED')
                runtime._VERIFIED.clear()

    def test_switch_reaps_only_other_owned_runtime_on_shared_port(self):
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference import local_provider as local
        selected = SimpleNamespace(_port=18089)
        prior = SimpleNamespace(_port=18089, stop=unittest.mock.Mock(), running=lambda:True)
        different_port = SimpleNamespace(_port=19999, stop=unittest.mock.Mock(), running=lambda:True)
        with patch.object(local, '_SERVERS', {'old':prior, 'new':selected, 'elsewhere':different_port}):
            local._stop_other_managed_servers(selected)
        prior.stop.assert_called_once()
        different_port.stop.assert_not_called()

    def test_installer_rejects_bad_download_and_preserves_4b_manifest(self):
        import io
        import os
        import tempfile
        from types import SimpleNamespace
        from tools.news import setup_laptop_models as setup
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'models').mkdir()
            legacy = root/'models'/'local-llm.json'
            legacy.write_text('preserve original 4B', encoding='utf-8')
            runtime = root/'runtime'/'llama-server.exe'
            with patch.object(setup, 'os', SimpleNamespace(name='nt', fsync=os.fsync)), \
                 patch.object(setup, 'imp_cache_dir', return_value=root), \
                 patch.object(setup, '_runtime', return_value=runtime), \
                 patch.object(setup, 'urlopen', return_value=io.BytesIO(b'corrupt')):
                with self.assertRaisesRegex(ValueError, 'MODEL_CHECKSUM_FAILED'):
                    setup.install('Qwen/Qwen3-0.6B-GGUF:Q8_0')
            self.assertEqual(legacy.read_text(encoding='utf-8'), 'preserve original 4B')
            self.assertFalse(list(root.rglob('*.download')))
            self.assertFalse((root/'models'/'Qwen3-0.6B-Q8_0.json').exists())

    def test_manifest_rejects_cross_model_pin_and_cache_path_escape(self):
        import json
        import tempfile
        from market_platform_foundation.intelligence.inference.local_models import model_manifest, manifest_relative
        chosen = 'Qwen/Qwen3-0.6B-GGUF:Q8_0'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/manifest_relative(chosen)
            path.parent.mkdir()
            payload = {'model_id':'Qwen/Qwen3-4B-GGUF:Q4_K_M', 'model_path':'model', 'runtime_path':'runtime'}
            path.write_text(json.dumps(payload), encoding='utf-8')
            self.assertIsNone(model_manifest(root, chosen))
            payload.update(model_id=chosen, cache_relative_paths=True, model_path='../outside.gguf')
            path.write_text(json.dumps(payload), encoding='utf-8')
            self.assertIsNone(model_manifest(root, chosen))

    def test_registry_preserves_4b_and_registers_official_small_artifacts(self):
        from market_platform_foundation.intelligence.inference.local_models import MODELS
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        self.assertEqual(len(MODELS), 3)
        self.assertEqual(MODELS[runtime.MODEL_ID].sha256, runtime.MODEL_HASH)
        for size in ('0.6B', '1.7B'):
            pin = MODELS[f'Qwen/Qwen3-{size}-GGUF:Q8_0']
            self.assertEqual(pin.quantization, 'Q8_0')
            self.assertEqual(pin.license, 'Apache-2.0')
            self.assertEqual(pin.layers, 28)

    def test_small_profiles_reduce_allocation_without_lowering_safety_floor(self):
        from market_platform_foundation.intelligence.inference.local_models import MODELS
        from market_platform_foundation.intelligence.inference import local_runtime as runtime
        statuses = []
        for pin in MODELS.values():
            manifest = runtime.apply_profile(LocalModelManifest(Path('server'), Path('model'),
                pin.model_id, pin.revision, runtime.RUNTIME_VERSION), pin.profile)
            with patch.object(runtime, 'verify_artifacts', return_value=None):
                value = runtime.readiness(manifest, sample={'available_bytes': 12*resources.GIB,
                    'commit_available_bytes': 12*resources.GIB})
            self.assertEqual(value['minimum_available_bytes'], 4*resources.GIB)
            self.assertEqual(value['model_hash'], pin.sha256)
            from market_platform_foundation.intelligence.inference.local_provider import LocalLlamaServer
            self.assertTrue(LocalLlamaServer(manifest).enforce_admission)
            statuses.append(value['estimated_peak_memory'])
        self.assertLess(statuses[0], statuses[1])
        self.assertLess(statuses[1], statuses[2])

    def test_explicit_selection_never_falls_back_to_legacy_4b(self):
        import tempfile
        from market_platform_foundation.intelligence.inference.local_models import model_manifest, MODELS
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'models').mkdir()
            (root/'models'/'local-llm.json').write_text('{"model_id":"legacy"}', encoding='utf-8')
            self.assertIsNone(model_manifest(root, next(iter(MODELS))))
            with self.assertRaisesRegex(ValueError, 'LOCAL_MODEL_NOT_IN_REGISTRY'):
                model_manifest(root, 'invented')

    def test_scope_validates_and_preserves_explicit_local_model(self):
        from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
        chosen = 'Qwen/Qwen3-0.6B-GGUF:Q8_0'
        body = {'universe':'US_EQUITIES', 'method':'STAGED_LOCAL_FIRST_EXPERIMENTAL', 'local_model_id':chosen}
        self.assertEqual(ScreenerAiService._query(body)['local_model_id'], chosen)
        self.assertEqual(ScreenerAiService._scope(ScreenerAiService._query(body), {})['local_model_id'], chosen)
        with self.assertRaisesRegex(ValueError, 'LOCAL_MODEL_NOT_IN_REGISTRY'):
            ScreenerAiService._query({**body, 'local_model_id':'wrong'})

    def test_cross_model_cache_identity_is_distinct(self):
        from market_platform_foundation.intelligence.inference.local_models import MODELS
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import LocalQualifier
        from tools.ai_screener_local_first_benchmark import load
        case = load()['cases'][0]
        hashes = {LocalQualifier(LocalChatInferenceProvider(base_url='http://127.0.0.1:18089',
            model_id=pin.model_id)).input(case['scope'], case['candidate'], load()['cutoff'])[0]
            for pin in MODELS.values()}
        self.assertEqual(len(hashes), 3)
