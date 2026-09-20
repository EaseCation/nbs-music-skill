# 可复现工作流

以下命令从仓库根目录执行。推荐虚拟环境，FFmpeg自行安装；没有自动下载模型、付费调用或第三方上传。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/toolkit.py extract '/path/Stems.zip' -o local/song/input
.venv/bin/python scripts/toolkit.py inspect local/song/input -o local/song/midi.json
.venv/bin/python scripts/toolkit.py audio '/path/Keyboard.wav' --midi local/song/midi.json --source Keyboard -o local/song/audio.json
```

ZIP提取拒绝目录穿越、符号链接、重复路径和已存在输出目录。manifest保存源ZIP与每个文件的哈希。对超大文件可显式调整提取大小上限。

## 决策与编配

1. 对照MIDI的节目号、音高/力度/起音密度，WAV的响度、频谱和短句，确认职责。`audio`提供20ms RMS窗口、LUFS/真峰值；可选对齐只是在±2秒内按起音能量打分的**候选**，不能自动当作确定偏移。
2. 使用 `examples/routing.json` 写明确规则。没有通用的“Vocals排除”“Guitar必然吉他”“最高音就是旋律”。谱面主线与某一物理轨不同。
3. 编配先保留离散起音。对长音的再奏、漏音恢复、八度修复必须有来源证据并记录，不能凭密度填补新旋律。清理重复也先查其是否实际上属于独立声部。
4. `--merge-exact` 仅合并量化到同一tick、同音色/音高/声像的事件，保留最大力度与全部来源ID；不默认合并，也不会猜测近邻音是否重复。不同角色的同音重叠需人工决定。

```bash
.venv/bin/python scripts/toolkit.py arrange local/song/midi.json --rules local/song/routing.json -o local/song/arrangement.json
.venv/bin/python scripts/toolkit.py encode local/song/arrangement.json --title 'Song - R1' -o local/song/song-r1.nbs
.venv/bin/python scripts/toolkit.py audit local/song/song-r1.nbs
```

每个源音符必须有去向。缺规则时失败；探索时可加 `--allow-unassigned`，随后编码也必须显式 `--allow-draft`，不能把未处理音符静默丢掉。

## 局部修订

```bash
.venv/bin/python scripts/toolkit.py focus local/song/arrangement.json --start 17 --end 35 -o local/song/focus.json
.venv/bin/python scripts/toolkit.py patch local/song/arrangement.json --changes local/song/changes.json -o local/song/arrangement-r2.json
.venv/bin/python scripts/toolkit.py encode local/song/arrangement-r2.json --title 'Song - R2' -o local/song/song-r2.nbs
.venv/bin/python scripts/toolkit.py diff local/song/song-r1.nbs local/song/song-r2.nbs -o local/song/diff.json
```

`focus`列出时间窗内全部声部，按实际音高排序；不先按source/role筛掉候选。patch用明确ID和expect条件，输出前后事件与基线哈希。文件名显式版本化，基线不可覆盖。可从基线重新应用补丁来撤回错误版本。

## 验证与交付

- 本工具Python读回 + 独立JS解析器交叉核对；开发测试另用pynbs核对写入。若目标有Java NBSDecoder，应另外在目标环境验证，不宣称本工具已验证所有服务端。
- diff应只出现预期音符变化，非问题段落与其他歌曲保留。Web从最终NBS播放，A/B基线必须与文档一致。
- 至少检查完整主线交接、纯钢琴段、最大同时发音段、尾声、变速点；单个时间点正常不代表整个独奏段已修正。
- 交付NBS、编配sidecar、修订diff、说明、可打开的HTML。输入音频和原版采样默认不入Git。

## 可选离线渲染与音色校准

网页无需此步骤；当需要批量生成WAV或检查某音区的采样响度时：

```bash
python3 scripts/render.py levels --pack local/soundpack.json --instrument 7 --pitches 78 80 83 84 86 -o local/bell-levels.json
python3 scripts/render.py render local/song/song-r2.nbs --pack local/soundpack.json -o local/song/mix.wav
python3 scripts/render.py render local/song/song-r2.nbs --pack local/soundpack.json --instrument 7 -o local/song/bell.wav
python3 scripts/toolkit.py audio local/song/mix.wav -o local/song/loudness.json
```

`levels`返回采样前400ms的RMS与峰值，不把不同音色同百分比误判为等响。根据原轨实际能量选择目标力度，并写回编配再编码，而不是只改音频。

`render`从最终NBS读回，默认0dB后级增益，声部不单独归一化，保留尾音并拒绝削波。可显式选择instrument/layer；`--gain-db`只用于明确的试听衰减，不改变NBS。FFmpeg变调与Web Audio重采样算法略有差异，不能要求PCM逐字节相同，但音高、起音、层音量和选音规则必须一致。
