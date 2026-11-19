# Amua 3.3.3 for Apple Silicon

This preview brings the 3.3.3 Mac application to M-series Macs running macOS 14 or later. The launcher, Java VM, Python interpreter, Vision OCR helper and Google Antigravity 1.5.9 runtime run natively on Apple Silicon. Manual decision-tree and Markov modelling works offline. The AI Workflow retains the Mac 3.3.3 account picker.

Download **Amua-3.3.3-macOS-Apple-Silicon.dmg**, open it and drag **Amua.app** into **Applications**. The app is ad hoc signed and has no Apple notarization. See INSTALL.txt for first-launch guidance.

The native build checks a visible app window, all 718 application class hashes against the Intel candidate, eight original-engine comparisons, scanned-PDF OCR, and package signatures. The verification report lists the executed groups and skipped private-fixture tests. Live provider sign-in on an M-series Mac remains unverified.

The release includes an app ZIP, application source, SHA256SUMS and build provenance. [Complete tagged source with regression fixtures](https://github.com/rejie-coder/amua_adapted/archive/refs/tags/v3.3.3-arm64.tar.gz).

Original Amua by Zachary J. Ward. Adapted and developed by Dr. Rejinten Jayawardhana.
