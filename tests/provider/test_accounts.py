import copy
import json
import io
import time
from pathlib import Path
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/provider'))
import broker
import provider_helper
from test_provider import MemoryKeys
class AccountFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()));self.keys=MemoryKeys();self.b=broker.Broker(self.temp.name,self.keys)
    def tearDown(self):self.temp.cleanup()
    def flow(self,client='reg-one',subject='subject-one',email='same@example.invalid',mode='add',account=None,attempt_id=None,scope=broker.SCOPES,error=None,token_error=None,omit_client=False,expected_active=None,identity_hook=None):
        launched=[];callback_errors=[]
        def browser(url):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query);launched.append(query)
            def callback():
                params={'state':query['state'][0]}
                if error:params.update(error)
                else:
                    params['code']='synthetic-code'
                    if not omit_client:params['client_id']=client
                try:urllib.request.urlopen(query['redirect_uri'][0]+'?'+urllib.parse.urlencode(params),timeout=3).read()
                except Exception as exc:callback_errors.append(type(exc).__name__)
            threading.Thread(target=callback,daemon=True).start();return True
        def http(url,data=None,form=False):
            if 'oauth/token' in url:
                if token_error:raise broker.BrokerError(token_error)
                self.assertEqual(data['client_id'],client)
                return {'id_token':'synthetic-id-'+client,'access_token':'synthetic-access-'+client,'refresh_token':'synthetic-refresh-'+client,'scope':scope,'expires_in':3600}
            return {'keys':[]}
        def identity(*args):
            if identity_hook:identity_hook()
            self.assertEqual(args[1],client)
            if expected_active is not None:self.assertEqual(self.b.meta.get('active'),expected_active)
            return {'sub':subject,'email':email}
        with patch.object(broker.webbrowser,'open',side_effect=browser),patch.object(broker,'http_json',side_effect=http),patch.object(broker,'verify_identity',side_effect=identity):
            result=self.b.connect(account=account,mode=mode,attempt_id=attempt_id)
        self.assertFalse(callback_errors);return result,launched[0]
    def active(self):
        result,query=self.flow(client='reg-active',subject='subject-active')
        return copy.deepcopy(self.keys.data),result
    def test_default_add_ignores_all_cached_pending_and_identity_hints(self):
        self.active();self.b.meta['pending_client']='legacy-workspace-bound';self.b.meta['pending_attempts']={'old-attempt':{'client_id':'other-workspace','verified':False}};self.b.save_meta()
        result,query=self.flow(client='reg-new',subject='subject-new',expected_active='reg-active')
        self.assertEqual(query['client_id'],['dynamic_agent_client']);self.assertEqual(query['agent_name_hint'],['Amua']);self.assertNotIn('id_token_hint',query);self.assertNotIn('login_hint',query)
        self.assertEqual(result['registration'],'reg-new');self.assertIn('reg-active',self.keys.data)
    def test_two_accounts_two_workspaces_same_email_are_distinct(self):
        for client,subject in [('reg-A-workspace1','subject-A'),('reg-A-workspace2','subject-A'),('reg-B-workspace1','subject-B')]:self.flow(client,subject)
        accounts=self.b.accounts()['accounts'];self.assertEqual(len(accounts),3);self.assertEqual(len({a['label'] for a in accounts}),3);self.assertEqual({a['email'] for a in accounts},{'same@example.invalid'})
        self.assertEqual({a['registration'] for a in accounts},set(self.keys.data))
        with patch.object(broker.webbrowser,'open',side_effect=AssertionError('No browser on switch')):
            result=self.b.switch('reg-A-workspace1')
        self.assertTrue(result['plan_enabled']);self.assertEqual(result['registration'],'reg-A-workspace1');self.assertEqual(len(self.keys.data),3)
        for client,tokens in self.keys.data.items():self.assertEqual(tokens['client_id'],client)
    def test_explicit_reauthorize_uses_selected_registration_and_hint_only(self):
        self.flow('reg-first','subject-first');self.flow('reg-second','subject-second')
        _,query=self.flow('reg-first','subject-first',mode='reauthorize',account='reg-first',omit_client=True,expected_active='reg-second')
        self.assertEqual(query['client_id'],['reg-first']);self.assertEqual(query['id_token_hint'],['synthetic-id-reg-first']);self.assertNotIn('agent_name_hint',query)
    def test_failed_cancelled_add_preserves_active_credentials(self):
        before,_=self.active();epoch=self.b.meta['epoch']
        with self.assertRaises(broker.BrokerError):self.flow('reg-failed','subject-failed',token_error='http_400_invalid_grant')
        self.assertEqual(self.b.status()['registration'],'reg-active');self.assertEqual(self.keys.data,before);self.assertEqual(self.b.meta['epoch'],epoch)
        with patch.object(broker.webbrowser,'open',side_effect=lambda url:self.b.cancelled.set()),patch.object(broker,'http_json') as network:
            with self.assertRaisesRegex(broker.BrokerError,'cancelled'):self.b.connect(mode='add')
            network.assert_not_called()
        self.assertEqual(self.b.status()['registration'],'reg-active');self.assertEqual(self.keys.data,before)
    def test_pending_retry_requires_specific_attempt_and_never_becomes_default(self):
        self.active()
        with self.assertRaises(broker.BrokerError) as failure:self.flow('reg-unvalidated','new-subject',token_error='http_400_invalid_grant')
        attempt=failure.exception.pending_attempt_id
        self.assertEqual(self.b.accounts()['pending_attempts'][0]['attempt_id'],attempt)
        with self.assertRaisesRegex(broker.BrokerError,'unknown_pending_attempt'):self.b.connect(mode='retry',attempt_id='not-known')
        result,query=self.flow('reg-unvalidated','new-subject',mode='retry',attempt_id=attempt,omit_client=True)
        self.assertEqual(query['client_id'],['reg-unvalidated']);self.assertNotIn('id_token_hint',query);self.assertNotIn('login_hint',query);self.assertEqual(result['registration'],'reg-unvalidated');self.assertFalse(self.b.accounts()['pending_attempts'])
    def test_workspace_denial_has_request_id_and_actionable_add_path(self):
        before,_=self.active()
        with self.assertRaises(broker.AuthorizationError) as failure:
            self.flow(error={'error':'access_denied','error_code':'3p_login_workspace_scope_denied','request_id':'req_synthetic_123'})
        detail=failure.exception.details;self.assertEqual(detail['category'],'workspace_scope_denied');self.assertEqual(detail['code'],'3p_login_workspace_scope_denied');self.assertEqual(detail['request_id'],'req_synthetic_123');self.assertIn('Add another account or workspace',detail['message']);self.assertIn('eligibility',detail['message'])
        self.assertEqual(self.b.status()['registration'],'reg-active');self.assertEqual(self.keys.data,before)
    def test_reauthorization_identity_mismatch_cannot_replace_credentials(self):
        before,_=self.active()
        with self.assertRaisesRegex(broker.BrokerError,'account_mismatch'):self.flow('reg-active','different-subject',mode='reauthorize',account='reg-active')
        self.assertEqual(self.keys.data,before);self.assertEqual(self.b.status()['registration'],'reg-active')
    def test_valid_identity_without_plan_permission_is_retained_and_ai_blocked(self):
        self.active();result,_=self.flow('reg-identity-only','subject-new',scope='openid profile email')
        self.assertTrue(result['connected']);self.assertTrue(result['signed_in']);self.assertFalse(result['plan_enabled'])
        self.assertIn('reg-identity-only',self.keys.data)
        with patch.object(broker,'http_json',side_effect=AssertionError('No inference or refresh allowed')):
            with self.assertRaises(broker.AuthorizationError) as failure:self.b.credentials()
        self.assertEqual(failure.exception.details['category'],'plan_permission_missing')
        self.assertTrue(self.b.switch('reg-active')['plan_enabled'])
    def test_switch_unknown_or_signed_out_does_not_change_active(self):
        self.active();self.b.meta['accounts']['reg-signed-out']={'subject':'other','email':'same@example.invalid','label':'Other'};self.b.save_meta()
        for account in ('not-known','reg-signed-out'):
            with self.assertRaises(broker.BrokerError):self.b.switch(account)
            self.assertEqual(self.b.status()['registration'],'reg-active')
    def test_add_callback_colliding_existing_client_rejects_other_subject(self):
        before,_=self.active()
        with self.assertRaisesRegex(broker.BrokerError,'account_mismatch'):self.flow('reg-active','other-subject',mode='add')
        self.assertEqual(self.keys.data,before);self.assertEqual(self.b.status()['registration'],'reg-active')
    def test_terminal_refresh_clears_only_bad_tokens_keeps_registration(self):
        self.flow('reg-other','subject-other');self.flow('reg-active','subject-active')
        self.keys.data['reg-active']['expires_at']=0;epoch=self.b.meta['epoch']
        with patch.object(broker,'http_json',side_effect=broker.BrokerError('http_400_invalid_grant')):
            with self.assertRaises(broker.AuthorizationError) as failure:self.b.credentials()
        self.assertEqual(failure.exception.details['category'],'reauthorization_required');self.assertNotIn('reg-active',self.keys.data);self.assertIn('reg-other',self.keys.data);self.assertIn('reg-active',self.b.meta['accounts']);self.assertEqual(self.b.meta['epoch'],epoch+1);self.assertFalse(self.b.status()['connected'])
    def test_temporary_refresh_failure_does_not_clear_tokens(self):
        self.active();self.keys.data['reg-active']['expires_at']=0;before=copy.deepcopy(self.keys.data)
        for category in ('network_timeout','http_503','http_400_invalid_client'):
            with patch.object(broker,'http_json',side_effect=broker.BrokerError(category)):
                with self.assertRaises(broker.BrokerError):self.b.credentials()
            self.assertEqual(self.keys.data,before)
    def test_stale_terminal_refresh_cannot_clear_newly_active_connection(self):
        self.active();self.keys.data['reg-active']['expires_at']=0
        def stale(*args,**kwargs):
            self.b.meta['epoch']+=1;self.b.save_meta();raise broker.BrokerError('http_400_invalid_grant')
        with patch.object(broker,'http_json',side_effect=stale):
            with self.assertRaisesRegex(broker.BrokerError,'stale_account_or_cancelled'):self.b.credentials()
        self.assertIn('reg-active',self.keys.data)
    def test_http_eligibility_metadata_and_no_policy_bypass(self):
        payload={'error':{'code':'subscription_sharing_user_not_eligible','message':'PRIVATE DIAGNOSTIC BODY'}}
        error=broker.urllib.error.HTTPError('https://api.openai.com/v1/responses',403,'synthetic',{'x-request-id':'req_synthetic_456'},io.BytesIO(json.dumps(payload).encode()))
        failure=broker.http_failure(error)
        self.assertEqual(failure.details['http_status'],403);self.assertEqual(failure.details['response_shape'],'error_object');self.assertEqual(failure.details['code'],'subscription_sharing_user_not_eligible');self.assertEqual(failure.details['request_id'],'req_synthetic_456');self.assertNotIn('PRIVATE',json.dumps(failure.details));self.assertIn('eligibility',failure.details['message'])
    def test_remove_inactive_revokes_selected_session_preserves_active(self):
        self.flow('reg-inactive','subject-inactive');self.flow('reg-active','subject-active');epoch=self.b.meta['epoch'];active_tokens=copy.deepcopy(self.keys.data['reg-active']);calls=[]
        def remote(url,data=None,form=False):
            # Prove revocation does not hold the metadata lock.
            fd=broker.os.open(self.b.support/'auth-state.lock',broker.os.O_RDWR)
            try:broker.fcntl.flock(fd,broker.fcntl.LOCK_EX|broker.fcntl.LOCK_NB)
            finally:broker.os.close(fd)
            calls.append((url,data))
            return {'revocation_endpoint':broker.AUTH+'/api/accounts/oauth/revoke'} if data is None else {}
        with patch.object(broker,'http_json',side_effect=remote):result=self.b.remove(account='reg-inactive')
        self.assertTrue(result['removed']);self.assertTrue(result['remote_revocation_confirmed']);self.assertEqual(calls[1][1]['client_id'],'reg-inactive');self.assertEqual(calls[1][1]['token'],'synthetic-refresh-reg-inactive')
        self.assertNotIn('reg-inactive',self.keys.data);self.assertEqual(self.keys.data['reg-active'],active_tokens);self.assertEqual(result['registration'],'reg-active');self.assertTrue(result['connected']);self.assertTrue(result['plan_enabled']);self.assertEqual(self.b.meta['epoch'],epoch)
    def test_remove_active_revocation_failure_still_removes_locally(self):
        self.flow('reg-other','subject-other');self.active();epoch=self.b.meta['epoch']
        with patch.object(broker,'http_json',side_effect=broker.BrokerError('network_timeout')):result=self.b.remove(account='reg-active')
        self.assertTrue(result['removed']);self.assertFalse(result['remote_revocation_confirmed']);self.assertFalse(result['connected']);self.assertIsNone(result['registration']);self.assertIsNone(result['account_label']);self.assertIn('not confirmed',result['message']);self.assertEqual(self.b.meta['epoch'],epoch+1)
        self.assertNotIn('reg-active',self.keys.data);self.assertIn('reg-other',self.keys.data);self.assertEqual([a['registration'] for a in result['accounts']],['reg-other'])
    def test_remove_only_selected_pending_attempt_no_revocation_or_credentials(self):
        before,_=self.active();epoch=self.b.meta['epoch'];self.b.meta['pending_client']='pending-one';self.b.meta['pending_attempts']={'attempt-one':{'client_id':'pending-one','verified':False},'attempt-two':{'client_id':'pending-two','verified':False}};self.b.save_meta()
        with patch.object(broker,'http_json',side_effect=AssertionError('Pending removal must not revoke')):result=self.b.remove(attempt_id='attempt-one')
        self.assertTrue(result['removed']);self.assertFalse(result['remote_revocation_attempted']);self.assertIsNone(result['remote_revocation_confirmed']);self.assertEqual([p['attempt_id'] for p in result['pending_attempts']],['attempt-two']);self.assertNotIn('pending_client',self.b.meta);self.assertEqual(self.keys.data,before);self.assertEqual(self.b.meta['epoch'],epoch);self.assertTrue(result['connected'])
    def test_remove_rejects_missing_unknown_and_ambiguous_selection(self):
        before,_=self.active()
        for values in ({},{'account':'reg-active','attempt_id':'some-attempt'},{'account':'unknown'},{'attempt_id':'unknown'},{'account':[]},{'attempt_id':[]}):
            with patch.object(broker,'http_json',side_effect=AssertionError('Invalid remove must not use network')):
                with self.assertRaises(broker.BrokerError):self.b.remove(**values)
            self.assertEqual(self.keys.data,before);self.assertEqual(self.b.status()['registration'],'reg-active')
    def test_late_reauthorization_cannot_resurrect_removed_inactive_connection(self):
        self.flow('reg-target','subject-target');self.flow('reg-active','subject-active');epoch=self.b.meta['epoch'];remover=broker.Broker(self.temp.name,self.keys)
        with self.assertRaisesRegex(broker.BrokerError,'stale_account_or_cancelled'):
            self.flow('reg-target','subject-target',mode='reauthorize',account='reg-target',identity_hook=lambda:remover.remove(account='reg-target'))
        self.assertNotIn('reg-target',self.keys.data);self.assertNotIn('reg-target',self.b.status() and self.b.meta['accounts']);self.assertEqual(self.b.meta['epoch'],epoch);self.assertEqual(self.b.status()['registration'],'reg-active')
    def test_remove_waits_for_refresh_then_revokes_latest_rotated_session(self):
        self.active();self.keys.data['reg-active']['expires_at']=0;refresher=broker.Broker(self.temp.name,self.keys);remover=broker.Broker(self.temp.name,self.keys)
        refreshing=threading.Event();release=threading.Event();removed=threading.Event();failures=[];result=[];revoked=[]
        def remote(url,data=None,form=False):
            if data and data.get('grant_type')=='refresh_token':
                refreshing.set()
                if not release.wait(3):raise AssertionError('Refresh test timed out')
                return {'access_token':'rotated-access','refresh_token':'rotated-refresh','expires_in':3600}
            if data is None:return {'revocation_endpoint':broker.AUTH+'/api/accounts/oauth/revoke'}
            revoked.append(data['token']);return {}
        def refresh():
            try:refresher.credentials()
            except Exception as error:failures.append(type(error).__name__)
        def remove():
            try:result.append(remover.remove(account='reg-active'))
            except Exception as error:failures.append(type(error).__name__)
            finally:removed.set()
        with patch.object(broker,'http_json',side_effect=remote):
            a=threading.Thread(target=refresh);a.start();self.assertTrue(refreshing.wait(2));b=threading.Thread(target=remove);b.start()
            self.assertFalse(removed.wait(.05),'Removal raced past the rotating refresh lock');release.set();a.join(3);b.join(3)
        self.assertFalse(a.is_alive());self.assertFalse(b.is_alive());self.assertFalse(failures);self.assertEqual(revoked,['rotated-refresh']);self.assertTrue(result[0]['removed']);self.assertNotIn('reg-active',self.keys.data);self.assertNotIn('reg-active',remover.meta['accounts'])
    def test_helper_remove_returns_updated_picker_and_status(self):
        self.active()
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(broker,'http_json',side_effect=broker.BrokerError('http_503')):
            result=provider_helper.run({'action':'remove','account':'reg-active'})
        self.assertTrue(result['removed']);self.assertEqual(result['accounts'],[]);self.assertEqual(result['pending_attempts'],[]);self.assertFalse(result['connected']);self.assertFalse(result['plan_enabled'])
    def test_helper_account_actions_and_structured_auth_error(self):
        self.active()
        with patch.object(provider_helper,'Broker',return_value=self.b):
            result=provider_helper.run({'action':'accounts/list'});self.assertEqual(len(result['accounts']),1)
            self.assertEqual(provider_helper.run({'action':'switch','account':'reg-active'})['registration'],'reg-active')
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'connect',return_value={'connected':True}) as connect:
            provider_helper.run({'action':'connect','mode':'reauthorize','account':'reg-active'})
            self.assertEqual(connect.call_args.args,('reg-active',));self.assertEqual(connect.call_args.kwargs['mode'],'reauthorize');self.assertIsNone(connect.call_args.kwargs['attempt_id']);self.assertTrue(callable(connect.call_args.kwargs['emit']))
if __name__=='__main__':unittest.main(verbosity=2)
