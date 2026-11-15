# 演示种草：边讲边展示

从一个真实使用场景切入，展示产品素材，再回到主播给出适用建议。

[返回模板选择](../../README.md#选一个模板开始) · [所有模板用法](../README.md)

| 成片封面 | 花字、素材与主播小窗 |
| :---: | :---: |
| <a href="https://github.com/ly85206559/Avatar-cast/releases/download/demo-product-demo-20261115/avatarcast-product-demo.mp4"><img src="../../docs/demos/avatarcast-product-demo.jpg" width="240" alt="AvatarCast 种草成片封面：虚拟主播和文案、字幕、剪辑三个花字"></a> | <img src="../../docs/demos/avatarcast-product-demo.gif" width="240" alt="6 秒成片节选：开场花字、步骤讲解、展示卡与界面截图切换、右下角主播小窗"> |

[▶ 观看或下载完整种草视频 · 87.82 秒 · 9:16 · 720p · 有声 MP4](https://github.com/ly85206559/Avatar-cast/releases/download/demo-product-demo-20261115/avatarcast-product-demo.mp4)

这条成片介绍 AvatarCast 自己，按**开场提问 → 制作步骤 → 历史样片 → 模板与素材展示 → 包装前后对照 → 开始使用**展开。可以借用它的结构，替换成自己的产品、特点和展示素材。

Grok Bot 提供 9 段原生画面与声音，本地用 Whisper 时间数据、Remotion 与 FFmpeg 完成包装，并人工校对字幕、花字、抠像与跨段衔接。它包含逐段审片和人工精修；日常使用从下方的短片流程开始。GIF 拼接三个时间区间，无声循环；封面和完整视频来自同一份已确认成片。[素材来源与截取时间](../../docs/demos/README.md#avatarcast-种草完整成片)

## 附上照片，直接告诉助手

```text
用演示种草模板介绍我的产品，展示我附上的产品图。
```

提供本人或已授权的主播照片、产品名称和至少一个真实特点；有产品图、截图或短视频时一起提供。助手会拟稿，并安排**全屏主播 → 素材主画面＋主播小窗 → 全屏主播**。没有展示素材也能开始，成片使用全屏口播；不会虚构产品实拍或用户评价。

默认约 10 秒、普通话、竖屏 720p。实际台词、素材与费用先一起确认。新口播使用自己的 Grok Bot 账号和额度；Codex / Claude Code 自身也可能收费。本地素材展示和重新包装不调用付费生成服务。

## 素材怎么用

需要多份素材与动态花字时，对助手说“展示这两份素材，加花字和主播小窗”。选择 Remotion 动态版后，`--asset` 可以重复，Whisper 在本地生成词级时间数据，匹配可靠时用于关键词强调。安装、费用和完整流程见 [动态种草指南](../../docs/REMOTION.md)。

![本地 Remotion 动态版，已有原片与两份示意卡依次展示](../../docs/demos/product-demo-remotion.gif)

动态版动图沿用「下班放松」原片，将已有示意卡裁为两份依次展示。Whisper 输出词级时间，花字使用局部可靠匹配词；整句字幕和展示区间为估时，仍需播放复核。动图无声，完整有声对照保存在本地。复现时运行 `scripts/preview_remotion.py`，不提交新生成。

- FFmpeg 版支持一份本地 JPG、PNG、WebP、MP4、MOV 或 WebM，Remotion 版支持多份素材。横屏素材会完整放入竖屏画面，窄小文字可能需要先裁剪或换成更清楚的截图。
- 素材的视频声音会静音；主播原声继续播放。素材只用于本地后期，不会作为口播生成任务的图片上传。
- 有文案结构时，素材展示绑定“展示特点”段；时间匹配不可靠时按文案长度估算。旧原片没有对应结构时，展示区间按总时长估算。两种情况都会提醒播放复核。
- 修改素材或切换包装可复用原片；修改对白、形象或表演需要单独生成并确认费用。

## 命令行示例

助手可参考 [example.json](example.json) 拟稿，并用一张项目截图完成计划；普通用户无需编辑 JSON：

```text
dhp make plan --image presenter.png --brief-file templates/product-demo/example.json --asset examples/showcase/avatarcast-catalog.png --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

这两步只准备本地计划。素材的路径与哈希包含在计划中，文件变化后需重新选择；生成前仍需审核完整方案与费用。

给已有原片加素材，不会重新生成：

```text
dhp make restyle --job-dir PATH_TO_COMPLETED_JOB --template product-demo --asset product.png --output-dir outputs/my-showcase
```

若原项目本来就是 `product-demo`，可以用 `--project PROJECT --asset NEW_FILE` 替换素材；新包装另存，原计划和原片保留。完整流程见[命令行指南](../../docs/CLI_GUIDE.md)。
