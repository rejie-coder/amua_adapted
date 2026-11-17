"""Regressions for disconnect/reconnect/add/switch and genuine provider reasons."""
import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
import gemini_acp as ga
from broker import BrokerError
class GoogleConnections(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(ga,'SUPPORT',Path(self.tmp.name));self.patch.start()
  self.runtime=patch.object(ga,'runtime',return_value=['synthetic']);self.runtime.start()
  self.factory=patch.object(ga,'ACP');self.acp=self.factory.start();self.client=self.acp.return_value
  self.client.info={'authMethods':[{'id':'oauth-personal'}],'agentCapabilities':{'auth':{'logout':{}}}}
  self.client.call.return_value={};self.b=ga.GeminiBroker()
 def tearDown(self):self.factory.stop();self.runtime.stop();self.patch.stop();self.tmp.cleanup()
 def add(self):
  self.b.connect(mode='add');return self.b.recipient()['registration']
 def test_add_two_accounts_switch_preserves_connections_and_isolates_profiles(self):
  a=self.add();first=self.b.recipient();b=self.add()
  self.assertNotEqual(a,b);self.assertEqual(len(self.b.accounts()['accounts']),2)
  homes=[call.args[1] for call in self.acp.call_args_list]
  self.assertNotEqual(homes[0],homes[1])
  scopes=[ga.environment(h,h/'settings')['ANTIGRAVITY_CREDENTIAL_SCOPE'] for h in homes]
  self.assertNotEqual(*scopes)
  self.b.switch(a);self.assertEqual(self.b.recipient(),first)
 def test_disconnect_then_reconnect_selected_and_add_another(self):
  a=self.add();old=self.b.recipient()
  self.b.logout();self.assertFalse(self.b.status()['connected'])
  with self.assertRaisesRegex(BrokerError,'gemini_auth_required'):self.b.recipient()
  self.assertEqual(self.client.call.call_args.args[0],'logout')
  self.b.connect(a,mode='reauthorize')
  self.assertTrue(self.b.status()['connected']);self.assertEqual(self.b.recipient()['registration'],a)
  self.assertNotEqual(old,self.b.recipient());self.assertEqual(len(self.b.accounts()['accounts']),1)
  self.assertNotEqual(self.add(),a)
 def test_success_waits_for_verified_session_and_emits_progress(self):
  events=[];self.b.connect(mode='add',emit=events.append)
  self.assertEqual(self.client.call.call_args.args[0],'authenticate');self.client.new_session.assert_called_once()
  self.assertEqual([e['phase'] for e in events],['browser','verifying'])
 def test_failed_auth_preserves_existing_active_account_and_lists_retry(self):
  a=self.add();self.client.call.side_effect=BrokerError('gemini_sign_in_failed')
  with self.assertRaisesRegex(BrokerError,'gemini_sign_in_failed'):self.b.connect(mode='add')
  self.assertEqual(self.b.recipient()['registration'],a)
  self.assertEqual(sum(not p['signed_in'] for p in self.b.accounts()['accounts']),1)
 def test_failed_session_never_marks_connection_signed_in(self):
  self.client.new_session.side_effect=BrokerError('gemini_auth_required')
  with self.assertRaises(BrokerError):self.b.connect(mode='add')
  self.assertFalse(self.b.status()['connected']);self.assertFalse(self.b.accounts()['accounts'][0]['signed_in'])
 def test_remove_only_selected_connection_and_picker_payload(self):
  a=self.add();b=self.add();result=self.b.remove(a)
  self.assertTrue(result['removed']);self.assertNotIn('provider_status',result)
  self.assertEqual([p['registration'] for p in result['accounts']],[b])
  self.assertEqual(self.b.recipient()['registration'],b)
 def test_unknown_profile_path_and_unsigned_switch_rejected(self):
  for value in ['../../other','google_bad',None]:
   with self.assertRaises(BrokerError):self.b.home(value)
  with self.assertRaises(BrokerError):self.b.switch('unknown')
 def test_concurrent_signin_cannot_replace_another(self):
  with self.b.operation():
   with self.assertRaisesRegex(BrokerError,'gemini_connection_busy'):ga.GeminiBroker().connect(mode='add')
 def test_connection_metadata_private_and_contains_no_credentials(self):
  self.add();p=self.b.meta_path
  self.assertEqual(p.stat().st_mode&0o777,0o600)
  data=p.read_text()
  for key in ['access_token','refresh_token','oauth_creds']:self.assertNotIn(key,data)
 def test_retired_client_and_other_auth_failure_remain_distinct(self):
  retired=ga.provider_error('authenticate',{'code':-32000,'message':'This client is no longer supported for Gemini Code Assist for individuals.'})
  failed=ga.provider_error('authenticate',{'code':-32000,'message':'Account is ineligible. https://example.invalid/auth?code=secret access_token=secret'})
  self.assertEqual(str(retired),'gemini_client_retired');self.assertEqual(str(failed),'gemini_sign_in_failed')
  self.assertIn('Account is ineligible',failed.details['message']);self.assertNotIn('secret',failed.details['message'])
if __name__=='__main__':unittest.main()
