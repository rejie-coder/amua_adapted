"""Run release checks in isolated profiles and retain exact outputs and failures."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=Path(os.environ.get('AMUA_TEST_APP',ROOT/'Amua.app'));RES=APP/'Contents/Resources';EVIDENCE=ROOT/'evidence'
PYTHON=RES/'python/bin/python3';JAVA=RES/'runtime/bin/java';JAR=RES/'Amua_0.3.6.jar';CLASSES=ROOT/'build/testclasses'
RESULTS={};ENV={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'src')}

def run(name,command,timeout=90,env=None):
    try:
        p=subprocess.run([str(c) for c in command],cwd=ROOT,capture_output=True,text=True,timeout=timeout,env=env or ENV)
        output=p.stdout+p.stderr;code=p.returncode
    except subprocess.TimeoutExpired as error:
        output='Timed out after '+str(timeout)+' seconds';code=124
    (EVIDENCE/(name+'.txt')).write_text(output)
    RESULTS[name]={'exit_code':code,'log':name+'.txt'}
    print(name,code,output[-300:].replace('\n',' '),flush=True)
    return output,code

def main():
    sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src'),str(ROOT/'tests/provider')]
    import model_chat as mc
    from test_model_chat import plan,EVIDENCE as SOURCE
    fixtures=ROOT/'build/test-support';fixtures.mkdir(exist_ok=True);CLASSES.mkdir(exist_ok=True)
    valid=fixtures/'synthetic-valid.amua';valid.write_text(mc.xml_for(plan(),SOURCE))
    p=plan();p['model']['parameters'][0]['expression']=None;unknown=fixtures/'synthetic-unknown.amua';unknown.write_text(mc.xml_for(p,SOURCE))
    variable=ROOT/'tests/hardening/fixtures/variable-updates.amua';context=mc.context(None,{'xml':variable.read_text(),'sha256':'synthetic'})
    corrected=fixtures/'variable-corrected.amua';corrected.write_text(mc.xml_for(mc.local_answer('approve structure',context),context))
    sources=list((ROOT/'tests/ui').glob('*.java'))+[ROOT/'tests/bridge'/name for name in ('AtomicSaveCheck.java','HeadlessEngineCheck.java','HeadlessPresentationCheck.java')]
    _,code=run('compile-checks',[ROOT/'build/toolchains/jdk8u512-b09/Contents/Home/bin/javac','-encoding','UTF-8','-cp',JAR,'-d',CLASSES,*sources])
    if code:raise SystemExit(code)
    cp=str(JAR)+':'+str(CLASSES)
    def java(name,klass,*args):
        support=fixtures/name;support.mkdir(exist_ok=True)
        return run(name,[JAVA,'-Djava.awt.headless=true','-Djava.util.prefs.userRoot='+str(support/'prefs'),'-Duser.dir='+str(support),'-Damua.support='+str(support),'-Damua.resources='+str(RES),'-cp',cp,klass,*args])
    run('provider-final',[PYTHON,'-B',ROOT/'tests/provider/run_in_memory_callbacks.py'])
    run('workflow-final',[PYTHON,'-B','-m','unittest','discover','-s',ROOT/'tests/workflow'])
    run('bridge-final',[PYTHON,'-B','-m','unittest','discover','-s',ROOT/'tests/bridge'])
    run('hardening-engine',[PYTHON,'-B',ROOT/'tests/hardening/check_packaged_engine.py'])
    run('image-chat-pipeline',[PYTHON,'-B',ROOT/'tests/hardening/check_image_chat.py'])
    java('image-chat-controller','v21.ImageChatControllerCheck',EVIDENCE/'image-chat')
    java('chat-attachments','v21.ChatAttachmentsCheck',EVIDENCE/'chat-attachments.png')
    java('atomic-save','AtomicSaveCheck')
    java('native-controller','v21.ModelChatControllerCheck',valid,fixtures,unknown)
    java('hardening-controller','v21.HardeningControllerCheck',variable,corrected,EVIDENCE/'hardening-sidebar.png')
    java('progress-ui','v21.ModelProgressCheck',valid)
    java('approval-wire-types','v21.ApprovalPlanCheck')
    fixtures_model=[ROOT/'evidence/engine-parity'/name for name in ('decision-tree.amua','markov.amua')]
    candidate,code=java('engine-candidate','HeadlessEngineCheck',*fixtures_model)
    original,basecode=run('engine-original',[JAVA,'-Djava.awt.headless=true','-cp',str(ROOT/'src/dependencies/baseline-fat-dependencies.jar')+':'+str(CLASSES),'HeadlessEngineCheck',*fixtures_model])
    cases=lambda output:[line for line in output.splitlines() if line.startswith('RESULT ')]
    equal=not code and not basecode and len(cases(candidate))==8 and cases(candidate)==cases(original)
    RESULTS['engine-equivalence']={'exact_equal':equal,'cases':cases(candidate),'exit_code':0 if equal else 1}
    java('native-presentation','HeadlessPresentationCheck',*fixtures_model)
    for mode in ('original','fixed'):
        run('compact-'+mode,[PYTHON,'-B',ROOT/'tests/hardening/check_compact_display.py','--java',JAVA,'--classes',CLASSES,'--mode',mode])
    for side in ('left','right'):
        a=EVIDENCE/('compact-original-'+side+'.csv');b=EVIDENCE/('compact-fixed-'+side+'.csv')
        equal=a.is_file() and b.is_file() and a.read_bytes()==b.read_bytes()
        RESULTS['compact-'+side+'-parity']={'exit_code':0 if equal else 1,'all_52_coordinates_equal':equal}
    capture=fixtures/'google-ui-capture.json';stub=fixtures/'google-ui-resources';(stub/'python/bin').mkdir(parents=True,exist_ok=True)
    python_link=stub/'python/bin/python3'
    if not python_link.exists():python_link.symlink_to(PYTHON)
    (stub/'provider_helper.py').write_text('import os,sys,json\nfrom pathlib import Path\nc=json.load(sys.stdin);Path(os.environ["AMUA_TEST_CAPTURE"]).write_text(json.dumps(c))\nprint(json.dumps({"ok":True,"provider":"gemini","provider_status":True,"connected":False,"message":"Synthetic Google status"}))\n')
    run('google-accounts-ui',[JAVA,'-Djava.awt.headless=false','-Djava.util.prefs.userRoot='+str(fixtures/'google-ui-prefs'),'-Damua.support='+str(fixtures),'-Damua.resources='+str(stub),'-cp',cp,'v21.GoogleAccountsCheck',capture],env={**ENV,'AMUA_TEST_CAPTURE':str(capture)})
    run('source-package-final',[PYTHON,'-B',ROOT/'tests/bridge/verify-source-package.py','--resources',RES,'--report',EVIDENCE/'source-package-final.json'])
    run('codesign-final',['/usr/bin/codesign','--verify','--deep','--strict',APP])
    run('signature-identity',['/usr/bin/codesign','-dv','--verbose=4',APP])
    (EVIDENCE/'release-checks.json').write_text(json.dumps(RESULTS,indent=2)+'\n')
    # Retain all failures, including native OCR environment failures.
    raise SystemExit(0 if all(r['exit_code']==0 for r in RESULTS.values()) else 1)

if __name__=='__main__':main()
