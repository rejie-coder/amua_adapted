"""Build a portable Windows x64 app with bundled runtimes. Never changes Mac builds."""
from pathlib import Path
import hashlib,json,os,shutil,struct,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build';APP=ROOT/'Amua';TOOLS=BUILD/'toolchains';BASE=ROOT/'src/dependencies/baseline-fat-dependencies.jar'
def run(*args,**kwargs):subprocess.run([str(a) for a in args],check=True,**kwargs)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 BUILD.mkdir(exist_ok=True);classes=BUILD/'classes';shutil.rmtree(classes,ignore_errors=True);classes.mkdir()
 home=Path(os.environ.get('AMUA_JAVA_HOME') or (str(TOOLS/'mac-jdk') if os.name!='nt' else os.environ.get('JAVA_HOME','')))
 javac=home/('bin/javac.exe' if os.name=='nt' else 'bin/javac');java=home/('bin/java.exe' if os.name=='nt' else 'bin/java')
 if not javac.is_file():raise SystemExit('Set AMUA_JAVA_HOME to a Java 8 JDK')
 sources=sorted((ROOT/'src/upstream/src').rglob('*.java'));ui=sorted((ROOT/'src/ui').rglob('*.java'))
 source_list=BUILD/'java-sources.txt';source_list.write_text(''.join(chr(34)+p.as_posix()+chr(34)+'\n' for p in sources),encoding='utf-8')
 run(javac,'-J-Dfile.encoding=UTF-8','-encoding','UTF-8','-source','8','-target','8','-cp',BASE,'-d',classes,'@'+str(source_list))
 ui_list=BUILD/'ui-sources.txt';ui_list.write_text(''.join(chr(34)+p.as_posix()+chr(34)+'\n' for p in ui),encoding='utf-8')
 run(javac,'-J-Dfile.encoding=UTF-8','-encoding','UTF-8','-source','8','-target','8','-cp',str(classes)+os.pathsep+str(BASE),'-d',classes,'@'+str(ui_list))
 entries={};packages={p.relative_to(ROOT/'src/upstream/src').parts[0] for p in sources}
 with zipfile.ZipFile(BASE) as z:
  for n in z.namelist():
   if n.endswith('/') or n.upper()=='META-INF/MANIFEST.MF' or n.upper().endswith(('.SF','.RSA','.DSA')) or n.endswith('.class') and n.split('/')[0] in packages:continue
   entries[n]=z.read(n)
 for p in classes.rglob('*.class'):entries[p.relative_to(classes).as_posix()]=p.read_bytes()
 for p in (ROOT/'src/upstream/resources').rglob('*'):
  if p.is_file():entries[p.relative_to(ROOT/'src/upstream/resources').as_posix()]=p.read_bytes()
 entries['META-INF/MANIFEST.MF']=b'Manifest-Version: 1.0\nMain-Class: main.Amua\n\n'
 jar=BUILD/'Amua_0.3.6.jar'
 with zipfile.ZipFile(jar,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(entries.items()):
   info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.create_system=0;info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,data)
 stage=BUILD/'Amua-stage';shutil.rmtree(stage,ignore_errors=True);stage.mkdir();res=stage/'Resources';res.mkdir()
 shutil.copytree(TOOLS/'jdk8u512-b09-jre',res/'runtime',symlinks=True)
 shutil.copytree(TOOLS/'python',res/'python',symlinks=True,ignore=shutil.ignore_patterns('__pycache__','pip','pip-*.dist-info'))
 shutil.copy2(ROOT/'src/dependencies/Amua.png',res/'Amua.png')
 shutil.copy2(jar,res/jar.name);shutil.copy2(ROOT/'src/native-support/windows/launch.py',stage/'launch.py')
 for name in ['windows_credentials.py','windows_locking.py','windows_process.py']:shutil.copy2(ROOT/'src/native-support/windows'/name,res/name)
 (res/'libexec').mkdir();(BUILD/'tools').mkdir(exist_ok=True)
 for folder in [res/'libexec',BUILD/'tools']:
  shutil.copy2(ROOT/'src/native-support/windows/ocr.py',folder/'amua-ocr.py');shutil.copy2(ROOT/'src/native-support/windows/windows-ocr.ps1',folder/'windows-ocr.ps1')
 for name in ['bootstrap.js','amua_mcp.py']:shutil.copy2(ROOT/'src/native-support'/name,res/name)
 for name in ['workflow_helper.py','engine_helper.py']:shutil.copy2(ROOT/'src'/name,res/name)
 for p in (ROOT/'src/provider').glob('*.py'):shutil.copy2(p,res/p.name)
 lib=res/'pythonlib';lib.mkdir()
 for name in ['workflow','provider']:shutil.copytree(ROOT/'src'/name,lib/name,ignore=shutil.ignore_patterns('__pycache__'))
 for p in (ROOT/'src/dependencies/python').iterdir():
  if p.name=='__pycache__':continue
  if p.is_dir():shutil.copytree(p,lib/p.name,ignore=shutil.ignore_patterns('__pycache__'))
  else:shutil.copy2(p,lib/p.name)
 shutil.copy2(ROOT/'LICENSE',stage/'LICENSE.txt');shutil.copy2(ROOT/'NOTICE.md',stage/'NOTICE.md')
 if (ROOT/'README-WINDOWS.txt').exists():shutil.copy2(ROOT/'README-WINDOWS.txt',stage/'README.txt')
 # PNG image payload inside a standard ICO; no artwork modification.
 icon=(ROOT/'src/upstream/src/images/logo_128.png').read_bytes();(BUILD/'Amua.ico').write_bytes(struct.pack('<HHHBBBBHHII',0,1,1,128,128,0,0,1,32,len(icon),22)+icon)
 rc=BUILD/'Amua.rc';rc.write_text('1 ICON "'+str(BUILD/'Amua.ico').replace('\\','/')+'"\n1 VERSIONINFO\nFILEVERSION 3,2,4,0\nPRODUCTVERSION 3,2,4,0\nFILEOS 0x40004L\nFILETYPE 0x1L\nBEGIN\n BLOCK "StringFileInfo"\n BEGIN\n BLOCK "040904b0"\n BEGIN\n VALUE "FileDescription", "Amua 3.2.4 for Windows"\n VALUE "ProductName", "Amua adapted"\n VALUE "FileVersion", "3.2.4"\n VALUE "OriginalFilename", "Amua.exe"\n END\n END\nEND\n')
 zig=next(TOOLS.glob('zig-*/zig.exe' if os.name=='nt' else 'zig-*/zig'));resource=BUILD/'Amua.res'
 run(zig,'rc','/fo',resource,'--',rc)
 run(zig,'cc','-target','x86_64-windows-gnu','-O2','-g0','-municode','-Wl,--subsystem,windows',ROOT/'src/native-support/windows/launcher.c',resource,'-o',stage/'Amua.exe','-lshell32','-luser32')
 # Canonical PE timestamp/checksum; executable code and resources are unchanged.
 executable=stage/'Amua.exe';image=bytearray(executable.read_bytes());pe_offset=struct.unpack_from('<I',image,0x3c)[0];struct.pack_into('<I',image,pe_offset+8,0);struct.pack_into('<I',image,pe_offset+24+64,0);executable.write_bytes(image)
 for debug in stage.glob('*.pdb'):debug.unlink()
 if APP.exists():
  prior=BUILD/'Amua-previous';shutil.rmtree(prior,ignore_errors=True);APP.rename(prior)
 stage.rename(APP)
 manifest={'version':'3.2.4','platform':'Windows','architecture':'x86_64','authenticode_signed':False,'compiler':subprocess.check_output([str(javac),'-version'],stderr=subprocess.STDOUT,text=True).strip(),'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').rglob('*') if p.is_file() and p.suffix in ['.py','.java','.js','.c'] and '__pycache__' not in p.parts},'files':{p.relative_to(APP).as_posix():sha(p) for p in APP.rglob('*') if p.is_file()},'jar_sha256':sha(APP/'Resources/Amua_0.3.6.jar')}
 with zipfile.ZipFile(APP/'Resources/Amua_0.3.6.jar') as z:
  manifest['jar_payload_sha256']=hashlib.sha256(''.join(name+'\0'+hashlib.sha256(z.read(name)).hexdigest()+'\n' for name in sorted(z.namelist())).encode()).hexdigest()
 data=(APP/'Amua.exe').read_bytes();offset=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,offset+6)[0];section_offset=offset+24+struct.unpack_from('<H',data,offset+20)[0];sections={}
 for i in range(count):
  at=section_offset+40*i;name=data[at:at+8].rstrip(b'\0').decode();size,start=struct.unpack_from('<II',data,at+16);sections[name]=hashlib.sha256(data[start:start+size]).hexdigest()
 manifest['launcher_sections_sha256']=sections
 (BUILD/'windows-build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Built',APP,'with',len(manifest['files']),'files')
if __name__=='__main__':main()
