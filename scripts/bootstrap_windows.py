"""Download hash-verified Windows x64 tools; never accepts personal credentials."""
from pathlib import Path
import hashlib,json,os,shutil,tarfile,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'build/toolchains'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def get(item,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 expected=item.get('sha256') or item.get('checksum') or item.get('shasum');url=item.get('url') or item.get('link') or item.get('tarball')
 if target.exists() and sha(target)==expected:return
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Amua-Windows-build/3.3.2'}),timeout=90) as source,target.with_suffix('.download').open('wb') as output:shutil.copyfileobj(source,output)
 partial=target.with_suffix('.download')
 if sha(partial)!=expected:partial.unlink();raise RuntimeError('Toolchain checksum mismatch')
 partial.replace(target)
def unpack(path):
 TOOLS.mkdir(parents=True,exist_ok=True);base=TOOLS.resolve()
 if zipfile.is_zipfile(path):
  with zipfile.ZipFile(path) as z:
   for n in z.namelist():
    if base not in (base/n).resolve().parents and (base/n).resolve()!=base:raise RuntimeError('Unsafe archive path')
   z.extractall(TOOLS)
 else:
  with tarfile.open(path) as t:
   for n in t.getmembers():
    if base not in (base/n.name).resolve().parents and (base/n.name).resolve()!=base:raise RuntimeError('Unsafe archive path')
   t.extractall(TOOLS)
def main():
 if os.name!='nt':raise SystemExit('Native bootstrap runs on Windows; Mac cross-builds use retained verified tools')
 spec=json.loads((ROOT/'scripts/toolchains-windows.json').read_text())
 for name,archive,sentinel in [('java','java.zip','jdk8u512-b09-jre/bin/java.exe'),('jdk','jdk.zip','jdk8u512-b09/bin/javac.exe'),('python','python.tar.gz','python/python.exe'),('zig_windows','zig.zip','zig-x86_64-windows-0.17.1/zig.exe')]:
  if not (TOOLS/sentinel).is_file():
   path=ROOT/'build/downloads'/archive;get(spec[name],path);unpack(path)
 baseline=json.loads((ROOT/'scripts/toolchains-intel.json').read_text())['baseline'];get(baseline,ROOT/baseline['target'])
 print('Verified Windows runtime/compiler inputs ready.')
if __name__=='__main__':main()
