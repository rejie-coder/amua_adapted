# Mac 3.3.3 verification

The public build must pass all 25 required groups with zero failure waivers and match all 718 compiled application classes against the checked local candidate. The gate includes eight exact original-engine results, 14 atomic-save cases, native OCR, source/package/signature checks, original/fixed 52-node OCD for both alignments, saturated fills and the real Swing Google picker with synthetic helper capture.

Local review verified real Google browser login, saved-session reuse in a separate final native process and fresh-profile isolation. Hosted tests use synthetic credentials and do not prove real account eligibility. Exact hosted pass/skip counts and artifact hashes are in release-verification.json and build-provenance.json, downloadable with the release. Private workbook fixtures are excluded from the repository and source archive; public synthetic fixtures cover workbook behavior separately.

Source and scope summaries are in docs/verification/mac-3.3.3. Working folder sizes and host-specific native binaries can differ; the public DMG is built and read back on the native Intel runner before release. No scientific policy recommendation follows solely from software validation.
