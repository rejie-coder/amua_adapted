# Amua 3.2.4 verification

Checks run on 16 November 2026 against the packaged Intel Mac candidate. Exact results and the retained failure are in [release-checks.json](verification/local/release-checks.json).

| Check | Result |
| --- | --- |
| Provider regressions and hardening | 124/124 pass; synthetic services and in-memory callbacks |
| Workflow parsing, OCR and recovery | 37/38 pass; actual scanned-PDF OCR fails |
| Bridge integration | 10/10 pass |
| Image chat pipeline | Pass: exact PNG bytes, one approved service call, malformed clarifications retained, input guard and original calculations |
| Image sidebar | Pass: preliminary/final separation, safe Retry, visible Apply, revision-bound replacement, validation, Undo/Redo and save/reload |
| Chatbox clipboard and file drops | Pass: text copy/cut/paste, shortcut/menu wiring, file-list/local-URI transfer, bitmap pixels, private PNG, no automatic send, limits/rejections and Clear racing a pending paste |
| Original numerical behavior | Eight exact outputs match the original tree/Markov cohort and seeded Monte Carlo engine |
| Native atomic saves | 14 checks pass |
| Native edit, hardening and progress controllers | Pass: variable-update retention, original validation, evidence privacy, stale-edit rejection and progress/Stop behavior |
| Approval transport | Pass: exact count/hash/recipient/model binding and invalid request rejection |
| Presentation | Native tree/Markov painting passes; 340×600 chat screenshots inspected |
| Source/package correspondence | 94 bundled source files match; compiled application classes match the JAR |
| Preservation | Previous JAR and working model hashes match; 145 shared tree/markov/math class files unchanged |
| Signature integrity | Deep strict verification passes; signature is ad hoc |

## Image numerical checks

The image replay supplies only the exact original PNG and a controlled remote response, never the known MCP model. Production intake, helper dispatch, proposal checks, review guards, native XML conversion, Java sidebar and original calculation engine are exercised. The fixture deliberately contains whole-model placeholder nodes and an absent WTP parameter target.

Those questions remain unresolved clarifications rather than rejecting the complete supported tree or writing to guessed targets. Unreviewed image inputs remain blocked. Explicit simulated local structure review cannot clear input review; a separate simulated input confirmation enables the controlled calculation. Such simulated confirmations are test actions, not user scientific acceptance.

The original engine returns Drug A **850 / 1.55 QALYs** and Drug B **1520 / 2.20 QALYs**. Independent incremental arithmetic yields **1030.769230769231 per QALY**; the native comparison table displays **1030.7692** at its configured four-decimal precision. See [pipeline evidence](verification/local/image-chat/results.json) and [sidebar output](verification/local/image-chat-controller.txt).

## Clipboard and drop checks

[Chatbox controller output](verification/local/chat-attachments.txt) uses the real Swing handler and a private clipboard with text, file-list, local-file-URI and bitmap payloads. It checks preserved question text, original file references, duplicate suppression, invalidated stale approvals, no inference, private PNG pixels, asynchronous image preparation, Send waiting, and Clear discarding a late image. Unsupported/oversized files, folders, symlinks, remote URIs and excessive file counts are rejected without changing the existing selection.

[Attachment preview](verification/local/chat-attachments.png) and [proposal preview](verification/local/image-chat/sidebar-proposal-ready.png) show the real panels in an isolated headless frame at 340×600. Physical Finder drag events, the macOS system clipboard and eligible-account live vision remain desktop acceptance checks.

## Remaining failures and limits

The full runner exits nonzero because `test_actual_english_scanned_pdf_local_ocr` fails with `unreadable-scanned-page`; the prior native diagnostic was CoreVideo -6662. This failure is retained in [workflow output](verification/local/workflow-final.txt), not skipped or renamed as a pass.

The exact failed 3.2.3 service response was unavailable. Its log category and the parser failure class were reproduced, but the controlled response does not establish what the service originally returned or that every future response will be correct. Local Keychain/Finder restrictions prevented live account and fresh desktop acceptance here. See [limits](verification/local/verification-limits.json).

No Developer ID identity/notarization or clean-Mac distribution was tested. Compilation retains existing unchecked code and test-only inert-frame Unsafe warnings; headless Swing emits font substitution warnings. These tests establish local implementation behavior, not scientific validation or 3.2.4 user acceptance.
