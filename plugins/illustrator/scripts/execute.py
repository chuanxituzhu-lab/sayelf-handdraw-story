#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-visual-director · 统一执行适配器 (Unified Execution Adapter)
==============================================================

职责：接在 assemble_prompt.py 之后，把装配好的 positive_prompt 真正发给文生图 API，
把像素画出来，返回本地图片路径（+ 可能的远程 URL）。这是把"出图计划"变成"图"的最后一步。

零密钥入体（安全铁律）：
  · 本文件不含任何 API key，全部从**环境变量**读取。
  · key 留在宿主，skill 只借用，符合 host-first / 创作逻辑本地化。

四家现役 provider（2026-08 核对官方文档；模型名/端点均可用环境变量覆盖，防止版本漂移）：
  ┌──────────┬───────────────────────────────┬──────────────────────────────────────────┬───────────────────┬────────┐
  │ provider │ 默认模型                      │ 端点                                       │ 环境变量(key)     │ 返回   │
  ├──────────┼───────────────────────────────┼──────────────────────────────────────────┼───────────────────┼────────┤
  │ gemini   │ gemini-3.1-flash-image        │ generativelanguage…/…:generateContent      │ GEMINI_API_KEY    │ base64 │
  │ openai   │ gpt-image-2 (DALL-E 3 已退役) │ api.openai.com/v1/images/generations       │ OPENAI_API_KEY    │ base64 │
  │ qwen     │ wan2.6-image                  │ dashscope…/api/v1/…/text2image/…(async)    │ DASHSCOPE_API_KEY │ URL    │
  │ seedream │ doubao-seedream-4-0-250828    │ ark.cn-beijing.volces.com/api/v3/images/…  │ ARK_API_KEY       │ URL    │
  └──────────┴───────────────────────────────┴──────────────────────────────────────────┴───────────────────┴────────┘

依赖：仅标准库（urllib / json / base64）。无需 pip install，符合一键傻瓜部署。

⚠️ 沙箱无法联网到这些 provider，本文件的真实出图需在**宿主环境**冒烟。
   为此提供 --dry-run：只组装并打印 请求 URL/头(key 脱敏)/体，不发送——可离线核对正确性。

用法：
  # 离线核对四家请求长啥样（key 脱敏，不发送）
  python execute.py --dry-run --provider all --prompt "a tired man reaching for a falling box"

  # 真实出图（需宿主已配置对应环境变量）
  python execute.py --provider gemini --prompt "..." --ratio 16:9 --out ./out.png

  # 从 assemble_prompt.py 的 JSON 直接接力（管道）
  python assemble_prompt.py --demo | python execute.py --from-plan --provider gemini --out ./out.png

  # 按降级链自动切（主路失败依次下移）
  python execute.py --provider auto --prompt "..." --out ./out.png
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 降级链默认顺序（与 assemble_prompt.FALLBACK_ORDER 对齐；seedream 在 auto 链尾兜底）
DEFAULT_CHAIN: List[str] = ["gemini", "openai", "qwen", "seedream"]

# ---- 环境变量名（key 只从这里读，绝不写进代码）----
KEY_ENV = {
    "gemini":   "GEMINI_API_KEY",
    "openai":   "OPENAI_API_KEY",
    "qwen":     "DASHSCOPE_API_KEY",
    "seedream": "ARK_API_KEY",
    # —— 预留位：Midjourney 至今无官方公开 API（2026-08 核实）——
    # 官方仅 Discord/网页；第三方 wrapper 违反 ToS 有封号风险，故不默认接线。
    # 待官方 API 落地或拿到企业开发者权限后，此处填对应 key 环境变量即可启用。
    "midjourney": "MJ_API_KEY",
}

# 已接线的现役 provider（midjourney 不在此列，属预留占位）
WIRED_PROVIDERS = ["gemini", "openai", "qwen", "seedream"]

# ---- 模型名 / 端点默认值，全部可被环境变量覆盖，防止版本漂移写死进代码 ----
def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()

def model_of(provider: str) -> str:
    return {
        "gemini":   _env("AIVD_GEMINI_MODEL",   "gemini-3.1-flash-image"),
        "openai":   _env("AIVD_OPENAI_MODEL",   "gpt-image-2"),
        "qwen":     _env("AIVD_QWEN_MODEL",     "wan2.6-image"),
        "seedream": _env("AIVD_SEEDREAM_MODEL", "doubao-seedream-4-0-250828"),
        # 预留：官方 API 落地后填现役版本，默认给当前默认模型名占位
        "midjourney": _env("AIVD_MJ_MODEL",     "midjourney-v8.1"),
    }[provider]

