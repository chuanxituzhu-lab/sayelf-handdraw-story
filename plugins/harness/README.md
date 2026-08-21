# Harness plugins

Plugin manifests are trusted server-side configuration. The browser can select enabled plugins but cannot create or edit commands.

Supported transports: `builtin`, `cli`, `http`, and Streamable HTTP `mcp-http`.

Enable non-builtin plugins with a comma-separated allowlist:

```text
SAYELF_HARNESS_ALLOW=codex,claude-code,workbuddy
```

Load additional manifests from `SAYELF_PLUGIN_DIR`. CLI commands execute without a shell. API credentials must be named by `authEnv` in the manifest and supplied through the server environment.
