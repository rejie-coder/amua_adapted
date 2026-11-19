# Install Amua on macOS

Amua 3.3.3 has native installers for Apple Silicon and Intel Macs with macOS 14 or later. In **Apple menu → About This Mac**, check the chip or processor.

## Download and install

1. For an M-series chip, select the [Apple Silicon preview](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.3.3-arm64). For an Intel processor, select the [Intel preview](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.3.3).
2. Download the DMG from the selected release.
3. Open the DMG and drag `Amua.app` onto `Applications`.
4. Eject the DMG and launch the app from Applications. Bundled Java and Python provide the required runtimes.
5. Back up existing `.amua` files before editing; save initial work to a new filename.

Verify the downloaded assets from their directory with `shasum -a 256 -c SHA256SUMS`. If you downloaded only the DMG, compare its `shasum -a 256` value with the matching line in that file; missing other assets are expected in the full check.

## First launch and signing

This is an **ad hoc signed, non-notarized preview**. The release pipeline checks signature integrity and reads the entire packaged app back from the DMG, but this does not establish Apple developer identity or clean-machine acceptance.

If macOS blocks an unidentified developer, first confirm the source and checksum. Review the app in System Settings → Privacy & Security and use Apple's normal **Open Anyway** process if you choose to trust the preview. Do not disable Gatekeeper globally or remove system protections. A warning about damage, a changed checksum or a failed signature requires investigation rather than an automatic override. See [Apple's guidance](https://support.apple.com/en-us/102445).

## Upgrades and local files

3.3.3 keeps local state under `~/Library/Application Support/Amua-v3.3.3`. Shared compatible ChatGPT connection credentials use the OS credential store. Installing the application does not replace user `.amua` files. Quit the old version normally before replacing the app in Applications, and preserve a copy if rollback is needed.

Removing the app alone does not erase models, local support files or shared credentials. Use the app's account controls to disconnect/remove a saved connection deliberately. Do not delete shared credential entries merely to uninstall one version.