def base_of(provider: str) -> str:
    return {
        "gemini":   _env("AIVD_GEMINI_BASE",   "https://generativelanguage.googleapis.com/v1beta"),
        "openai":   _env("AIVD_OPENAI_BASE",   "https://api.openai.com/v1"),
        # 百炼地域不同 base 不同：北京 dashscope.aliyuncs.com / 新加坡 dashscope-intl.aliyuncs.com
        "qwen":     _env("AIVD_QWEN_BASE",     "https://dashscope.aliyuncs.com/api/v1"),
        "seedream": _env("AIVD_SEEDREAM_BASE", "https://ark.cn-beijing.volces.com/api/v3"),
        # 预留：无官方端点，留空。接入官方/企业 API 或自选 wrapper 时用 AIVD_MJ_BASE 注入
        "midjourney": _env("AIVD_MJ_BASE",     ""),
    }[provider]

# ---- 画幅 → 各家 size 词表（每家方言不同）----
def size_for(provider: str, ratio: str) -> str:
    landscape = {"16:9", "3:2", "21:9", "4:3"}
    portrait  = {"9:16", "2:3", "3:4"}
    if provider == "openai":
        # gpt-image-2 仅接受这几档
        if ratio in landscape: return "1536x1024"
        if ratio in portrait:  return "1024x1536"
        return "1024x1024"
    if provider == "qwen":
        # 万相用 * 分隔；给常见几档
        if ratio in landscape: return "1280*720"
        if ratio in portrait:  return "720*1280"
        return "1024*1024"
    if provider == "seedream":
        # 火山方舟支持 1K/2K/4K 或精确像素；用精确像素最稳
        if ratio in landscape: return "1280x720"
        if ratio in portrait:  return "720x1280"
        return "1024x1024"
    if provider == "midjourney":
        # MJ 用 --ar，尺寸由模型定；此处仅给占位（wrapper 若需 size 再调）
        return "1024x1024"
    # gemini 用 aspect_ratio 而非像素，size 不用于请求体
    return "1024x1024"


# ============================================================================ #
# 请求构造：每家返回 (url, headers, body_dict)。dry-run 只打印这三样。
# ============================================================================ #
def build_request(provider: str, prompt: str, ratio: str, api_key: str
                  ) -> Tuple[str, Dict[str, str], dict]:
    model = model_of(provider)
    base = base_of(provider)

    if provider == "gemini":
        # 原生 generateContent：图像走 inline_data 返回 base64
        url = f"{base}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json",
                   "x-goog-api-key": api_key}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": ratio},
            },
        }
        return url, headers, body

    if provider == "openai":
        url = f"{base}/images/generations"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key}"}
        body = {"model": model, "prompt": prompt,
                "size": size_for(provider, ratio), "n": 1}
        return url, headers, body

    if provider == "seedream":
        # 火山方舟，OpenAI 兼容格式
        url = f"{base}/images/generations"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key}"}
        body = {"model": model, "prompt": prompt,
                "size": size_for(provider, ratio),
                "response_format": "url", "watermark": False}
        return url, headers, body

    if provider == "qwen":
        # 百炼 文生图 V2 异步端点：先提交任务，再轮询（见 call_qwen）
        url = f"{base}/services/aigc/text2image/image-synthesis"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key}",
                   "X-DashScope-Async": "enable"}
        w, h = size_for(provider, ratio).split("*")
        body = {"model": model,
                "input": {"prompt": prompt},
                "parameters": {"size": f"{w}*{h}", "n": 1}}
        return url, headers, body

    if provider == "midjourney":
        # ⚠ 预留占位：MJ 无官方公开 API（2026-08 核实）。
        # 下面按最常见的第三方 wrapper OpenAI 兼容形态预置骨架；
        # 未设 AIVD_MJ_BASE 时 build 会在 call_midjourney 里被拦截，不会误发。
        url = f"{base}/images/generations" if base else "<MJ_BASE_未配置>/images/generations"
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {api_key}"}
        body = {"model": model, "prompt": prompt,
                "size": size_for(provider, ratio)}
        return url, headers, body

    raise ValueError(f"未知 provider: {provider}")


# ============================================================================ #
# HTTP 工具（纯标准库）
# ============================================================================ #
def _post(url: str, headers: Dict[str, str], body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _get(url: str, headers: Dict[str, str], timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _download(url: str, out_path: str, timeout: int = 120) -> None:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(out_path, "wb") as f:
        f.write(resp.read())


# ============================================================================ #
# 各家真实调用：统一返回 {"provider","model","local_path","remote_url"}
# ============================================================================ #
def _save_b64(b64: str, out_path: str) -> None:
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))

