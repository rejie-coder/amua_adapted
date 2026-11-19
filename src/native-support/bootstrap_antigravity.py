"""Fetch the official signed Apple Silicon CLI without running its system installer."""
import hashlib,json,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
VERSION='1.5.9'
URL='https://storage.googleapis.com/antigravity-public/antigravity-cli/1.5.9-4515810895593472/darwin-arm/cli_mac_arm64.tar.gz'
SHA512='690cd6a5a5fdb23564fb1b14f7f6ae368fa3636b7630f56c574a6dfc0e2791a0e5b93d6515be1650c8a268cfb28440e1b9cbaa1c5b85aa762ab25b51c1fccda5'
def main():
 cache=ROOT/'build/downloads';cache.mkdir(parents=True,exist_ok=True)
 archive=cache/('antigravity-'+VERSION+'-darwin-arm64.tar.gz')
 if not archive.exists():urllib.request.urlretrieve(URL,archive)
 if hashlib.sha512(archive.read_bytes()).hexdigest()!=SHA512:raise RuntimeError('Antigravity archive checksum mismatch')
 target=ROOT/'build/toolchains/antigravity';target.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as tar:
  member=tar.getmember('antigravity')
  if not member.isfile():raise RuntimeError('Expected regular executable')
  binary=target/'agy';binary.write_bytes(tar.extractfile(member).read());binary.chmod(0o755)
 record={'version':VERSION,'source_url':URL,'archive_sha512':SHA512,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'bytes':binary.stat().st_size,'platform':'darwin-arm64','manifest_url':'https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/darwin_arm64.json'}
 (ROOT/'build/antigravity-runtime-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
 print('Verified native Antigravity',VERSION,'darwin-arm64',record['bytes'],'bytes')
if __name__=='__main__':main()
