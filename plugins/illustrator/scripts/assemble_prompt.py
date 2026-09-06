#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-visual-director · 防衰减 Prompt 装配器 (Anti-Decay Prompt Assembler)
======================================================================

职责边界（第一性原则）:
  · 语义解构（把抽象痛点拆成 Action/Prop/Trace）是"创作"，由调用方(模型)完成后喂进来。
  · 本脚本只做"装配"：把已解构的证据 + 风格预设，按四步法确定性地拼成最终 prompt。
  · 装配是纯函数：同样输入 + 同样 seed → 同样输出。杜绝 Math.random 式不可复现。

四步法装配顺序（防衰减，顺序不可颠倒）:
  1. Hard Constraints  硬约束   —— Style DNA + 画幅，永远第一，锁死基底
  2. Evidence          证据层   —— subject/action/prop/trace，强制焦点物进画面
  3. Composition       构图层   —— 由 seed 决定的留白/机位，具体几何而非形容词
  4. Style             风格层   —— 五选一手绘风格描述

模型方言铁律（来自复盘）:
  · 权重语法 (word:1.15) 是 SD/ComfyUI 方言。发给 FLUX/DALL-E/Midjourney 等
    自然语言模型只会降质 → NL 路线一律剥离权重语法、把负面约束折叠进正向文本。
  · 只有 SDXL/ComfyUI 路线才输出独立 negative prompt 与权重语法。

用法:
  python assemble_prompt.py --demo
  python assemble_prompt.py \
      --subject "a tired office worker" \
      --action "reaching out to catch another falling box" \
      --prop "a towering stack of oversized cardboard boxes" \
      --trace "boxes tilting, one already slipping from the top" \
      --style pen_line_vibrant \
      --ratio 16:9 \
      --model flux \
      --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ----------------------------------------------------------------------------- #
# 0. Style DNA —— 全局硬约束，任何风格、任何模型都不可协商
# ----------------------------------------------------------------------------- #
STYLE_DNA_POSITIVE: List[str] = [
    "high purity high saturation high brightness color",
    "zero grey pollution",
    "warm ivory-white base",
    "deep charcoal-black structural lines",
    "low visual noise",
    "vast intentional negative space",
    "one single emotion, one story, one moment, one hook",
]
STYLE_DNA_NEGATIVE: List[str] = [
    "muddy colors", "grey wash", "low contrast", "cluttered background",
    "busy composition", "photorealistic skin texture", "watermark", "text artifacts",
    "multiple competing focal points",
]

# ----------------------------------------------------------------------------- #
# 1. 风格矩阵 —— 五档高饱和手绘。positive 用自然语言，可安全发给任何模型；
#    weighted 仅在 SD 方言下附加 (token:weight)。详见 references/style-matrix.md
# ----------------------------------------------------------------------------- #
@dataclass
class StylePreset:
    key: str
    label: str
    positive: str          # 自然语言风格描述（所有模型通用）
    sd_weighted: str       # SD/ComfyUI 专用带权重强化片段
    extra_negative: List[str] = field(default_factory=list)


