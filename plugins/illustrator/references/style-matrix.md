# 高饱和 / 高明度手绘风格控制矩阵 (High-Vibrancy Style Matrix)

> 何时读本文件：需要为某个故事挑选风格、或需要某档风格的完整正/负向片段时。
> 五档风格共享同一 **Style DNA**（高纯度·高饱和·高明度·零灰污·暖象牙白基底·深炭黑结构·低噪·大留白·一图一情绪），差异只在"笔触与上色语言"。

## 选型速查

| key | 中文名 | 笔触语言 | 上色语言 | 最适合的情绪/场景 |
|-----|--------|----------|----------|-------------------|
| `pen_line_vibrant` | 钢笔线描 | 精细/粗犷黑墨线、交叉排线 | 高饱和鲜艳、明亮光感 | 需要"线条叙事感"的痛点金句、沉浸叙事 |
| `marker_line` | 马克笔线描 | 粗犷厚重笔触、手绘感强 | 高明度、饱和平铺 | 街头感、随性、生活流痛点 |
| `color_block_frame` | 色块线框 | 干净黑框线 | 高饱和撞色、平面色块 | 强海报感、观点鲜明的 Hook |
| `vibrant_pure_block` | 纯色高亮色块 | 无外描或极简边 | 无渐变平涂、硬光影戏剧对比 | 强戏剧冲突、极简高级感 |
| `gouache_pop` | 不透明水粉 | 可见笔身、厚涂 | 厚重浓郁颜料质感 | 温度感、情绪厚度、怀旧 |

## 各档完整片段

### 1. pen_line_vibrant · 钢笔线描（高饱和沉浸）
- **positive**：vivid pen line art illustration, bold and crisp black ink pen outlines, rich high saturation, brilliant luminous lighting, vibrant color accents, expressive pen cross-hatching, immersive narrative atmosphere, clear line-art texture
- **SD 权重强化**：`(bold crisp black ink outlines:1.2), (high saturation:1.15)`
- **额外负面**：blurry lines, sketchy uncertain strokes

### 2. marker_line · 马克笔线描（粗犷高明度）
- **positive**：bold marker illustration, thick rough hand-drawn strokes, high brightness, strong tactile marker texture, confident gestural line work, saturated marker fills
- **SD 权重强化**：`(thick rough marker strokes:1.2), (high brightness:1.15)`
- **额外负面**：thin timid lines, digital vector flatness

### 3. color_block_frame · 色块线框（撞色海报）
- **positive**：clean black outline poster illustration, high saturation clashing color blocks, flat bold shapes, graphic poster composition, crisp geometric framing
- **SD 权重强化**：`(clean black outline:1.2), (clashing color blocks:1.15)`
- **额外负面**：gradient shading, soft edges, painterly blending

### 4. vibrant_pure_block · 纯色高亮色块（平涂戏剧光）
- **positive**：pure flat color-block illustration, no gradient flat fills, dramatic hard light-shadow contrast, bold saturated hues, theatrical spotlight staging
- **SD 权重强化**：`(flat pure color fills:1.2), (dramatic hard shadow:1.15)`
- **额外负面**：gradients, airbrush, soft ambient light

### 5. gouache_pop · 不透明水粉（厚重浓郁）
- **positive**：opaque gouache painting, thick heavy pigment texture, rich vivid saturated color, visible brush body, matte painterly surface, punchy pop palette
- **SD 权重强化**：`(thick opaque gouache:1.2), (rich saturated pigment:1.15)`
- **额外负面**：transparent watercolor, thin washes, digital smoothness

## Style DNA 硬约束（所有档共用，装配时永远排在最前）
- **正向**：high purity high saturation high brightness color / zero grey pollution / warm ivory-white base / deep charcoal-black structural lines / low visual noise / vast intentional negative space / one single emotion · one story · one moment · one hook
- **负向**：muddy colors / grey wash / low contrast / cluttered background / busy composition / photorealistic skin texture / watermark / text artifacts / multiple competing focal points

## 方言铁律（勿违反）
- **NL 路线**（FLUX / DALL-E 3 / Midjourney）：只发自然语言 positive，**剥掉所有 `(token:weight)` 权重语法**，把关键负面折叠成一句 "Avoid …" 正向禁令。权重语法发给自然语言模型只会降质。
- **SD 路线**（SDXL / ComfyUI）：才允许输出 `(token:weight)` 权重语法与独立 negative prompt。
