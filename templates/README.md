# 选模板，换成自己的内容

[产品推荐](product-intro/README.md) · [知识分享](knowledge-share/README.md) · [情感共鸣](empathy/README.md)

对 Codex / Claude Code 说用途并附上授权人像，助手会读取模板、拟好三段结构的短台词、选好包装并准备计划。普通用户无需填写 JSON 或时间线。

模板的工作流相同：**了解必要事实 → 按槽位拟稿 → 你确认台词与费用 → 生成 → 本地包装 → 播放复核**。产品推荐需要真实产品信息，知识分享需要一个主题，情感共鸣需要具体处境。配方只使用原片中已说出的短句，不会自动补造价格、效果或证据。

## 命令行使用

```text
dhp make templates
dhp make templates product-intro
dhp make plan --image presenter.png --brief-file templates/product-intro/example.json --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

示例 brief 包含 `request`、`title`、`template` 和 `beats`。三个模板的槽位分别是：

| 模板 ID | 三个写稿槽位 | 默认包装 |
| --- | --- | --- |
| `product-intro` | `audience` 谁需要 → `benefit` 一个卖点 → `fit` 适用建议 | 短句强调、小幅景别变化 |
| `knowledge-share` | `question` 问题 → `explanation` 解释／例子 → `takeaway` 一句话结论 | 要点推进 |
| `empathy` | `situation` 处境 → `reframe` 温和回应 → `action` 小行动 | 稀疏关键句 |

CLI 按顺序连接助手写好的槽位，补齐句末标点，不调用额外写稿服务。`script` 与 `beats` 同时提供时必须一致。也可沿用已有 `script`，用 `--template ID` 选择配方；此时文案结构由调用者负责。

`--template auto` 按制作意图中的关键词选用模板，未命中时保留通用口播；助手应优先按实际语义判断。显式 `style` 可以覆盖模板配色，模板决定内容编排。

计划保存模板 ID 和版本，生成前的哈希审核包含这部分；批准后改变模板或台词需要新计划。模板计划的 `run` / `resume` 自动尝试本地 Vosk 匹配与包装。`restyle --project` 默认沿用原模板，换模板时显式传 `--template ID`；自定义 `--pack-file` 会替代模板，不能与显式模板同时传入。

## 费用与验证范围

新口播仍使用你自己的 Grok Bot 账号和额度，生成前确认费用。模板、写稿槽位、本地语音识别与重新包装没有独立的付费生成调用；助手账号自身按其规则计费。

模板已用已有原片验证本地编排、导出与保守降级，本轮新增生成为 0。模板页动图使用流程测试对白，不代表产品、情感题材已分别生成完整新样片。缺少对应题材的展示材料见 [demo 清单](../docs/DEMO_ASSETS.md)。

识别文本不匹配、置信度不足或模型缺失时，只保留简单标题与估算字幕。成功匹配的时间也是识别估计，不能代替逐词强制对齐或人工口型验收。
