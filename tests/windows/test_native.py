"""Actual Windows APIs, packaged helpers and owned processes; no real account requests."""
from pathlib import Path
import ctypes as C,importlib.util,json,os,subprocess,sys,tempfile,time,unittest,uuid
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'Amua';RES=APP/'Resources';PYTHON=RES/'python/python.exe'
sys.path[:0]=[str(RES),str(RES/'pythonlib'),str(ROOT/'tests/provider'),str(ROOT/'tests')]
import windows_locking as locks
import windows_process as processes
from windows_credentials import CredentialStore,CredentialError
import model_chat as mc
class NativeWindows(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
 def helper(self,name,data):
  result=subprocess.run([str(PYTHON),'-B',str(RES/name)],input=json.dumps(data,ensure_ascii=False),encoding='utf-8',capture_output=True,env={**os.environ,'PYTHONPATH':str(RES/'pythonlib'),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},timeout=25)
  self.assertEqual(result.returncode,0,result.stderr[:1000]);return json.loads(result.stdout)
 def test_win64_structure_layouts(self):
  self.assertEqual(C.sizeof(processes.STARTUPINFO),104);self.assertEqual(C.sizeof(processes.EXTENDED_LIMITS),144)
 def test_read_only_process_liveness(self):
  self.assertTrue(processes.pid_alive(os.getpid()));self.assertFalse(processes.pid_alive(2147483646));self.assertTrue(processes.pid_alive(os.getpid()))
 def test_real_credential_manager_chunking_rotation_and_cleanup(self):
  store=CredentialStore();account='amua-test-'+uuid.uuid4().hex;value={'token':'TEST-ONLY-'+('abc'*4000),'unicode':'සිංහල ü'}
  try:
   self.assertIsNone(store.read(account));store.write(account,value);self.assertEqual(store.read(account),value);store.write(account,{'replacement':True});self.assertEqual(store.read(account),{'replacement':True})
   with self.assertRaises(CredentialError):store.write(account,{'oversize':'x'*70000})
   self.assertEqual(store.read(account),{'replacement':True})
  finally:store.delete(account)
  self.assertIsNone(store.read(account))
 def test_native_file_lock_blocks_other_process_then_releases(self):
  path=self.folder/'lock';fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);locks.flock(fd,locks.LOCK_EX|locks.LOCK_NB)
  code='import sys,os;sys.path.insert(0,sys.argv[1]);import windows_locking as w;f=os.open(sys.argv[2],os.O_RDWR);\ntry:w.flock(f,w.LOCK_EX|w.LOCK_NB)\nexcept BlockingIOError:sys.exit(7)'
  try:
   args=[str(PYTHON),'-c',code,str(RES),str(path)];self.assertEqual(subprocess.run(args).returncode,7)
  finally:os.close(fd)
  self.assertEqual(subprocess.run(args).returncode,0)
 def test_owned_engine_job_has_no_console_or_shell_and_completes(self):
  with tempfile.TemporaryFile() as output:
   child=processes.Child([str(PYTHON),'-c','import sys;print(sys.argv[1])','space & ü value'],output)
   try:self.assertEqual(child.wait(10),0);output.seek(0);self.assertIn('space & ü value',output.read().decode('utf-8'))
   finally:child.close()
 def test_job_kills_child_if_owner_is_killed(self):
  parent=self.folder/'owner.py';parent.write_text('import sys,time,tempfile\nsys.path.insert(0,sys.argv[1])\nfrom windows_process import Child\nf=tempfile.TemporaryFile();c=Child([sys.executable,"-c","import time;time.sleep(60)"],f)\nprint(c.pid,flush=True)\ntime.sleep(60)\n',encoding='utf-8')
  owner=subprocess.Popen([str(PYTHON),str(parent),str(RES)],stdout=subprocess.PIPE,text=True,encoding='utf-8');pid=None
  try:
   pid=int(owner.stdout.readline());self.assertTrue(processes.pid_alive(pid));owner.kill();owner.wait(5)
   end=time.monotonic()+5
   while processes.pid_alive(pid) and time.monotonic()<end:time.sleep(.05)
   self.assertFalse(processes.pid_alive(pid),'Engine survived its owner job handle')
  finally:
   if owner.poll() is None:owner.kill();owner.wait(5)
   if pid and processes.pid_alive(pid):subprocess.run(['taskkill.exe','/PID',str(pid),'/T','/F'],capture_output=True)
   owner.stdout.close()
 def test_packaged_workflow_intake_unicode_and_save_reopen(self):
  source=self.folder/'Data ü.csv';source.write_text('p,cost,qaly\n0.7,1000,2.0\n',encoding='utf-8')
  result=self.helper('workflow_helper.py',{'action':'intake','paths':[str(source)]});self.assertTrue(result['ok'],result);project=result['project'];target=self.folder/'Draft ü.amuax'
  save=self.helper('workflow_helper.py',{'action':'save','project':project,'path':str(target)});self.assertTrue(save['ok'],save);self.assertIn('Windows',save['saved']['durability'])
  opened=self.helper('workflow_helper.py',{'action':'open','path':str(target)});self.assertTrue(opened['ok'],opened);self.assertEqual(opened['project']['provenance'],project['provenance'])
 def test_packaged_image_proposal_review_and_engine(self):
  from test_image_chat import image_chat
  preview,proposal,broker=image_chat(self.folder);self.assertEqual(len(broker.calls),1);self.assertEqual(len(proposal['proposal']['model']['nodes']),7)
  evidence=mc.context(None,{'xml':proposal['candidate_xml'],'sha256':'test'});structure=mc.local_answer('approve structure',evidence);evidence=mc.context(None,{'xml':mc.xml_for(structure,evidence),'sha256':'test'});reviewed=mc.local_answer('approve inputs',evidence)
  result=self.helper('engine_helper.py',{'action':'engine-analysis','operation':'run','xml':mc.xml_for(reviewed,evidence),'target_hash':'test'})
  self.assertTrue(result['ok'],result);self.assertTrue(result['completed']);actual={(r['strategy'],r['outcome']):r['value'] for r in result['results']}
  self.assertAlmostEqual(actual['Drug A','Cost ($)'],850);self.assertAlmostEqual(actual['Drug A','Effectiveness (QALYs)'],1.55);self.assertAlmostEqual(actual['Drug B','Cost ($)'],1520);self.assertAlmostEqual(actual['Drug B','Effectiveness (QALYs)'],2.2)
 def test_original_pending_image_inputs_stay_blocked(self):
  from test_image_chat import image_chat
  _,proposal,_=image_chat(self.folder);result=self.helper('engine_helper.py',{'action':'engine-analysis','operation':'run','xml':proposal['candidate_xml'],'target_hash':'test'});self.assertFalse(result['ok'])
 def test_output_budget_kills_native_child_and_removes_snapshot(self):
  import shutil
  resources=self.folder/'Output guard resources';(resources/'runtime/bin').mkdir(parents=True)
  shutil.copy2(ROOT/'build/windows-output-stub.exe',resources/'runtime/bin/java.exe')
  for name in ['engine_helper.py','windows_process.py']:shutil.copy2(RES/name,resources/name)
  request={'action':'engine-analysis','operation':'run','xml':'<test-only/>','target_hash':'test'}
  before=set(Path(tempfile.gettempdir()).glob('amua-analysis-*'))
  result=subprocess.run([str(PYTHON),str(resources/'engine_helper.py')],input=json.dumps(request),text=True,encoding='utf-8',capture_output=True,timeout=15)
  self.assertEqual(result.returncode,0,result.stderr);answer=json.loads(result.stdout);self.assertFalse(answer['ok']);self.assertIn('output limit',answer['error']['message'].lower())
  self.assertEqual(set(Path(tempfile.gettempdir()).glob('amua-analysis-*'))-before,set())
 def test_forced_stop_removes_confidential_snapshot_files(self):
  import shutil
  resources=self.folder/'Stop guard resources';(resources/'runtime/bin').mkdir(parents=True)
  shutil.copy2(ROOT/'build/windows-slow-stub.exe',resources/'runtime/bin/java.exe')
  for name in ['engine_helper.py','windows_process.py']:shutil.copy2(RES/name,resources/name)
  track=self.folder/'snapshot-path.txt';environment={**os.environ,'AMUA_TEST_SNAPSHOT_TRACK':str(track)}
  helper=subprocess.Popen([str(PYTHON),str(resources/'engine_helper.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=environment)
  model=None
  try:
   helper.stdin.write(json.dumps({'action':'engine-analysis','operation':'run','xml':'CONFIDENTIAL TEST INPUT','target_hash':'test'}));helper.stdin.close();deadline=time.monotonic()+10
   while not track.exists() and time.monotonic()<deadline:time.sleep(.05)
   self.assertTrue(track.exists(),'Slow child did not receive the snapshot');model=Path(track.read_text());self.assertTrue(model.exists())
   helper.kill();helper.wait(5);deadline=time.monotonic()+5
   while model.exists() and time.monotonic()<deadline:time.sleep(.05)
   self.assertFalse(model.exists(),'Forced termination retained confidential XML');self.assertFalse(model.with_name('command.json').exists(),'Forced termination retained command data')
  finally:
   if helper.poll() is None:helper.kill();helper.wait(5)
   if model and model.parent.exists():shutil.rmtree(model.parent,ignore_errors=True)
   helper.stdout.close();helper.stderr.close()
 def test_native_app_front_door_and_single_instance(self):
  support=self.folder/'Private profile ü';environment={**os.environ,'AMUA_TEST_SUPPORT':str(support),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONPATH':'X:/untrusted-must-be-cleared','PYTHONHOME':'X:/untrusted-must-be-cleared'}
  app=subprocess.Popen([str(APP/'Amua.exe')],env=environment);java_pid=None
  try:
   deadline=time.monotonic()+45;state={}
   while time.monotonic()<deadline:
    status=support/'status.json'
    if status.exists():
     try:state=json.loads(status.read_text(encoding='utf-8'))
     except (ValueError,OSError):state={}
    if state.get('ready'):break
    if app.poll() is not None:
     log=(support/'Amua.log').read_text(encoding='utf-8',errors='replace') if (support/'Amua.log').exists() else 'No Java startup log'
     self.fail('GUI exited early: '+str(app.returncode)+' '+log[-3000:])
    time.sleep(.2)
   log=(support/'Amua.log').read_text(encoding='utf-8',errors='replace') if (support/'Amua.log').exists() else ''
   self.assertTrue(state.get('ready'),log[-3000:]);java_pid=state['pid'];self.assertTrue(processes.pid_alive(java_pid))
   self.assertFalse((support/'%SystemDrive%').exists(),'Windows cache path expanded into the app profile')
   # Verify via its actual read-only MCP protocol, then activate existing instance.
   safe_env={**os.environ,'AMUA_TEST_SUPPORT':str(support),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
   status=subprocess.run([str(PYTHON),str(RES/'amua_mcp.py'),'--call','status'],capture_output=True,text=True,encoding='utf-8',env=safe_env,timeout=20)
   self.assertEqual(status.returncode,0,status.stderr);self.assertTrue(processes.pid_alive(java_pid),'Read-only status terminated Java')
   second=subprocess.run([str(APP/'Amua.exe')],env=safe_env,timeout=15);self.assertEqual(second.returncode,0);self.assertEqual(json.loads((support/'status.json').read_text())['pid'],java_pid)
  finally:
   if app.poll() is None:app.kill();app.wait(10)
   if java_pid:
    deadline=time.monotonic()+5
    while processes.pid_alive(java_pid) and time.monotonic()<deadline:time.sleep(.1)
    self.assertFalse(processes.pid_alive(java_pid),'GUI survived native launcher job closure')
if __name__=='__main__':unittest.main(verbosity=2)
