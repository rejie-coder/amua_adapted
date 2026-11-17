"""Fetch the official signed Intel CLI without running its system installer."""
import hashlib,json,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
VERSION='1.5.9'
URL='https://storage.googleapis.com/antigravity-public/antigravity-cli/1.5.9-4515810895593472/darwin-x64/cli_mac_x64.tar.gz'
SHA512='5f3fd16127de1229bd978509649b0d77b602796292f465ab0e001edd141e902b4b9759991f744cde3264b892f7299eafca6fbae619eca8db24b985d7db40f25e'
def main():
 cache=ROOT/'build/downloads';cache.mkdir(parents=True,exist_ok=True)
 archive=cache/('antigravity-'+VERSION+'-darwin-x64.tar.gz')
 if not archive.exists():urllib.request.urlretrieve(URL,archive)
 if hashlib.sha512(archive.read_bytes()).hexdigest()!=SHA512:raise RuntimeError('Antigravity archive checksum mismatch')
 target=ROOT/'build/toolchains/antigravity';target.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as tar:
  member=tar.getmember('antigravity')
  if not member.isfile():raise RuntimeError('Expected regular executable')
  binary=target/'agy';binary.write_bytes(tar.extractfile(member).read());binary.chmod(0o755)
 record={'version':VERSION,'source_url':URL,'archive_sha512':SHA512,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'bytes':binary.stat().st_size,'platform':'darwin-x64','manifest_url':'https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/darwin_amd64.json'}
 (ROOT/'build/antigravity-runtime-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 print('Verified native Antigravity',VERSION,'darwin-x64',record['bytes'],'bytes')
if __name__=='__main__':main()
