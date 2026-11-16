# Install Amua on an Intel Mac

Amua 3.2.4 targets **Intel x86_64 Macs with macOS 14 or later**. The launcher, Java runtime, Python runtime and OCR helper in this download are Intel binaries. This page covers the Intel package; the separate [Windows x64 preview](https://github.com/rejie-coder/amua_adapted/wiki/Windows) has its own portable ZIP. Native Apple Silicon is still pending.

## Download and install

1. Open [Releases](https://github.com/rejie-coder/amua_adapted/releases) and select the 3.2.4 Intel preview.
2. Download `Amua-3.2.4-macOS-Intel.dmg`. The other assets contain source, checksums and verification details.
3. Open the DMG and drag `Amua.app` onto `Applications`.
4. Eject the DMG and launch the app from Applications. Bundled Java and Python provide the required runtimes.
5. Back up existing `.amua` files before editing; save initial work to a new filename.

Verify the downloaded assets from their directory with `shasum -a 256 -c SHA256SUMS`. If you downloaded only the DMG, compare its `shasum -a 256` value with the matching line in that file; missing other assets are expected in the full check.

## First launch and signing

This is an **ad hoc signed, non-notarized preview**. The release pipeline checks signature integrity and reads the entire packaged app back from the DMG, but this does not establish Apple developer identity or clean-machine acceptance.

If macOS blocks an unidentified developer, first confirm the source and checksum. Review the app in System Settings → Privacy & Security and use Apple's normal **Open Anyway** process if you choose to trust the preview. Do not disable Gatekeeper globally or remove system protections. A warning about damage, a changed checksum or a failed signature requires investigation rather than an automatic override. See [Apple's guidance](https://support.apple.com/en-us/102445).

## M-series Macs

This first package is Intel-only. On Apple Silicon, running it would require Rosetta and has not been accepted on an M-series test machine. Apple states that general Rosetta support ends after macOS 27, so this is not a durable native Apple Silicon solution. See [Apple's transition guidance](https://developer.apple.com/news/?id=w5ngl9k2). Native Apple Silicon follows the Windows work in the agreed release order.

## Upgrades and local files

3.2.4 keeps local state under `~/Library/Application Support/Amua-v3.2.4`. Shared compatible ChatGPT connection credentials use the OS credential store. Installing the application does not replace user `.amua` files. Quit the old version normally before replacing the app in Applications, and preserve a copy if rollback is needed.

Removing the app alone does not erase models, local support files or shared credentials. Use the app's account controls to disconnect/remove a saved connection deliberately. Do not delete shared credential entries merely to uninstall one version.
