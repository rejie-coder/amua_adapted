# Build the Intel Mac app

The repository contains the application source snapshot, adapted upstream Java source, UI/helpers, tests, dependency notices and release scripts. It targets Intel x86_64 and macOS 14+. Use an Intel Mac with Xcode command-line tools, Python 3 and internet access for the first bootstrap.

```sh
python3 scripts/bootstrap_intel.py
build/toolchains/python/bin/python3 -B src/native-support/build.py
```

Bootstrap downloads only the pinned items in `scripts/toolchains-intel.json` and verifies SHA256 before extraction/use: original Amua 0.3.6 dependency container, Temurin Java 8u512-b09, and standalone CPython 3.12.16. No token or account secret is required for public build inputs. The original container supplies third-party classes/resources; the application engine classes are rebuilt from the included source. Original engine and dependency versions are not silently upgraded.

The result is `Amua.app`; source/binary hashes are recorded in `build/build-manifest.json`. The bundle is `local.rejie.amua.v324`, with support profile `Amua-v3.2.4`. A source archive is a snapshot, not a claim that the working sources equal a historical commit: `src/upstream/ORIGIN.json` records the adaptation history, while the manifest identifies actual source files. No nested private Git history is required to build.

## Run checks

```sh
PYTHONDONTWRITEBYTECODE=1 Amua.app/Contents/Resources/python/bin/python3 -B tests/hardening/run_release_checks.py
python3 scripts/verify_release.py
```

The full runner exits nonzero for any test failure. The preview verifier accepts only the exact documented actual scanned-PDF OCR failure when it is the sole failure; any other failure blocks release. It records that waiver explicitly and compares all 717 compiled application class files with the checked local 3.2.4 candidate. A previously accepted OCR limitation does not become a pass.

Provider tests use controlled identities/responses, not live inference. Native sidebar tests use real Swing/model objects in an inert headless frame. Local source/compiled-class correspondence, original engine comparisons and native atomic saves are included. See [verification](https://github.com/rejie-coder/amua_adapted/blob/main/docs/Verification-3.2.4.md).

## Package

```sh
python3 scripts/package_intel.py
```

Packaging requires successful verification. It checks Intel binary architecture and signature integrity, creates a read-only compressed DMG, mounts it, compares every app file/link with the checked source bundle and verifies the mounted app signature, then ejects it. Outputs include the DMG, corresponding source archive, checksums, installation instructions and build provenance. It refuses to overwrite an existing DMG.

Local builds are ad hoc signed. Developer ID/notarization require a real signing identity and appropriate Apple account setup. The inherited `src/native-support/sign_distribution.py` prepares a separate distribution copy for that future workflow; no Developer ID identity or notarization is supplied here.

Private CKD/D2P acceptance workbooks and images are not distributed. Tests requiring those inputs report explicit skips; generated public XLSX cases exercise transport and intake/error/persistence guards without disclosing the private material. Public CI counts therefore differ from the earlier local 124-provider/38-workflow evidence. Exact executed/skipped cases are retained in CI outputs and the release verification asset.

For Windows, use the separately tagged Windows source archive and [Windows build instructions](https://github.com/rejie-coder/amua_adapted/wiki/Windows). Main retains the Intel source; Windows-specific native launcher/OS adapters are on `v3.2.4-windows`.
