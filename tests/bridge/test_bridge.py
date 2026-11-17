import importlib.util,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'src/native-support/amua_mcp.py'
spec=importlib.util.spec_from_file_location('candidate',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BridgeTests(unittest.TestCase):
 def test_status_bad_shapes(self):
  with tempfile.TemporaryDirectory() as d:
   old=m.SUPPORT;m.SUPPORT=Path(d)
   try:
    for value in ('{','[]','null','true','{"heartbeat_ms":"x"}','{"running":true,"ready":true,"pid":true,"heartbeat_ms":1,"instance":"x"}'):
     (Path(d)/'status.json').write_text(value); self.assertFalse(m.state()['responsive'])
   finally:m.SUPPORT=old
 def test_status_live_stale(self):
  with tempfile.TemporaryDirectory() as d:
   old=m.SUPPORT;m.SUPPORT=Path(d)
   try:
    value={'running':True,'ready':True,'pid':os.getpid(),'heartbeat_ms':time.time()*1000,'instance':'test'}
    f=Path(d)/'status.json';f.write_text(json.dumps(value));self.assertTrue(m.state()['responsive'])
    value['heartbeat_ms']=1;f.write_text(json.dumps(value));self.assertEqual(m.state()['state'],'unresponsive')
   finally:m.SUPPORT=old
 def test_protocol_errors_and_continuation(self):
  lines=['{','[]',json.dumps({'jsonrpc':'2.0','id':1,'method':'unknown'}),json.dumps({'jsonrpc':'2.0','id':2,'method':'ping','params':[]}),json.dumps({'jsonrpc':'2.0','method':'ping'}),json.dumps({'jsonrpc':'2.0','id':3,'method':'ping'})]
  p=subprocess.run([sys.executable,str(P)],input='\n'.join(lines)+'\n',text=True,capture_output=True,check=True)
  replies=[json.loads(x) for x in p.stdout.splitlines()];self.assertEqual(len(replies),5)
  self.assertEqual([x['error']['code'] for x in replies[:4]],[-32700,-32600,-32601,-32602]);self.assertEqual(replies[-1]['result'],{})
 def test_identity(self):
  self.assertIn('Amua-v3.3.3',str(m.SUPPORT));self.assertEqual(m.APP,ROOT/'Amua.app')
if __name__=='__main__':unittest.main()
