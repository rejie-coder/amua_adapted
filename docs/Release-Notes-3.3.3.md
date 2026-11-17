# Amua 3.3.3 for Intel Mac — preview

This update fixes Google/Gemini reconnect and account selection by replacing the retired Gemini CLI with Google's official Antigravity ACP 1.5.9 runtime. The Google picker supports new sign-in, selected reauthorization, adding another connection, saved switching and removal. Connections have separate profiles/credential namespaces; errors show sanitized provider reasons. Real browser sign-in and separate-process saved-session reuse were verified locally.

The self-contained app keeps Java, Python, OCR and the signed native Google runtime. Conservative packaging reductions save 64.2 MB (15.37%) against the local 3.3.2 app: stored Java JARs are compressed with every entry's bytes preserved, unused Python installation/embedding/Tk files are omitted, and Node/oldGemini are removed. Native build size can vary slightly by host.

Original compact OCD/right-left alignment and solid node symbols, larger chat fonts, attachments, editable native models, Undo/Redo and original calculations are preserved. Eight original-engine comparisons agree;167 numerical/model and46 display classes match3.3.2. Hosted release gates every 718 compiled application classes against the local candidate, source/package correspondence, native runtimes, original 52-node geometry/solidfills, Google picker and atomic saves. Exact hosted counts/skips are in release-verification.json; no failing group or OCR failure is waived.

Requires an Intel x86_64 Mac with macOS 14 or later. Download the DMG and drag Amua.app to Applications. Java/Python/Google runtime need no separate installation. The outer app is ad hoc signed, not Apple-notarized; review normal macOS first-launch controls. Google's native executable retains its own Developer ID signature. Native Apple Silicon is not included.

Google controls eligibility, licensing and usage. Hosted tests use no real credentials; local sign-in evidence is distinct from scientific response/clean-machine acceptance. Claude remains unavailable. This release does not update Windows 3.3.2's older Google client.

Assets include the DMG, app ZIP, corresponding source, SHA256SUMS, installation instructions, build provenance and exact verification. Earlier releases remain available. Original Amua by Zachary J. Ward; adapted/developed by Dr. Rejinten Jayawardhana. GPLv3-or-later and original/third-party notices retained.
