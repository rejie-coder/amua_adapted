# Third party components and source

Original copyright and licence notices remain in the source and bundled runtime distributions. The adaptation licence does not replace third-party licences.

| Component | Included purpose and source |
| --- | --- |
| Amua 0.3.6 by Zachary J. Ward | Original engine/framework; GPLv3-or-later headers and full licence retained. Adapted source is in `src/upstream`; [upstream source](https://github.com/zward/Amua) and pinned original release are recorded in the build manifest. |
| Azul Zulu OpenJDK 8u512-b09 | Bundled Java runtime and build compiler. Its retained `LICENSE`, `ASSEMBLY_EXCEPTION` and `THIRD_PARTY_README` describe GPLv2 with Classpath Exception and third-party notices. [Vendor binaries/source](https://www.azul.com/downloads/?package=jdk#zulu). |
| CPython 3.12.16 standalone | Bundled Python runtime from python-build-standalone. Its distribution licences and library notices are retained. [CPython source](https://github.com/python/cpython), [standalone build project](https://github.com/astral-sh/python-build-standalone). Exact artifact/hash is pinned. |
| pypdf 7.1.0 | Local PDF parsing. Vendored source and BSD licence are retained under `src/dependencies/python` and bundled Python libraries. |
| JFreeChart 1.0.19 and JCommon 1.0.23 | Original chart dependencies, distributed within the pinned upstream container. LGPL notices/source are available from the respective [JFreeChart](https://github.com/jfree/jfreechart) and [JCommon](https://github.com/jfree/jcommon) projects. |
| Apache Commons Math 3.6.1 | Original numerical dependency; Apache licence/notice from the container is retained in `docs/third-party/baseline/META-INF`. [Project source](https://commons.apache.org/proper/commons-math/). |
| JAXB RI and related libraries | Original XML-binding dependencies retained from the upstream container. Exact declarations appear in `src/upstream/.classpath` and `src/dependencies/manifest.json`; notices and source are maintained by the [JAXB project](https://github.com/eclipse-ee4j/jaxb-ri). |
| Fonts and image resources | Original resource files and copyright headers are retained; font metadata identifies the corresponding Noto families. Adapted app artwork is included as source assets. |

The release source archive contains application source, resources and build/release scripts. Runtime/dependency sources and licence exceptions remain under their vendors' terms; consult the retained distributions and upstream projects when redistributing or changing them. The original dependency container is downloaded with a pinned SHA256 rather than silently replaced by a newer binary.

The Windows source tag additionally records SHA256-pinned Windows Java/Python runtime and Zig compiler inputs in `scripts/toolchains-windows.json`. Zig is a build tool, not bundled with the app. Windows OCR uses OS Windows.Media.Ocr and Windows.Data.Pdf components; these OS components are not redistributed. Runtime licenses remain inside the portable application.


## Google runtime in Mac 3.3.3

The app bundles Google Antigravity CLI 1.5.9, downloaded from the official Google release archive with SHA512 verification. The executable remains Google Developer-ID-signed. Google service terms and account eligibility apply. The old Node/Gemini CLI package is not included in this Mac version. Google integration: https://antigravity.google/docs/ide/extensions/acp/. Exact archive URL/digests: src/native-support/bootstrap_antigravity.py.
