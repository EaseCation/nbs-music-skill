# NBS Music Toolkit

独立的 Codex skill 与工具仓库：Suno 原创器乐提示词、MIDI/WAV预处理、可追溯编配、NBS力度分层、局部修订比对，以及纯浏览器音符盒试听。

技能入口：[SKILL.md](SKILL.md)。工具命令见 `python3 scripts/toolkit.py --help`；完整流程见 [workflow](references/workflow.md)。

## 试听工具

已内置16种音符盒音色。直接打开 `web/index.html`，或生成单文件HTML后导入NBS即可。没有音频后端，没有预先生成的分轨MP3，没有AI分轨复核界面。

```bash
python3 scripts/toolkit.py build-web -o dist/nbs-player.html
```

内置采样的来源与归属见 `web/SAMPLES.md`；用户歌曲与生成结果放在Git忽略的local/dist中。详细边界见 [web说明](references/web.md)。

## 用作技能

可以直接指定本仓库的SKILL.md，或按所在客户端的技能安装方式把仓库链接到技能目录。不自动修改个人全局技能设置。

## 验证

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests
npm ci
npm test
```

完整开发依赖可用 `python3 -m pip install -r requirements-dev.txt` 安装（含独立写入校验 pynbs）。测试覆盖实际格式往返、变化tempo、空曲、多力度、层冲突、换音色时实际音高保持、局部diff与格式损坏。浏览器手动验收清单见 `tests/browser-checklist.md`。

## 许可

代码与文档采用 [MIT License](LICENSE)。`web/soundpack.js` 内的 Minecraft 音频采样不属于 MIT 授权范围，其版权与来源见 [采样说明](web/SAMPLES.md)。