def call_gemini(prompt, ratio, api_key, out_path) -> dict:
    url, headers, body = build_request("gemini", prompt, ratio, api_key)
    resp = _post(url, headers, body)
    # candidates[0].content.parts[].inline_data.data = base64
    for part in resp.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inline_data") or part.get("inlineData")
        if inline and inline.get("data"):
            _save_b64(inline["data"], out_path)
            return {"provider": "gemini", "model": model_of("gemini"),
                    "local_path": out_path, "remote_url": None}
    raise RuntimeError(f"gemini 返回无图像数据: {json.dumps(resp)[:200]}")

def call_openai(prompt, ratio, api_key, out_path) -> dict:
    url, headers, body = build_request("openai", prompt, ratio, api_key)
    resp = _post(url, headers, body)
    d0 = resp.get("data", [{}])[0]
    if d0.get("b64_json"):
        _save_b64(d0["b64_json"], out_path)
        return {"provider": "openai", "model": model_of("openai"),
                "local_path": out_path, "remote_url": None}
    if d0.get("url"):
        _download(d0["url"], out_path)
        return {"provider": "openai", "model": model_of("openai"),
                "local_path": out_path, "remote_url": d0["url"]}
    raise RuntimeError(f"openai 返回无图像: {json.dumps(resp)[:200]}")

def call_seedream(prompt, ratio, api_key, out_path) -> dict:
    url, headers, body = build_request("seedream", prompt, ratio, api_key)
    resp = _post(url, headers, body)
    d0 = resp.get("data", [{}])[0]
    if d0.get("url"):
        _download(d0["url"], out_path)
        return {"provider": "seedream", "model": model_of("seedream"),
                "local_path": out_path, "remote_url": d0["url"]}
    if d0.get("b64_json"):
        _save_b64(d0["b64_json"], out_path)
        return {"provider": "seedream", "model": model_of("seedream"),
                "local_path": out_path, "remote_url": None}
    raise RuntimeError(f"seedream 返回无图像: {json.dumps(resp)[:200]}")

def call_qwen(prompt, ratio, api_key, out_path, poll_interval=3, max_wait=180) -> dict:
    # 1) 提交异步任务
    url, headers, body = build_request("qwen", prompt, ratio, api_key)
    submit = _post(url, headers, body)
    task_id = submit.get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"qwen 未返回 task_id: {json.dumps(submit)[:200]}")
    # 2) 轮询任务结果
    q_headers = {"Authorization": f"Bearer {api_key}"}
    task_url = f"{base_of('qwen')}/tasks/{task_id}"
    waited = 0
    while waited < max_wait:
        r = _get(task_url, q_headers)
        status = r.get("output", {}).get("task_status")
        if status == "SUCCEEDED":
            results = r.get("output", {}).get("results", [])
            img_url = results[0].get("url") if results else None
            if not img_url:
                raise RuntimeError(f"qwen 成功但无 url: {json.dumps(r)[:200]}")
            _download(img_url, out_path)
            return {"provider": "qwen", "model": model_of("qwen"),
                    "local_path": out_path, "remote_url": img_url}
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            raise RuntimeError(f"qwen 任务失败: {json.dumps(r)[:200]}")
        time.sleep(poll_interval)
        waited += poll_interval
    raise RuntimeError(f"qwen 轮询超时 {max_wait}s")

def call_midjourney(prompt, ratio, api_key, out_path) -> dict:
    # ⚠ 预留占位：MJ 无官方公开 API。只有当宿主显式注入 AIVD_MJ_BASE
    #   （指向官方企业端点或你自选的第三方 wrapper）时才放行，否则清晰拒绝、不静默。
    base = base_of("midjourney")
    if not base:
        raise NotImplementedError(
            "Midjourney 暂无官方公开 API（2026-08 核实），未接线。\n"
            "  · 官方仅 Discord/网页；第三方 wrapper 违反 MJ 服务条款、有封号风险，需自行评估。\n"
            "  · 如已拿到官方企业 API 或决定用某 wrapper，注入两个环境变量即可启用：\n"
            "      export AIVD_MJ_BASE='https://<你的端点>/v1'\n"
            "      export MJ_API_KEY='...'\n"
            "    （必要时再用 AIVD_MJ_MODEL 覆盖模型名；返回结构若非 OpenAI 兼容，回报以校准）")
    # —— 已注入 base：按 OpenAI 兼容 wrapper 尝试（同 seedream 解析）——
    url, headers, body = build_request("midjourney", prompt, ratio, api_key)
    resp = _post(url, headers, body)
    d0 = resp.get("data", [{}])[0]
    if d0.get("url"):
        _download(d0["url"], out_path)
        return {"provider": "midjourney", "model": model_of("midjourney"),
                "local_path": out_path, "remote_url": d0["url"]}
    if d0.get("b64_json"):
        _save_b64(d0["b64_json"], out_path)
        return {"provider": "midjourney", "model": model_of("midjourney"),
                "local_path": out_path, "remote_url": None}
    raise RuntimeError(f"midjourney wrapper 返回结构未知，需校准: {json.dumps(resp)[:200]}")

