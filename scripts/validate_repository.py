#!/usr/bin/env python3
"""Validate the frozen v0.1.0 repository contract without third-party packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    schemas = sorted(SCHEMA_DIR.glob("*.schema.json"))
    expected = {
        "beat", "character", "frame", "motion", "project", "prop",
        "relation", "scene", "shot", "story", "style", "visual_evidence",
    }
    found = {path.name.removesuffix(".schema.json") for path in schemas}
    if found != expected:
        fail(f"schema set mismatch: expected {sorted(expected)}, found {sorted(found)}", errors)

    for path in schemas:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"{path.relative_to(ROOT)}: invalid JSON: {exc}", errors)
            continue
        if document.get("$schema") != SCHEMA_DRAFT:
            fail(f"{path.relative_to(ROOT)}: must declare Draft 2020-12", errors)
        if document.get("type") != "object":
            fail(f"{path.relative_to(ROOT)}: root type must be object", errors)
        if not document.get("required"):
            fail(f"{path.relative_to(ROOT)}: must define required fields", errors)
        pending = [document]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str) and not reference.startswith(("#", "http://", "https://")):
                    target = (path.parent / reference.split("#", 1)[0]).resolve()
                    if not target.is_file():
                        fail(f"{path.relative_to(ROOT)}: unresolved $ref {reference!r}", errors)
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)

    text_checks = {
        ROOT / "SKILL.md": ["---", "name: sayelf-handdraw-story", "description:"],
        ROOT / "rules" / "visual_director_rules.yaml": ["version:", "continuity:", "staging:", "motion:"],
        ROOT / "styles" / "warm_handdraw_story_v1.yaml": ["id:", "line:", "color:", "texture:", "lighting:"],
        ROOT / "docs" / "validation" / "DAY30_REVIEW.md": ["# Day 30 Final Review", "## Version Decision"],
    }
    for path, markers in text_checks.items():
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}", errors)
            continue
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                fail(f"{path.relative_to(ROOT)}: missing {marker!r}", errors)

    runtime_files = [
        ROOT / "package.json",
        ROOT / "core" / "continuity.mjs",
        ROOT / "interfaces" / "cli" / "index.mjs",
        ROOT / "interfaces" / "web" / "server.mjs",
        ROOT / "interfaces" / "web" / "public" / "index.html",
        ROOT / "interfaces" / "web" / "public" / "styles.css",
        ROOT / "interfaces" / "web" / "public" / "app.js",
        ROOT / "tests" / "continuity.test.mjs",
        ROOT / "tests" / "web.test.mjs",
        ROOT / "examples" / "story-sequence" / "shot-01.json",
        ROOT / "examples" / "story-sequence" / "shot-02.json",
    ]
    for path in runtime_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing or empty {path.relative_to(ROOT)}", errors)

    if errors:
        print("repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"repository validation passed: {len(schemas)} schemas and 4 contract files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
