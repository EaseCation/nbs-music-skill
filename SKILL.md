---
name: nbs-music-skill
description: 将 Suno 原创器乐、MIDI/WAV 分轨或现成 NBS 制作为可复核的 Minecraft 音符盒音乐，包括提示词、分轨取舍、音量分层编码、修订比对与浏览器本地试听。适用于歌曲转 NBS 及其试听工具，不用于服务器部署。
---

# NBS 音乐制作技能

目标是交付实际游戏能读、音量写在文件里、可追溯原始音符的 NBS；试听直接读取最终 NBS，不另做一个听起来更响的版本。

## 按任务读取

- 写 Suno 提示词：读 [references/prompts.md](references/prompts.md)。不承诺提示词能严格控制配器或保证干净分轨；先核对当时 Suno 版本和用户实际导出物。
- ZIP/MIDI/WAV 转编配：读 [references/workflow.md](references/workflow.md) 和 [references/schema.md](references/schema.md)。`scripts/toolkit.py` 提供独立命令，所有路径由参数传入；`scripts/render.py` 提供采样响度表与最终NBS离线渲染。
- NBS 编码、音量、音高问题：读 [references/nbs.md](references/nbs.md)。先确定目标解码器支持的力度、微调与声像；`game` 配置是本次 EC 项目的层音量惯例，不代表所有播放器。
- 修复局部听感：先读 [references/pitfalls.md](references/pitfalls.md)，从不可变基线做 `focus → patch → encode → diff`。不能仅凭 AI 分轨名或旧的 role 标签定位主旋律。
- 生成可复用试听集：读 [references/web.md](references/web.md)。纯浏览器解析 NBS、使用内置16种采样播放和导出 WAV；不依赖预渲染 MP3 或后端音频服务。

## 必须保留的约束

1. 先盘点输入、SHA-256、MIDI tempo 图和音频时间偏移。源文件只读；非法 MIDI 调号仅在内存中隔离并记录，不能顺便重写节奏。
2. 主旋律高音排查覆盖时间窗内**所有声部**，比较实际发声音高。选音记录必须列出 source ID、时间、音高、旧/新音色与力度；批量改动要有明确范围和前置条件。
3. 音符盒无可控制的延音。自然采样尾音仍然存在；不要加循环铺底，也不要根据 MIDI note-off 强行截断采样。需要复奏时作为显式编曲决定记录。
4. 不擅自折叠到原版两八度。不限游戏音域不等于 NBS 存储无限：超出键值 0–87 应报错并提出格式/自定义音色方案，不能静默移八度。
5. 主奏太轻时先查完整独奏段、层音量、音色的实际响度和漏音；不要只提高网页总音量。默认不复制同音同色音符来增响，不单独归一化分声部。
6. MIDI 的 program 与 AI 文件名都是线索，不是事实。静音分轨可能产生大量虚假 MIDI；Vocals 也可能含有效器乐。只有证据支持时才排除/合并。
7. 保留已满意的部分。撤回要恢复原始编配/NBS/试听一致的基线；比较实际发声属性，不因层编号变化误判整首被改动。
8. 自动工具输出只是候选分析；不要声称听过音频。交付区分程序验证、频谱/能量证据及用户实听结果。

## 工具入口

```bash
python3 scripts/toolkit.py --help
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests
npm ci
npm test
```

`encode/audit/diff/patch/focus/build-web` 只需 Python 标准库；`inspect/arrange` 使用 mido；音频分析使用 numpy 和 FFmpeg，音色包构建需要 FFmpeg。不在运行时自动安装依赖。

提示词、路由规则、编配 JSON、NBS、sidecar、局部修订记录、前后 diff 和试听 HTML 是不同产物。普通 NBS 只能恢复物理层与音色，不能凭空恢复“主旋律/伴奏”或原始分轨；语义来自 SHA-256 匹配的 sidecar。
