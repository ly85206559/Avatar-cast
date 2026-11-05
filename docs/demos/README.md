# 模板与组件预览素材

使用者已同意公开展示既有虚拟形象样片；这些静态帧和无声动图用于本仓库的模板选择与组件图鉴。本轮仅从已完成的原片进行本地包装、截帧和 GIF 导出，没有新生成请求。

- `product-intro / knowledge-share / empathy`：同一条约 10 秒流程测试口播，三种模板的实际包装。原片 SHA-256 为 `967c7a31e552c8620563b528aaddf6b94a370511a3782c5fd079b851d8e85a63`。三条本地 Vosk 匹配成功，组件时间仍为识别估计。
- `three-point`：已有「下班放松」题材原片的本地重包，原片 SHA-256 为 `51ec210667cb24b09bdcd668a9bc05139731b9c95db3a6c9bf2f7ae505331bb5`。本地识别未完整匹配，字幕和三个方法的切换按文案长度估算，需播放复核；完整有声 MP4 保留在本地。
- `product-demo`：同一条「下班放松」原片，配合依据原对白绘制的[示意卡](../../examples/showcase/relax-card.png)，演示素材主画面、主播小窗与切回主播。素材和原片均在本地处理；这不是产品推荐成片。识别未匹配，展示时间按文案长度估算。
- 8 个英文组件名：各约 4 秒的实际演示，使用已完成的第一条测试口播“你好，这是 AvatarCast 的数字人口播测试。我们先验证画面、声音和字幕是否同步。”；文字与来源由此测试内容准备，时间为估算。
- 每个名称有 `.jpg` 静态帧和 `.gif` 循环预览。没有公开原视频、原始音轨、配置、令牌或任务对话。

这些预览不能用来证明新的产品推荐台词、情感表演、逐词对齐或人工口型验收；对应题材完整 demo 的补齐计划见 [DEMO_ASSETS.md](../DEMO_ASSETS.md)。

复现脚本为 [preview_library.py](../../scripts/preview_library.py)，独立组件示例在 [examples/components](../../examples/components/)。代码的 MIT 许可证不代表获得示例形象的再利用授权；复用形象请另行取得素材授权。

三点干货的预览使用 [preview_three_point.py](../../scripts/preview_three_point.py)，从已完成的「下班放松」原片及其人像重建计划并在本地重包。脚本会核对原片对白、人像及原片哈希，不提交生成：

```text
python scripts/preview_three_point.py --job-dir PATH_TO_RELAXATION_JOB --image PATH_TO_ITS_PRESENTER --output-dir outputs/three-point-preview --preview-dir outputs/three-point-gif --asr-model PATH_TO_VOSK_MODEL
python scripts/preview_product_demo.py --job-dir PATH_TO_RELAXATION_JOB --image PATH_TO_ITS_PRESENTER --output-dir outputs/product-demo-preview --preview-dir outputs/product-demo-gif --asr-model PATH_TO_VOSK_MODEL
```

输出目录都必须尚不存在。先确认素材授权再公开预览；该示例人像不随代码许可证授权复用。
