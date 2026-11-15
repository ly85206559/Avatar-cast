# 模板与组件预览素材

## AvatarCast 种草完整成片

用户已确认将重拍开场版完整成片公开用于本仓库的演示种草 demo。成片为 87.821 秒、720 × 1280、H.264 / AAC，包含花字、素材切换、主播小窗、历史样片和包装前后对照。

- [完整有声 MP4](https://github.com/ly85206559/Avatar-cast/releases/download/demo-product-demo-20261115/avatarcast-product-demo.mp4) 托管在 GitHub Release，文件大小 24,124,368 字节，SHA-256 为 `2c5ca00d3f948cb52f3ac7f3670673e7496b04725475526f147cbc6c33f1ba71`。
- [封面 JPG](avatarcast-product-demo.jpg) 截自同一成片的 4.30 秒。
- [无声 GIF](avatarcast-product-demo.gif) 依次节选 2.30–4.70、12.80–14.60、38.90–40.70 秒，展示关键词花字、步骤讲解与主播小窗、素材卡和界面截图切换。总长 6 秒，360 × 640，10 fps。

源片使用现有 Grok Bot 账号分段生成，后期结合本地 Whisper 时间数据、Remotion、FFmpeg 和人工校对。公开版本沿用用户确认的重拍开场与后续八段；这次封面、GIF 与上传均使用该已完成版本。历史样片在画面内展示时保留静音提示。完整成片可公开播放，示例形象的再利用仍需另行取得素材授权。

## 早期模板与组件预览

`product-demo-remotion.gif` 与对应 JPG 使用同一条「下班放松」原片及已有示意卡的两份裁切，演示本地 Whisper 与 Remotion 动态包装。整句匹配未通过，字幕和素材区间为估时；花字来自局部可靠匹配词。GIF 无声，可用 `scripts/preview_remotion.py` 重现本地有声对照。

使用者已同意公开展示既有虚拟形象样片；这些静态帧和无声动图用于本仓库的模板选择与组件图鉴。本轮仅从已完成的原片进行本地包装、截帧和 GIF 导出，没有新生成请求。

- `product-intro / knowledge-share / empathy`：同一条约 10 秒流程测试口播，三种模板的实际包装。原片 SHA-256 为 `967c7a31e552c8620563b528aaddf6b94a370511a3782c5fd079b851d8e85a63`。三条本地 Vosk 匹配成功，组件时间仍为识别估计。
- `three-point`：已有「下班放松」题材原片的本地重包，原片 SHA-256 为 `51ec210667cb24b09bdcd668a9bc05139731b9c95db3a6c9bf2f7ae505331bb5`。本地识别未完整匹配，字幕和三个方法的切换按文案长度估算，需播放复核；完整有声 MP4 保留在本地。
- `product-demo`：同一条「下班放松」原片，配合依据原对白绘制的[示意卡](../../examples/showcase/relax-card.png)，演示素材主画面、主播小窗与切回主播。素材和原片均在本地处理；这不是产品推荐成片。识别未匹配，展示时间按文案长度估算。
- 8 个英文组件名：各约 4 秒的实际演示，使用已完成的第一条测试口播“你好，这是 AvatarCast 的数字人口播测试。我们先验证画面、声音和字幕是否同步。”；文字与来源由此测试内容准备，时间为估算。
- 上述早期预览各有 `.jpg` 静态帧和 `.gif` 循环动图，原视频与原始音轨保留在本地。

这些预览不能用来证明新的产品推荐台词、情感表演、逐词对齐或人工口型验收；对应题材完整 demo 的补齐计划见 [DEMO_ASSETS.md](../DEMO_ASSETS.md)。

复现脚本为 [preview_library.py](../../scripts/preview_library.py)，独立组件示例在 [examples/components](../../examples/components/)。代码的 MIT 许可证不代表获得示例形象的再利用授权；复用形象请另行取得素材授权。

三点干货的预览使用 [preview_three_point.py](../../scripts/preview_three_point.py)，从已完成的「下班放松」原片及其人像重建计划并在本地重包。脚本会核对原片对白、人像及原片哈希，不提交生成：

```text
python scripts/preview_three_point.py --job-dir PATH_TO_RELAXATION_JOB --image PATH_TO_ITS_PRESENTER --output-dir outputs/three-point-preview --preview-dir outputs/three-point-gif --asr-model PATH_TO_VOSK_MODEL
python scripts/preview_product_demo.py --job-dir PATH_TO_RELAXATION_JOB --image PATH_TO_ITS_PRESENTER --output-dir outputs/product-demo-preview --preview-dir outputs/product-demo-gif --asr-model PATH_TO_VOSK_MODEL
```

输出目录都必须尚不存在。先确认素材授权再公开预览；该示例人像不随代码许可证授权复用。
