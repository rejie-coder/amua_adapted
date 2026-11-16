# Workflow core

This standard-library Python package supplies deterministic bounded source intake and non-executable portable drafts. Run the sibling `workflow_helper.py` once per JSON request; it reads stdin and emits exactly one JSON object on stdout. Errors are sanitized and do not print source content or paths.

Requests:

- `{"action":"intake","paths":["selected absolute file or folder path"]}`: returns `{ok,project,summary}`. Folder scope is one visible level. Exact supplied D2P workbook + pinned two reference PNGs produces the full manually transcribed presentation draft. Other selections produce complete source-scope containment, including every physical cell and drawing text; this is not inferred clinical topology.
- `{"action":"save","project":PROJECT,"path":"...amuax","expected_hash":null}`: create only if absent. For an explicitly reviewed overwrite supply the current archive SHA-256. Returns `{ok,saved:{sha256,generation_id,...}}`. New generation identity per publication. Saves are local atomic replacements with one known-good `.previous` archive and exclusive lock.
- `{"action":"open","path":"...amuax","recover":false}`: returns project, summary and current archive hash. Recovery optionally loads the prior verified archive when current is invalid; save a copy after recovery.
- `{"action":"answer","project":PROJECT,"question_id":"UUID","value":VALUE,"unit":"EXPECTED UNIT","expected_revision":N}`: typed answer is marked `answered_pending_review`, never silently treated as a validated scientific correction. Mapping questions require JSON objects; numeric questions require finite numbers; revision/unit mismatches reject.
- `{"action":"synthetic"}`: returns a clearly labelled additive fixture with comparator unknown.
- `{"action":"preview-synthetic","project":PROJECT}`: returns an isolated conventional legacy XML proposal for the known synthetic first-year subtotal, expected 370 LKR, with SHA-256. The Java integration must validate the isolated candidate with the actual original engine before promotion/export. It does not unlock comparator or cost-effectiveness claims.
- `{"action":"prepare-digest","project":PROJECT}`: creates a durable pending chunk ledger with every physical source ID; 16k estimated text budget minus 4k reserved. No content is transmitted; provider limits/image costs remain unverified.

`project.graph.nodes` is a list of `{id,label,parent,relationship,terminal,source_ids,...}`. The sole root has `parent:null`. D2P has presentation groups and additive modules; 18/6/2 terminal counts apply within A/B/C, not globally exclusive outcomes. Patient component arrays and once-only programme ledger remain separate. CKD uses explicit `source-record` containment with a separate `dependency_edges` array, preserving all 2,269 cell records and drawing XML facts. Each broken-reference/cache-error root has an explicit typed question and conservative dependency closure.

The manifest inventories all package parts and identities; cell formulas retain original/shared/effective forms, cache/error, styles and source properties. Comments, tables, drawing relationships and XML are preserved as extracted facts. Dependency tracing supports lexical A1/ranges with a bounded operation count. Named, dynamic, structured, iterative and external formula semantics are unresolved, never claimed fully evaluated. No Excel recalculation, macro execution or link fetch occurs. Image dimensions are header-checked but no OCR/ancestry inference is claimed.

Archives intentionally reject executable modules until an integrated validated promotion/persistence service exists. Legacy `.amua` draft saves are rejected. The Java synthetic module demonstration is separate from draft archives. General complete source coverage, reviewed assumptions, all-route validated promotion, project-level PSA/EVPI, command journal/deduplication, parser OS sandbox, network/cloud filesystem semantics and actual crash-kill/disk-full testing remain outside this core checkpoint's proven guarantees. Existing manual models are unaffected.