STYLE_MATRIX: Dict[str, StylePreset] = {
    "pen_line_vibrant": StylePreset(
        key="pen_line_vibrant",
        label="钢笔线描 (高饱和沉浸)",
        positive=(
            "vivid pen line art illustration, bold and crisp black ink pen outlines, "
            "rich high saturation, brilliant luminous lighting, vibrant color accents, "
            "expressive pen cross-hatching, immersive narrative atmosphere, "
            "clear line-art texture"
        ),
        sd_weighted="(bold crisp black ink outlines:1.2), (high saturation:1.15)",
        extra_negative=["blurry lines", "sketchy uncertain strokes"],
    ),
    "marker_line": StylePreset(
        key="marker_line",
        label="马克笔线描 (粗犷高明度)",
        positive=(
            "bold marker illustration, thick rough hand-drawn strokes, high brightness, "
            "strong tactile marker texture, confident gestural line work, "
            "saturated marker fills"
        ),
        sd_weighted="(thick rough marker strokes:1.2), (high brightness:1.15)",
        extra_negative=["thin timid lines", "digital vector flatness"],
    ),
    "color_block_frame": StylePreset(
        key="color_block_frame",
        label="色块线框 (撞色海报)",
        positive=(
            "clean black outline poster illustration, high saturation clashing color blocks, "
            "flat bold shapes, graphic poster composition, crisp geometric framing"
        ),
        sd_weighted="(clean black outline:1.2), (clashing color blocks:1.15)",
        extra_negative=["gradient shading", "soft edges", "painterly blending"],
    ),
    "vibrant_pure_block": StylePreset(
        key="vibrant_pure_block",
        label="纯色高亮色块 (平涂戏剧光)",
        positive=(
            "pure flat color-block illustration, no gradient flat fills, "
            "dramatic hard light-shadow contrast, bold saturated hues, "
            "theatrical spotlight staging"
        ),
        sd_weighted="(flat pure color fills:1.2), (dramatic hard shadow:1.15)",
        extra_negative=["gradients", "airbrush", "soft ambient light"],
    ),
    "gouache_pop": StylePreset(
        key="gouache_pop",
        label="不透明水粉 (厚重浓郁)",
        positive=(
            "opaque gouache painting, thick heavy pigment texture, rich vivid saturated color, "
            "visible brush body, matte painterly surface, punchy pop palette"
        ),
        sd_weighted="(thick opaque gouache:1.2), (rich saturated pigment:1.15)",
        extra_negative=["transparent watercolor", "thin washes", "digital smoothness"],
    ),
}

# ----------------------------------------------------------------------------- #
# 2. 模型路由 —— 主路 FLUX → 备路 DALL-E 3 → 备路 SDXL / Midjourney
#    dialect: "nl"  = 自然语言模型，剥离权重、无独立 negative
#             "sd"  = SD/ComfyUI，允许权重语法 + 独立 negative prompt
# ----------------------------------------------------------------------------- #
@dataclass
class ModelRoute:
    key: str
    label: str
    dialect: str            # "nl" | "sd"
    ratio_flag: str         # 画幅参数写法
    supports_negative: bool


MODEL_ROUTES: Dict[str, ModelRoute] = {
    # —— 四家现役自然语言模型（NL 方言：不吃 ComfyUI 权重语法）——
    "gemini":     ModelRoute("gemini", "Gemini Nano Banana 2 (gemini-3.1-flash-image)", "nl", "aspect ratio {ratio}", False),
    "openai":     ModelRoute("openai", "OpenAI gpt-image-2 (DALL-E 3 已退役)", "nl", "aspect ratio {ratio}", False),
    "qwen":       ModelRoute("qwen", "通义万相 wan2.6/2.7-image (DashScope)", "nl", "size {ratio}", False),
    "seedream":   ModelRoute("seedream", "即梦 Seedream (火山方舟 doubao-seedream)", "nl", "aspect ratio {ratio}", False),
    # —— 可选备路 ——
    "flux":       ModelRoute("flux", "FLUX (FAL.ai)", "nl", "--ar {ratio}", False),
    "midjourney": ModelRoute("midjourney", "Midjourney", "nl", "--ar {ratio}", False),
    # —— 唯一 SD 方言：才允许权重语法 + 独立 negative ——
    "sdxl":       ModelRoute("sdxl", "SDXL / ComfyUI", "sd", "size {ratio}", True),
}
# 降级顺序：按 Nicola 指定 gemini → openai → qwen → 即梦，SD 兜底
FALLBACK_ORDER: List[str] = ["gemini", "openai", "qwen", "seedream", "sdxl"]

VALID_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "21:9"}

