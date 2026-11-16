"""Real loopback callbacks with isolated keys and synthetic remote responses."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/provider'))
import broker
import provider_helper
from test_provider import MemoryKeys


class SignInCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.keys = MemoryKeys()
        self.b = broker.Broker(self.temp.name, self.keys)
        self.pages = []
        self.events = []
        self.queries = []

    def tearDown(self):
        self.temp.cleanup()

    def flow(self, failure=None, mode='add', attempt=None, plan=True, blocking_browser=False):
        callbacks = []
        def browser(url):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            self.queries.append(query)
            def callback():
                params = {'code': 'private-code', 'state': query['state'][0], 'client_id': 'issued-test'}
                with urllib.request.urlopen(query['redirect_uri'][0]+'?'+urllib.parse.urlencode(params), timeout=5) as response:
                    page = response.read().decode()
                    self.pages.append((page, response.headers, bool(self.keys.read('issued-test'))))
            t = threading.Thread(target=callback)
            callbacks.append(t)
            t.start()
            if blocking_browser:
                t.join(4)
                if t.is_alive():raise AssertionError('Browser controller waited but Amua did not process the callback')
            return True
        def remote(url, data=None, form=False):
            if 'oauth/token' in url:
                q = self.queries[-1]
                self.assertTrue(form)
                self.assertEqual(data['redirect_uri'], q['redirect_uri'][0])
                self.assertEqual(data['resource'], q['resource'][0])
                self.assertEqual(data['client_id'], 'issued-test')
                self.assertEqual(broker.b64(hashlib.sha256(data['code_verifier'].encode()).digest()), q['code_challenge'][0])
                if failure: raise failure
                return {'access_token':'private-access', 'refresh_token':'private-refresh', 'id_token':'private-id',
                        'scope':broker.SCOPES if plan else 'openid profile email', 'expires_in':3600}
            return {'keys': []}
        def identity(token, client, nonce, keys):
            self.assertEqual(nonce, self.queries[-1]['nonce'][0])
            return {'sub':'verified-test', 'email':'test@example.invalid'}
        try:
            with patch.object(broker.webbrowser,'open',side_effect=browser), patch.object(broker,'http_json',side_effect=remote), patch.object(broker,'verify_identity',side_effect=identity):
                return self.b.connect(mode=mode, attempt_id=attempt, emit=self.events.append)
        finally:
            for thread in callbacks:
                thread.join(6)
                self.assertFalse(thread.is_alive())

    def test_browser_success_follows_verified_durable_save_and_restart(self):
        result = self.flow()
        self.assertTrue(result['connected'])
        page, headers, stored = self.pages[-1]
        self.assertTrue(stored)
        self.assertIn('Connected to ChatGPT', page)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        for secret in ('private-code','private-access','private-refresh','private-id',self.queries[-1]['state'][0]):
            self.assertNotIn(secret, page)
        self.assertEqual([e.get('stage') for e in self.events[1:]], ['callback_received','exchanging_code','verifying_identity','saving_connection'])
        self.assertTrue(broker.Broker(self.temp.name, self.keys).status()['connected'])

    def test_invalid_grant_is_not_browser_success_and_retry_uses_fresh_pkce(self):
        error = broker.AuthorizationError('http_400_invalid_grant','Code rejected.', 'req_test_123','invalid_grant',http_status=400)
        with self.assertRaises(broker.AuthorizationError) as caught:
            self.flow(failure=error)
        page, _, stored = self.pages[-1]
        self.assertFalse(stored)
        self.assertIn('sign-in did not finish', page)
        self.assertIn('invalid_grant', page)
        self.assertNotIn('Connected to ChatGPT', page)
        detail = caught.exception.details
        self.assertEqual(detail['request_id'], 'req_test_123')
        self.assertIn('fresh authorization', detail['message'])
        self.assertTrue(self.flow(mode='retry', attempt=detail['pending_attempt_id'])['connected'])
        first, second = self.queries
        self.assertEqual(second['client_id'], ['issued-test'])
        for key in ('nonce','state','code_challenge'):
            self.assertNotEqual(first[key], second[key])
        self.assertFalse(self.b.accounts()['pending_attempts'])

    def test_missing_plan_permission_is_signed_in_but_not_claimed_ai_ready(self):
        result = self.flow(plan=False)
        self.assertTrue(result['connected'])
        self.assertFalse(result['plan_enabled'])
        self.assertIn('plan access is unavailable', self.pages[-1][0])
        self.assertNotIn('Connected to ChatGPT', self.pages[-1][0])

    def test_blocking_browser_navigation_cannot_delay_code_exchange(self):
        self.assertTrue(self.flow(blocking_browser=True)['connected'])
        self.assertIn('Connected to ChatGPT', self.pages[-1][0])

    def test_failed_browser_launch_stops_promptly(self):
        with patch.object(broker.webbrowser,'open',return_value=False):
            with self.assertRaisesRegex(broker.BrokerError,'browser_unavailable'):
                self.b.connect()
        self.assertFalse(self.b.status()['connected'])

    def test_oauth_diagnostics_keep_finite_reason_without_raw_provider_text(self):
        for text, expected in [('Invalid PKCE code verifier.','pkce_verification_failed'),('Redirect URI mismatch.','redirect_uri_rejected'),('Code already used.','code_already_used'),('Code expired.','code_expired'),('Invalid client.','client_rejected')]:
            body={'error':'invalid_grant','error_description':text+' PRIVATE-CODE-OR-PROVIDER-TEXT'}
            error=broker.urllib.error.HTTPError('https://example.invalid/token',400,'synthetic',{},io.BytesIO(json.dumps(body).encode()))
            failure=broker.http_failure(error)
            self.assertEqual(failure.details['oauth_reason'],expected)
            self.assertNotIn('PRIVATE',json.dumps(failure.details))
            self.assertNotIn('PRIVATE',broker.sign_in_error(failure))

    def test_helper_forwards_sign_in_progress(self):
        def connect(*args, emit, **kwargs):
            emit({'event':'auth_progress','stage':'saving_connection'})
            return {'connected':True}
        with patch.object(provider_helper,'Broker',return_value=self.b), patch.object(self.b,'connect',side_effect=connect):
            self.assertTrue(provider_helper.run({'action':'connect'}, self.events.append)['connected'])
        self.assertEqual(self.events,[{'event':'auth_progress','stage':'saving_connection'}])

if __name__ == '__main__':
    unittest.main()
