# Amua 3.3.0 Windows preview

All conversation stays in the Amua AI Workflow sidebar. Choose ChatGPT or Gemini, connect your own account, select an evidence folder, and describe the decision tree you need. Existing source inventory, reviewed outgoing evidence, native editable proposals, conversational edits, and Review workspace critique share the same validation path.

Gemini uses bundled official Gemini CLI 0.68.0 and Node 24.11.1 through ACP. Connect account opens Google's browser sign-in; conversation returns to Amua. Use the Google account associated with your eligible subscription. Google controls entitlement, quota and availability. No API-key or Vertex billing fallback is offered. Gemini defaults to the model selected by the official CLI/account; Amua does not promise a specific model or paid-plan entitlement.

**Claude subscription support is unavailable.** Its entry explains the limitation and sends nothing. This preview does not deliver all three working providers. Anthropic's documented subscription access rules do not establish an embedded Amua integration meeting the user's requirements.

The Gemini profile is separate from existing CLI settings/accounts. CLI tools, hooks, and MCP servers are disabled; Amua denies ACP permission/file/terminal requests. Model proposals are parsed and validated locally, then require review before application. Disable connection removes Amua's connection marker; it does not revoke Google tokens. Revoke remote access using your Google account. Google CLI manages its own credential storage in the dedicated profile, not Amua's ChatGPT Credential Manager store. Evidence/history may persist in Google's CLI profile; keep the Windows user profile private.

Native Windows build/test results are supplied by Actions, including a no-inference real CLI protocol check. Controlled responses test routing and model handling. A real Google sign-in, subscription entitlement, end-to-end evidence-to-tree response and physical desktop acceptance remain pending. No live inference or quota was used during development.

Unsigned Windows x64 preview. Original numerical engine retained. Existing 3.2.4 release files are not replaced.

Sources: https://geminicli.com/docs/cli/acp-mode/ ; https://geminicli.com/docs/get-started/authentication/ ; https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account
