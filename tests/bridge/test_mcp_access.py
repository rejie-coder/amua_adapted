import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mcp320',ROOT/'src/native-support/amua_mcp.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class McpAccessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.previous=m.SUPPORT;m.SUPPORT=Path(self.tmp.name)
 def tearDown(self):m.SUPPORT=self.previous;self.tmp.cleanup()
 def test_protocol_and_metadata_never_record_tool_arguments(self):
  result=m.rpc({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','clientInfo':{'name':'Hermes Test'}}})
  self.assertEqual(result['serverInfo']['version'],'3.3.3');self.assertEqual(len(m.handle({'method':'tools/list'})['tools']),18)
  with patch.object(m,'request',return_value={'accepted':True}):m.execute('set_text',{'id':'c1','text':'PRIVATE USER MODEL TEXT'})
  data=json.loads((m.SUPPORT/'mcp-last-client.json').read_text());self.assertEqual(set(data),{'client','method','at_utc'});self.assertEqual(data['client'],'Hermes Test');self.assertNotIn('PRIVATE',json.dumps(data))
 def test_disable_blocks_existing_clients_and_reenable_restores(self):
  path=m.SUPPORT/'mcp-access.properties';path.write_text('enabled=false\n')
  with patch.object(m,'request',side_effect=AssertionError('Disabled client must not reach app')):
   with self.assertRaisesRegex(RuntimeError,'disabled'):m.execute('new_model',{'type':'decision_tree'})
   self.assertFalse(m.execute('status',{})['access_enabled'])
  path.write_text('enabled=true\n')
  with patch.object(m,'request',return_value={'ready':True}) as request:self.assertTrue(m.execute('status',{})['ready']);request.assert_called_once()
 def test_invalid_access_setting_fails_closed(self):
  (m.SUPPORT/'mcp-access.properties').write_text('invalid')
  self.assertFalse(m.access_enabled())
 def test_self_test_is_read_only_and_requires_ready_app(self):
  marker=json.dumps({'client':'Actual connected agent','method':'amua_status'});(m.SUPPORT/'mcp-last-client.json').write_text(marker)
  with patch.object(m,'request',return_value={'ready':True,'responsive':True}) as request:
   result=m.self_test();self.assertTrue(result['ok']);self.assertEqual(result['tools_available'],18);self.assertEqual(request.call_args.args[0],'status');self.assertEqual((m.SUPPORT/'mcp-last-client.json').read_text(),marker)
  (m.SUPPORT/'mcp-access.properties').write_text('enabled=false\n')
  with patch.object(m,'request',side_effect=AssertionError('No app access when disabled')):self.assertFalse(m.self_test()['ok'])
 def test_isolated_release_identity(self):
  self.assertEqual(m.APP,ROOT/'Amua.app');self.assertEqual(m.VERSION,'3.3.3')
if __name__=='__main__':unittest.main()
