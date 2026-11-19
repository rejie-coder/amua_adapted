import json,subprocess,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'src/dependencies/python'))
from workflow.batches import selection_plan,intake_batch
class BatchPrecision(unittest.TestCase):
 def test_actual_nashorn_json_roundtrip_preserves_file_metadata(self):
  java=R/'build/toolchains/zulu8.98.0.111-ca-jdk8.0.512-macosx_aarch64/Contents/Home/bin/java'
  with tempfile.TemporaryDirectory() as td:
   source=Path(td).resolve()/'source.txt';source.write_text('Selected synthetic source')
   plan=selection_plan([source]);entry=plan['entries'][0]
   for key in ('device','inode','mtime_ns'):self.assertIsInstance(entry[key],str)
   expression="var r=new java.io.BufferedReader(new java.io.InputStreamReader(java.lang.System.in,'UTF-8'));print(JSON.stringify(JSON.parse(r.readLine())));"
   script=Path(td)/'roundtrip.js';script.write_text(expression)
   result=subprocess.run([str(java),'jdk.nashorn.tools.Shell',str(script)],input=json.dumps(plan)+'\n',text=True,capture_output=True,check=True)
   echoed=json.loads(result.stdout);self.assertEqual(echoed['entries'][0]['mtime_ns'],str(source.stat().st_mtime_ns))
   parsed=intake_batch(echoed);self.assertEqual(parsed['selection']['entries'][0]['status'],'inventoried');self.assertEqual(len(parsed['project']['provenance']['files']),1)
 def test_changed_file_after_nashorn_safe_snapshot_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   source=Path(td).resolve()/'source.txt';source.write_text('old');plan=json.loads(json.dumps(selection_plan([source])));source.write_text('new changed bytes')
   parsed=intake_batch(plan);self.assertEqual(parsed['selection']['entries'][0]['status'],'failed');self.assertEqual(parsed['pending'],0)
if __name__=='__main__':unittest.main()