Run tests from the work-package folder:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests/workflow -v
```

## Expanded local document intake and progressive folder scope

The later user instruction expands the supported input scope beyond the original handoff. Local `.docx`, `.pdf`, `.html`/`.htm` now supplement XLSX, CSV/TSV, UTF-8 text/Markdown/RST/JSON and PNG/JPEG. Legacy `.doc`, `.xls`, arbitrary archives and other formats remain explicit unsupported source entries. These capabilities extract source facts; they do not establish scientific validity or silently resolve uncertainty.

DOCX inventories every package part and relationship, paragraphs across document/header/footer/footnote/endnote/comment parts, table/row/cell containment and paragraph associations, and embedded media identities/hashes. Inserted/deleted/field/drawing features are flagged. Styles/settings/numbering XML remains retained for later review. Field codes, links, macros, embedded objects and scripts are never executed; images are not silently counted as understood. Long paragraphs become an identified parent and ordered 8,000-character source segments, preserving all characters and citations.

PDF uses pinned, vendored **pypdf 7.1.0** with bundled Python 3.12. The official wheel SHA-256, source URL and license record are in `evidence/pypdf-dependency.json`; package contents and BSD license are under `src/dependencies/python`. Copy those directory contents into the app's `Resources/pythonlib`, beside workflow. Every PDF page has an ID, ordinal, bounds and extraction status; metadata, text, annotations/URI facts and image descriptors are inventoried. An extraction failure retains that page's ID/failure and continues other pages. Empty/image-only pages remain unreadable or explicitly unreviewed. A bundled native Vision/PDFKit helper now performs English OCR locally on unreadable PDF pages. Text, regions and confidence remain explicitly unreviewed; missing/failed OCR leaves the page unreadable. Encrypted PDFs require a separately decrypted local copy. Text extraction cannot prove reading order, table geometry or figure semantics; these require review. Parser limits include 2,000 pages/document, 16 MiB page stream expansion, two million extracted characters/page and 20 million document characters. Whole-document failures stay explicit source entries with hashes.

Saved HTML yields ordered local text blocks, links, metadata and image references. Script/style/template content is excluded from prose. No network request, JavaScript, CSS layout evaluation, external image loading or embedded-resource execution occurs. An unfetched image/iframe remains unresolved. News/article prices keep their source text and date metadata; the parser does not assume a currency/year or claim that a saved price is current.

Additional helper actions:

```json
{"action":"selection-plan","paths":["/selected/folder"],"options":{"recursive":false,"include_hidden":false,"max_entries":10000}}
```

The returned `selection` contains every visible selected file's metadata plus explicit exclusions. Default folder scope is visible and nonrecursive; recursion/hidden inclusion requires explicit options. Symlinks/special files are excluded. The metadata-only plan does not mark any source processed. An exceeded enumeration/depth bound returns an explicit error instead of a truncated successful plan.

```json
{"action":"intake-batch","selection":SELECTION,"offset":0,"count":20,"project":OPTIONAL_PREVIOUS_PROJECT}
```

Returns updated `selection`, `project`, `summary`, `processed_entry_ids`, `next_offset`, `pending` and `failed_or_unsupported`. Continue with the returned selection/project and next offset until pending is zero; inspect all failed/unsupported entries before claiming coverage. Retry failures using explicit smaller batches where appropriate. File identity/size/modification metadata is checked against the selection snapshot; changed inputs fail visibly. Duplicate filenames and identical bytes from separate selections retain distinct identities. Saved project `provenance.selection_scope` retains relative names/statuses and exclusions without absolute source paths. The plan's internal read paths are not included in that saved scope record.

Direct `intake` retains its 20-file default bound. An optional `options` object may set `max_file_bytes` up to 100 MiB and `max_total_bytes` per batch up to 500 MiB; defaults remain 25/100 MiB. XLSX/DOCX archive expansion stays independently bounded. Progressive batching scales total selected work without claiming unbounded memory, arbitrary format support or an unlimited model context. A project exceeding the independent 10,000-node display envelope retains the physical source ledger with an explicit presentation-limit reason; it does not silently omit source records. AI chunk/usage budgets and semantic assembly remain separate.

New source shapes preserve compatibility:

- All new formats use `records:[{id,line,text,kind,locator,...}]`. Segment, table, page and link metadata remains in outgoing deterministic digests.
- DOCX uses `kind:"document"`, `document_format:"DOCX"`, `parts`, `relationships`, `media_parts`, `parse_issues`.
- PDF uses `kind:"pdf"`, `pages:[{id,page,status,text,bounds,images,...}]`, `metadata`, `parse_issues`, `records`.
- HTML uses `kind:"article"`, `links`, `images`, `metadata`, `records`.
- Failed parsing uses `kind:"parse-error"`, hash, format, sanitized reason/category and `extraction_status:"incomplete"`.

`source_items()` and digest coverage enumerate every new record/part/page/relationship identity. New format tests generate actual synthetic OOXML/PDF files, retain all text and page identities, exercise mixed folders, unreadable scanned pages, unsupported PDF page filters, changed-selection detection and 25-file progressive processing. Reproduce the full suite with the packaged Python 3.12 (or another Python 3.10+ with the vendored dependency path):

```sh
PYTHONPATH=src build/toolchains/python/bin/python3.12 -m unittest discover -s tests/workflow -v
```


Local OCR is now bundled as Resources/libexec/amua-ocr (macOS14 Intel candidate). It renders selected pages offscreen, recognizes English locally, and retains cited regions/confidence. The native helper enforces8MP/15s bounds and parent-death exit; the adapter allows20s per page. No OCR result is scientific validation. See evidence/intake-ocr-results.json and native-ocr-final-stage-tests.txt.
