# Amua adapted

Amua adapted is a desktop decision-tree and Markov modelling application based on **Amua by Zachary J. Ward**, adapted and developed by **Dr. Rejinten Jayawardhana**. This repository contains the editable engine, integrated AI Workflow, local MCP bridge and Intel Mac packaging source. Windows source and binaries have separate release tags.

**Intel Mac 3.3.3 (macOS 14+)**: [installation DMG](https://github.com/rejie-coder/amua_adapted/releases/download/v3.3.3/Amua-3.3.3-macOS-Intel.dmg) · [all assets and checksums](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.3.3) · [release notes](docs/Release-Notes-3.3.3.md).

**Windows 3.3.2**: [portable ZIP](https://github.com/rejie-coder/amua_adapted/releases/download/v3.3.2-windows/Amua-3.3.2-Windows-x64.zip) · [Windows guidance](docs/Windows.md). Its older Gemini CLI needs the Google personal-account migration now implemented on Mac; the Windows Google fix has not been released. Manual modelling and its compact display correction remain available.

[Install](docs/Installing.md) · [AI Workflow](docs/AI-Workflow.md) · [Documentation](docs/README.md) · [Wiki](https://github.com/rejie-coder/amua_adapted/wiki) · [Build](docs/Building.md)

## Mac 3.3.3

- Google/Gemini sign-in uses Google's official Antigravity ACP runtime. The retired personal Gemini CLI is removed.
- Connect/Accounts support first sign-in, reconnect, adding another Google connection, switching and removal. Separate profiles and credential namespaces keep connections apart. Provider errors show sanitized reasons.
- Original compact OCD, terminal alignment and solid red/green/blue symbols are retained. Larger chat fonts and a responsive sidebar improve readability.
- Java, Python, native OCR and Google's signed native runtime are bundled. No separate runtime installation is needed. The local app's file contents are64.2 MB/15.37%smaller than3.3.2; [packaging details](docs/Size-Optimization.md) explain the measurement.
- Manual native .amua editing, original validation/calculations, proposal review, Undo/Redo and text/file/image chat attachments remain.

Google browser sign-in and reuse of the saved connection were verified locally. Hosted tests use synthetic credentials and do not authenticate a real account. Google determines account eligibility and limits; there is no API-key fallback. Claude remains unavailable. Manual modelling works without AI sign-in.

## Install and verify

Download the DMG, open it and drag **Amua.app** into **Applications**. Eject the image and open the installed app. Requires Intel x86_64 and macOS 14 or later; native Apple Silicon is not included.

The outer app is ad hoc signed and **not Apple-notarized**. Follow normal macOS Privacy & Security review if first launch is blocked; do not disable Gatekeeper globally. Check SHA256SUMS and the release's build provenance. The native Google executable retains Google's Developer ID signature.

The local candidate passes 20 release groups,146 provider tests,38 workflow tests(including actual English scanned-PDF OCR),10 bridge tests and a real Swing Google-picker test. The public build also gates compact original/candidate52-node geometry, signed native runtime and source/package correspondence; its exact pass/skip counts are in the downloadable verification report. All718 compiled application classes must match the checked candidate; eight original-engine results must agree.

AI output is a proposal. Review source transcription, probabilities, costs, outcomes, units and assumptions before approving inputs. Structure approval does not approve numerical values. A valid calculation does not establish scientific validity or a policy recommendation. Clean-machine and broader live-account/scientific acceptance remain separate.

## Source and licence

Project adaptations are GPLv3-or-later; original copyright headers and [GPL licence](LICENSE) are retained. [NOTICE](NOTICE.md) and [third-party information](docs/Third-Party.md) identify upstream and bundled runtimes. The release includes corresponding application source and build scripts. Keep the checked runtime versions when rebuilding.

This is an independent adaptation, not an official release or endorsement by the original Amua author or the AI providers. Never post credentials, patient data or confidential documents in public issues.
