# 3.3.0 provider checks

New controlled checks cover provider isolation, no API-key environment inheritance, stalled child termination, account-marker binding, private-thought filtering, and disabled agent tools. Bundled CLI handshake is checked without inference on native Windows. No claim of live Google subscription acceptance; Claude is unavailable. Historical 3.2.4 review follows.

# Windows audit and correction tracking

This review challenges the assumption that a Java application becomes portable simply by replacing its runtime. The existing Windows prototype was incomplete. Findings below must be checked against actual Windows results before publication.

| Finding | Correction and required evidence |
| --- | --- |
| Actual startup exited because an expected icon was missing | Copy the root icon and verify its source/package digest; exercise real GUI startup |
| Removing Windows system variables corrupted OS cache paths | Preserve SystemDrive/ProgramData/system program folders; launch in a disposable Unicode profile and reject literal %SystemDrive% folders |
| Permission tests depended on blocked PowerShell module loading | Query native .NET ACLs directly, without changing machine execution policy |
| Forced termination could retain confidential input snapshots | Hold XML/command files with Windows delete-on-close handles; force-kill test checks both disappear; OCR PDF stays in memory |
| POSIX imports/signals/resource budgets crash Windows parsing | Windows locks, native job memory/CPU limits and a wall deadline; packaged helper intake/save/reopen test |
| Directory fsync reports failure after a successful Windows save | Preserve file flush, backup, verified atomic replacement and lock; platform-specific directory handling; native save fault-boundary tests; power-loss durability remains unproved |
| POSIX process-group cancellation and Java path fail on Windows | Suspended native child assigned to kill-on-close job before resume; owner-death, bounded output and snapshot-cleanup tests |
| Read-only MCP liveness used os.kill(pid,0) | Windows OpenProcess/query exit status, never a signal; native status must leave the app alive |
| Launcher was a console executable | PE GUI subsystem, Unicode quoting, embedded icon/version and native front-door launch test |
| Host Python environment and codepage could change startup or corrupt Unicode | Clear Python customization variables, disable user site, force UTF-8; native launch with poisoned Python environment and Unicode source test |
| Secure account backend was not integrated into the packaged app | Bundle Windows Credential Manager backend; native chunking/rotation/cleanup test without actual credentials or plaintext fallback |
| Mac-only PDF OCR could silently leave Windows pages unreadable | App-owned bounded Windows PDF/OCR adapter; installed English OCR availability and extraction test; unknown confidence is not fabricated |
| POSIX-only permissions/tests do not establish Windows privacy | Native ACL checks for screenshot storage, Windows credential tests and explicit OS-specific test replacements/skips |
| Spaces/Unicode paths and argument limits can break builds and launching | Javac argument files, native Windows quoting and GUI/profile tests; no shell evaluation of source paths |

Public source excludes private workbooks, account state and historical online transcripts. Existing Intel release assets and numerical algorithms remain unchanged. Tests use controlled image responses and synthetic accounts; they do not establish live image-reading or clinical correctness. Native Windows desktop/language availability, SmartScreen/unsigned preview, and crash/network filesystem limits remain explicit acceptance boundaries.
