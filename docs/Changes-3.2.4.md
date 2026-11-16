# Amua 3.2.4 image chat changes

The 3.2.3 log recorded `invalid_question_target`. The failed raw service response was unavailable, so its exact question binding cannot be reconstructed. Code inspection reproduced rejection when a whole-model question included a placeholder node, as the previous schema example encouraged. Missing WTP parameter targets could reject an otherwise usable tree in the same way.

## Proposal handling

The image contract explicitly describes decision/chance/terminal topology, independent Cost and QALY dimensions, complete expression arrays, exact image citations and native terminal payoff placement. It asks for supported structure despite missing context. Native currency display symbols are accepted; parameter and expression restrictions remain intact.

Whole-model questions have no executable target. A numerical question with an invalid node, dimension or absent parameter becomes an unresolved clarification retaining its original target for review. No numerical value is assigned to a guessed target. Valid numerical targets remain bound. Duplicate question identifiers receive unique identifiers without losing the question text.

Graph validity, unsupported numerical fields, scientific input review, source references and provider-forged approvals remain enforced. Malformed model values and security violations still reject the proposal. The new path normalizes clarification metadata only; it does not repair probabilities, invent inputs or weaken native calculation checks.

## Sidebar behavior

The initial outline is named PRELIMINARY and recorded separately from the checked final proposal. Repeating Send excludes an unchanged preliminary outline from workspace evidence; manual edits remain included. A checked proposal can replace that outline through an explicit, revision-bound undoable edit. Apply tree proposal stays visible in the header and is disabled when no proposal is ready.

Failed proposals clear the pending Apply state and show that no final tree was applied. A user-triggered Retry carries the local failure category through a fresh preview; there is no automatic retry loop. Structured validation errors explain common failure categories without persisting raw provider responses or account data.

## Chatbox clipboard and file drops

Command C/X/V/A and context menus operate on chat text; the reply transcript supports copying. A chat-specific transfer handler delegates ordinary text to the existing editor, imports copied/dropped file lists and local file URLs, and encodes pasted bitmap screenshots into private PNG attachments. File drops always copy references and cannot move original files. The native model canvas clipboard is unchanged.

Image preparation runs in a background worker. Send waits while preparation is pending. Clear invalidates pending work and removes a late PNG instead of reattaching it. New attachments invalidate stale requests/proposals and stop an active helper, but do not send anything. Duplicates do not create repeated sources. File count/size/type and symlink limits are checked before changing the source list; the existing intake/review path still checks content when sending. Pasted-image storage is bounded and remains local for source provenance.

## Test scope

The exact user PNG is prepared and sent through the real image/helper dispatch. Only the remote service response is substituted with a controlled fixture containing the malformed question bindings. The working MCP model is never input to this replay. Native sidebar application, validation guards, review, Undo/Redo, save/reload and original engine calculation are exercised separately. These checks establish the corrected local path, not live image recognition accuracy.

Clipboard checks use the real Swing handler with a private test clipboard, file-list/local-URI transfer payloads and pixel-checked bitmap data. They verify text copy/cut/paste, no automatic send, stale approval invalidation, rejected attachments, asynchronous encoding and Clear racing a late result. Physical Finder drag events and the macOS system clipboard still require acceptance in the normal desktop session.
