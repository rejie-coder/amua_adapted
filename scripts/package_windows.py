"""Export the complete portable app only after native Windows checks pass."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'Amua';DIST=ROOT/'dist'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require_checks(results):
 required={'gemini-runtime','package-static','compile-output-guard-stub','compile-stop-guard-stub','windows-native','native-ocr-diagnostic','provider-regression','test_public_intake','test_mixed_formats','test_ocr','test_hardening','test_batch_precision','compile-native-tests','prepare-image-fixture','atomic-saves','image-sidebar','chat-clipboard-drop','progress-sidebar','approval-wire-types','windows-original-engine','baseline-original-engine','engine-equivalence'}
 if set(results)!=required:raise SystemExit('Incomplete/unexpected native Windows check groups')
 failed=[k for k,v in results.items() if v['exit_code']]
 if failed:raise SystemExit('Native Windows checks failed: '+str(failed))
 if len(results['engine-equivalence'].get('exact_outputs',[]))!=8:raise SystemExit('Missing original-engine equivalence evidence')
def main():
 results=json.loads((ROOT/'evidence/windows-checks.json').read_text());require_checks(results)
 DIST.mkdir(exist_ok=True);target=DIST/'Amua-3.3.1-Windows-x64.zip'
 if target.exists():raise SystemExit('Preserve existing ZIP before making another build')
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(APP.rglob('*')):
   if p.is_file():z.write(p,arcname='Amua/'+p.relative_to(APP).as_posix())
 with zipfile.ZipFile(target) as z:
  if z.testzip() is not None:raise RuntimeError('ZIP integrity failed')
  for p in APP.rglob('*'):
   if p.is_file() and hashlib.sha256(z.read('Amua/'+p.relative_to(APP).as_posix())).hexdigest()!=sha(p):raise RuntimeError('ZIP readback mismatch')
 for source,name in [('evidence/windows-checks.json','windows-checks.json'),('evidence/windows-package-verification.json','package-verification.json'),('build/windows-build-manifest.json','build-provenance.json'),('README-WINDOWS.txt','README-WINDOWS.txt'),('TEST_REPORT.md','TEST_REPORT.md'),('RED_TEAM.md','RED_TEAM.md')]:shutil.copy2(ROOT/source,DIST/name)
 from export_windows_source import export
 export()
 (DIST/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(DIST.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8');print('Native-checked Windows ZIP verified:',target)
if __name__=='__main__':main()
