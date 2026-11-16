"""Static package/source/PE verification. This is not a native execution claim."""
from pathlib import Path
import ast,hashlib,json,struct,zipfile
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'Amua';RES=APP/'Resources'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pe(path):
 data=path.read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0]
 if data[:2]!=b'MZ' or data[offset:offset+4]!=b'PE\0\0':raise RuntimeError('Invalid PE binary: '+path.name)
 machine=struct.unpack_from('<H',data,offset+4)[0];subsystem=struct.unpack_from('<H',data,offset+24+68)[0]
 if machine!=0x8664:raise RuntimeError('Wrong Windows architecture: '+path.name)
 return {'machine':'x86_64','subsystem':subsystem,'sha256':sha(path)}
def main():
 binaries={name:pe(APP/name) for name in ['Amua.exe','Resources/runtime/bin/java.exe','Resources/runtime/bin/javaw.exe','Resources/runtime/bin/amua-javaw.exe','Resources/python/python.exe','Resources/python/pythonw.exe','Resources/gemini/node.exe']}
 from windows_dpi import derive
 if (RES/'runtime/bin/amua-javaw.exe').read_bytes()!=derive((RES/'runtime/bin/javaw.exe').read_bytes()):raise RuntimeError('DPI launcher is not the exact derived runtime copy')
 if binaries['Amua.exe']['subsystem']!=2:raise RuntimeError('Launcher must be a Windows GUI executable')
 required=[(ROOT/'src/dependencies/Amua.png',RES/'Amua.png'),(ROOT/'src/engine_helper.py',RES/'engine_helper.py'),(ROOT/'src/workflow_helper.py',RES/'workflow_helper.py'),(ROOT/'src/native-support/bootstrap.js',RES/'bootstrap.js'),(ROOT/'src/native-support/amua_mcp.py',RES/'amua_mcp.py'),(ROOT/'src/native-support/windows/launch.py',APP/'launch.py')]
 for p in (ROOT/'src/native-support/windows').glob('*.py'):
  if p.name not in ['launch.py','ocr.py']:required.append((p,RES/p.name))
 required.extend([(ROOT/'src/native-support/windows/ocr.py',RES/'libexec/amua-ocr.py'),(ROOT/'src/native-support/windows/windows-ocr.ps1',RES/'libexec/windows-ocr.ps1')])
 for package in ['workflow','provider']:
  for p in (ROOT/'src'/package).rglob('*.py'):required.append((p,RES/'pythonlib'/package/p.relative_to(ROOT/'src'/package)))
 for p in (ROOT/'src/provider').glob('*.py'):required.append((p,RES/p.name))
 for p in (ROOT/'src/dependencies/python').rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:required.append((p,RES/'pythonlib'/p.relative_to(ROOT/'src/dependencies/python')))
 for source,target in required:
  if not target.is_file() or sha(source)!=sha(target):raise RuntimeError('Stale/missing bundled source '+str(target.relative_to(APP)))
  if target.suffix=='.py':ast.parse(target.read_text(encoding='utf-8'))
 if sha(RES/'gemini/package/bundle/gemini.js')!=sha(ROOT/'build/toolchains/gemini/package/bundle/gemini.js'):raise RuntimeError('Stale Gemini bundle')
 expected=json.loads((ROOT/'scripts/expected-classes-3.2.4.json').read_text());allowed={'base/AtomicModelSave.class','base/AtomicModelSave$1.class','base/AtomicModelSave$2.class','v21/McpAccess.class','gui/frmMain.class','gui/frmAboutAmua.class','v21/WorkflowText.class'};changed=[]
 with zipfile.ZipFile(RES/'Amua_0.3.6.jar') as z:
  for name,digest in expected.items():
   if hashlib.sha256(z.read(name)).hexdigest()!=digest:changed.append(name)
  allowed.update(name for name in changed if name=='v21/WorkflowPanel.class' or name.startswith('v21/WorkflowPanel$'))
  display=json.loads((ROOT/'scripts/expected-display-classes-3.3.2.json').read_text())
  for name,digest in display.items():
   if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise RuntimeError('Unexpected display class bytes: '+name)
  allowed.update(display)
  if set(changed)-allowed:raise RuntimeError('Unexpected native application code change: '+str(set(changed)-allowed))
  numerical=[name for name in expected if name.split('/')[0] in ['tree','markov','math'] and name not in display]
  if any(name in changed for name in numerical):raise RuntimeError('Numerical class changed')
 report={'platform':'Windows x64','binaries':binaries,'bundled_sources_verified':len(required),'application_class_files_checked':len(expected),'expected_platform_class_changes':changed,'numerical_classes_byte_identical':len(numerical),'reviewed_display_classes':sorted(display),'authenticode_signed':False}
 (ROOT/'evidence/windows-package-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