# ----------------------------------------------------------------------------- #
# 3. 确定性构图 —— 用 seed 派生留白比例与机位，替换 phase6 里恒为 0.38 的假几何
# ----------------------------------------------------------------------------- #
def _seed_int(seed: Optional[int], salt: str) -> int:
    """把 (seed, salt) 稳定地映射成一个整数；seed=None 时仍确定（退化为纯 salt 哈希）。"""
    basis = f"{seed if seed is not None else 'noseed'}::{salt}"
    return int(hashlib.sha256(basis.encode("utf-8")).hexdigest(), 16)


_NEG_SPACE_BANDS = [
    (0.55, "expansive negative space, subject anchored to one third"),
    (0.62, "generous breathing room, off-center subject placement"),
    (0.70, "dominant emptiness, small isolated subject"),
]
_CAMERA_ANGLES = [
    "eye-level medium shot",
    "slightly low angle, subject looming",
    "high angle looking down, subject dwarfed",
    "wide establishing shot, subject small in frame",
]


def derive_composition(seed: Optional[int]) -> Dict[str, str]:
    band = _NEG_SPACE_BANDS[_seed_int(seed, "negspace") % len(_NEG_SPACE_BANDS)]
    angle = _CAMERA_ANGLES[_seed_int(seed, "camera") % len(_CAMERA_ANGLES)]
    ratio_val, phrase = band
    return {
        "negative_space_ratio": f"{ratio_val:.2f}",
        "negative_space_phrase": phrase,
        "camera": angle,
    }


# ----------------------------------------------------------------------------- #
# 4. 证据层 —— 强制 subject + action + prop + trace 同框，修复"叙事与画面解耦"
# ----------------------------------------------------------------------------- #
@dataclass
class Evidence:
    subject: str
    action: str
    prop: str
    trace: str = ""

    def validate(self) -> None:
        missing = [k for k in ("subject", "action", "prop") if not getattr(self, k).strip()]
        if missing:
            raise ValueError(f"证据层缺失必填字段: {missing}（subject/action/prop 不可为空）")

    def to_clause(self) -> str:
        parts = [self.subject.strip(), self.action.strip(),
                 f"with {self.prop.strip()}"]
        if self.trace.strip():
            parts.append(f"({self.trace.strip()})")
        return ", ".join(parts)


# ----------------------------------------------------------------------------- #
# 5. 主装配函数
# ----------------------------------------------------------------------------- #
def assemble(
    evidence: Evidence,
    style_key: str,
    ratio: str = "16:9",
    model: str = "flux",
    seed: Optional[int] = None,
    hook_line: str = "",
) -> Dict:
    evidence.validate()
    if style_key not in STYLE_MATRIX:
        raise ValueError(f"未知风格 '{style_key}'，可选: {list(STYLE_MATRIX)}")
    if model not in MODEL_ROUTES:
        raise ValueError(f"未知模型 '{model}'，可选: {list(MODEL_ROUTES)}")
    if ratio not in VALID_RATIOS:
        raise ValueError(f"非法画幅 '{ratio}'，可选: {sorted(VALID_RATIOS)}")

    style = STYLE_MATRIX[style_key]
    route = MODEL_ROUTES[model]
    comp = derive_composition(seed)

    # ---- 四步法：顺序即防衰减 ----
    # 1) Hard Constraints
    hard = list(STYLE_DNA_POSITIVE)
    # 2) Evidence
    evidence_clause = evidence.to_clause()
    # 3) Composition
    comp_clause = f"{comp['camera']}, {comp['negative_space_phrase']}"
    # 4) Style
    if route.dialect == "sd":
        style_clause = f"{style.positive}, {style.sd_weighted}"
    else:  # nl 方言：剥离一切权重语法
        style_clause = style.positive

    positive_prompt = ", ".join([
        ", ".join(hard),
        evidence_clause,
        comp_clause,
        style_clause,
    ])

    # 画幅参数按模型方言写
    ratio_fragment = route.ratio_flag.format(ratio=ratio)

    # negative prompt 只在支持的 sd 路线单独给；nl 路线折叠进正向的硬约束里已隐含
    negative_prompt = ""
    if route.supports_negative:
        negative_prompt = ", ".join(STYLE_DNA_NEGATIVE + style.extra_negative)

    # nl 路线把最关键的负面折叠成一句正向禁令，避免另开 negative 通道
    if route.dialect == "nl":
        positive_prompt += (
            ". Avoid muddy grey colors, cluttered background, "
            "and multiple competing focal points"
        )

    final_positive = f"{positive_prompt} {ratio_fragment}".strip()

    return {
        "style_preset": style.key,
        "style_label": style.label,
        "model": route.key,
        "model_label": route.label,
        "dialect": route.dialect,
        "seed": seed,
        "ratio": ratio,
        "hook_line": hook_line.strip(),
        "composition": comp,
        "evidence": asdict(evidence),
        "positive_prompt": final_positive,
        "negative_prompt": negative_prompt,       # nl 路线为空字符串，符合方言
        "fallback_order": FALLBACK_ORDER,
    }


