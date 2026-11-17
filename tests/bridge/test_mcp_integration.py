"""Real stdio RPC and production file bridge with a synthetic headless Swing host."""
import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RES=ROOT/'Amua.app/Contents/Resources'
@unittest.skipUnless((ROOT/'build/testclasses/v21/McpHeadlessHost.class').exists(),'Compile the isolated Java test host first')
class McpIntegrationTests(unittest.TestCase):
 def test_stdio_controls_synthetic_host_and_access_switch(self):
  with tempfile.TemporaryDirectory() as temp:
   profile=Path(temp);host_log=open(profile/'host.log','w')
   host=subprocess.Popen([str(RES/'runtime/bin/java'),'-Djava.awt.headless=true','-Damua.support='+temp,'-Damua.resources='+str(RES),'-Damua.fixture='+str(ROOT/'evidence/engine-parity/decision-tree.amua'),'-cp',str(RES/'Amua_0.3.6.jar')+':'+str(ROOT/'build/testclasses'),'jdk.nashorn.tools.Shell',str(ROOT/'tests/bridge/mcp-headless-host.js')],stdout=host_log,stderr=host_log)
   client=None
   try:
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and not (profile/'status.json').exists():
     if host.poll() is not None:raise AssertionError((profile/'host.log').read_text())
     time.sleep(.05)
    self.assertTrue((profile/'status.json').exists(),(profile/'host.log').read_text())
    wrapper="import importlib.util,sys;from pathlib import Path;s=importlib.util.spec_from_file_location('server',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.SUPPORT=Path(sys.argv[2]);m.BRIDGE=m.SUPPORT/'bridge';m.serve()"
    client=subprocess.Popen([str(RES/'python/bin/python3'),'-B','-c',wrapper,str(RES/'amua_mcp.py'),temp],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    def rpc(ident,method,params=None):
     client.stdin.write(json.dumps({'jsonrpc':'2.0','id':ident,'method':method,'params':params or {}})+'\n');client.stdin.flush();line=client.stdout.readline();self.assertTrue(line,'MCP server stopped unexpectedly');return json.loads(line)
    init=rpc(1,'initialize',{'protocolVersion':'2025-11-25','clientInfo':{'name':'Isolated stdio integration test'}});self.assertEqual(init['result']['serverInfo']['version'],'3.3.3')
    self.assertEqual(len(rpc(2,'tools/list')['result']['tools']),18)
    def call(ident,name,args=None):return rpc(ident,'tools/call',{'name':name,'arguments':args or {}})['result']
    status=call(3,'amua_status')['structuredContent'];self.assertTrue(status['ready']);self.assertEqual(len(status['models']),1)
    summary=call(4,'amua_model_summary')['structuredContent'];self.assertEqual(summary['type'],'decision_tree');self.assertGreater(len(summary['nodes']),3)
    ident=(profile/'field-id.txt').read_text();op=call(5,'amua_set_text',{'id':ident,'text':'after-synthetic'})['structuredContent']['operation_id']
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and (profile/'field-value.txt').read_text()!='after-synthetic':time.sleep(.05)
    self.assertEqual((profile/'field-value.txt').read_text(),'after-synthetic')
    (profile/'mcp-access.properties').write_text('enabled=false\n')
    self.assertTrue(call(6,'amua_model_summary')['isError']);self.assertFalse(call(7,'amua_status')['structuredContent']['access_enabled'])
    # Independently exercise the app-side gate with an authenticated synthetic request.
    (profile/'bridge/direct.request.json').write_text(json.dumps({'id':'direct','method':'model_summary','params':{},'token':'synthetic-bridge-token','deadline':time.time()+5}))
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and not (profile/'bridge/direct.response.json').exists():time.sleep(.05)
    self.assertIn('disabled',json.loads((profile/'bridge/direct.response.json').read_text())['error'])
    (profile/'mcp-access.properties').write_text('enabled=true\n');self.assertTrue(call(8,'amua_status')['structuredContent']['ready'])
   finally:
    if client:
     client.stdin.close();client.wait(timeout=5);client.stdout.close();client.stderr.close()
    (profile/'stop').touch()
    try:host.wait(timeout=5)
    except subprocess.TimeoutExpired:host.kill();host.wait()
    host_log.close()
if __name__=='__main__':unittest.main()