CALLERS = {"gemini": call_gemini, "openai": call_openai,
           "qwen": call_qwen, "seedream": call_seedream,
           "midjourney": call_midjourney}


# ============================================================================ #
# 对外主入口：单 provider / auto 降级
# ============================================================================ #
def generate(provider: str, prompt: str, ratio: str, out_path: str) -> dict:
    key = os.getenv(KEY_ENV[provider], "").strip()
    if not key:
        raise EnvironmentError(
            f"缺少环境变量 {KEY_ENV[provider]}（{provider} 的 API key）。"
            f" 请在宿主 export {KEY_ENV[provider]}=... 后重试。")
    return CALLERS[provider](prompt, ratio, key, out_path)

def generate_auto(prompt: str, ratio: str, out_path: str,
                  chain: Optional[List[str]] = None) -> dict:
    chain = chain or DEFAULT_CHAIN
    errors = []
    for prov in chain:
        try:
            result = generate(prov, prompt, ratio, out_path)
            result["fallback_used"] = errors  # 记录之前失败的路
            return result
        except Exception as e:  # noqa: BLE001 —— 降级本就要吞异常继续下一路
            errors.append({"provider": prov, "error": str(e)[:160]})
            continue
    raise RuntimeError(f"降级链全部失败: {json.dumps(errors, ensure_ascii=False)}")


# ============================================================================ #
# dry-run：离线打印请求，key 脱敏，绝不发送
# ============================================================================ #
def _redact(headers: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in headers.items():
        if k.lower() in ("authorization", "x-goog-api-key"):
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out

def dry_run(provider: str, prompt: str, ratio: str) -> dict:
    fake_key = "DRYRUN"
    url, headers, body = build_request(provider, prompt, ratio, fake_key)
    out = {"provider": provider, "model": model_of(provider),
           "key_env": KEY_ENV[provider],
           "key_present": bool(os.getenv(KEY_ENV[provider])),
           "method": "POST", "url": url,
           "headers": _redact(headers), "body": body}
    if provider not in WIRED_PROVIDERS:
        out["status"] = "RESERVED_未接线（无官方公开API，需注入 AIVD_MJ_BASE 启用）"
    return out


# ============================================================================ #
# CLI
# ============================================================================ #
def _read_prompt(args) -> Tuple[str, str]:
    """返回 (prompt, ratio)。--from-plan 时从 stdin 的 assemble JSON 读取。"""
    if args.from_plan:
        plan = json.load(sys.stdin)
        return plan["positive_prompt"], plan.get("ratio", args.ratio)
    if not args.prompt:
        raise SystemExit("需要 --prompt，或用 --from-plan 从管道读 assemble_prompt 的 JSON")
    return args.prompt, args.ratio

def main() -> int:
    p = argparse.ArgumentParser(description="ai-visual-director 统一执行适配器")
    p.add_argument("--provider", default="auto",
                   choices=["auto", "all", "gemini", "openai", "qwen", "seedream", "midjourney"])
    p.add_argument("--prompt", default="")
    p.add_argument("--from-plan", action="store_true",
                   help="从 stdin 读取 assemble_prompt.py 的 JSON")
    p.add_argument("--ratio", default="16:9")
    p.add_argument("--out", default="./aivd_out.png")
    p.add_argument("--dry-run", action="store_true",
                   help="只组装并打印请求（key 脱敏），不发送")
    args = p.parse_args()

    prompt, ratio = _read_prompt(args)

    if args.dry_run:
        if args.provider in ("all", "auto"):
            provs = DEFAULT_CHAIN + ["midjourney"]  # 含预留位，方便查看骨架
        else:
            provs = [args.provider]
        out = [dry_run(pr, prompt, ratio) for pr in provs]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.provider == "all":
        raise SystemExit("--provider all 只用于 --dry-run；真实出图请选具体 provider 或 auto")

    if args.provider == "auto":
        result = generate_auto(prompt, ratio, args.out)
    else:
        result = generate(args.provider, prompt, ratio, args.out)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
