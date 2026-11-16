# Amua 3.2.4 source

This snapshot contains the adapted upstream Java source and resources, integrated UI, provider/workflow helpers, native launcher and packaging code. Original copyright headers and the GPL licence are retained. `upstream/ORIGIN.json` records upstream/adaptation history; the build manifest hashes the actual included working sources. Historical commit IDs alone do not identify this modified snapshot.

No nested Git checkout is required. From the repository root, run `python3 scripts/bootstrap_intel.py`, then `build/toolchains/python/bin/python3 -B src/native-support/build.py`. See [build instructions](../docs/Building.md), [release process](../docs/Releasing.md) and [third-party notices](../docs/Third-Party.md). The pinned original container supplies dependency classes/resources; the application classes are rebuilt from this source.

Private acceptance workbooks, user models/accounts and local Git history are excluded from the public distribution. Generated fixtures cover public intake/transport checks; exact skips and the separate OCR limitation remain explicit in verification evidence.
