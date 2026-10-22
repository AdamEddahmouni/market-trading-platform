from __future__ import annotations
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
from pathlib import Path
from unittest.mock import Mock
from tools.controlled_replay.env import build_controlled_replay_environment
from tools.ui1 import run_ui_api
from market_platform_foundation.ui_api.server import UiApiHandler
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload, SecretLeakError

class PortableReplayIsolationTests(unittest.TestCase):
    def test_replay_rejects_current_market_routes_before_provider_or_cache_access(self):
        handler=type('ReplayHandler',(UiApiHandler,),{'store':SimpleNamespace(data_mode='FIXTURE_REPLAY')})
        httpd=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        try:
            with patch('market_platform_foundation.ui_api.server.authorize_http_request',return_value=None), patch('market_platform_foundation.ui_api.screener_projections.read_screener',side_effect=AssertionError('provider/cache boundary crossed')), patch('market_platform_foundation.finviz.request_manager.urllib_get',side_effect=AssertionError('forbidden live Finviz network request')), patch.dict(os.environ,{'IMP_FINVIZ_LIVE':'1','IMP_MOOMOO_LIVE':'1','IMP_LIVE_OBSERVATIONAL':'1'}):
                for method,path in [('GET','/screener?refresh=1&result_set=old'),('GET','/screener/preview?instrument=SPY'),('GET','/screener/options'),('GET','/screener/news'),('GET','/screener/chart'),('GET','/discover/run'),('GET','/discover/mixed'),('POST','/screener/window'),('POST','/screener/reevaluation/start'),('POST','/screener/connect'),('PUT','/screener/config')]:
                    with self.subTest(method=method,path=path):
                        conn=http.client.HTTPConnection('127.0.0.1',httpd.server_address[1],timeout=5)
                        conn.request(method,path,body='{}',headers={'Content-Type':'application/json'})
                        response=conn.getresponse();payload=json.loads(response.read());conn.close()
                        self.assertEqual(response.status,403)
                        self.assertEqual(payload.get('reason_code',payload.get('code')),'MODE_BLOCKED')
        finally:httpd.shutdown();httpd.server_close();thread.join(5)

    def test_replay_provider_health_does_not_create_or_probe_live_runtime(self):
        from market_platform_foundation.ui_api.live_projections import build_provider_health_payload
        with patch('market_platform_foundation.ui_api.live_projections._runtime_or_none',side_effect=AssertionError('live runtime touched')):
            payload=build_provider_health_payload(SimpleNamespace(data_mode='FIXTURE_REPLAY'))
        self.assertFalse(payload['available'])
        self.assertEqual(payload['status'],'NOT_APPLICABLE')

    def test_controlled_replay_does_not_start_warmup_with_live_gates_present(self):
        from tools.ui1.run_ui_api import start_screener_warmup
        with patch.dict(os.environ,{'IMP_CONTROLLED_REPLAY':'1','IMP_FINVIZ_LIVE':'1','IMP_SCREENER_WARMUP':'1'}), patch('tools.ui1.run_ui_api.threading.Thread'):
            self.assertIsNone(start_screener_warmup())

    def test_finviz_replay_denial_precedes_credential_cache_and_network(self):
        from market_platform_foundation.finviz.request_manager import FinvizRequestManager
        manager=FinvizRequestManager.__new__(FinvizRequestManager)
        with patch.dict(os.environ,{'IMP_CONTROLLED_REPLAY':'1','IMP_FINVIZ_LIVE':'1'}):
            with self.assertRaisesRegex(RuntimeError,'REPLAY'):
                manager.get('https://elite.finviz.com/export.ashx',params={},api_key='synthetic-fixture-token',cache_ttl_s=60)

    def test_finviz_network_sinks_deny_replay_including_login(self):
        from market_platform_foundation.finviz.http_client import urllib_get, UrllibSession
        session=UrllibSession()
        with patch.dict(os.environ,{'IMP_CONTROLLED_REPLAY':'1'}), patch('urllib.request.urlopen',side_effect=AssertionError('forbidden network')), patch.object(session._opener,'open',side_effect=AssertionError('forbidden login network')):
            for call in [lambda:urllib_get('https://elite.finviz.com/export.ashx'),lambda:session.get('https://elite.finviz.com/'),lambda:session.post('https://elite.finviz.com/login')]:
                with self.subTest(call=call),self.assertRaisesRegex(RuntimeError,'REPLAY'):
                    call()

    def test_finviz_validation_and_recovery_deny_before_callbacks(self):
        from market_platform_foundation.finviz.credential_manager import FinvizCredentialManager
        manager=FinvizCredentialManager()
        manager.set_http_getter(lambda *args,**kwargs: self.fail('credential validation callback reached'))
        with patch.dict(os.environ,{'IMP_CONTROLLED_REPLAY':'1'}), patch('market_platform_foundation.finviz.credential_manager.recover_token_via_login',side_effect=AssertionError('login recovery reached')):
            with self.assertRaisesRegex(RuntimeError,'REPLAY'):manager.validate_token('synthetic-fixture-token')
            with self.assertRaisesRegex(RuntimeError,'REPLAY'):manager.attempt_recovery()

    def test_direct_login_transport_cannot_bypass_replay_with_custom_factory(self):
        from market_platform_foundation.finviz.login_recovery import recover_token_via_login
        for flag in ('1', 'TRUE', 'Yes'):
            factory = unittest.mock.Mock(side_effect=AssertionError('login session constructed'))
            with self.subTest(flag=flag), patch.dict(os.environ, {'IMP_CONTROLLED_REPLAY': flag}):
                with self.assertRaisesRegex(RuntimeError, 'REPLAY'):
                    recover_token_via_login(username='fixture-user', password='fixture-pass', session_factory=factory)
                factory.assert_not_called()

    def test_login_transport_checks_authority_again_before_next_request(self):
        from market_platform_foundation.finviz.login_recovery import recover_token_via_login, LOGIN_PAGE_URL
        calls = []
        def first_request(url, **kwargs):
            calls.append(url)
            os.environ['IMP_CONTROLLED_REPLAY'] = '1'
            return SimpleNamespace(url=LOGIN_PAGE_URL, status_code=200, text='fixture login page')
        session = SimpleNamespace(get=first_request, post=lambda *a, **kw: calls.append('forbidden post'), close=lambda: None)
        with patch.dict(os.environ, {'IMP_CONTROLLED_REPLAY': '0'}):
            with self.assertRaisesRegex(RuntimeError, 'REPLAY'):
                recover_token_via_login(username='fixture-user', password='fixture-pass', session_factory=lambda: session)
        self.assertEqual(calls, [LOGIN_PAGE_URL])

    def test_finite_public_finviz_metadata_passes_secret_audit(self):
        assert_no_secrets_in_payload({'finviz':{'authentication':'HEALTHY','credential_source':'PRIVATE_FILE','finviz_credential_generation':2,'auth_recoveries':0,'last_auth_error':'AUTH_EXPIRED'}})

    def test_finviz_metadata_names_do_not_exempt_secret_values(self):
        for key in ['authentication','credential_source','finviz_credential_generation','auth_recoveries','last_auth_error']:
            with self.subTest(key=key),self.assertRaises(SecretLeakError):
                assert_no_secrets_in_payload({'finviz':{key:'synthetic-fixture-token'}})
        for value in [-1,0.5]:
            with self.subTest(value=value),self.assertRaises(SecretLeakError):
                assert_no_secrets_in_payload({'finviz':{'auth_recoveries':value}})



