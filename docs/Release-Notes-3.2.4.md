# Amua 3.2.4 for Intel Mac preview

Download **Amua-3.2.4-macOS-Intel.dmg**, open it and drag **Amua.app** into **Applications**. Requires an Intel x86_64 Mac with macOS 14 or later. Java and Python are included.

This release corrects desktop image-chat question-target rejection, separates preliminary outlines from checked final proposals, and adds chatbox text/image/file paste and file drag-and-drop. Attachments wait for Send and outgoing review. Native model values remain editable and supported edits preserve Undo/Redo and original engine validation/calculation.

**Preview limitations:** the app is ad hoc signed, not Developer ID signed or Apple-notarized. First launch may be blocked; follow the documented normal macOS Privacy & Security review. Clean-machine and signed-in live vision acceptance remain open. The local workflow suite has one actual scanned-PDF OCR failure; the release verification asset records whether that exact limitation also occurred on the build runner. No new failure is waived. Controlled vision responses and private clipboard tests are not physical desktop/live-account evidence.

The checked local candidate passes 124 provider tests, 10 bridge tests, native image/sidebar/clipboard checks, 14 atomic saves and eight original-engine comparisons. The release build must match all 717 checked application class files, verify the packaged sources/signature and read the app back from its DMG before publication.

The image example yields Drug A 850/1.55 QALYs, Drug B 1520/2.20 QALYs and an incremental ratio of 1030.76923077 per QALY. Review source values and scientific context; these calculations do not select a clinically appropriate drug without the missing threshold/assumptions.

**Intel only:** this is not a native M-series build. Windows is next; native Apple Silicon follows Windows. AI features require an eligible provider account/workspace; a subscription alone does not guarantee inference access. Manual modelling remains available without AI sign-in.

Assets include the DMG, corresponding source archive, SHA256SUMS, INSTALL.txt, build provenance and exact release verification. Use the [installation guide](https://github.com/rejie-coder/amua_adapted/blob/main/docs/Installing.md), [user guide](https://github.com/rejie-coder/amua_adapted/blob/main/docs/AI-Workflow.md), [source](https://github.com/rejie-coder/amua_adapted) and [known limitations](https://github.com/rejie-coder/amua_adapted/blob/main/docs/Troubleshooting.md).

Original Amua by Zachary J. Ward; adapted and developed by Dr. Rejinten Jayawardhana. GPLv3-or-later with retained original and third-party notices.
