# Self-contained package optimization

| App | File-content bytes | Decimal MB |
| --- | ---: | ---: |
| Mac 3.3.2 | 417,290,702 | 417.3 |
| Mac 3.3.3 | 353,136,940 | 353.1 |
| Reduction | 64,153,762 | 64.2 (15.37%) |

Measurement sums regular file contents in Amua.app, excluding duplicate symlink targets. Finder allocated size and compressed downloads use different measurements. The working folder also holds source, tests, toolchains and intermediate build artifacts; those are separate from Amua.app.

Changes:

1. Replaced the retired Node.js/Gemini CLI package with Google's signed native Antigravity CLI 1.5.9. Its Developer ID signature remains intact. The new native executable includes its backend and needs no Node installation.
2. Recompressed Java runtime JARs that had stored every entry uncompressed. Every entry name, order and decompressed byte content was compared and preserved. All Java classes, resources, fonts and certificates remain. Removed the obsolete CDS archive tied to the old JAR layout; the VM loads the preserved classes normally.
3. Removed the standalone Python runtime's unused dynamic embedding library (the interpreter is statically linked), C headers/configuration helpers, Tk/IDLE components and package installation tools. Python's interpreter, standard processing/network/crypto libraries and all Amua format parsers remain.

The package containing the new Google runtime was 429.5 MB before packaging reductions; reductions saved 76.7 MB there. The net saving compared with 3.3.2 is 64.2 MB because the Google runtime also changed.

Detailed removed-file and JAR comparisons: build/size-optimization.json. Cross-version measurement: evidence/size-comparison.json. Complete final bundle hashes: build/build-manifest.json. The final self-contained runtimes passed the full release checks, original-engine comparisons, real Google sign-in and cached-session verification.
