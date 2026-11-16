#!/usr/bin/env python3
"""Verify packaged parser/provider sources and new UI classes without any account/network action."""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
R=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,default=R/'Amua.app/Contents/Resources');p.add_argument('--report',type=Path,default=R/'evidence/source-package-check.json');a=p.parse_args();res=a.resources.resolve()
checks=[]
def same(source,target):
 assert target.is_file(),'Missing packaged file: '+str(target.relative_to(res))
 expected=hashlib.sha256(source.read_bytes()).hexdigest();actual=hashlib.sha256(target.read_bytes()).hexdigest();assert expected==actual,'Stale packaged source: '+str(target.relative_to(res));checks.append({'file':str(target.relative_to(res)),'sha256':actual})
same(R/'src/workflow_helper.py',res/'workflow_helper.py')
same(R/'src/engine_helper.py',res/'engine_helper.py')
for name in ('bootstrap.js','amua_mcp.py'):same(R/'src/native-support'/name,res/name)
for package in ('workflow','provider'):
 for source in (R/'src'/package).rglob('*.py'):
  if '__pycache__' in source.parts:continue
  same(source,res/'pythonlib'/package/source.relative_to(R/'src'/package))
 for source in (R/'src/provider').glob('*.py'):
  if package=='provider':same(source,res/source.name)
for source in (R/'src/dependencies/python').rglob('*'):
 if source.is_file() and '__pycache__' not in source.parts:same(source,res/'pythonlib'/source.relative_to(R/'src/dependencies/python'))
if (R/'src/native-support/ocr.swift').is_file():
 native=res/'libexec/amua-ocr';assert native.is_file(),'Missing bundled OCR helper'
 same(R/'build/tools/amua-ocr',native)
 probe=subprocess.run([str(native),'--pdf','/nonexistent-synthetic-fixture.pdf','--page','0','--max-pixels','8000000'],text=True,capture_output=True,timeout=5)
 assert probe.returncode==0 and not probe.stderr,'OCR helper preflight failed'
 assert json.loads(probe.stdout)['reason_category']=='invalid_arguments','OCR helper protocol mismatch'
with zipfile.ZipFile(res/'Amua_0.3.6.jar') as z:
 for compiled in (R/'build/classes').rglob('*.class'):
  name=compiled.relative_to(R/'build/classes').as_posix();assert z.read(name)==compiled.read_bytes(),'Compiled class differs: '+name
 for source in (R/'src/ui').glob('*.java'):
  assert 'v21/'+source.stem+'.class' in z.namelist(),'Missing UI class '+source.stem
run=subprocess.run([str(res/'python/bin/python3'),'-B','-c',"import sys;sys.path[:0]=sys.argv[1:];import pypdf;import workflow.batches,workflow.mixed_formats;import transport;print('pypdf='+pypdf.__version__)",str(res),str(res/'pythonlib')],text=True,capture_output=True,timeout=20)
assert run.returncode==0,run.stderr
result={'resources':str(res),'checked_source_files':len(checks),'source_files':checks,'imports':run.stdout.strip(),'candidate_jar_sha256':hashlib.sha256((res/'Amua_0.3.6.jar').read_bytes()).hexdigest(),'account_or_network_actions':False};a.report.write_text(json.dumps(result,indent=2)+'\n');print('PASS source/package correspondence',len(checks),'files;',run.stdout.strip())
