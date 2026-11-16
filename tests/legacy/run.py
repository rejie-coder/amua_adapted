#!/usr/bin/env python3
"""Run standalone original-engine regressions against this work-package bundle."""
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
RESOURCES=ROOT/'Amua.app/Contents/Resources'
JAR=RESOURCES/'Amua_0.3.6.jar'
JAVA=RESOURCES/'runtime/bin/java'
OUT=ROOT/'evidence'
WORK=ROOT/'build/legacy'
WORK.mkdir(parents=True,exist_ok=True)
(WORK/'home').mkdir(exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
initial=sha(JAR)
commands=[
    [str(JAVA),'-Djava.awt.headless=true','-Dtest.output='+str(OUT/'legacy-math.json'),'-cp',str(JAR),'jdk.nashorn.tools.Shell',str(ROOT/'tests/legacy/math-check.js')],
    [str(JAVA),'-Dtest.root='+str(ROOT),'-Duser.home='+str(WORK/'home'),'-cp',str(JAR),'jdk.nashorn.tools.Shell',str(ROOT/'tests/legacy/workflow-check.js')]
]
records=[]
for name,command in zip(['math','workflows'],commands):
    start=time.monotonic()
    env={'PATH':'/usr/bin:/bin','HOME':str(WORK/'home'),'LANG':'en_US.UTF-8','TMPDIR':os.environ.get('TMPDIR','/private/tmp')}
    result=subprocess.run(command,cwd=WORK,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    (OUT/('legacy-'+name+'.log')).write_text(result.stdout)
    records.append({'suite':name,'command':command,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),'result':json.loads((OUT/('legacy-'+name+'.json')).read_text())})
report={'date':time.strftime('%Y-%m-%d'),'platform':platform.platform(),'architecture':platform.machine(),'candidate_jar_sha256':initial,'candidate_unchanged_during_checks':initial==sha(JAR),'java_version':subprocess.run([str(JAVA),'-version'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout,'scripts':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tests/legacy').glob('*.js')},'fixtures':{p.name:sha(p) for p in (ROOT/'evidence/engine-parity').glob('*.amua')},'runs':records}
(OUT/'legacy-regression.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'tests':sum(r['result']['tests'] for r in records),'failures':sum(r['result']['failures'] for r in records),'candidate_unchanged':report['candidate_unchanged_during_checks']}))
raise SystemExit(0 if all(r['exit_code']==0 for r in records) and report['candidate_unchanged_during_checks'] else 1)
