"""Export the complete portable app only after native Windows checks pass."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'Amua';DIST=ROOT/'dist'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 results=json.loads((ROOT/'evidence/windows-checks.json').read_text());failed=[k for k,v in results.items() if v['exit_code']]
 if failed:raise SystemExit('Native Windows checks failed: '+str(failed))
 DIST.mkdir(exist_ok=True);target=DIST/'Amua-3.2.4-Windows-x64.zip'
 if target.exists():raise SystemExit('Preserve existing ZIP before making another build')
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(APP.rglob('*')):
   if p.is_file():z.write(p,arcname='Amua/'+p.relative_to(APP).as_posix())
 with zipfile.ZipFile(target) as z:
  if z.testzip() is not None:raise RuntimeError('ZIP integrity failed')
  for p in APP.rglob('*'):
   if p.is_file() and hashlib.sha256(z.read('Amua/'+p.relative_to(APP).as_posix())).hexdigest()!=sha(p):raise RuntimeError('ZIP readback mismatch')
 for source,name in [('evidence/windows-checks.json','windows-checks.json'),('evidence/windows-package-verification.json','package-verification.json'),('build/windows-build-manifest.json','build-provenance.json'),('README-WINDOWS.txt','README-WINDOWS.txt')]:shutil.copy2(ROOT/source,DIST/name)
 (DIST/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(DIST.iterdir()) if p.is_file() and p.name!='SHA256SUMS'),encoding='utf-8');print('Native-checked Windows ZIP verified:',target)
if __name__=='__main__':main()
