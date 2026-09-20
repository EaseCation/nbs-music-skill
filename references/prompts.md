# Suno 提示词与交付预期

先确定用途（循环等待大厅／短颁奖入场／完整主题曲）、情绪曲线、速度范围、动机和前后景。不要把本次农场主题或音域偏好固定成所有项目的规定。

Suno 支持自然语言描述风格与配器，以及版本/界面提供的器乐开关、结构标签、排除风格等控制；是否能导出 MIDI/多分轨、分轨数和权限随版本与套餐变化。开始新任务时核对用户实际界面或 Suno 官方帮助，不把“AI 分轨”描述为可靠的原始工程轨。仅有音频时，另行选择转录工具；本工具不伪装成自动高质量音频转 MIDI 模型。

## 写法

- Style 写用途、脉冲/速度、音色职责、短动机、情绪发展与自然结尾。
- Instrumental 开关优先于单靠 “no vocals”；可用结构标签表达 intro / A / lift / breakdown / final return，但其长度和具体音符无法保证。
- 强调 discrete struck notes、short articulated motifs、rests、call-and-response。不要堆叠大量矛盾指令。
- 排除 sustained string pads、legato strings、ambient drones、held synth beds、choir、vocal ad-libs、reverb wash；排除词是倾向，不是保障。生成后仍要筛选。
- 用户允许丰富配器，不等于全部叠在主旋律。让 bell/iron xylophone/banjo 分句接力，bass/drums 提供结构，guitar 轻伴奏。MC guitar 在本次采样中偏淡，别靠它独自压过整个乐队。
- 配器名称可以用 Minecraft 音色对应的自然语言，不要求 Suno 模仿游戏采样，也无需为本项目限定两八度。

## 可直接生成的模板

```bash
python3 scripts/toolkit.py prompt --theme 'the first seed becoming a golden harvest' \
  --arc 'curious sparse opening, playful growth, brief quiet anticipation, joyous award reveal' \
  --setting 'a farming game lobby and seasonal award ceremony'
```

等待大厅：中等密度、循环动机、短暂留白、小幅升降，不持续大高潮。
颁奖：清楚的期待段、短停顿、强拍揭晓、主题回归；高潮靠节奏密度、配器交接、低音走向，而非大面积长弦乐。

候选例：

1. **Seed to Sunrise** — Warm pastoral instrumental, 104 BPM, a curious four-note banjo motif answered by iron xylophone. Light piano broken chords, soft guitar offbeats, rounded plucked bass, dry kick and rim clicks. Sparse dawn opening, playful growth, a brief intimate breakdown, then a bright bell-accented return. Clear short attacks and intentional rests; foreground melody stays distinct.
2. **Golden Harvest Parade** — Joyful ceremonial instrumental, 116 BPM, crisp mallet-led fanfare, restrained pling accents, alternating bell and iron-xylophone answers. Banjo rhythmic figures, gentle piano harmony, plucked bass, snare and light hi-hat. Anticipation, a short breath before the award reveal, a confident celebratory theme, and a clean resolved ending. Rich orchestration with separated registers and short articulated notes.
3. **Home with the Harvest** — Tender pastoral instrumental, 88 BPM, warm iron-xylophone melody, short piano responses, delicate high chimes, soft guitar accompaniment, plucked bass and sparse clicks. A reflective opening grows into a grateful homecoming, settles briefly, then returns with quiet triumph. Express emotion through melodic movement and silence, with no dependence on held notes.

统一负向候选：`vocals, choir, sustained strings, bowed string pads, drones, long held synth chords, smeared legato melody, heavy reverb wash, distorted guitar lead`。按当前界面放入排除字段；没有该字段时写入描述并接受可能不服从的事实。
