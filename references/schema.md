# 数据契约

`inspect` 输出 `suno-nbs-midi/1`：`files` 含 SHA-256、tempo_changes、repairs、issues；`notes` 含 source_id、source、track、channel、program、start/end（秒）、pitch（实际 MIDI 半音）、velocity、CC7/CC11、pan。source_id 前缀使用源文件内容哈希，不能只按 Vocal/Guitar 名字命名。MIDI format 2 与 SMPTE 时间分辨率明确拒绝。

`arrange` 输出 `suno-nbs-arrangement/1`：

```json
{"duration": 5.0, "events": [
  {"id":"source-note-1", "source_ids":["source-note-1"], "source":"Keyboard", "role":"lead", "time":0.5, "duration":0.2, "pitch":72, "instrument":10, "volume":72, "pan":100}
]}
```

- `time` 是已对齐音频时间轴的绝对秒数；end/duration 仅供分析，NBS 不存可控延音。
- `pitch` 表示目标实际发声 MIDI 音高，不是 NBS key。音色切换时重新换算 key。
- `instrument` 为 NBS 原版音色 ID 0–15，见 nbs.md。
- `volume` 0–100，编码到层音量（game）或逐音力度（nbs）。`pan` 0–200，100 为中间。
- `role/source` 是经分析后赋予的标签；NBS 层名不是可信的原始 AI 轨名。
- 每个源音符在 `dispositions` 中保留 kept / excluded / merged / unassigned。缺规则默认失败；`--allow-unassigned` 只能产出带 draft 标志的草稿。

规则：`rules` 中每条有 `select`、`instrument`、`role`，以及 `volume` 或 `gain`，可选 `transpose/pan/reason`。select 可用 source、track、channel、program、pitch_min/max、time_start/end、ids，时间窗为左闭右开。多条命中同一音符会报错，避免无意覆盖。`exclude:true` 必须带 reason。

`offset` 或 `offsets: {"Guitar":0.43}` 在匹配时间窗之前加到起音上。偏移来自具体项目证据，不能复用农场项目数值。

`encode` 同时生成 `song.nbs.json`：包含 NBS SHA-256、编码 profile、tps，以及每个事件的 tick/layer/key/source/role。浏览器可将它与 NBS 一同导入，只有哈希匹配才添加语义分组。

`patch` 使用显式 ID，且所有 expect 前置条件必须符合。没有按“声音尖”自动猜测音符的补丁功能。

```json
[{"id":"source-note-1", "expect":{"instrument":14,"pitch":84}, "set":{"instrument":7,"role":"sparkle"}, "reason":"Window audit and source MIDI confirm this is the upper sparkle, not the ordinary melody"}]
```
