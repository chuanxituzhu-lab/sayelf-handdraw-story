---
name: ai-visual-director
description: |
  AI 视觉导演 · 双层导演核心引擎（ai-visual-director）
  把抽象概念 / 现代人痛点故事 / 脚本段落，编译成"叙事焦点必现于画面、可复现、防衰减"的高饱和手绘 Prompt，
  再按 主路 FLUX → 备路 DALL-E 3 → SDXL / Midjourney 的降级路由直连出图。
  凡涉及：把一句感受/痛点/金句变成配图、单图 Hook 海报、四格连环画（起承转合）、
  钢笔线描 / 马克笔 / 色块线框 / 纯色高亮 / 不透明水粉 等高饱和手绘风格生成、
  抽象概念可视化、防 Prompt 衰减、图文一致性校验、多模型出图降级——必须激活本技能。
  也适用于：SAYELF 视觉叙事、社媒配图脚本、观点海报、情绪金句配图、把 userIdea 拆成 动作+道具+痕迹、
  自动出图（接 Gemini / OpenAI gpt-image / 通义万相 / 即梦 Seedream 文生图 API 一键返回图片）。
---

# 🎬 AI 视觉导演 · 双层核心引擎

在统一仓库中，本 Skill 是可替换的视觉导演插件，路径为 `plugins/illustrator/SKILL.md`。它消费故事 Core 已确定的主体、道具、动作、痕迹和画幅，不重新拆镜、不改变帧数；连续故事请先使用 `scripts/story_to_prompts.py`，再把同编号的图片提示词与视频分镜交给宿主或 Provider。

> **一句话本质**：观众记住的从来不是形容词，而是一个"动作 + 道具 + 痕迹"构成的瞬间。
> 导演的活儿，是把抽象的"感受"翻译成可以被画出来的"证据"。

---

## 〇、Style DNA（不可协商的基底）

任何风格、任何模型，以下基底永远成立，装配时永远排在 Prompt 最前：

> 高纯度 · 高饱和 · 高明度 · 零灰污 · 暖象牙白基底 · 深炭黑结构线 · 低视觉噪音 · 大留白
> **一图一情绪 · 一图一故事 · 一图一瞬间 · 一图一 Hook**

违反 DNA（例如灰调、多焦点、堆满背景）即判定为衰减，须重做。

---

