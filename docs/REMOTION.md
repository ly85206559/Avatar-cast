# 动态种草模板与 Whisper 时间轴

对助手说“用演示种草模板，按顺序展示这两份素材，加上花字和主播小窗”，附上授权人像、产品事实和本地图片／视频。助手准备依赖、拟稿、确认生成费用，并在原片完成后本地剪辑。已有原片可以直接重新包装。

## 本地工具与费用

- Whisper 采用 `faster-whisper`，使用本地多语言模型和 CPU int8 推理。首次安装和下载模型需要联网，转写仅加载指定的本地目录。
- Remotion 使用 Node.js、React 和本地浏览器渲染。首次安装会下载 npm 依赖，缺少浏览器时 Remotion 会下载渲染浏览器。已有 Chrome 可通过 `REMOTION_BROWSER_EXECUTABLE` 指定完整路径。
- 截至 2026-11-13，Remotion 官方为个人和不超过 3 人的小公司提供免费许可，涵盖商用和自动化。其他组织需要按官方条款选择许可证。AvatarCast 的 MIT 许可证覆盖本项目代码，使用者仍需遵守依赖许可。助手应说明适用条件，用户已确认的许可条件可沿用。[Remotion 许可与价格](https://www.remotion.dev/docs/license/pricing)
- 本地转写、素材展示和渲染不调用视频生成服务。新口播、重拍、另行生成图片或配乐的费用单独核实。

## 首次准备

在仓库虚拟环境中运行以下命令。Windows 可使用 `npm.cmd`。

```bash
python -m pip install -e '.[native,whisper]'
npm ci --prefix src/dhp/remotion_template
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='outputs/models/faster-whisper-small')"
```

将 `WHISPER_MODEL_PATH` 设为下载模型的绝对目录。PowerShell 使用 `$env:WHISPER_MODEL_PATH = '模型完整目录'`，macOS / Linux 使用 `export WHISPER_MODEL_PATH='模型完整目录'`。已安装 wheel 的用户，可通过 `python -c "import dhp; from pathlib import Path; print(Path(dhp.__file__).parent / 'remotion_template')"` 找到 npm 模板目录。Node.js 需 18 及以上版本。

## 用已有原片试模板

```bash
dhp make restyle --job-dir PATH_TO_COMPLETED_JOB --template product-demo --renderer remotion --asset first.png --asset second.mp4 --title "你的标题" --output-dir outputs/promo-edit
```

`--project PATH_TO_PROJECT` 可以替代 `--job-dir`，复用原计划中所有已完成片段。`--asset` 可重复，顺序即展示顺序。图片保持完整比例，视频从自身开头播放并循环，素材声音静音，整条主播原声保留。

输出包括 `final.mp4`、`subtitles.srt`、`alignment.json`、`remotion.json` 和 `qa.json`。时间轴中保留原始识别词、置信度、句子边界、素材场景区间与估时标记。对齐失败时使用文案估时字幕，并在画面和报告中提示复核。花字只选完整匹配文稿、置信度至少 0.8 且时间有效的词，保留其实际识别时间；整句匹配失败时仍可使用这样的局部匹配词，每句最多一处。匹配结果均需播放复核。

展示段优先使用计划中的 `demo` 台词边界；没有可靠结构时使用中间 25%–75% 的区间。多份素材在该区间内依次均分，每份至少 0.5 秒，过多时应减素材或延长原片。这个默认规则仍需要播放复核，尚未支持每份素材独立绑定某个关键词。

强调卡从匹配词出现的识别时间开始，至少显示 0.65 秒以便阅读。原始识别结束时间仍保留在时间轴中。

## 接入新片制作

助手编写的 brief 可增加以下字段，其余文案槽位沿用演示种草模板。

```json
{
  "request": "演示种草，展示两份产品素材",
  "template": "product-demo",
  "renderer": "remotion",
  "title": "轻松展示产品",
  "beats": {
    "hook": "想把产品介绍清楚？",
    "problem": "光说特点还不够直观。",
    "demo": "配上你自己的产品图和演示画面。",
    "fit": "先把一个特点讲明白。"
  },
  "asset": ["产品图片的绝对路径", "演示视频的绝对路径"]
}
```

`make plan --image PHOTO --brief-file BRIEF` 会记录渲染器和每份素材的路径、类型、哈希。`make show` 展示完整审核计划，确认后才执行原有 `make run`。`run` / `resume` 完成后自动使用 Remotion 与 Whisper；费用确认、原任务恢复和素材变更检查沿用原流程。用 `--renderer ffmpeg` 可选择已有单素材包装。

只换包装可运行 `make restyle --project PROJECT --renderer remotion`，原计划保持独立。也可用 `--asr-engine whisper` 为 FFmpeg 包装启用 Whisper，或用 `--asr-engine vosk` 选择已有识别器。`--asr-model` 始终指向所选识别器的本地模型。

## 验证范围

此模板提供动态短句字幕、匹配词强调、顺序素材展示、主播小窗以及前后全屏主播。原生 Grok 多段音色一致性需要逐段试听，识别时间也需播放复核。已有短片验证覆盖本地剪辑；约 90 秒新口播仍需真实账号、完整制作计划与相应额度。

实现参考了 digital-human-koubo 的内容驱动剪辑思路。React 模板与 Python 集成为本项目实现。[参考项目花字编排](https://github.com/andyhuo520/digital-human-koubo/blob/f661a6c047bb74ea306ef58aeb1d461a52c01871/skills/digital-human-koubo/references/huazi.md)
