# 8 个基础组件图鉴

[返回模板选择](../README.md#选一个模板开始) · [本地包装参数](LOCAL_PACKAGING.md)

先看效果，再告诉助手“加一个价格卡”“把三个步骤依次显示出来”。助手根据真实内容准备参数和时间线，你不需要认识组件英文名。

下列动图均由已完成的授权虚拟形象原片在本地渲染，播放约 4 秒并循环。素材台词是“先验证画面、声音和字幕”，时间为估算；没有请求新的生成，也没有新增商品或表演。GIF 无声，不能证明口型或语音质量。

| 组件与实际动图 | 对助手这样说 | 用途与示例 |
| --- | --- | --- |
| **文字卡**<br><img src="demos/TextCard.gif" width="180" alt="文字卡进出场动图"> | “开头先提出一个问题” | 标题／定义／收束。[TextCard 示例](../examples/components/TextCard.json) |
| **关键词强调**<br><img src="demos/KeywordEmphasis.gif" width="180" alt="短句强调动图"> | “把这句重点突出一下” | 整句或短语强调。[KeywordEmphasis 示例](../examples/components/KeywordEmphasis.json) |
| **数字卡**<br><img src="demos/MetricCard.gif" width="180" alt="带来源的三项检查数字卡"> | “说到数量时显示数字和单位” | 需真实数值与依据。[MetricCard 示例](../examples/components/MetricCard.json) |
| **文字证据聚焦**<br><img src="demos/EvidenceFocus.gif" width="180" alt="原话摘录及来源卡"> | “把这段依据展示出来” | 摘录与来源，不是截图放大。[EvidenceFocus 示例](../examples/components/EvidenceFocus.json) |
| **文字对比**<br><img src="demos/ComparePanel.gif" width="180" alt="同一维度的文字双栏对比"> | “把这两种方式放在一起对照” | 两边必须是同一比较维度。[ComparePanel 示例](../examples/components/ComparePanel.json) |
| **步骤推进**<br><img src="demos/StepProgress.gif" width="180" alt="三步骤依次高亮的动图"> | “讲到哪一步，就突出哪一步” | 2–4 步随讲解推进。[StepProgress 示例](../examples/components/StepProgress.json) |
| **主播景别**<br><img src="demos/HostReframe.gif" width="180" alt="同一主播画面局部放大与恢复"> | “重点那句稍微推近一点” | 本地缩放，不改变表演。[HostReframe 示例](../examples/components/HostReframe.json) |
| **复盘板**<br><img src="demos/RecapBoard.gif" width="180" alt="总结已讲内容的复盘卡"> | “结尾回顾刚才的几个要点” | 只回收已讲过的内容。[RecapBoard 示例](../examples/components/RecapBoard.json) |

## 怎么用

优先告诉助手用途，它会使用模板或准备匹配你实际内容的 `pack.json`。上述 JSON 是针对这条测试口播的可运行示例，需要至少 4.5 秒原片；换台词时要换文字、来源与时间，不能把示例数字当成商品事实。

```text
dhp make restyle --job-dir PATH_TO_COMPLETED_JOB --style explainer --pack-file pack.json
```

纯本地渲染，不上传素材、不提交生成。`--pack-file` 与 `--request` / 显式 `--template` 不同时使用。想少操心时直接选[完整模板](../templates/README.md)，由助手处理组合与时间。

图鉴复现脚本为 [preview_library.py](../scripts/preview_library.py)，需要文中指定的已完成测试原片；原片和私人任务文件不随仓库分发。组件实现、输入校验与降级约束见 [LOCAL_PACKAGING.md](LOCAL_PACKAGING.md)。
