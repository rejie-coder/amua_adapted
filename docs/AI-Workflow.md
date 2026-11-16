# Use AI Workflow

AI Workflow builds proposals that become ordinary editable native models after review. It does not make an AI answer scientifically authoritative.

## Connect your own account

Choose Continue with ChatGPT or Accounts. Add a new connection for a different account or workspace; select an existing connection to reauthorize it. Browser authorization, account eligibility and workspace policy are controlled by the provider. A failed new sign-in preserves the previously active connection. There is no automatic paid-API fallback.

## Attach sources in the chatbox

Click the question field. Type or paste text, paste a copied screenshot/image or copied files with Command V, or drag ordinary source files into the field. Command C/X/V/A and right-click actions support chat text; replies can be copied.

Pasted screenshots are encoded as private local PNGs in the background and shown in the source list. Wait for preparation before sending. Copied/dropped files retain their original paths. Attachments do not start a send. Adding new sources invalidates old request/proposal state; a new outgoing review is required. Clear attachments from the right-click menu or sidebar Clear control.

The chatbox allows 20 ordinary files, 25 MiB each and 100 MiB total. Supported sources include PNG/JPEG, XLSX, DOCX, PDF, saved HTML, text, CSV, TSV, Markdown, RST and JSON. Folder inspection uses Select files / folder and progressive batches. Legacy DOC/XLS, symlinks, remote file URLs and unsupported formats are rejected. A scanned PDF requires local OCR; a selected PNG/JPEG can be sent directly as an image.

## Ask and review

Ask for the desired model and specify the unit of analysis and outcome dimensions. Turn off Include current workspace model when creating an independent model from an image. Saved source inventory is excluded by default; opt in only when intended.

Press Send. Local source inspection precedes the outgoing review, which identifies the selected sources/images, workspace inclusion, recipient, model and request scope. Review before approving. One Send normally authorizes one proposal call; no automatic retries or session-wide reset loops are started.

## Apply the final proposal

A PRELIMINARY source outline may appear while the service works. It is not the final image-derived tree. When Proposal ready appears, use the visible Apply tree proposal control. Review the candidate and create a new tab or explicitly replace the unchanged preliminary outline. Edits are bound to the reviewed model revision and support Undo/Redo.

Use Questions for unresolved context and Review inputs for values, units and derivations. Do not approve unseen or unsupported data. Structure approval cannot clear numerical input review. A malformed numeric question target remains an unresolved clarification; the app does not write its answer into a guessed parameter or node.

## Validate and calculate

Resolve missing values, use the original full model checker, then run. Confirm completion in the console. Save a new `.amua` file. Explicit local validate/run/one-way commands use the original engine; a remote suggestion alone does not authorize execution.

If a proposal fails checks, FINAL TREE NOT APPLIED is shown. User-triggered Retry carries the validation category into a fresh review. Stop cancels the current helper and discards late output. Status does not cancel an active request. Progress-aware waiting uses an idle interval, not a fixed total-duration cutoff.
