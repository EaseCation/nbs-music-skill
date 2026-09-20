# 纯浏览器试听

`web/`是无依赖静态源码，直接打开index.html即可导入NBS和音色包。播放器不发出网络请求、不上传文件、不调用后端、不需要预渲染MP3。首次音频播放仍需浏览器允许的用户点击。

为了让用户只导入NBS就能用，先从其本机Minecraft资源构建音色包，再生成包含音色的单文件HTML：

```bash
python3 scripts/toolkit.py soundpack --index '/path/minecraft/assets/indexes/INDEX.json' --assets '/path/minecraft/assets' -o local/soundpack.json
python3 scripts/toolkit.py build-web --pack local/soundpack.json -o dist/nbs-player.html
```

也支持之前任务生成的 `{name,path,hash}` 数组格式sample-index.json。提取前核验每个原版采样SHA-1，用FFmpeg转为浏览器兼容PCM WAV。Git不提交原版采样；dist/local已忽略。

可预置多个曲目与可选sidecar：

```bash
python3 scripts/toolkit.py build-web --pack local/soundpack.json --nbs local/song/song-r1.nbs local/song/song-r2.nbs -o dist/review.html
```

sidecar自动查找同路径 `song.nbs.json`，有文件但哈希不匹配时拒绝打包。对现有仅NBS曲目，仍可自动列出音色及全部物理层，无需编配JSON。

## 精简交互

- 一次导入多个NBS，在曲目选择器切换。
- 全曲播放、进度定位、音符时间轴、显式总音量。
- 按音色/实际NBS层独奏、静音、搜索；有验证过的sidecar才显示语义声部。
- 同位置A/B对比两个NBS，切换时恢复全部声部，避免套用另一文件的层编号。
- 当前NBS下载；当前所选声部在浏览器OfflineAudioContext渲染成WAV。无独立声部归一化；导出检测采样削波并阻止损坏结果。

不放AI分轨复核、源文件大表格、Suno参考母带等项目专用功能。原始音频诊断放在CLI报告中。

## 边界

- 支持NBS v0–v5。自定义音色缺采样时明确报错，不能替换为默认钢琴。
- game配置忽略逐音velocity/fine/panning，使用层音量与层声像；full NBS配置支持这些字段。目标解码器若还有别的差异，须显式扩展profile并测试。
- 不依赖原MIDI音长，不切断采样自然尾音。完整渲染保留最后音符的尾音；NBS循环信息不自动循环。
- 默认16种本机原版采样，不内置“近似合成音”假装原版。无音色包时可以解析查看，播放按钮保持不可用。
- 导出采用44.1kHz立体声16位PCM，15分钟内存上限；浏览器文件上限20MB/15万音符。常规几分钟音乐适用，超大项目应拆分或改用专用音频工作站。
- Chrome/Edge/Safari需支持AudioContext、OfflineAudioContext和StereoPannerNode。若浏览器不支持file://上的crypto.subtle，则普通NBS可用，sidecar哈希验证需静态localhost或安全上下文；不要跳过哈希验证。
