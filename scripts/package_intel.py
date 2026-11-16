"""Create and read back an Intel installation DMG plus corresponding source."""
from pathlib import Path
import hashlib,json,os,plistlib,shutil,subprocess,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist';NAME='Amua-3.2.4-macOS-Intel.dmg'
def run(*args):
 result=subprocess.run([str(v) for v in args],capture_output=True,text=True)
 if result.returncode:raise RuntimeError(str(args[0])+': '+result.stderr.strip())
 return result.stdout
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def contents(folder):
 return {p.relative_to(folder).as_posix():('link:'+os.readlink(p) if p.is_symlink() else sha(p)) for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
def main():
 verification=json.loads((ROOT/'evidence/release-verification.json').read_text())
 if verification.get('application_classes_match_local_candidate')!=717:raise SystemExit('Release verification required before packaging')
 DIST.mkdir(exist_ok=True);app=ROOT/'Amua.app';dmg=DIST/NAME
 if dmg.exists():raise SystemExit('DMG already exists; preserve it before making a new release artifact')
 for binary in ['Contents/MacOS/Amua','Contents/Resources/runtime/bin/java','Contents/Resources/python/bin/python3','Contents/Resources/libexec/amua-ocr']:
  if run('/usr/bin/lipo','-archs',app/binary).strip()!='x86_64':raise SystemExit('Unexpected architecture: '+binary)
 run('/usr/bin/codesign','--verify','--deep','--strict',app)
 archive=DIST/'Amua-3.2.4-macOS-Intel.zip'
 if archive.exists():raise SystemExit('ZIP already exists; preserve it before making another artifact')
 run('/usr/bin/ditto','-c','-k','--keepParent','--sequesterRsrc',app,archive)
 with tempfile.TemporaryDirectory(prefix='amua-zip-readback-') as unpacked:
  run('/usr/bin/ditto','-x','-k',archive,unpacked)
  if contents(app)!=contents(Path(unpacked)/'Amua.app'):raise RuntimeError('ZIP readback differs from checked app')
 with tempfile.TemporaryDirectory(prefix='amua-dmg-') as temporary:
  staging=Path(temporary)/'image';staging.mkdir();shutil.copytree(app,staging/'Amua.app',symlinks=True);(staging/'Applications').symlink_to('/Applications');shutil.copy2(ROOT/'docs/INSTALL.txt',staging/'INSTALL.txt');shutil.copy2(ROOT/'LICENSE',staging/'LICENSE.txt')
  run('/usr/bin/hdiutil','create','-volname','Amua 3.2.4 Intel','-srcfolder',staging,'-format','UDZO','-ov',dmg)
 run('/usr/bin/hdiutil','verify',dmg)
 info=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-plist',str(dmg)]));mount=next(Path(e['mount-point']) for e in info['system-entities'] if e.get('mount-point'))
 try:
  if not (mount/'Applications').is_symlink() or os.readlink(mount/'Applications')!='/Applications':raise RuntimeError('Applications install link missing')
  if contents(app)!=contents(mount/'Amua.app'):raise RuntimeError('DMG app differs from the checked app')
  run('/usr/bin/codesign','--verify','--deep','--strict',mount/'Amua.app')
 finally:run('/usr/bin/hdiutil','detach',mount)
 from export_source import export
 source=export()
 provenance={'version':'3.2.4','architecture':'x86_64','minimum_macos':'14.0','signature':'ad hoc; not notarized','source_commit':os.environ.get('GITHUB_SHA'),'dmg_readback_identical':True,'dmg_signature_verified':True,'build_manifest':json.loads((ROOT/'build/build-manifest.json').read_text()),'verification':json.loads((ROOT/'evidence/release-verification.json').read_text())}
 (DIST/'build-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');shutil.copy2(ROOT/'docs/INSTALL.txt',DIST/'INSTALL.txt');shutil.copy2(ROOT/'evidence/release-verification.json',DIST/'release-verification.json')
 files=sorted(p for p in DIST.iterdir() if p.is_file() and p.name!='SHA256SUMS');(DIST/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files));print('Verified DMG and corresponding source ready:',dmg)
if __name__=='__main__':main()
