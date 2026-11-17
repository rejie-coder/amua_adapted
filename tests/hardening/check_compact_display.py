"""Compare actual GUI OCD geometry against original Amua on a synthetic tree."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--classes', type=Path, required=True)
    parser.add_argument('--mode', choices=['original', 'fixed'], required=True)
    args = parser.parse_args()
    jar = ROOT / ('src/dependencies/baseline-fat-dependencies.jar' if args.mode == 'original'
                  else 'Amua.app/Contents/Resources/Amua_0.3.6.jar')
    with tempfile.TemporaryDirectory(prefix='amua-compact-display-') as directory:
        profile = Path(directory).resolve()
        model = profile / 'synthetic.amua'
        shutil.copy2(ROOT / 'tests/fixtures/compact-tree-52.amua', model)
        before = hashlib.sha256(model.read_bytes()).hexdigest()
        command = [str(args.java), '-Djava.awt.headless=false',
                   '-Djava.util.prefs.userRoot=' + str(profile / 'prefs'),
                   '-Duser.dir=' + str(profile),
                   '-Damua.support=' + str(profile / 'support'),
                   '-cp', str(jar) + os.pathsep + str(args.classes),
                   'CompactDisplayRegression', str(model),
                   str(ROOT / 'evidence' / ('compact-' + args.mode)), args.mode]
        result = subprocess.run(command, cwd=profile, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=60)
        print(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(result.returncode)
        if hashlib.sha256(model.read_bytes()).hexdigest() != before:
            raise RuntimeError('Display test modified its source model')
    print('PASS synthetic source file preserved')

if __name__ == '__main__':
    main()
