import json, os, sys, tempfile, unittest, subprocess, signal, time
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
def ready(b):
 ident='google_'+'a'*32
 b.write({'version':1,'active':ident,'accounts':{ident:{'label':'Synthetic Google connection','signed_in':True,'generation':'synthetic'}}})
 return ident

class GeminiTests(unittest.TestCase):
 def test_protocol_roundtrip_filters_thoughts(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);stub=p/'fake.py';stub.write_text(FAKE)
   c=ga.ACP([sys.executable,'-B',str(stub)],p/'home',timeout=2)
   try:
    c.new_session();events=[]
    out=c.call('session/prompt',{'sessionId':c.session,'prompt':[]},events.append)
    self.assertEqual(out['stopReason'],'end_turn');self.assertEqual(len(events),2);self.assertEqual(events[0],{'event':'inference_progress','phase':'thinking'});self.assertNotIn('PRIVATE',str(events))
   finally:c.close()
   self.assertIsNotNone(c.p.poll())
 def test_agent_permission_and_filesystem_requests_denied(self):
  stub=FAKE.replace("elif m=='session/prompt':", """elif m=='session/prompt':
  print(json.dumps({'jsonrpc':'2.0','id':'permission','method':'session/request_permission','params':{}}),flush=True)
  answer=json.loads(sys.stdin.readline())
  assert answer['result']['outcome']['outcome']=='cancelled'
  print(json.dumps({'jsonrpc':'2.0','id':'file','method':'fs/read_text_file','params':{'path':'private'}}),flush=True)
  answer=json.loads(sys.stdin.readline())
  assert answer['error']['code']==-32601""")
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);script=p/'fake.py';script.write_text(stub)
   c=ga.ACP([sys.executable,'-B',str(script)],p/'home',timeout=2)
   try:
    c.new_session();events=[]
    self.assertEqual(c.call('session/prompt',{'sessionId':c.session,'prompt':[]},events.append)['stopReason'],'end_turn')
   finally:c.close()
 def test_stalled_child_stopped(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(BrokerError,'model_chat_stalled'):
    ga.ACP([sys.executable,'-B','-c','import time; time.sleep(5)'],Path(d),timeout=.1)
 def test_environment_does_not_inherit_billing_or_injection(self):
  with patch.dict(os.environ,{'GEMINI_API_KEY':'secret','GOOGLE_API_KEY':'secret','NODE_OPTIONS':'bad','GOOGLE_GEMINI_BASE_URL':'bad','GOOGLE_APPLICATION_CREDENTIALS':'bad'}):
   env=ga.environment(Path('/isolated'),Path('/settings'))
   for key in ['GEMINI_API_KEY','GOOGLE_API_KEY','NODE_OPTIONS','GOOGLE_GEMINI_BASE_URL','GOOGLE_APPLICATION_CREDENTIALS']:self.assertNotIn(key,env)
   self.assertEqual(env['HOME'],str(Path('/isolated')))
   self.assertNotIn('GEMINI_CLI_HOME',env)
   self.assertTrue(env['ANTIGRAVITY_CREDENTIAL_SCOPE'].startswith('amua-'))
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
   b=ga.GeminiBroker();ready(b);b.approved_recipient={'registration':'old'}
   with patch.object(ga,'ACP') as acp:
    with self.assertRaisesRegex(BrokerError,'recipient_changed'):b.request('gemini-cli-default',[])
    acp.assert_not_called()
 def test_native_proposal_uses_shared_validation(self):
  from test_model_chat import plan
  sample=plan();sample['model']['nodes'][2]['sources']=[]
  with tempfile.TemporaryDirectory() as d,patch.object(ga,'SUPPORT',Path(d)),patch.object(ga,'runtime',return_value=['unused']),patch.object(ga,'ACP') as factory:
   b=ga.GeminiBroker();ready(b)
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
  self.assertIn('command(*)',ga.SETTINGS['permissions']['deny'])
  self.assertIn('read_file(*)',ga.SETTINGS['permissions']['deny'])
  self.assertEqual(ga.SETTINGS['auth']['type'],'oauth-personal')

 @unittest.skipIf(sys.platform == 'win32', 'POSIX process groups')
 def test_close_stops_owned_process_group(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);stub=p/'fake.py'
   stub.write_text("import subprocess,os\nchild=subprocess.Popen([__import__('sys').executable,'-B','-c','import time; time.sleep(60)'])\nopen('child.pid','w').write(str(child.pid))\n"+FAKE)
   c=ga.ACP([sys.executable,'-B',str(stub)],p/'home',timeout=3)
   child=int((c.cwd/'child.pid').read_text())
   self.assertEqual(os.getpgid(child),c.p.pid)
   c.close()
   for _ in range(50):
    state=subprocess.run(['ps','-o','stat=','-p',str(child)],capture_output=True,text=True).stdout.strip()
    if not state or state.startswith('Z'):break
    time.sleep(.02)
   self.assertTrue(not state or state.startswith('Z'),state)
   self.assertNotIn(c,ga._active_clients)
 @unittest.skipIf(sys.platform == 'win32', 'POSIX helper SIGTERM cleanup')
 def test_helper_sigterm_stops_cli(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);stub=p/'fake.py';stub.write_text(FAKE)
   script="import sys,time;sys.path.insert(0,sys.argv[1]);import gemini_acp as ga;from pathlib import Path;c=ga.ACP([sys.executable,'-B',sys.argv[2]],Path(sys.argv[3]),timeout=3);print(c.p.pid,flush=True);time.sleep(60)"
   helper=subprocess.Popen([sys.executable,'-B','-c',script,str(Path(ga.__file__).parent),str(stub),str(p/'home')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   try:
    child=int(helper.stdout.readline().strip());helper.terminate();helper.communicate(timeout=8)
    self.assertEqual(helper.returncode,128+signal.SIGTERM)
    self.assertNotEqual(subprocess.run(['ps','-p',str(child)],capture_output=True).returncode,0)
   finally:
    if helper.poll() is None:helper.kill();helper.communicate()
 def test_packaged_macos_runtime_and_handshake(self):
  if sys.platform != 'darwin':self.skipTest('Mac bundle')
  res=Path(os.environ.get('AMUA_TEST_APP',Path(__file__).resolve().parents[2]/'Amua.app'))/'Contents/Resources'
  if not (res/'antigravity/agy').is_file():self.skipTest('Bundle not built')
  with patch.object(ga,'__file__',str(res/'gemini_acp.py')):
   command=ga.runtime()
  self.assertEqual(Path(command[0]).name,'agy')
  self.assertEqual(subprocess.check_output([command[0],'--version'],text=True).strip(),'1.5.9')
  with tempfile.TemporaryDirectory() as d:
   c=ga.ACP(command,Path(d),timeout=45)
   try:
    self.assertEqual(c.info['protocolVersion'],1)
    self.assertIn('oauth-personal',[a['id'] for a in c.info['authMethods']])
   finally:c.close()

if __name__=='__main__':unittest.main()
