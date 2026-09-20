# 内置音符盒采样

`soundpack.js` 包含16种 Minecraft Java 原版音符盒采样，来自本机官方客户端资产。音频版权归 Mojang / Microsoft 所有；未将其声称为本项目原创或套用代码的许可。Open Note Block Studio 是内置音色体验的参考，本项目未复制其代码或自定义音色。

每个条目保存原资源的 SHA-1、音色 ID、采样基准 MIDI 音高和 PCM WAV 数据。只进行单声道44.1kHz PCM格式转换，没有归一化或附加混音处理。采样基准见 `references/nbs.md`。

源码页和单文件构建默认加载这些采样。`build-web --pack path.json` 可替换默认音色包，不会同时打入两套采样；页面的“播放设置”也可临时加载自定义包。
