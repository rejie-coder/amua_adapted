# Windows x64 preview

[Download the portable ZIP](https://github.com/rejie-coder/amua_adapted/releases/download/v3.2.4-windows/Amua-3.2.4-Windows-x64.zip) from the [Windows release](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.2.4-windows). Target desktops are 64-bit Windows 10/11. Native Windows verification runs on Windows Server 2022; separate clean desktop acceptance remains necessary. Native Windows ARM is not supplied.

Extract the **entire** ZIP to a local folder you can write to, then open `Amua/Amua.exe`. Keep `launch.py` and `Resources` beside it. Java and Python are bundled; no system runtime or administrator installation is required. This preview is not Authenticode signed. Review its origin and checksums when Windows shows an unknown-publisher warning.

Manual editable decision trees and Markov models use the original Amua calculations. For AI Workflow, connect your own eligible ChatGPT account/workspace. Paste text, screenshots or files into the chatbox, or drop files there, then inspect the attachment list before Send. Controlled tests verify the image proposal/review/calculation path; live provider interpretation still requires acceptance. Review all numerical inputs and unresolved assumptions, run the full native checker, and inspect completed results.

English scanned-PDF OCR uses Windows OS components with bounded memory/time. Missing language/components or unreadable pages remain unresolved. Windows does not report calibrated OCR confidence; the adapter records unknown confidence and requires review. No global PowerShell execution-policy change is needed.

Application state is under `%LOCALAPPDATA%\Amua-v3.2.4`; compatible provider registration is under `%LOCALAPPDATA%\Amua-v2.1\provider`. Credentials use Windows Credential Manager without a plaintext fallback. Screenshot attachments persist in the profile's chat-attachments folder after Clear; remove unwanted local screenshots separately. Keep the Windows account and profile permissions private. Save new models separately and back up originals. File flush/backup/atomic replacement are tested; power-loss or network/cloud-sync durability is not established.

To build on Windows, use the source archive or tag `v3.2.4-windows`:

```powershell
python scripts/bootstrap_windows.py
$env:AMUA_JAVA_HOME = "$PWD\build\toolchains\jdk8u512-b09"
build/toolchains/python/python.exe -B scripts/build_windows.py
Amua/Resources/python/python.exe -B tests/windows/run_checks.py
Amua/Resources/python/python.exe -B scripts/package_windows.py
```

Bootstrap verifies hashes in `scripts/toolchains-windows.json` before extracting Java, Python and Zig. Run in a fresh source directory with no existing ZIP in `dist`. Packaging refuses failed or missing required checks, reads the ZIP back, and exports public source, audit/verification reports and SHA256 checksums. Publication uses the repository-scoped Actions token; it checks uploaded digests, reads the uploaded ZIP back and verifies the tag before making the preview public. Existing Intel assets are preserved.

Original Amua: Zachary J. Ward. Adaptation: Dr. Rejinten Jayawardhana. GPLv3-or-later; bundled components retain their licenses. See NOTICE.md, docs/Third-Party.md, scripts/toolchains-windows.json and the runtime license files inside the portable application.
