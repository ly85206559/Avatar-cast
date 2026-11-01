# 已有原片的本地组件包装

8 个组件已接入 `dhp make restyle` 与原生视频组装。它们由现有 Python／FFmpeg 渲染，不需要新的模型账号、Node 或付费生成。现阶段支持文字卡片与景别变化；证据聚焦呈现有来源的文字摘录，对比呈现文本双栏，截图推近和真实商品画中画尚未接入。

## 让助手操作

对已完成的视频说：“保留原声，做成知识讲解包装”“少点花字”或“把依据展示出来”。助手读取原片与台词，准备组件时间线，再运行：

```text
dhp make restyle --project outputs/my-video --style explainer --pack-file pack.json
```

`--style` 支持 `clean / promo / explainer / warm / auto`。`--pack-file` 决定卡片文字与时间，覆盖原来的静态标题布局；修改这类标题时编辑对应 `TextCard`。不指定此参数时保留原有静态包装和保守裁尾行为。

显式组件时间线以规范化后的完整原片为基准，单位为秒，不裁尾、不改台词或表演。输出新目录，源任务、审核计划、原视频保持不变。未完成任务会停止，不能借此补交生成任务。

## 最小时间线

```json
{
  "timing": "estimated",
  "components": [
    {"use": "TextCard", "at": 0, "until": 2, "title": "先说清一个问题"},
    {"use": "KeywordEmphasis", "at": 2, "until": 5, "text": "突出一个重点"},
    {"use": "HostReframe", "at": 5, "until": 8, "scale": 1.08}
  ]
}
```

`timing` 为 `estimated`（估算）或 `manual_reviewed`（调用者已看片复核）。后者是调用者的声明，程序不会据此宣称已做 ASR 或逐词对齐。时间必须是有限数值，`0 <= at < until`，并落在实际成片内。原片不足 8 秒时，需要调整上例时间。

每一时刻尽量只保留一个主要信息卡；字幕位于下方，人脸附近留白。程序不自动识别人脸安全区，裁切和卡片进入／退出处仍需检查。

| 组件 | 必填内容（另需 `use / at / until`） | 使用边界 |
| --- | --- | --- |
| `TextCard` | `title`；可选 `body` | 短标题最多 16 字，正文最多 80 字；问题、定义、收束共用此组件 |
| `KeywordEmphasis` | `text` | 最多 24 字；按片段显示，不宣称逐词同步 |
| `MetricCard` | 字符串 `value / unit / label / source` | 显示数字终值、单位和依据；不生成未提供的价格或增长过程 |
| `EvidenceFocus` | `claim / evidence / source` | 有来源的文字摘录，保留必要上下文；不是截图渲染 |
| `ComparePanel` | `dimension`，`left / right` 各含 `title / text` | 同一比较维度的文字双栏；不代表实测产品效果 |
| `StepProgress` | `steps`，`step_times` | 2–4 个短步骤；时间递增且第一项等于 `at`，当前讲解项高亮 |
| `HostReframe` | `scale` | 1–1.35 倍局部放大；仅改变画面，字幕与标识不跟着缩放 |
| `RecapBoard` | `title / items` | 2–4 个已讲过的短要点；一个结论可直接用文字卡 |

缺参数、未知字段、越界时间会报错。QA 记录组件清单、时间来源、零生成请求和原始素材哈希；原有字幕依旧按段长估算，不能据此判断口型或台词准确。

## 复现三组前后对照

[推广](../examples/packaging/promo.json)、[知识](../examples/packaging/explainer.json)、[温暖](../examples/packaging/warm.json)是围绕已有 10 秒 AvatarCast 测试台词编写的具体样例。它们用于对比呈现方式，不能直接当作任意商品的文案或新生成的情感表演。

```text
python scripts/preview_components.py --job-dir PATH_TO_COMPLETED_PILOT --output-dir outputs/components-preview
```

脚本读取已完成任务的 `job.json / original.mp4`，检查源视频哈希，生成三组 `comparison.mp4`（左原片／右包装）、独立竖屏成片、QA、时间线副本与本地 `index.html`。三组共用同一原片与原声，覆盖全部 8 个组件；示例时间为估算，需播放复核。源码与样例跨平台，但本轮真实素材播放验证在 Windows，macOS／Linux 未做真实素材运行验收。

此脚本只接受上述测试台词，避免将不相符的原片标成证据来源。个人原片未随仓库分发；其他台词请让助手准备匹配的时间线并使用 `make restyle --pack-file`。
