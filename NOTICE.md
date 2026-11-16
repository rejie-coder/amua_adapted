# Attribution and adaptation notice

**Amua**, the original modelling framework and engine, was created by **Zachary J. Ward**. Upstream: https://github.com/zward/Amua. Original copyright headers, source and GPL licence remain intact.

**Amua adapted / Amua (ReyJay)** is adapted and developed by **Dr. Rejinten Jayawardhana**. This distribution adds a native Mac launcher/bundled runtimes, integrated AI Workflow, model proposal validation/review, source intake, clipboard/drop support, local MCP integration and packaging controls. The adapted application source is GPLv3-or-later, subject to retained third-party notices and licence exceptions.

This project is independent of the original author and OpenAI. Names identify the upstream framework and supported services; no endorsement is implied. AI account access remains governed by the provider's eligibility and workspace policies.

Third-party notices and source references are in [docs/Third-Party.md](docs/Third-Party.md), the upstream source, dependency notices and bundled Java/Python distributions. Adaptation version 3.2.4 uses engine 0.3.6.

Windows3.3.1 includes a derived, unsigned copy of the bundled Java8 GUI launcher, named amua-javaw.exe. Only its DPI-awareness manifest and PE signature/checksum metadata are changed; the original javaw.exe is retained. Reproducible transformation source: scripts/windows_dpi.py. Upstream runtime licenses remain under Resources/runtime.
