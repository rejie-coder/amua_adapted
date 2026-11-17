# Publish an Intel preview

The Intel Mac build and release workflow runs on GitHub's `macos-15-intel` runner. It downloads hash-pinned toolchains/dependencies, rebuilds from source, runs the acceptance suite, compares 717 compiled classes with the checked 3.2.4 candidate, and reads the installer back before publishing.

The normal push path builds/verifies without publication. A main-branch commit containing `[publish-intel]`, or an explicit workflow dispatch with Publish enabled, authorizes the checked release step. The publishing job uses the repository-scoped GitHub Actions token; no personal token is embedded in source or configuration.

The script creates a draft release, uploads all checked assets, then exposes the preview. Existing public releases are not overwritten. If a draft upload is interrupted, inspect its commit and assets before retrying; automatic clobbering is intentionally refused. A changed application version needs updated bundle identity, expected class manifest, release tag/notes and artifact names before publication.

Assets include `Amua-3.3.3-macOS-Intel.dmg`, `Amua-3.2.4-source.tar.gz`, `SHA256SUMS`, `INSTALL.txt`, `build-provenance.json` and `release-verification.json`. Exact CI logs/results remain in the workflow artifact. Do not label a release notarized, Apple Silicon native, live-account accepted or scientifically validated without the corresponding evidence.

## Known OCR waiver

The full test runner keeps the OCR failure. `verify_release.py` accepts only a sole `workflow-final` failure containing exactly the named actual English scanned-PDF test, one failure and no test errors. The release verification asset states the waiver. Any additional failure or compiled-class mismatch blocks publication. If native OCR passes on another machine, the verifier records no waiver; that does not retroactively change the earlier local failure.

## Wiki

Reviewed wiki pages live in `docs/wiki`. The Sync wiki workflow mirrors them into the separate `.wiki.git` repository. GitHub requires an initial page to be created through the Wiki UI before that repository is cloneable. If needed, create a Home page once, then run Sync wiki. The main repository's complete documentation remains available independently. The workflow reports a clone/permission problem instead of claiming the wiki is published.

See [GitHub's wiki instructions](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages).

## Release order

The Intel workflow preserves its existing release. The separate Windows workflow/tag publishes its own portable ZIP after native gates, source/package verification, uploaded asset digest checks and ZIP readback. See [Windows release/build guidance](Windows.md). Native Apple Silicon follows Windows and is not supplied by either package.

Private CKD/D2P acceptance workbooks and images are not distributed. Tests requiring those inputs report explicit skips; generated public XLSX cases exercise transport and intake/error/persistence guards without disclosing the private material. Public CI counts therefore differ from the earlier local 124-provider/38-workflow evidence. Exact executed/skipped cases are retained in CI outputs and the release verification asset.
