# Amua adapted

Amua adapted is a desktop decision-tree and Markov modelling application based on **Amua by Zachary J. Ward**, adapted and developed by **Dr. Rejinten Jayawardhana**. This repository contains the editable model engine, integrated AI Workflow, local MCP bridge and Intel Mac packaging source. Windows source is published with the separate Windows tag and source archive.

**Amua 3.2.4 previews are available for Intel Mac (macOS 14+) and Windows x64.** Native Apple Silicon follows Windows; the Intel package is not a native M-series application.

[Download releases](https://github.com/rejie-coder/amua_adapted/releases) · [Install on Mac](docs/Installing.md) · [User guide](docs/AI-Workflow.md) · [Documentation](docs/README.md) · [Wiki](https://github.com/rejie-coder/amua_adapted/wiki) · [Build from source](docs/Building.md)

**Published Intel preview:** [Download the installation DMG](https://github.com/rejie-coder/amua_adapted/releases/download/v3.2.4/Amua-3.2.4-macOS-Intel.dmg). [Release assets and checksums](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.2.4) include the app ZIP, application source, installation instructions and build verification. For the full repository and regression fixtures, download the [tagged source archive](https://github.com/rejie-coder/amua_adapted/archive/refs/tags/v3.2.4.tar.gz).

**Windows preview:** [Download the complete portable ZIP](https://github.com/rejie-coder/amua_adapted/releases/download/v3.2.4-windows/Amua-3.2.4-Windows-x64.zip), extract it, then open **Amua/Amua.exe**. Java and Python are bundled. See [Windows installation/build guidance](docs/Windows.md) and the [Windows source, audit and verification assets](https://github.com/rejie-coder/amua_adapted/releases/tag/v3.2.4-windows). Windows 10/11 x64 is the target; native CI runs on Windows Server 2022. This unsigned preview still needs clean desktop/live account acceptance.

## Install on Intel Mac

Download **Amua-3.2.4-macOS-Intel.dmg** from the release Assets, open it and drag **Amua.app** to **Applications**. Eject the disk image, then open the installed app. Java and Python are bundled; no separate runtime installation is required. Check the supplied `SHA256SUMS` if verifying the download.

This preview uses a local ad hoc signature and is **not Apple-notarized**. macOS may block first launch. Follow the normal Privacy & Security review described in the [installation guide](docs/Installing.md); do not disable Gatekeeper globally. Clean-machine acceptance is still pending.

## Work with models

Manual editing, native `.amua` files, full model validation and calculations use the original engine. AI Workflow can inventory source files, propose editable trees, ask unresolved questions and apply reviewed edits with Undo/Redo. Text copy/paste, pasted screenshots or files, and file drag-and-drop work in the chatbox. Attachments wait for Send and outgoing review.

AI features require an eligible connected ChatGPT account/workspace and internet access. Provider eligibility, limits and policies remain authoritative; a subscription alone is not a guarantee of availability. Manual modelling does not require AI sign-in. No silent paid-API fallback is included.

## Verified scope and known limits

The local 3.2.4 candidate passes 124 provider tests, 10 bridge tests, native image/sidebar/clipboard checks and eight exact original-engine comparisons. Workflow tests pass 37/38: actual scanned-PDF OCR remains unresolved in that local environment. The published Intel build passed its GitHub runner checks with **zero OCR waivers**, and all 717 application classes matched the checked candidate. This adds evidence on the build runner; live account, physical desktop and clean-machine acceptance remain separate. [Verification evidence](docs/Verification-3.2.4.md) distinguishes controlled service responses from live account acceptance.

The separate Windows release gates publication on native startup/process/credential/OCR/save/image/controller checks and eight original-engine comparisons. See its downloadable reports for explicit private/POSIX test skips. Its 145 numerical classes remain byte-identical to the checked candidate.

AI output is a proposal. Check the image transcription, dimensions, units, probabilities, costs, QALYs and assumptions before approving inputs. Structure approval does not approve numerical inputs. A valid calculation is not scientific validation or a treatment recommendation. Missing perspective, time horizon, comparator, currency context or willingness-to-pay must be resolved explicitly.

## Source and licence

Project adaptations are provided under GPLv3-or-later, with original copyright headers and [GPL licence](LICENSE) retained. [NOTICE](NOTICE.md) identifies the upstream project, adaptation and bundled dependencies. The release includes corresponding application source and build scripts; pinned third-party runtime/dependency inputs are described in [Building](docs/Building.md) and [third-party notices](docs/Third-Party.md).

This is an independent adaptation, not an official release or endorsement by the original Amua author or OpenAI. [Contributions](CONTRIBUTING.md) and [security reports](SECURITY.md) are welcome; never post credentials, patient data or confidential source files in issues.