# ----------------------------------------------------------------------------- #
# 6. 四格连环画：起·承·转·合，共享同一 subject/prop/seed 保持一致性
# ----------------------------------------------------------------------------- #
def assemble_four_panel(
    subject: str,
    prop: str,
    beats: Dict[str, Dict[str, str]],  # {"起":{"action":...,"trace":...}, ...}
    style_key: str,
    ratio: str = "1:1",
    model: str = "flux",
    seed: Optional[int] = None,
) -> Dict:
    order = ["起", "承", "转", "合"]
    missing = [b for b in order if b not in beats]
    if missing:
        raise ValueError(f"四格缺少节拍: {missing}（需齐备 起/承/转/合）")
    panels = []
    for i, beat in enumerate(order):
        ev = Evidence(
            subject=subject, prop=prop,
            action=beats[beat].get("action", ""),
            trace=beats[beat].get("trace", ""),
        )
        # 每格用 seed+i 派生构图，保证四格构图各异但整体可复现
        panel_seed = None if seed is None else seed * 100 + i
        out = assemble(ev, style_key, ratio, model, panel_seed,
                       hook_line=beats[beat].get("hook", ""))
        out["panel"] = beat
        panels.append(out)
    return {"mode": "four_panel", "subject": subject, "prop": prop,
            "style_preset": style_key, "panels": panels}


# ----------------------------------------------------------------------------- #
# 7. CLI
# ----------------------------------------------------------------------------- #
def _demo() -> Dict:
    ev = Evidence(
        subject="a tired man bent under the weight",
        action="desperately reaching out with one hand to catch another falling box",
        prop="a towering stack of oversized cardboard boxes",
        trace="the top box already tilting and slipping free",
    )
    return assemble(ev, "pen_line_vibrant", "16:9", "gemini", seed=42,
                    hook_line="压垮人的从来不是一只箱子，而是已经很重了还要去接更多")


def main() -> int:
    p = argparse.ArgumentParser(description="ai-visual-director 防衰减 Prompt 装配器")
    p.add_argument("--demo", action="store_true", help="跑内置示范样例")
    p.add_argument("--subject"); p.add_argument("--action")
    p.add_argument("--prop"); p.add_argument("--trace", default="")
    p.add_argument("--style", default="pen_line_vibrant", choices=list(STYLE_MATRIX))
    p.add_argument("--ratio", default="16:9")
    p.add_argument("--model", default="gemini", choices=list(MODEL_ROUTES))
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--hook", default="")
    args = p.parse_args()

    if args.demo:
        result = _demo()
    else:
        if not (args.subject and args.action and args.prop):
            p.error("非 --demo 模式下 --subject/--action/--prop 均为必填")
        ev = Evidence(args.subject, args.action, args.prop, args.trace)
        result = assemble(ev, args.style, args.ratio, args.model, args.seed, args.hook)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
