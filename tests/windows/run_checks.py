"""Run native Windows tests and preserve exact failures, skips and engine evidence."""
from pathlib import Path
import json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'Amua';RES=APP/'Resources';JAVA=RES/'runtime/bin/java.exe';PYTHON=RES/'python/python.exe';OUT=ROOT/'evidence';RESULTS={}
ENV={**os.environ,'PYTHONPATH':str(RES)+os.pathsep+str(RES/'pythonlib')+os.pathsep+str(ROOT/'src'),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'}
def run(name,args,timeout=120):
 try:p=subprocess.run([str(a) for a in args],cwd=ROOT,env=ENV,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout);code=p.returncode;log=p.stdout+p.stderr
 except subprocess.TimeoutExpired as e:code=124;log='Timed out after '+str(timeout)+' seconds'
 (OUT/(name+'.txt')).write_text(log,encoding='utf-8');RESULTS[name]={'exit_code':code,'log':name+'.txt'};print(name,code,log[-280:].replace('\n',' '),flush=True);return log,code

def main():
 OUT.mkdir(exist_ok=True)
 run('package-static',[PYTHON,'-B',ROOT/'scripts/verify_windows_package.py'])
 zig=next((ROOT/'build/toolchains').glob('zig-*/zig.exe'));run('compile-output-guard-stub',[zig,'cc','-target','x86_64-windows-gnu','-O2',ROOT/'tests/windows/output_stub.c','-o',ROOT/'build/windows-output-stub.exe'])
 run('compile-stop-guard-stub',[zig,'cc','-target','x86_64-windows-gnu','-DSLOW_ONLY','-O2',ROOT/'tests/windows/output_stub.c','-o',ROOT/'build/windows-slow-stub.exe'])
 run('windows-native',[PYTHON,'-B','-m','unittest','discover','-v','-s',ROOT/'tests/windows','-p','test_native.py'],180)
 run('native-ocr-diagnostic',[PYTHON,'-B',ROOT/'tests/windows/report_ocr.py'])
 run('provider-regression',[PYTHON,'-B',ROOT/'tests/windows/run_provider.py'])
 for module in ['test_public_intake.py','test_mixed_formats.py','test_ocr.py','test_hardening.py','test_batch_precision.py']:
  run(module[:-3],[PYTHON,'-B','-m','unittest','discover','-v','-s',ROOT/'tests/workflow','-p',module])
 jdk=ROOT/'build/toolchains/jdk8u512-b09';javac=jdk/'bin/javac.exe';classes=ROOT/'build/windows-testclasses';classes.mkdir(exist_ok=True)
 sources=list((ROOT/'tests/ui').glob('*.java'))+[ROOT/'tests/bridge'/n for n in ['AtomicSaveCheck.java','HeadlessEngineCheck.java','HeadlessPresentationCheck.java']]
 argfile=ROOT/'build/windows-test-sources.txt';argfile.write_text(''.join('"'+p.as_posix()+'"\n' for p in sources),encoding='utf-8')
 _,compile_code=run('compile-native-tests',[javac,'-encoding','UTF-8','-cp',RES/'Amua_0.3.6.jar','-d',classes,'@'+str(argfile)])
 cp=str(RES/'Amua_0.3.6.jar')+os.pathsep+str(classes)
 def java(name,klass,*args):
  import tempfile
  support=Path(tempfile.mkdtemp(prefix='amua-native-ui-'))
  try:return run(name,[JAVA,'-Djava.awt.headless=true','-Djava.util.prefs.userRoot='+str(support/'prefs'),'-Damua.support='+str(support),'-Damua.resources='+str(RES),'-cp',cp,klass,*args])
  finally:
   import shutil
   shutil.rmtree(support,ignore_errors=True)
 if not compile_code:
  # Produce the same controlled image responses for the actual native sidebar.
  image=OUT/'image-chat';image.mkdir(exist_ok=True)
  fixture=ROOT/'tests/windows/make_image_fixture.py';run('prepare-image-fixture',[PYTHON,'-B',fixture])
  java('atomic-saves','AtomicSaveCheck')
  java('image-sidebar','v21.ImageChatControllerCheck',image)
  java('chat-clipboard-drop','v21.ChatAttachmentsCheck',OUT/'windows-chat-attachments.png')
  java('progress-sidebar','v21.ModelProgressCheck',image/'reviewed.amua')
  java('approval-wire-types','v21.ApprovalPlanCheck')
  models=[ROOT/'evidence/engine-parity'/n for n in ['decision-tree.amua','markov.amua']]
  actual,c=java('windows-original-engine','HeadlessEngineCheck',*models)
  baseline,b=run('baseline-original-engine',[JAVA,'-Djava.awt.headless=true','-cp',str(ROOT/'src/dependencies/baseline-fat-dependencies.jar')+os.pathsep+str(classes),'HeadlessEngineCheck',*models])
  rows=lambda log:[line for line in log.splitlines() if line.startswith('RESULT ')]
  equivalent=not c and not b and len(rows(actual))==8 and rows(actual)==rows(baseline);RESULTS['engine-equivalence']={'exit_code':0 if equivalent else 1,'exact_outputs':rows(actual)}
 (OUT/'windows-checks.json').write_text(json.dumps(RESULTS,indent=2)+'\n',encoding='utf-8')
 failures=[k for k,v in RESULTS.items() if v['exit_code']]
 print('Failed groups:',failures);raise SystemExit(1 if failures else 0)
if __name__=='__main__':main()
