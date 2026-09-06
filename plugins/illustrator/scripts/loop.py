#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-visual-director · 闭环编排器 (Closed-Loop Orchestrator)
=========================================================

把三环拧成一个确定性闭环：
    装配(记住 Prop) → 出图 → 回读图验"Prop在吗"
        ├─ 在  → 通过，返回图
        └─ 不在 → 换 seed 重装配 → 重出 → 再验（最多 max_attempts 次）

这是"防衰减"从 prompt 端延伸到成图端的最后一步：不只把话说对，还确认画对了。

依赖：同目录 assemble_prompt.py / execute.py / verify.py，仅标准库。
key 全部从环境变量读（出图 + 看图复用同源 key），零密钥入体。

⚠ 真实出图/看图需在宿主联网环境跑。本文件提供 --dry-run 展示闭环各步请求骨架。

用法：
  # 完整闭环：一句感受 → 保证焦点物进画面的成图
  python loop.py \
    --subject "a tired man bent under the weight" \
    --action "reaching out to catch another falling box" \
    --prop "a towering stack of oversized cardboard boxes" \
    --trace "the top box already tilting and slipping free" \
    --style pen_line_vibrant --ratio 16:9 \
    --provider gemini --vision gemini \
    --seed 42 --max-attempts 3 --out ./out.png

  # 离线看闭环会怎么走（不发请求）
  python loop.py --subject s --action a --prop p --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys

import assemble_prompt as A
import execute as E
import verify as V


def run_loop(subject: str, action: str, prop: str, trace: str = "",
             style: str = "pen_line_vibrant", ratio: str = "16:9",
             provider: str = "gemini", vision: str = "gemini",
             seed: int = 42, max_attempts: int = 3,
             threshold: float = 0.6, out_path: str = "./out.png") -> dict:
    attempts = []
    for i in range(max_attempts):
        cur_seed = seed + i * 1000  # 每次换 seed → 换构图，逼出不同画面
        # 1) 装配（证据层强制 subject+action+prop 同框）
        ev = A.Evidence(subject=subject, action=action, prop=prop, trace=trace)
        plan = A.assemble(ev, style, ratio, provider, cur_seed)
        # 2) 出图
        gen = E.generate(provider, plan["positive_prompt"], ratio, out_path)
        # 3) 回读图验焦点物
        verdict = V.verify(gen["local_path"], prop, vision,
                           subject=subject, action=action, threshold=threshold)
        attempts.append({"attempt": i + 1, "seed": cur_seed,
                         "passed": verdict["passed"],
                         "confidence": verdict["confidence"],
                         "reason": verdict["reason"]})
        if verdict["passed"]:
            return {"status": "PASSED", "attempts_used": i + 1,
                    "seed": cur_seed, "image": gen["local_path"],
                    "remote_url": gen.get("remote_url"),
                    "verdict": verdict, "history": attempts}
    # 用尽次数仍未通过：返回最后一张 + 全部历史，交人工定夺，不假装成功
    return {"status": "FAILED_MAX_ATTEMPTS", "attempts_used": max_attempts,
            "image": out_path, "history": attempts,
            "hint": "焦点道具始终未稳定进画面：考虑加大 Prop 描述、换风格，或换 provider"}


def dry_run(subject: str, action: str, prop: str, trace: str,
            style: str, ratio: str, provider: str, vision: str, seed: int) -> dict:
    ev = A.Evidence(subject=subject, action=action, prop=prop, trace=trace)
    plan = A.assemble(ev, style, ratio, provider, seed)
    exec_dry = E.dry_run(provider, plan["positive_prompt"], ratio)
    # verify 的 dry-run 需要一张真图；这里只展示指令，不读文件
    instruction = V.build_instruction(prop, subject, action)
    return {
        "loop": ["assemble", "execute", "verify", "retry-if-fail"],
        "step1_assemble": {"positive_prompt": plan["positive_prompt"],
                            "composition": plan["composition"], "seed": seed},
        "step2_execute": {"provider": provider, "model": exec_dry["model"],
                          "url": exec_dry["url"]},
        "step3_verify": {"vision": vision, "model": V.vision_model_of(vision),
                         "instruction": instruction,
                         "pass_rule": "present==true 且 confidence>=阈值"},
        "step4_retry": "不通过则 seed+=1000 重装配重出，直到 max_attempts",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="ai-visual-director 闭环编排器")
    p.add_argument("--subject", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--prop", required=True)
    p.add_argument("--trace", default="")
    p.add_argument("--style", default="pen_line_vibrant", choices=list(A.STYLE_MATRIX))
    p.add_argument("--ratio", default="16:9")
    p.add_argument("--provider", default="gemini",
                   choices=["gemini", "openai", "qwen", "seedream"])
    p.add_argument("--vision", default="gemini", choices=["gemini", "openai"])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--threshold", type=float, default=0.6)
    p.add_argument("--out", default="./out.png")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.dry_run:
        out = dry_run(args.subject, args.action, args.prop, args.trace,
                      args.style, args.ratio, args.provider, args.vision, args.seed)
    else:
        out = run_loop(args.subject, args.action, args.prop, args.trace,
                       args.style, args.ratio, args.provider, args.vision,
                       args.seed, args.max_attempts, args.threshold, args.out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
