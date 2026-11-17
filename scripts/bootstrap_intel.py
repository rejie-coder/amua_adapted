"""Fetch pinned Intel build inputs, verifying SHA256 before extraction/use."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,tarfile,tempfile,urllib.request
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
 p=argparse.ArgumentParser();p.add_argument('--seed',type=Path,help='Use the already retained local 3.3.3 toolchains; no downloads.');a=p.parse_args()
 manifest=json.loads((ROOT/'scripts/toolchains-intel.json').read_text());baseline=ROOT/manifest['baseline']['target'];tools=ROOT/'build/toolchains';tools.mkdir(parents=True,exist_ok=True)
 if a.seed:
  source=a.seed.resolve();candidate=source/'src/dependencies/baseline-fat-dependencies.jar'
  if sha(candidate)!=manifest['baseline']['sha256']:raise RuntimeError('Local baseline SHA256 mismatch')
  baseline.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate,baseline)
  for name in ['jdk8u512-b09','python']:
   if not (tools/name).exists():shutil.copytree(source/'build/toolchains'/name,tools/name,symlinks=True)
 else:
  download(manifest['baseline'],baseline)
  for name,sentinel in [('jdk',tools/'jdk8u512-b09/Contents/Home/bin/javac'),('python',tools/'python/bin/python3')]:
   if not sentinel.exists():
    archive=ROOT/'build/downloads'/(name+'.tar.gz');download(manifest[name],archive);extract(archive,tools)
 if sha(baseline)!=manifest['baseline']['sha256']:raise RuntimeError('Baseline container is not the approved version')
 for command in [[tools/'jdk8u512-b09/Contents/Home/bin/javac','-version'],[tools/'python/bin/python3','--version']]:subprocess.run([str(c) for c in command],check=True)
 (ROOT/'build/toolchain-provenance.json').write_text(json.dumps({'inputs':manifest,'local_seed':bool(a.seed)},indent=2)+'\n')
 subprocess.run([str(tools/'python/bin/python3'),'-B',str(ROOT/'src/native-support/bootstrap_antigravity.py')],check=True)
 print('Pinned Intel inputs ready; baseline SHA256 verified.')
if __name__=='__main__':main()
