"""Windows candidate supervisor. Started by Amua.exe inside a kill-on-close Job Object."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RESOURCES=ROOT/'Resources'
sys.path.insert(0,str(RESOURCES))
import windows_locking as locks

def support_path():
 override=os.environ.get('AMUA_TEST_SUPPORT')
 if override:return Path(override).resolve()
 base=os.environ.get('LOCALAPPDATA')
 if not base:raise RuntimeError('User application storage is unavailable')
 return Path(base)/'Amua-v3.2.4'
def alert(message):
 import ctypes
 ctypes.windll.user32.MessageBoxW(None,message,'Amua 3.2.4 for Windows',0x10)
def activate(support):
 token=(support/'bridge.token').read_text();request={'method':'activate','params':{'files':[str(Path(p).resolve()) for p in sys.argv[1:] if Path(p).suffix.lower()=='.amua']},'token':token,'deadline':time.time()+30}
 target=support/'bridge'/(uuid.uuid4().hex+'.request.json');temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(request),encoding='utf-8');temporary.replace(target)
def main():
 if sys.platform!='win32':raise RuntimeError('This launcher requires Windows')
 support=support_path();support.mkdir(parents=True,exist_ok=True);bridge=support/'bridge';bridge.mkdir(exist_ok=True)
 with (support/'app.lock').open('a+b') as lock:
  try:locks.flock(lock,locks.LOCK_EX|locks.LOCK_NB)
  except BlockingIOError:activate(support);return 0
  (support/'bridge.token').write_text(uuid.uuid4().hex+uuid.uuid4().hex,encoding='utf-8')
  log=support/'Amua.log'
  if log.exists() and log.stat().st_size>2*1024*1024:
   previous=support/'Amua.previous.log';previous.unlink(missing_ok=True);log.replace(previous)
  java=RESOURCES/'runtime/bin/javaw.exe';jar=RESOURCES/'Amua_0.3.6.jar'
  if not java.is_file() or not jar.is_file():raise RuntimeError('The complete application must be extracted before launching')
  args=[str(java),'-Xms64m','-Xmx2g','-XX:+UseG1GC','-Dsun.net.client.defaultConnectTimeout=4000','-Dsun.net.client.defaultReadTimeout=4000','-Damua.support='+str(support),'-Damua.resources='+str(RESOURCES),'-cp',str(jar),'jdk.nashorn.tools.Shell',str(RESOURCES/'bootstrap.js'),'--']+[str(Path(p).resolve()) for p in sys.argv[1:] if Path(p).suffix.lower()=='.amua']
  allowed=('SystemRoot','SystemDrive','WINDIR','ProgramData','ProgramFiles','ProgramFiles(x86)','CommonProgramFiles','CommonProgramFiles(x86)' ,'USERPROFILE','LOCALAPPDATA','APPDATA','TEMP','TMP','USERNAME','USERDOMAIN','PROCESSOR_ARCHITECTURE')
  environment={k:os.environ[k] for k in allowed if k in os.environ};environment['PATH']=str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32');environment['PYTHONUTF8']='1';environment['PYTHONIOENCODING']='utf-8';environment['PYTHONNOUSERSITE']='1';environment['PYTHONDONTWRITEBYTECODE']='1'
  with log.open('ab') as output:
   child=subprocess.Popen(args,cwd=str(support),env=environment,stdin=subprocess.DEVNULL,stdout=output,stderr=output,creationflags=subprocess.CREATE_NO_WINDOW)
   return child.wait()
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception:alert('Amua could not start. Extract the complete candidate to a local folder and try again. Manual models and account credentials have not been deleted.');raise SystemExit(1)
