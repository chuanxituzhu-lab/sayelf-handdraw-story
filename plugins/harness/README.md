# Harness plugins

Plugin manifests are trusted server-side configuration. The browser can select enabled plugins but cannot create or edit commands.

Supported transports: `builtin`, `cli`, `http`, and Streamable HTTP `mcp-http`.

Enable non-builtin plugins with a comma-separated allowlist:

```text
SAYELF_HARNESS_ALLOW=codex,claude-code,workbuddy
```

The WebUI also supports human-confirmed connections. Click a disconnected plugin, open its server-configured `authUrl` (Codex ships the official sign-in guide), finish the manual login or CLI authorization, then click “I finished authorization”. Only after that confirmation is the harness marked connected for the running server. A plugin can override its authorization page with `authUrlEnv`.

Load additional manifests from `SAYELF_PLUGIN_DIR`. CLI commands execute without a shell. API credentials must be named by `authEnv` in the manifest and supplied through the server environment.

## Media previews

An image or video provider can return a `media` array alongside its assistant text:

```json
{"message":"这里是预览", "media":[{"type":"image","url":"https://example.test/story.png","alt":"story frame"},{"type":"video","url":"https://example.test/story.mp4","alt":"motion preview"}]}
```

The server keeps this structured result backstage and the WebUI renders image previews and native video controls. Only `http`, `https`, and image/video data URLs are accepted; at most eight items are displayed.