## 一、系统架构（四层）

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 统一接口层  CLI / REST / MCP (OpenClaw · Claude Code)       │
├──────────────────────────────────────────────────────────────┤
│ 2. 双层导演核心引擎                                            │
│   ├─ 语义解构：抽象痛点 → 动作 Action + 道具 Prop + 痕迹 Trace │
│   ├─ 叙事模式：单图 Hook 金句  /  四格 起·承·转·合 连环画      │
│   └─ 防衰减引擎：Hard Constraints → Evidence → Comp → Style    │
├──────────────────────────────────────────────────────────────┤
│ 3. 高饱和手绘风格矩阵（5 档，详见 references/style-matrix.md） │
│   pen_line_vibrant / marker_line / color_block_frame /        │
│   vibrant_pure_block / gouache_pop                            │
├──────────────────────────────────────────────────────────────┤
│ 4. 多模型降级路由 + 执行层 (scripts/execute.py)                │
│   Gemini → OpenAI → Qwen万相 → 即梦Seedream (SDXL 兜底)        │
│   ⚠ DALL-E 3 已于 2026-03 退役，OpenAI 现役为 gpt-image-2     │
├──────────────────────────────────────────────────────────────┤
│ 5. 出图一致性闭环 (scripts/verify.py + loop.py)                │
│   回读成图验焦点物 Prop → 不达标换 seed 重出（复用视觉模型）   │
└──────────────────────────────────────────────────────────────┘
```

**四家现役 provider（模型名/端点均可用环境变量覆盖，防版本漂移）**：

| provider | 默认模型 | key 环境变量 | 返回 |
|----------|----------|--------------|------|
| gemini | gemini-3.1-flash-image (Nano Banana 2) | `GEMINI_API_KEY` | base64 |
| openai | gpt-image-2（DALL-E 3 已退役） | `OPENAI_API_KEY` | base64 |
| qwen | wan2.6-image（DashScope 百炼，异步轮询） | `DASHSCOPE_API_KEY` | URL |
| seedream | doubao-seedream-4-0-250828（火山方舟） | `ARK_API_KEY` | URL |
| midjourney | ⚠ **预留位**：无官方公开 API（2026-08 核实），未接线 | `MJ_API_KEY` | — |

> **Midjourney 说明**：官方至今仅 Discord/网页，无自助 REST API；第三方 wrapper 违反 MJ 服务条款、有封号风险。
> 故 `midjourney` 仅作预留占位——调用时清晰拒绝、不静默。待官方 API 落地或拿到企业开发者权限，
> 注入 `AIVD_MJ_BASE` + `MJ_API_KEY` 即可启用（骨架按 OpenAI 兼容预置，返回结构不符时回报校准）。

**分工铁律**：语义解构是"创作"，由你（模型）完成；四步法装配是"确定性拼装"，交给
`scripts/assemble_prompt.py`。两者不可混淆——创作不写死进脚本，拼装不靠临场发挥。

---

## 二、导演工作流（照此顺序执行）

### 第 1 步 · 语义解构：把感受拆成能画的证据

输入是抽象的（"很累"、"内耗"、"被生活压垮"）。禁止把抽象词直接塞进画面——
那会产出"赛博朋克机器人打斗里很安静"这类叙事与画面解耦的废图。

按三要素拆解，每一项都必须是**可被画笔画出来的具体物**：

| 要素 | 定义 | 反例（抽象，禁止） | 正例（具体，可画） |
|------|------|--------------------|--------------------|
| **动作 Action** | 主体正在做的一个动词 | "感到焦虑" | 伸手去接正在下坠的箱子 |
| **道具 Prop** | 承载情绪的实体物 | "压力" | 一摞高耸的超大纸箱 |
| **痕迹 Trace** | 暗示前因后果的细节 | "很久了" | 最顶的箱子已倾斜滑脱 |

**自检**：把三要素念给一个没看过原文的人，他能不能画出来？不能→重拆。

### 第 2 步 · 选叙事模式

- **单图 Hook 模式**：一句金句 + 一张图，追求一击即中。用 `assemble`。
- **四格连环画（起·承·转·合）**：一个转折需要铺垫时用。用 `assemble_four_panel`，
  四格共享同一 subject / prop / seed，保证人物道具一致、构图各异。

### 第 3 步 · 选风格（读 references/style-matrix.md 速查表）

按情绪定调：线条叙事→`pen_line_vibrant`；街头随性→`marker_line`；
观点海报→`color_block_frame`；戏剧极简→`vibrant_pure_block`；温度厚重→`gouache_pop`。

### 第 4 步 · 装配 Prompt（防衰减引擎，交给脚本）

四步法顺序即防衰减，**顺序不可颠倒**：

```
1. Hard Constraints  Style DNA + 画幅        锁死基底
2. Evidence          subject+action+prop+trace 强制焦点物同框
3. Composition       seed 派生的留白+机位      具体几何，非形容词
4. Style             五档之一的风格片段        最后上色
```

调用（完整可直接复制）：

```bash
python scripts/assemble_prompt.py \
  --subject "a tired man bent under the weight" \
  --action "reaching out with one hand to catch another falling box" \
  --prop "a towering stack of oversized cardboard boxes" \
  --trace "the top box already tilting and slipping free" \
  --style pen_line_vibrant \
  --ratio 16:9 \
  --model flux \
  --seed 42 \
  --hook "压垮人的从来不是一只箱子，而是已经很重了还要去接更多"
```

先跑内置示范确认环境：`python scripts/assemble_prompt.py --demo`

脚本返回 JSON，含 `positive_prompt` / `negative_prompt` / `composition` / `fallback_order`。

### 第 5 步 · 出图（两种接入模式，宿主二选一）

**方言铁律**（`assemble_prompt.py` 已内建，勿手动违反）：
- NL 路线（Gemini / OpenAI / Qwen / Seedream / FLUX / MJ）→ 纯自然语言，**剥掉 `(token:weight)` 权重语法**。权重语法是 SD/ComfyUI 方言，发给自然语言模型只会降质。
- SD 路线（SDXL/ComfyUI）→ 才允许权重语法 + 独立 negative prompt。

**模式 A · 只出计划（host-first，最安全）**：skill 只吐 `positive_prompt` 等 JSON，
由宿主自己接的图片工具执行。Claude Code / Codex / OpenClaw 若已自带出图工具，用这个。

**模式 B · 自动出图（接了文生图，一键直达图 URL）**：用 `scripts/execute.py`。
key 只从环境变量读，**零密钥入体**。完整可复制：

```bash
# 管道直连：装配 → 出图（gemini 主路）
python scripts/assemble_prompt.py --demo \
  | python scripts/execute.py --from-plan --provider gemini --out ./out.png

# 自动降级（gemini → openai → qwen → seedream 依次尝试）
python scripts/assemble_prompt.py --demo \
  | python scripts/execute.py --from-plan --provider auto --out ./out.png

