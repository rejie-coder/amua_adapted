from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parents[2];RES=R/'Amua.app/Contents/Resources';JAVA=RES/'runtime/bin/java';JAR=RES/'Amua_0.3.6.jar';JC=R/'build/toolchains/zulu8.98.0.111-ca-jdk8.0.512-macosx_aarch64/Contents/Home/bin/javac'
REPORT={}
def run(name,cmd,**kwargs):
 p=subprocess.run([str(x) for x in cmd],text=True,capture_output=True,timeout=90,**kwargs);(R/'evidence'/(name+'.txt')).write_text(p.stdout+p.stderr);REPORT[name]={'returncode':p.returncode,'stdout':p.stdout[-5000:]};print(name,p.returncode,p.stdout[-1000:],flush=True);return p
run('bridge-unit',[RES/'python/bin/python3',R/'tests/bridge/test_bridge.py'])
classes=R/'build/testclasses';classes.mkdir(exist_ok=True)
sources=[R/'tests/bridge/AtomicSaveCheck.java']+list((R/'tests/ui').glob('*.java'));cp=str(JAR)+':'+str(classes)
run('test-compile',[JC,'-encoding','UTF-8','-cp',cp,'-d',classes,*sources])
for name in ['AtomicSaveCheck','LayoutCheck','ZoomCheck','EngineLayoutCheck']:
 run(name,[JAVA,'-Damua.resources='+str(RES),'-cp',cp,name])
integration=R/'build/support-workflow-integration';integration.mkdir(exist_ok=True)
run('WorkflowIntegrationCheck',[JAVA,'-Duser.dir='+str(integration),'-Damua.support='+str(integration),'-Damua.resources='+str(RES),'-cp',cp,'v21.WorkflowIntegrationCheck',R/'evidence/inputs/D2P cost analysis Cluster care.xlsx',R/'evidence/prior/d2p_tree.png',R/'evidence/prior/d2p_tree_v2.png'])
run('headless',[JAVA,'-Djava.awt.headless=true','-cp',JAR,'jdk.nashorn.tools.Shell',R/'tests/bridge/headless-check.js'])
for name in ['deferred-check','ui-size-check']:
 support=R/'build'/('support-'+name);(support/'bridge').mkdir(parents=True,exist_ok=True)
 p=run(name,[JAVA,'-Damua.support='+str(support),'-Damua.resources='+str(RES),'-Damua.evidence='+str(R/'evidence'),'-cp',JAR,'jdk.nashorn.tools.Shell',R/'tests/bridge'/(name+'.js')],cwd=str(R/'build'))
output=R/'evidence/engine-parity';support=R/'build/support-parity-final';(support/'bridge').mkdir(parents=True,exist_ok=True)
p=run('engine-parity',[JAVA,'-Damua.support='+str(support),'-Damua.resources='+str(RES),'-cp',JAR,'jdk.nashorn.tools.Shell',R/'tests/bridge/parity-driver.js','--','candidate',output],cwd=str(R/'build'))
a=json.loads((output/'original-results.json').read_text());b=json.loads((output/'candidate-results.json').read_text());REPORT['engine-parity']['exact_equal']=a['cases']==b['cases'];(output/'comparison.json').write_text(json.dumps({'exact_equal':a['cases']==b['cases'],'candidate_sha256':hashlib.sha256(JAR.read_bytes()).hexdigest(),'cases':b['cases']},indent=2))
REPORT['candidate_sha256']=hashlib.sha256(JAR.read_bytes()).hexdigest();(R/'evidence/build-engine-checks.json').write_text(json.dumps(REPORT,indent=2));assert all(v['returncode']==0 for v in REPORT.values() if isinstance(v,dict));assert a['cases']==b['cases']
