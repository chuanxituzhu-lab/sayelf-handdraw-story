from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins" / "illustrator" / "scripts"))
from story_to_prompts import build_plan  # noqa: E402


class StoryToPromptsTests(unittest.TestCase):
    def read(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_storyleaf_frames_keep_image_video_ids_in_lockstep(self) -> None:
        payload = self.read("storyleaf/完整Demo/最后一根稻草.json")
        plan = build_plan(
            payload,
            "the same sand-brown one-humped camel, both eyes visible",
            "red load rope, blue rolled blanket, square wicker basket, one golden straw",
            "pen_line_vibrant",
            "9:16",
            "gemini",
            42,
        )
        self.assertEqual(plan["frame_count"], 5)
        self.assertEqual(plan["image_ids"], plan["video_ids"])
        self.assertEqual(plan["frames"][0]["id"], "F001")

    def test_canonical_project_derives_subject_prop_and_motion(self) -> None:
        payload = self.read("examples/story-sequence/shot-01.json")
        plan = build_plan(payload, "", "", "pen_line_vibrant", "16:9", "gemini", 7)
        self.assertEqual(plan["frame_count"], 1)
        self.assertEqual(plan["image_ids"], plan["video_ids"])
        self.assertIn("drift gently right", plan["frames"][0]["video"]["prompt"])


if __name__ == "__main__":
    unittest.main()
