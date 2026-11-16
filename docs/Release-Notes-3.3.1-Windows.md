# Amua 3.3.1 Windows readability fix

Fixes the tiny interface reported on a Windows laptop in 3.3.0. Windows now scales the complete legacy Swing interface according to Settings → System → Display → Scale: menus, toolbar, sidebar, dialogs and canvas stay in the same coordinate system. Chat and message-entry text use 14-point fonts, source text 13-point, and sidebar controls 12-point.

Extract the complete new ZIP into a new folder and open Amua.exe. Save work and close the previous version first. Use Windows' recommended display scale. If you change display scaling or move between differently scaled monitors, restart Amua. This compatibility approach may look softer than native high-DPI rendering. It does not change saved model zoom or calculations.

Technical fix: the pinned Java8 javaw.exe advertises DPI awareness although this UI has fixed logical sizes. The package retains the original signed runtime launcher and derives a separate unsigned amua-javaw.exe with dpiAware=false, stripping its now-invalid Authenticode certificate. The JVM also receives sun.java2d.dpiaware=false. No system registry, other Java installations, Windows settings, or numerical classes are modified. Build verification checks the exact derived bytes. Native tests query the running GUI's Windows DPI-awareness state (must be DPI-unaware for OS scaling); sidebar tests check font sizes and layout. Physical acceptance on the reported laptop remains pending.

ChatGPT and experimental Gemini remain in Amua's chatbox. Gemini live-account acceptance is still pending. Claude subscription integration remains unavailable. See the 3.3.0 notes for provider scope; 3.3.0 release assets are preserved.

Implementation references:
- https://learn.microsoft.com/en-us/windows/win32/sbscs/application-manifests
- https://docs.oracle.com/en/java/javase/25/troubleshoot/java-2d-properties.html
