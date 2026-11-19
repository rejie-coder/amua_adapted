# Build Amua 3.3.3 on Apple Silicon

Use an M-series Mac with macOS 14 or later, Xcode command-line tools and Python 3. From a fresh checkout run the following commands.

```sh
python3 scripts/bootstrap_arm64.py
build/toolchains/python/bin/python3 -B src/native-support/build.py
PYTHONDONTWRITEBYTECODE=1 Amua.app/Contents/Resources/python/bin/python3 -B tests/hardening/run_release_checks.py
python3 scripts/verify_release.py
Amua.app/Contents/Resources/python/bin/python3 -B Amua.app/Contents/Resources/amua_mcp.py --check > evidence/arm64-launch.json
python3 scripts/package_arm64.py
```

The bootstrap verifies the pinned original dependency JAR, Azul Zulu OpenJDK 8u512-b09, standalone CPython 3.12.16 and the Google Antigravity CLI 1.5.9. The launch check requires a graphical macOS session. The release workflow runs the tests in a fresh macOS 15 Apple Silicon VM.
