"""Fetch pinned Apple Silicon build inputs, verifying SHA256 before extraction/use."""
from pathlib import Path
import platform,hashlib,json,shutil,subprocess,tarfile,tempfile,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def download(item,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and sha(target)==item['sha256']:return
 request=urllib.request.Request(item['url'],headers={'User-Agent':'Amua-pinned-build/3.3.3'})
 with urllib.request.urlopen(request,timeout=60) as source,target.with_suffix('.download').open('wb') as dest:shutil.copyfileobj(source,dest)
 temporary=target.with_suffix('.download')
 if sha(temporary)!=item['sha256']:temporary.unlink();raise RuntimeError('SHA256 mismatch: '+target.name)
 temporary.replace(target)
def extract(archive,destination):
 destination.mkdir(parents=True,exist_ok=True);base=destination.resolve()
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar.getmembers():
   target=(base/member.name).resolve()
   if target!=base and base not in target.parents:raise RuntimeError('Archive escapes destination')
   if member.issym() or member.islnk():
    link=(target.parent/member.linkname).resolve() if member.issym() else (base/member.linkname).resolve()
    if link!=base and base not in link.parents:raise RuntimeError('Archive link escapes destination')
  tar.extractall(base)
def main():
 if platform.system() != 'Darwin' or platform.machine() != 'arm64':
  raise SystemExit('Build on a native Apple Silicon Mac.')
 manifest=json.loads((ROOT/'scripts/toolchains-arm64.json').read_text());baseline=ROOT/manifest['baseline']['target'];tools=ROOT/'build/toolchains';tools.mkdir(parents=True,exist_ok=True)
 download(manifest['baseline'],baseline)
 for name,sentinel in [('jdk',tools/'zulu8.98.0.111-ca-jdk8.0.512-macosx_aarch64/Contents/Home/bin/javac'),('python',tools/'python/bin/python3')]:
  if not sentinel.exists():
   archive=ROOT/'build/downloads'/(name+'.tar.gz');download(manifest[name],archive);extract(archive,tools)
 if sha(baseline)!=manifest['baseline']['sha256']:raise RuntimeError('Baseline container is not the approved version')
 for command in [[tools/'zulu8.98.0.111-ca-jdk8.0.512-macosx_aarch64/Contents/Home/bin/javac','-version'],[tools/'python/bin/python3','--version']]:subprocess.run([str(c) for c in command],check=True)
 (ROOT/'build/toolchain-provenance.json').write_text(json.dumps({'inputs':manifest},indent=2)+'\n')
 subprocess.run([str(tools/'python/bin/python3'),'-B',str(ROOT/'src/native-support/bootstrap_antigravity.py')],check=True)
 print('Pinned Apple Silicon inputs ready; baseline SHA256 verified.')
if __name__=='__main__':main()
