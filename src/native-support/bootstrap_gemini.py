"""Prepare pinned Gemini CLI and Intel macOS Node; no account or inference."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SPECS = {
    'cli': {'url': 'https://registry.npmjs.org/@google/gemini-cli/-/gemini-cli-0.68.0.tgz',
            'name': 'gemini-cli-0.68.0.tgz',
            'sha256': '325099ddcb56937c27d119e7297bfa8a5e29b529bae3c92fdf3b71a36d5fa006'},
    'node': {'url': 'https://nodejs.org/dist/v24.11.1/node-v24.11.1-darwin-x64.tar.gz',
             'name': 'node-v24.11.1-darwin-x64.tar.gz',
             'sha256': '096081b6d6fcdd3f5ba0f5f1d44a47e83037ad2e78eada26671c252fe64dd111'},
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def obtain(spec, directory):
    target = directory / spec['name']
    if not target.exists():
        temporary = target.with_suffix('.download')
        request = urllib.request.Request(spec['url'], headers={'User-Agent': 'Amua-Mac-build/3.3.3'})
        with urllib.request.urlopen(request, timeout=90) as source, temporary.open('wb') as output:
            shutil.copyfileobj(source, output)
        if digest(temporary) != spec['sha256']:
            raise RuntimeError('Pinned runtime checksum mismatch')
        temporary.rename(target)
    if digest(target) != spec['sha256']:
        raise RuntimeError('Cached runtime checksum mismatch')
    return target

def main():
    downloads = ROOT / 'build/downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    paths = {key: obtain(spec, downloads) for key, spec in SPECS.items()}
    target = ROOT / 'build/toolchains/gemini'
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(paths['node'], 'r:gz') as archive:
        for source, destination in [('bin/node', 'node'), ('LICENSE', 'NODE-LICENSE.txt')]:
            entry = archive.getmember('node-v24.11.1-darwin-x64/' + source)
            if not entry.isfile():
                raise RuntimeError('Unexpected Node archive member')
            (target / destination).write_bytes(archive.extractfile(entry).read())
    os.chmod(target / 'node', 0o755)
    package = target / 'package'
    if package.exists():
        shutil.rmtree(package)
    with tarfile.open(paths['cli'], 'r:gz') as archive:
        for entry in archive.getmembers():
            path = Path(entry.name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != 'package':
                raise RuntimeError('Unexpected CLI archive path')
            destination = target / path
            if entry.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif entry.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(entry).read())
            else:
                raise RuntimeError('Unexpected CLI archive member')
    manifest = {'cli_version': '0.68.0', 'node_version': '24.11.1',
                'platform': 'darwin-x64', 'archives': SPECS,
                'files': {str(p.relative_to(target)): digest(p)
                          for p in target.rglob('*') if p.is_file()}}
    (ROOT / 'build/gemini-runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Pinned Gemini CLI 0.68.0 / macOS x64 Node 24.11.1 prepared and verified.')

if __name__ == '__main__':
    main()
