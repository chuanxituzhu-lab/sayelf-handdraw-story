# sayelf-handdraw-story

A schema-first Codex skill for turning stories into consistent hand-drawn video plans.

## Status

`v0.1.0` maintenance candidate. The repository defines planning contracts and visual-direction rules; image/video generation remains provider-side. The local WebUI can display provider-returned image and video previews without exposing hidden project JSON.

## Repository contract

- `SKILL.md` — skill entry point and frozen product boundary.
- `schemas/` — JSON Schema contracts for project planning data.
- `rules/visual_director_rules.yaml` — continuity and staging rules.
- `styles/warm_handdraw_story_v1.yaml` — bundled style profile.
- `scripts/validate_repository.py` — dependency-free repository validation.
- `core/continuity.mjs` — deterministic project, reference, timeline, and continuity checks.
- `interfaces/cli/index.mjs` — local `validate` and `continuity` commands.
- `interfaces/web/` — private local WebUI and JSON API using Node.js standard libraries.
- `examples/story-sequence/` — two consecutive project snapshots.
- `tests/` — Node built-in regression tests.
- `docs/validation/DAY30_REVIEW.md` — evidence-based maintenance review.

## Validate

```text
python scripts/validate_repository.py
```

The command checks that every required artifact exists, JSON Schemas parse and declare Draft 2020-12, YAML assets contain their required top-level keys, and the skill entry point has valid frontmatter.

Run the executable continuity tests with Node.js 20 or newer:

```text
npm test
npm run validate:example
npm run continuity:example
npm run web
```

Then open `http://127.0.0.1:4175`. The WebUI accepts natural-language story instructions; structured JSON stays inside the local server process. If a Harness returns a `media` array, generated image previews and native video playback appear in the conversation.

The default WebUI is now a bilingual natural-language workspace. Project JSON remains server-side and the browser receives only a validated summary. A local guide is always available; external AI harnesses are disabled until explicitly allowlisted:

```text
SAYELF_HARNESS_ALLOW=codex,claude-code,workbuddy
```

Built-in plugin manifests live in `plugins/harness/`. Additional trusted manifests can be loaded with `SAYELF_PLUGIN_DIR`. Supported transports are shell-free CLI execution, HTTP APIs, and Streamable HTTP MCP. API keys are read from environment variables declared by server-side manifests and are never returned to the browser. Disconnected external harnesses can be connected from the WebUI through a human authorization step: open the configured authorization link, complete provider login or CLI sign-in, then confirm in the WebUI.

`validate` reports broken identifiers, references, and timeline ranges. `continuity` additionally compares stable character, prop, style, scene-location, and scene-time fields with a previous snapshot. A report is either `PASS` or `REVISE`; the CLI exits with code `2` for a revision request.

## Frozen boundary

Connected CLI harnesses also support live sessions. The WebUI keeps an SSE event stream open for incremental assistant output, sends follow-up user messages to the same session, and applies each completed turn to the hidden workspace. The raw session endpoints are `/api/live-sessions`, `/api/live-sessions/:id/events`, and `/api/live-sessions/:id/messages`.

Allowed in `v0.1.x`: bug fixes, schema corrections, tests, validation evidence, and documentation. New renderers, providers, editing surfaces, platforms, and workflow layers require a separately validated version proposal.
