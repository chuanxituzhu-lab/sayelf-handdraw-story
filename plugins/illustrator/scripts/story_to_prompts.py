#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Storyleaf 或 sayelf-handdraw-story 的故事 JSON 转成逐帧视觉导演计划。

这是一个离线桥接器：不调用网络、不读取 API key，只复用同目录的确定性
assemble_prompt.py。每个图片提示词与一个同编号视频分镜配对，共享 subject、prop、
style、画幅和连续性说明。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from assemble_prompt import Evidence, STYLE_MATRIX, assemble


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_visual_identity(items: Any, fallback: str) -> str:
    if not isinstance(items, list):
        return fallback
    for item in items:
        if not isinstance(item, dict):
            continue
        identity = item.get("visual_identity")
        if isinstance(identity, dict):
            details = [item.get("name"), identity.get("shape"), identity.get("costume"), identity.get("palette")]
            value = ", ".join(_text(part) for part in details if _text(part))
        else:
            value = _text(item.get("name"))
        if value:
            return value
    return fallback


def _frame_items(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    frames = payload.get("frames")
    if isinstance(frames, list) and frames:
        shots = {item.get("id"): item for item in payload.get("shots", [])
                 if isinstance(item, dict) and item.get("id")}
        motions: Dict[str, List[str]] = {}
        for motion in payload.get("motions", []):
            if isinstance(motion, dict) and motion.get("shot_id") and _text(motion.get("action")):
                motions.setdefault(motion["shot_id"], []).append(_text(motion["action"]))
        enriched = []
        for raw in frames:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            shot = shots.get(item.get("shot_id"), {})
            if shot:
                motion_text = "; ".join(motions.get(shot.get("id"), []))
                if not _text(item.get("action")):
                    intent = _text(shot.get("visual_intent"))
                    item["action"] = "; ".join(value for value in (intent, motion_text) if value)
                item.setdefault("duration", shot.get("duration"))
                item.setdefault("camera", shot.get("camera") or shot.get("size"))
            enriched.append(item)
        return enriched
    shots = payload.get("shots")
    if isinstance(shots, list) and shots:
        return [item for item in shots if isinstance(item, dict)]
    raise ValueError("故事 JSON 缺少非空 frames 或 shots 数组")


def _frame_action(frame: Dict[str, Any]) -> str:
    return next((value for value in (_text(frame.get("scene")), _text(frame.get("action")),
                                     _text(frame.get("visual_intent")), _text(frame.get("source"))) if value), "")


def _frame_seconds(frame: Dict[str, Any]) -> float | None:
    for key in ("seconds", "duration"):
        value = frame.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def build_plan(payload: Dict[str, Any], subject: str, prop: str,
               style: str, ratio: str, model: str, seed: int | None,
               trace: str = "") -> Dict[str, Any]:
    frames = list(_frame_items(payload))
    if not subject:
        subject = _first_visual_identity(payload.get("characters"), "")
    if not prop:
        prop = _first_visual_identity(payload.get("props"), "")
    if not subject or not prop:
        raise ValueError("必须提供 --subject 与 --prop，或在 canonical 项目的 characters/props 中提供它们")

    shared_trace = _text(trace) or _text(payload.get("continuity"))
    output_frames: List[Dict[str, Any]] = []
    for index, frame in enumerate(frames):
        frame_id = _text(frame.get("id")) or f"F{index + 1:03d}"
        action = _frame_action(frame)
        if not action:
            raise ValueError(f"帧 {frame_id} 缺少 scene/action/visual_intent/source")
        frame_seed = None if seed is None else seed * 100 + index
        evidence = Evidence(subject=subject, action=action, prop=prop,
                            trace=_text(frame.get("trace")) or shared_trace)
        assembled = assemble(evidence, style, ratio, model, frame_seed,
                             hook_line=_text(payload.get("title")) or _text(payload.get("story", {}).get("title")))
        seconds = _frame_seconds(frame)
        camera = _text(frame.get("camera")) or _text(frame.get("size"))
        video_prompt = action
        if camera:
            video_prompt += f"\n运镜：{camera}"
        if shared_trace:
            video_prompt += f"\n连续性：{shared_trace}"
        output_frames.append({
            "id": frame_id,
            "seconds": seconds,
            "image": {
                "positive_prompt": assembled["positive_prompt"],
                "negative_prompt": assembled["negative_prompt"],
                "composition": assembled["composition"],
                "seed": assembled["seed"],
            },
            "video": {
                "id": frame_id,
                "seconds": seconds,
                "prompt": video_prompt,
                "camera": camera,
                "transition": _text(frame.get("transition")),
                "sound": _text(frame.get("sound")),
            },
        })

    ids = [frame["id"] for frame in output_frames]
    return {
        "version": "1.0",
        "title": _text(payload.get("title")) or _text(payload.get("story", {}).get("title")) or "未命名故事",
        "source_version": payload.get("version"),
        "style": style,
        "model": model,
        "ratio": ratio,
        "frame_count": len(output_frames),
        "continuity_lock": {"subject": subject, "prop": prop, "trace": shared_trace},
        "image_ids": ids,
        "video_ids": ids,
        "frames": output_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Storyleaf → Visual Director 离线桥接器")
    parser.add_argument("--story", required=True, help="Storyleaf 或 canonical 项目的 JSON 文件")
    parser.add_argument("--subject", default="", help="稳定主体；canonical 项目可省略")
    parser.add_argument("--prop", default="", help="稳定焦点道具；canonical 项目可省略")
    parser.add_argument("--trace", default="", help="共享连续性说明，默认读取故事 JSON 的 continuity")
    parser.add_argument("--style", default="pen_line_vibrant", choices=list(STYLE_MATRIX))
    parser.add_argument("--ratio", default="", help="画幅；默认读取故事 JSON 的 ratio，否则 16:9")
    parser.add_argument("--model", default="gemini", help="assemble_prompt 支持的模型路由")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="", help="输出 JSON 文件；省略则打印到 stdout")
    args = parser.parse_args()

    payload = json.loads(Path(args.story).read_text(encoding="utf-8"))
    ratio = _text(args.ratio) or _text(payload.get("ratio")) or "16:9"
    plan = build_plan(payload, _text(args.subject), _text(args.prop), args.style,
                       ratio, args.model, args.seed, _text(args.trace))
    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
