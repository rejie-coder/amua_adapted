# Release the Apple Silicon preview

The Apple Silicon workflow runs on pushes to the macos-3.3.3-arm64 branch. Include `[publish-arm64]` in the commit message to publish after native verification. The release uses its own tag, `v3.3.3-arm64`.

The runner checks application bytecode, the packaged UI, original engine results, runtime architectures, signatures and archive readback. It verifies the uploaded DMG and ZIP before making the preview public. The build provenance records the tested commit, toolchain pins, launch evidence and checks. Full build and test logs are available as a workflow artifact.
