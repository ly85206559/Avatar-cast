# 已有原片的本地组件包装

想直接选成品结构，先看[内容模板](../templates/README.md)；想指定某个效果，先看[8 个组件的实际动图与用法](COMPONENT_GALLERY.md)。模板项目会在 `run` / `resume` 完成后自动尝试包装；已有原片可用 `make restyle --template ID`，不会重新生成对白。三点干货需要计划中保存对应的三个方法，否则只保留标题并提示。

演示种草可额外使用一份本地图片或视频：`make restyle --job-dir JOB --template product-demo --asset MEDIA`。有展示文案角色时按角色定位，否则按总时长估算；结果需播放复核。素材音轨静音，主播原声保留。替换素材使用新的编辑输出，不改原计划。

8 个组件已接入 `dhp make restyle` 与原生视频组装。它们由现有 Python／FFmpeg 渲染，不需要新的模型账号、Node 或付费生成。现阶段支持文字卡片与景别变化；证据聚焦呈现有来源的文字摘录，对比呈现文本双栏，截图推近和真实商品画中画尚未接入。

## 让助手操作

优先直接给一句话，程序会选配方并尝试本地语音匹配：

```text
dhp make restyle --project outputs/my-video --request "把这条做成知识分享"
dhp make restyle --job-dir outputs/completed-native-job --request "做成温暖陪伴"
```

无需填写 `--style` 或组件 JSON。推广组合强调已说出的短句并小幅变景；知识组合用已说出的要点推进，单个要点用文字摘录；温暖组合只保留少量关键句。不会因为用途是带货就补造商品、价格或测评，原片对白与表演保持原样。

本地识别需要 `python -m pip install -e ".[asr]"`，并从 [Vosk 官方模型页](https://alphacephei.com/vosk/models)下载中文 `vosk-model-small-cn-0.22`（约 42 MB）。模型不随仓库分发；解压后设置 `VOSK_MODEL_PATH`，或仅本次传 `--asr-model MODEL_DIRECTORY`。命令运行时不下载模型、不上传媒体、不调用外部识别服务；FFmpeg 可使用已有系统版本或 `.[native]` 的本地备用版本。

匹配规则是去掉标点后的文本完全一致，各词置信度至少 0.8，并有有效、顺序正确的时间戳；短句边界使用识别词的起止时间，不插值缺词。这个阈值是保守的选择规则，不能证明识别正确或口型合格。拼写不同、额外对白、低置信度或模型不可用都会降级为简单字幕与标题卡，结果含中文复核提示。降级时不保留复杂语音卡点，也不自动重试或换付费服务。

降级字幕优先按逗号、句号等标点拆成短句，各短句独立按字数占比分配估算时间，不再为凑行长挪动句尾字符。英文单词与小数保持完整；没有标点的长中文仍需按画面宽度折行，未提供中文语义分词保证。字幕时间仍须播放复核，这项改善不会把识别失败标成匹配成功。

输出包含 `pack.json`、`alignment.json` 和 QA，记录原始识别词、置信度、匹配／降级原因。成功的字幕状态为 `vosk_matched_sentence_bounds`，组件状态为 `asr_matched`；降级字幕依然标为估算。所有路径都需要播放复核，`speech_accuracy` 和口型质量不会因此自动变成通过。

若需手工调整组件，仍可使用下面的显式时间线入口；`--request` 与 `--pack-file` 不能同时使用。

对已完成的视频说：“保留原声，做成知识讲解包装”“少点花字”或“把依据展示出来”。助手读取原片与台词，准备组件时间线，再运行：

```text
dhp make restyle --project outputs/my-video --style explainer --pack-file pack.json
```

`--style` 支持 `clean / promo / explainer / warm / auto`。`--pack-file` 决定卡片文字与时间，覆盖原来的静态标题布局；修改这类标题时编辑对应 `TextCard`。没有指定 `--pack-file` 和 `--request` 时，保留原有静态包装和保守裁尾行为。

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

手写 `timing` 使用 `estimated`（估算）或 `manual_reviewed`（调用者已看片复核）。自动配方另可产生 `asr_matched`，表示采用识别匹配边界，不是人工验收或逐词强制对齐。时间必须是有限数值，`0 <= at < until`，并落在实际成片内。原片不足 8 秒时，需要调整上例时间。

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
