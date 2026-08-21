---
name: sayelf-handdraw-story
description: Turn a short story into a structured hand-drawn video plan with reusable character, style, scene, shot, frame, and motion specifications. Use for planning or reviewing story-led hand-drawn videos; it does not render media.
---

# Sayelf Handdraw Story

Produce a deterministic planning package before any image or video generation.

## Workflow

1. Extract story beats without inventing plot events.
2. Define stable character and prop identities before scene planning.
3. Select one style profile and keep it unchanged across the project.
4. Convert beats into scenes, shots, frames, and restrained motion cues.
5. Record visual evidence for continuity decisions and human review.
6. Validate every document against the matching file in `schemas/`.
7. For a sequence, run `node interfaces/cli/index.mjs continuity <current.json> --previous <previous.json>` and resolve every reported drift before rendering.

Use `rules/visual_director_rules.yaml` for composition and continuity decisions. Use `styles/warm_handdraw_story_v1.yaml` only when a warm, tactile hand-drawn treatment matches the request.

## Boundaries

- Preserve the supplied story's meaning, chronology, and named identities.
- Prefer readable staging and small purposeful motion over decorative complexity.
- Treat character, prop, palette, and line-language continuity as hard constraints.
- Allow shot size, composition, visible subjects, and purposeful motion to change without treating them as identity drift.
- Flag uncertain creative choices for human review instead of silently expanding the story.
- Return planning data only. Rendering, model selection, publishing, and platform-specific export are outside this skill.
