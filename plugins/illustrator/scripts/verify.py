#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-visual-director · 出图一致性校验器 (Consistency Verifier)
===========================================================

闭环的最后一环。回答一个**可证伪的封闭问题**：
    装配时那个焦点道具 Prop，在成图里真的出现了吗？

不判美丑、不判高级感——那是主观的，交给人。校验器只做客观的"焦点物命中"判定，
因为只有客观判定才能驱动"不达标→换 seed 重出"的确定性循环。

看图用**已配置的视觉模型**（复用出图那把 key，零新依赖，host-first）：
  · gemini → generateContent 多模态（图 + 文，返回 JSON）
  · openai → /v1/chat/completions 多模态（gpt-4o 系）
key 只从环境变量读，与 execute.py 同源。

判定协议（逼模型给结构化答案，不写小作文）：
  输入：图片 + 焦点道具描述 Prop（+ 可选 subject/action）
  输出：{"present": true/false, "confidence": 0.0~1.0, "reason": "一句话"}
  通过条件：present == true 且 confidence >= 阈值（默认 0.6）

用法：
  # 单独校验一张已生成的图
  python verify.py --image ./out.png --prop "a towering stack of oversized cardboard boxes" --vision gemini

  # dry-run：只打印将发给视觉模型的请求（key 脱敏，不发送），离线可测
  python verify.py --image ./out.png --prop "..." --vision gemini --dry-run
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.request
from typing import Dict, Optional, Tuple

# 复用 execute.py 的 key 环境变量约定
KEY_ENV = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}

def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()

def vision_model_of(vision: str) -> str:
    return {
        "gemini": _env("AIVD_GEMINI_VISION", "gemini-3.1-flash"),  # 多模态判读用非图像版
        "openai": _env("AIVD_OPENAI_VISION", "gpt-4o"),
    }[vision]

def vision_base_of(vision: str) -> str:
    return {
        "gemini": _env("AIVD_GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta"),
        "openai": _env("AIVD_OPENAI_BASE", "https://api.openai.com/v1"),
    }[vision]


# ---- 判定指令：焦点物命中，强制 JSON 回复 ----
def build_instruction(prop: str, subject: str = "", action: str = "") -> str:
    focus = f"焦点道具(prop): {prop}"
    if subject:
        focus += f"\n主体(subject): {subject}"
    if action:
        focus += f"\n动作(action): {action}"
    return (
        "你是图像一致性审核器。判断下面这张图里，指定的焦点道具是否清晰出现在画面主体区。\n"
        f"{focus}\n\n"
        "只回一个 JSON，不要任何多余文字、不要 markdown 代码块：\n"
        '{"present": true 或 false, "confidence": 0.0到1.0的小数, "reason": "一句话依据"}\n'
        "present=道具是否作为可辨识的实体出现在画面里（不是背景噪点、不是文字提及）。"
    )


# ---- 图片读为 base64 + mime ----
def load_image_b64(path: str) -> Tuple[str, str]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"找不到图片: {path}")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii"), mime


# ---- 请求构造（返回 url, headers, body）----
def build_request(vision: str, image_b64: str, mime: str, instruction: str,
                  api_key: str) -> Tuple[str, Dict[str, str], dict]:
    model = vision_model_of(vision)
    base = vision_base_of(vision)

    if vision == "gemini":
        url = f"{base}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        body = {"contents": [{"parts": [
            {"text": instruction},
            {"inline_data": {"mime_type": mime, "data": image_b64}},
        ]}], "generationConfig": {"responseMimeType": "application/json"}}
        return url, headers, body

    if vision == "openai":
        url = f"{base}/chat/completions"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key}"}
        body = {"model": model, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": instruction},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ]}]}
        return url, headers, body

    raise ValueError(f"未知视觉 provider: {vision}")


def _post(url: str, headers: Dict[str, str], body: dict, timeout: int = 90) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---- 从各家响应里抠出模型回复的文本，再解析成判定 JSON ----
def _extract_text(vision: str, resp: dict) -> str:
    if vision == "gemini":
        parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    if vision == "openai":
        return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    return ""

def _parse_verdict(text: str) -> dict:
    t = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        v = json.loads(t)
    except json.JSONDecodeError:
        # 容错：模型偶尔夹字，抠第一个 {...}
        i, j = t.find("{"), t.rfind("}")
        if i == -1 or j == -1:
            raise RuntimeError(f"视觉模型未返回可解析 JSON: {text[:160]}")
        v = json.loads(t[i:j + 1])
    return {"present": bool(v.get("present", False)),
            "confidence": float(v.get("confidence", 0.0)),
            "reason": str(v.get("reason", ""))[:200]}


# ---- 对外主入口 ----
def verify(image_path: str, prop: str, vision: str = "gemini",
           subject: str = "", action: str = "", threshold: float = 0.6) -> dict:
    key = os.getenv(KEY_ENV[vision], "").strip()
    if not key:
        raise EnvironmentError(
            f"缺少环境变量 {KEY_ENV[vision]}（{vision} 视觉判读的 key）。"
            f" 请在宿主 export {KEY_ENV[vision]}=... 后重试。")
    image_b64, mime = load_image_b64(image_path)
    instruction = build_instruction(prop, subject, action)
    url, headers, body = build_request(vision, image_b64, mime, instruction, key)
    resp = _post(url, headers, body)
    verdict = _parse_verdict(_extract_text(vision, resp))
    verdict["passed"] = verdict["present"] and verdict["confidence"] >= threshold
    verdict["threshold"] = threshold
    verdict["vision"] = vision
    verdict["prop"] = prop
    return verdict


def dry_run(image_path: str, prop: str, vision: str,
            subject: str = "", action: str = "") -> dict:
    image_b64, mime = load_image_b64(image_path)
    instruction = build_instruction(prop, subject, action)
    url, headers, body = build_request(vision, image_b64, mime, instruction, "DRYRUN")
    # 脱敏 + 截断 base64，避免刷屏
    safe_headers = {k: ("***REDACTED***" if k.lower() in ("authorization", "x-goog-api-key") else v)
                    for k, v in headers.items()}
    body_preview = json.loads(json.dumps(body))
    _truncate_b64(body_preview)
    return {"vision": vision, "model": vision_model_of(vision),
            "key_env": KEY_ENV[vision], "key_present": bool(os.getenv(KEY_ENV[vision])),
            "url": url, "headers": safe_headers,
            "instruction": instruction, "body_preview": body_preview}

def _truncate_b64(obj) -> None:
    """递归把长 base64 串换成占位，dry-run 打印时不刷屏。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and len(v) > 80:
                obj[k] = f"<base64 {len(v)} chars 已截断>"
            else:
                _truncate_b64(v)
    elif isinstance(obj, list):
        for it in obj:
            _truncate_b64(it)


def main() -> int:
    p = argparse.ArgumentParser(description="ai-visual-director 出图一致性校验器")
    p.add_argument("--image", required=True, help="待校验的图片路径")
    p.add_argument("--prop", required=True, help="装配时的焦点道具描述")
    p.add_argument("--subject", default="")
    p.add_argument("--action", default="")
    p.add_argument("--vision", default="gemini", choices=["gemini", "openai"])
    p.add_argument("--threshold", type=float, default=0.6)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.dry_run:
        out = dry_run(args.image, args.prop, args.vision, args.subject, args.action)
    else:
        out = verify(args.image, args.prop, args.vision,
                     args.subject, args.action, args.threshold)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
