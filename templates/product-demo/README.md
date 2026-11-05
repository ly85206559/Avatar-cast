# 演示种草：边讲边展示

从一个真实使用场景切入，展示产品素材，再回到主播给出适用建议。

[返回模板选择](../../README.md#选一个模板开始) · [所有模板用法](../README.md)

![演示种草布局：素材主画面、主播小窗，再切回主播](../../docs/demos/product-demo.gif)

上图使用已有「下班放松」口播和根据原对白绘制的示意卡，展示镜头切换，**不是产品推荐成片**。GIF 无声；素材展示区间与字幕为估算，需播放复核。本地重包没有提交生成。

## 附上照片，直接告诉助手

```text
用演示种草模板介绍我的产品，展示我附上的产品图。
```

提供本人或已授权的主播照片、产品名称和至少一个真实特点；有产品图、截图或短视频时一起提供。助手会拟稿，并安排**全屏主播 → 素材主画面＋主播小窗 → 全屏主播**。没有展示素材也能开始，成片使用全屏口播；不会虚构产品实拍或用户评价。

默认约 10 秒、普通话、竖屏 720p。实际台词、素材与费用先一起确认。新口播使用自己的 Grok Bot 账号和额度；Codex / Claude Code 自身也可能收费。本地素材展示和重新包装不调用付费生成服务。

## 素材怎么用

- 支持一份本地 JPG、PNG、WebP、MP4、MOV 或 WebM。横屏素材会完整放入竖屏画面，窄小文字可能需要先裁剪或换成更清楚的截图。
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
