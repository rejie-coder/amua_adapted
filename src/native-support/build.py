#!/usr/bin/env python3
"""Isolated source build. Run from any cwd; never modifies installed baseline."""
from pathlib import Path
import hashlib,json,os,plistlib,shutil,subprocess,sys,zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BUILD=ROOT/'build'
APP=ROOT/'Amua.app'
BASE=ROOT/'src/dependencies/baseline-fat-dependencies.jar'
JDK=BUILD/'toolchains/jdk8u512-b09/Contents/Home'
def run(*args):subprocess.run([str(x) for x in args],check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def makejar(path,entries):
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(entries.items()):
   i=zipfile.ZipInfo(name,(2026,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16;z.writestr(i,data)
def main():
 BUILD.mkdir(exist_ok=True)
 tools=BUILD/'tools';tools.mkdir(exist_ok=True)
 ocr=tools/'amua-ocr'
 run('/usr/bin/xcrun','swiftc','-O','-target','x86_64-apple-macosx14.0','-framework','AppKit','-framework','PDFKit','-framework','Vision',HERE/'ocr.swift','-o',ocr)
 run('/usr/bin/codesign','--force','--sign','-',ocr)
 run('/usr/bin/codesign','--verify','--strict',ocr)
 out=BUILD/'classes';shutil.rmtree(out,ignore_errors=True);out.mkdir()
 sources=sorted((ROOT/'src/upstream/src').rglob('*.java'))
 run(JDK/'bin/javac','-encoding','UTF-8','-source','8','-target','8','-cp',BASE,'-d',out,*sources)
 ui=sorted((ROOT/'src/ui').rglob('*.java'))
 if not ui:raise SystemExit('Missing integrated UI source')
 run(JDK/'bin/javac','-encoding','UTF-8','-source','8','-target','8','-cp',str(out)+os.pathsep+str(BASE),'-d',out,*ui)
 entries={}
 # Retain only third-party classes from the fat baseline dependency container.
 packages={p.relative_to(ROOT/'src/upstream/src').parts[0] for p in sources}
 with zipfile.ZipFile(BASE) as z:
  baselineclasses={n for n in z.namelist() if n.endswith('.class') and n.split('/')[0] in packages}
  for n in z.namelist():
   if n.endswith('/') or (n.upper()=='META-INF/MANIFEST.MF' or n.upper().endswith(('.SF','.RSA','.DSA'))) or (n.endswith('.class') and n.split('/')[0] in packages):continue
   entries[n]=z.read(n)
 for p in out.rglob('*'):
  if p.is_file():entries[p.relative_to(out).as_posix()]=p.read_bytes()
 for folder in (ROOT/'src/upstream/resources',):
  for p in folder.rglob('*'):
   if p.is_file():entries[p.relative_to(folder).as_posix()]=p.read_bytes()
 entries['META-INF/MANIFEST.MF']=b'Manifest-Version: 1.0\nMain-Class: main.Amua\n\n'
 jar=BUILD/'Amua_0.3.6.jar';makejar(jar,entries)
 if APP.exists():
  if APP.is_symlink() or not (APP/'Contents/Info.plist').is_file():raise SystemExit('Unrecognized candidate target')
  with (APP/'Contents/Info.plist').open('rb') as f:
   if plistlib.load(f).get('CFBundleIdentifier')!='local.rejie.amua.v333':raise SystemExit('Wrong candidate identity')
 stage=BUILD/'Amua.app';shutil.rmtree(stage,ignore_errors=True)
 res=stage/'Contents/Resources';exe=stage/'Contents/MacOS';res.mkdir(parents=True);exe.mkdir()
 shutil.copy2(jar,res/jar.name)
 (res/'libexec').mkdir()
 shutil.copy2(ocr,res/'libexec/amua-ocr')
 for n in ('bootstrap.js','amua_mcp.py'):shutil.copy2(HERE/n,res/n)
 for n in ('Amua.icns','Amua.png'):shutil.copy2(ROOT/'src/dependencies'/n,res/n)
 shutil.copy2(ROOT/'src/upstream/LICENSE',res/'AMUA-LICENSE.txt')
 shutil.copytree(JDK/'jre',res/'runtime',symlinks=True)
 shutil.copytree(BUILD/'toolchains/python',res/'python',symlinks=True)
 shutil.copytree(BUILD/'toolchains/antigravity',res/'antigravity')
 run('/usr/bin/codesign','--verify','--strict',res/'antigravity/agy')
 lib=res/'pythonlib';lib.mkdir()
 # Bundle pinned pure-Python format parsers with their package notices.
 thirdparty=ROOT/'src/dependencies/python'
 if thirdparty.exists():
  for dependency in thirdparty.iterdir():
   if dependency.name=='__pycache__':continue
   if dependency.is_dir():shutil.copytree(dependency,lib/dependency.name,ignore=shutil.ignore_patterns('__pycache__'))
   else:shutil.copy2(dependency,lib/dependency.name)
 shutil.copy2(ROOT/'src/engine_helper.py',res/'engine_helper.py')
 for name in ('workflow','provider'):
  helper=ROOT/'src'/name/(name+'_helper.py')
  if not helper.exists():helper=ROOT/'src'/(name+'_helper.py')
  if helper.exists():shutil.copy2(helper,res/helper.name)
  if name=='provider':
   for module in helper.parent.glob('*.py'):shutil.copy2(module,res/module.name)
  source=ROOT/'src'/name
  if source.exists():shutil.copytree(source,lib/name,ignore=shutil.ignore_patterns('__pycache__'))
 plist={'CFBundleDevelopmentRegion':'en','CFBundleDisplayName':'Amua (ReyJay) V 3.3.3','CFBundleName':'Amua (ReyJay) V 3.3.3','CFBundleExecutable':'Amua','CFBundleIdentifier':'local.rejie.amua.v333','CFBundlePackageType':'APPL','CFBundleShortVersionString':'3.3.3','CFBundleVersion':'1','CFBundleIconFile':'Amua.icns','NSHighResolutionCapable':True,'LSMultipleInstancesProhibited':True,'LSMinimumSystemVersion':'14.0'}
 with (stage/'Contents/Info.plist').open('wb') as f:plistlib.dump(plist,f)
 (stage/'Contents/PkgInfo').write_text('APPL????')
 run('/usr/bin/xcrun','clang','-arch','x86_64','-mmacosx-version-min=14.0','-O2','-fobjc-arc','-framework','Cocoa',HERE/'launcher.m','-o',exe/'Amua')
 for cache in stage.rglob('__pycache__'):shutil.rmtree(cache)
 from optimize_bundle import optimize
 optimization=optimize(res)
 (BUILD/'size-optimization.json').write_text(json.dumps(optimization,indent=2)+'\n')
 run('/usr/bin/codesign','--force','--sign','-',stage)
 run('/usr/bin/codesign','--verify','--strict',stage)
 target=stage
 if '--stage-only' not in sys.argv:
  if APP.exists():
   backup=BUILD/'Amua.previous.app';shutil.rmtree(backup,ignore_errors=True);APP.rename(backup)
  stage.rename(APP);target=APP
 compiled={p.relative_to(out).as_posix() for p in out.rglob('*.class')}
 manifest={'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').rglob('*') if p.is_file() and p.suffix in ('.java','.py','.js','.swift','.m') and '.git' not in p.parts and '__pycache__' not in p.parts},'upstream_baseline_commit':'fcce8ebbf8bf5ab03a49f7388868f323812ec7f8','source_revision':os.environ.get('GITHUB_SHA',json.loads((ROOT/'src/upstream/ORIGIN.json').read_text())['local_adaptation_history_head']),'ocr':{'source_sha256':sha(HERE/'ocr.swift'),'binary_sha256':sha(target/'Contents/Resources/libexec/amua-ocr'),'architecture':'x86_64','target':'macOS14','maximum_pixels':8000000,'page_timeout_seconds':15},'source_files':len(sources),'ui_files':len(ui),'baseline_jar_sha256':sha(BASE),'candidate_jar_sha256':sha(target/'Contents/Resources'/jar.name),'missing_baseline_engine_classes':sorted(baselineclasses-compiled),'added_engine_classes':sorted(compiled-baselineclasses),'java_release':(res if False else target/'Contents/Resources/runtime/release').read_text() if (target/'Contents/Resources/runtime/release').exists() else (JDK/'release').read_text(),'google_runtime':{'provider':'Antigravity ACP','cli_version':'1.5.9','architecture':'x86_64','binary_sha256':sha(target/'Contents/Resources/antigravity/agy')},'size_optimization':optimization,'python_version':subprocess.check_output([str(target/'Contents/Resources/python/bin/python3'),'--version'],text=True).strip(),'files':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*') if p.is_file() and not p.is_symlink()}}
 (BUILD/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))
if __name__=='__main__':main()
