import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
from broker import BrokerError
import gemini_acp as ga
import provider_helper as ph

FAKE='''import json,sys
for line in sys.stdin:
 q=json.loads(line);m=q.get('method');i=q.get('id');r={}
 if m=='initialize':r={'protocolVersion':1,'authMethods':[{'id':'oauth-personal'}]}
 elif m=='session/new':r={'sessionId':'test'}
 elif m=='session/prompt':
  print(json.dumps({'jsonrpc':'2.0','method':'session/update','params':{'sessionId':'test','update':{'sessionUpdate':'agent_thought_chunk','content':{'type':'text','text':'PRIVATE'}}}}),flush=True)
  print(json.dumps({'jsonrpc':'2.0','method':'session/update','params':{'sessionId':'test','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'{"intent":"review","message":"Review","questions":[]}'}}}}),flush=True)
  r={'stopReason':'end_turn'}
 print(json.dumps({'jsonrpc':'2.0','id':i,'result':r}),flush=True)
'''
class GeminiTests(unittest.TestCase):
 def test_protocol_roundtrip_filters_thoughts(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);stub=p/'fake.py';stub.write_text(FAKE)
   c=ga.ACP([sys.executable,str(stub)],p/'home',timeout=2)
   try:
    c.new_session();events=[]
    out=c.call('session/prompt',{'sessionId':c.session,'prompt':[]},events.append)
    self.assertEqual(out['stopReason'],'end_turn');self.assertEqual(len(events),1);self.assertNotIn('PRIVATE',str(events))
   finally:c.close()
   self.assertIsNotNone(c.p.poll())
 def test_stalled_child_stopped(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(BrokerError,'model_chat_stalled'):
    ga.ACP([sys.executable,'-c','import time; time.sleep(5)'],Path(d),timeout=.1)
 def test_environment_does_not_inherit_billing_or_injection(self):
  with patch.dict(os.environ,{'GEMINI_API_KEY':'secret','GOOGLE_API_KEY':'secret','NODE_OPTIONS':'bad','GOOGLE_GEMINI_BASE_URL':'bad','GOOGLE_APPLICATION_CREDENTIALS':'bad'}):
   env=ga.environment(Path('/isolated'),Path('/settings'))
   for key in ['GEMINI_API_KEY','GOOGLE_API_KEY','NODE_OPTIONS','GOOGLE_GEMINI_BASE_URL','GOOGLE_APPLICATION_CREDENTIALS']:self.assertNotIn(key,env)
   self.assertEqual(env['GEMINI_CLI_HOME'],'/isolated')
 def test_claude_and_unknown_never_fall_back(self):
  with patch.object(ph,'Broker') as broker:
   for provider,error in [('claude','claude_subscription_unavailable'),('other','unknown_provider')]:
    with self.assertRaisesRegex(BrokerError,error):ph.run({'provider':provider,'action':'status'})
   broker.assert_not_called()
 def test_gemini_routes_without_chatgpt_credentials(self):
  with patch.object(ga,'GeminiBroker') as gemini,patch.object(ph,'Broker') as chatgpt:
   gemini.return_value.status.return_value={'provider':'gemini'}
   self.assertEqual(ph.run({'provider':'gemini','action':'status'}),{'provider':'gemini'})
   chatgpt.assert_not_called()
 def test_recipient_rechecked_before_launch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(ga,'SUPPORT',Path(d)):
   b=ga.GeminiBroker();b.marker.write_text('{"registration":"new"}');b.approved_recipient={'registration':'old'}
   with patch.object(ga,'ACP') as acp:
    with self.assertRaisesRegex(BrokerError,'recipient_changed'):b.request('gemini-cli-default',[])
    acp.assert_not_called()
 def test_native_proposal_uses_shared_validation(self):
  from test_model_chat import plan
  sample=plan();sample['model']['nodes'][2]['sources']=[]
  with tempfile.TemporaryDirectory() as d,patch.object(ga,'SUPPORT',Path(d)),patch.object(ga,'runtime',return_value=['unused']),patch.object(ga,'ACP') as factory:
   b=ga.GeminiBroker();b.marker.write_text('{"registration":"synthetic"}')
   c=factory.return_value;c.session='s';c.info={}
   def call(method,params,emit):
    self.assertEqual(method,'session/prompt');emit({'event':'delta','text':json.dumps(sample)})
    return {'stopReason':'end_turn'}
   c.call.side_effect=call
   cmd={'provider':'gemini','action':'chat-preview','text':'Create a synthetic tree','paths':[],'budget_session_id':'gemini_test_session'}
   preview=ph.run(cmd)
   cmd.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model=preview['resolved_model'],approved_max_calls=1)
   result=ph.run(cmd)
   self.assertTrue(result['ok']);self.assertIn('<tree>',result['candidate_xml']);self.assertEqual(c.call.call_count,1)
   sample['model']['nodes'][2]['probability']='Java.type("bad")'
   with self.assertRaises(BrokerError):ph.run(cmd)
 def test_tools_and_api_auth_disabled(self):
  self.assertEqual(ga.SETTINGS['tools']['core'],['__amua_no_agent_tools__'])
  self.assertEqual(ga.SETTINGS['security']['auth']['selectedType'],'oauth-personal')
  self.assertFalse(ga.SETTINGS['hooksConfig']['enabled'])
if __name__=='__main__':unittest.main()