# 离线核对请求（key 脱敏，不发送）——上线前先跑这个确认端点/模型名正确
python scripts/execute.py --provider all --prompt "test" --ratio 16:9 --dry-run
```

宿主需先 `export` 对应 key（缺 key 会显式报错，不静默出废图）：
`GEMINI_API_KEY` / `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` / `ARK_API_KEY`。
模型漂移时用 `AIVD_<PROVIDER>_MODEL` / `AIVD_<PROVIDER>_BASE` 覆盖，无需改代码。

**一致性校验（出图后，闭环最后一环）**：只判一个可证伪的封闭问题——装配时的焦点道具 Prop 是否真的进了画面？不判美丑（主观，交给人）。用 `scripts/verify.py` 复用已配视觉模型（Gemini/GPT-4o）回读图片，逼其回 `{present, confidence, reason}` JSON；`present && confidence>=阈值` 才算过。

### 第 6 步 · 闭环（可选，一键从感受到"保证焦点物进画面"的成图）

用 `scripts/loop.py` 把三环拧成确定性闭环：**装配 → 出图 → 验 Prop → 不过则换 seed 重出**（最多 N 次）。

```bash
python scripts/loop.py \
  --subject "a tired man bent under the weight" \
  --action "reaching out to catch another falling box" \
  --prop "a towering stack of oversized cardboard boxes" \
  --trace "the top box already tilting and slipping free" \
  --style pen_line_vibrant --ratio 16:9 \
  --provider gemini --vision gemini \
  --seed 42 --max-attempts 3 --out ./out.png
```

通过则返回图 + 用了几次；用尽仍不过则**如实返回 FAILED + 全部历史**（不假装成功），并提示加大 Prop 描述/换风格/换 provider。看图 key 复用出图 key，零新依赖。

---

## 三、示范：从一句感受到最终 Prompt

**输入**：压垮人的从来不是一只箱子，而是已经很重了，还要伸手去接更多。

**解构**：
- Action：一只手伸出去接正在下坠的箱子
- Prop：一摞高耸的超大纸箱
- Trace：最顶的箱子已经倾斜、正从顶端滑脱

**风格**：`pen_line_vibrant`　**画幅**：16:9　**模型**：FLUX　**seed**：42

**产出 positive_prompt**（脚本装配，节选顺序即四步法）：
> high purity high saturation high brightness color, zero grey pollution, warm ivory-white base, deep charcoal-black structural lines, low visual noise, vast intentional negative space, one single emotion one story one moment one hook, **a tired man bent under the weight, reaching out with one hand to catch another falling box, with a towering stack of oversized cardboard boxes, (the top box already tilting and slipping free)**, high angle looking down subject dwarfed, dominant emptiness small isolated subject, vivid pen line art illustration, bold and crisp black ink pen outlines, rich high saturation, brilliant luminous lighting … Avoid muddy grey colors, cluttered background, and multiple competing focal points --ar 16:9

注意：DNA 在最前、焦点物（人+接箱动作+纸箱+滑脱痕迹）在证据层同框、构图是具体机位、风格最后上色——这正是防衰减。

---

## 四、四格连环画（起·承·转·合）

用脚本内 `assemble_four_panel(subject, prop, beats, style_key, seed=...)`：
- `beats` 传入 `{"起":{"action","trace"}, "承":..., "转":..., "合":...}`。
- 四格共享 subject/prop/seed，人物道具一致；每格 seed 派生不同构图，避免四张雷同。
- 起=常态铺垫，承=压力累积，转=临界翻转，合=收束落点（金句往往落在"合"）。

---

## 五、九大开发原则落地对照（自查清单）

1. **先审计后动手**：改脚本前先 `--demo` 跑通、备份原文件。
2. **查官方文档**：接新出图模型前先核对其 ratio / 权重 / negative 支持，再登记进 `MODEL_ROUTES`。
3. **蒸馏不覆盖**：新增风格 → 往 `STYLE_MATRIX` 加一档，不改已有档的语义。
4. **不破坏现有系统**：接口签名（`assemble` / `assemble_four_panel`）保持稳定。
5. **一键傻瓜部署**：所有命令完整可直接复制粘贴，无需填空。
6. **完整可靠代码**：脚本为纯函数、同 seed 可复现、非法输入显式报错。
7. **安全可直用**：本体不含任何 API key；key 由宿主注入，创作逻辑本地化。
8. **新增沿用同原则**：加模型/风格须同样过 DNA 与方言铁律。
9. **外部模块穿透蒸馏**：任何从 GitHub 抄来的 prompt 语法先判方言归属，禁止直接复制。

---

## 六、边界与禁令

- 禁止把抽象词直接进画面（解耦废图的根因）。
- 禁止向 NL 模型发权重语法。
- 禁止无 seed 时用随机数假装可复现——无 seed 也须走确定性哈希退化路径。
- 禁止一图多焦点 / 灰调 / 堆满背景（违反 Style DNA）。
- 本体不落地任何密钥、不代管资金/账户、不做与出图无关的副作用。