class ReplayStartupTests(unittest.TestCase):
    def test_replay_marked_store_cannot_gain_current_market_access_from_live_mode_label(self):
        handler = type('MarkedReplayHandler', (UiApiHandler,), {
            'store': SimpleNamespace(data_mode='LIVE_OBSERVATIONAL', controlled_replay=True)})
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('market_platform_foundation.ui_api.server.authorize_http_request', return_value=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
                connection.request('GET', '/screener?refresh=1')
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                self.assertEqual(json.loads(response.read())['reason_code'], 'MODE_BLOCKED')
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_saved_settings_cannot_restore_live_provider_gates_during_replay_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text('IMP_LIVE_OBSERVATIONAL=1\nIMP_MOOMOO_LIVE=1\nIMP_FINNHUB_LIVE=1\n')
            environment = build_controlled_replay_environment({}, root=root)
            observed = {}
            def bootstrap():
                os.environ['IMP_NEWSAPI_LIVE'] = '1'
            def serve(**kwargs):
                observed.update(os.environ)
            with patch.dict(os.environ, environment, clear=True), patch.object(run_ui_api, 'ROOT', root), \
                    patch.object(run_ui_api, 'parse_args', return_value=SimpleNamespace(serve=True, host='127.0.0.1', port=8766)), \
                    patch.object(run_ui_api, 'bootstrap_process_environment', side_effect=bootstrap), \
                    patch.object(run_ui_api, 'configure_login_transport'), patch.object(run_ui_api, 'serve', side_effect=serve):
                self.assertEqual(run_ui_api.main(), 0)
            for gate in ('IMP_LIVE_OBSERVATIONAL', 'IMP_MOOMOO_LIVE', 'IMP_FINNHUB_LIVE', 'IMP_NEWSAPI_LIVE'):
                self.assertNotEqual(observed.get(gate), '1', gate)
            self.assertEqual(observed['IMP_PAPER_EXECUTION'], '0')

    def test_store_composition_denies_live_runtime_even_with_reintroduced_live_gate(self):
        store = SimpleNamespace(load=Mock(), data_mode='FIXTURE_REPLAY', data_provider='INTERNAL')
        with patch.dict(os.environ, {'IMP_CONTROLLED_REPLAY': '1', 'IMP_LIVE_OBSERVATIONAL': '1'}, clear=True), \
                patch.object(run_ui_api, 'ReplayStore', return_value=store), \
                patch('market_platform_foundation.ui_api.live_intelligence.bind_ui_api_intelligence'), \
                patch('tools.ibkr.runtime_bootstrap.install_ibkr_observational_provider') as ibkr, \
                patch('market_platform_foundation.market_data.live_runtime.get_live_runtime') as live:
            self.assertIs(run_ui_api._load_store(), store)
            self.assertEqual(store.data_mode, 'FIXTURE_REPLAY')
            ibkr.assert_not_called()
            live.assert_not_called()


if __name__ == '__main__':
    unittest.main()
