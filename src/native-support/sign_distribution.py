#!/usr/bin/env python3
"""Prepare a separate Developer ID distribution; never changes the local app.

Requires an existing Developer ID Application identity. Optional notarization
uses an existing notarytool Keychain profile; no credential values are accepted.
"""
import argparse,plistlib,shutil,subprocess,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def run(*command):subprocess.run([str(c) for c in command],check=True)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--identity',required=True);parser.add_argument('--notary-profile');args=parser.parse_args()
    if args.identity=='-' or 'Developer ID Application' not in args.identity:raise SystemExit('Use a Developer ID Application identity, not an ad hoc signature.')
    identities=subprocess.check_output(['/usr/bin/security','find-identity','-v','-p','codesigning'],text=True)
    if args.identity not in identities:raise SystemExit('The requested signing identity is not available; local build preserved.')
    output=ROOT/'distribution';output.mkdir(exist_ok=True);app=output/'Amua.app'
    if app.exists():raise SystemExit('Distribution app already exists; preserve it or choose a new release folder.')
    shutil.copytree(ROOT/'Amua.app',app,symlinks=True)
    with tempfile.TemporaryDirectory() as directory:
        entitlements=Path(directory)/'java.plist'
        entitlements.write_bytes(plistlib.dumps({'com.apple.security.cs.allow-jit':True,'com.apple.security.cs.allow-unsigned-executable-memory':True}))
        for path in sorted(app.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if path.is_symlink() or not path.is_file():continue
            with path.open('rb') as stream:magic=stream.read(4)
            if magic not in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):continue
            flags=['--force','--options','runtime','--timestamp','--sign',args.identity]
            if path.name=='java':flags+=['--entitlements',str(entitlements)]
            run('/usr/bin/codesign',*flags,path)
        run('/usr/bin/codesign','--force','--options','runtime','--timestamp','--sign',args.identity,app)
    run('/usr/bin/codesign','--verify','--deep','--strict',app)
    archive=output/'Amua-3.2.4.zip'
    run('/usr/bin/ditto','-c','-k','--keepParent','--sequesterRsrc',app,archive)
    if args.notary_profile:
        run('/usr/bin/xcrun','notarytool','submit',archive,'--keychain-profile',args.notary_profile,'--wait')
        run('/usr/bin/xcrun','stapler','staple',app);run('/usr/bin/xcrun','stapler','validate',app)
        run('/usr/sbin/spctl','--assess','--type','execute','--verbose=4',app)
        archive.unlink();run('/usr/bin/ditto','-c','-k','--keepParent','--sequesterRsrc',app,archive)
    print('Prepared '+str(archive)+('. Notarization and stapling completed.' if args.notary_profile else '. Notarization remains required before general distribution.'))
if __name__=='__main__':main()
