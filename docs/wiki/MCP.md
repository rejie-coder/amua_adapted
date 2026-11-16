# Connect through MCP

The optional MCP bridge controls the local running Amua application. Built-in AI Workflow can create/edit native model proposals without MCP; the two paths are separate and success in one does not prove the other.

The Intel 3.2.4 bundle includes `Contents/Resources/amua_mcp.py`, a Python stdio MCP server and one-call command-line bridge. For an app installed in Applications, a read-only check is:

```sh
/Applications/Amua.app/Contents/Resources/python/bin/python3 \
  /Applications/Amua.app/Contents/Resources/amua_mcp.py --call status
```

Run `--help` to inspect the bundled interface. A client that supports stdio MCP can use that Python executable as the command and the bridge script as its argument. The app must be running in the same user's normal desktop session. The bridge uses the version-specific `Amua-v3.2.4` support directory and local access token; do not publish that directory or token.

This release does not automatically replace an existing MCP registration. Check the configured application path when multiple versions are installed. Inspect observed controls before acting, inspect dialogs and console after actions, and save to a new `.amua` path unless replacement is explicitly intended. A Run click is not evidence that a simulation completed.

On Windows, use the bundled `Amua/Resources/python/python.exe` as the stdio command and `Amua/Resources/amua_mcp.py` as its script argument. Use absolute paths in the client configuration. The application’s MCP screen supplies PowerShell quoting for its actual installation path. Read-only process liveness uses Windows query APIs; status does not signal Java. See [Windows setup](https://github.com/rejie-coder/amua_adapted/wiki/Windows).
