# 选模板，换成自己的内容

[三点干货](three-point/README.md) · [演示种草](product-demo/README.md) · [产品推荐](product-intro/README.md) · [知识分享](knowledge-share/README.md) · [情感共鸣](empathy/README.md)

对 Codex / Claude Code 说用途并附上授权人像，助手会读取模板、拟好短台词、选好包装并准备计划。普通用户无需填写 JSON 或时间线。

模板的工作流相同：**了解必要事实 → 按槽位拟稿 → 你确认台词与费用 → 生成 → 本地包装 → 播放复核**。产品推荐需要真实产品信息，知识分享需要一个主题，情感共鸣需要具体处境。配方只使用原片中已说出的短句，不会自动补造价格、效果或证据。

## 命令行使用

```text
dhp make templates
dhp make templates product-intro
dhp make plan --image presenter.png --brief-file templates/product-intro/example.json --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

示例 brief 包含 `request`、`title`、`template` 和 `beats`。模板的槽位分别是：

| 模板 ID | 写稿槽位 | 默认包装 |
| --- | --- | --- |
| `three-point` | `hook` 开场 → `point_1/2/3` 三个方法 → `closing` 收尾 | 三个方法逐项强调、小幅景别变化 |
| `product-demo` | `hook` 开场 → `problem` 情境 → `demo` 展示 → `fit` 建议 | 素材主画面、主播小窗、切回主播 |
| `product-intro` | `audience` 谁需要 → `benefit` 一个卖点 → `fit` 适用建议 | 短句强调、小幅景别变化 |
| `knowledge-share` | `question` 问题 → `explanation` 解释／例子 → `takeaway` 一句话结论 | 要点推进 |
| `empathy` | `situation` 处境 → `reframe` 温和回应 → `action` 小行动 | 稀疏关键句 |

CLI 按顺序连接助手写好的槽位，补齐句末标点，不调用额外写稿服务。`script` 与 `beats` 同时提供时必须一致。三点干货要保留 `beats` 才能自动安排三个方法；演示种草使用 `beats` 定位展示段，旧原片则按时长估算。没有展示素材时使用全屏口播。

`--template auto` 按制作意图中的关键词选用模板，未命中时保留通用口播；助手应优先按实际语义判断。显式 `style` 可以覆盖模板配色，模板决定内容编排。

计划保存模板 ID 和版本；三点干货与演示种草还保存文案结构，展示素材记录路径与哈希。生成前的哈希审核包含这些内容，批准后改变模板或台词需要新计划。模板计划的 `run` / `resume` 自动尝试本地 Vosk 匹配与包装。`restyle --project` 默认沿用原模板，换模板时显式传 `--template ID`；自定义 `--pack-file` 会替代模板，不能与显式模板同时传入。

## 费用与验证范围

新口播仍使用你自己的 Grok Bot 账号和额度，生成前确认费用。模板、写稿槽位、本地语音识别与重新包装没有独立的付费生成调用；助手账号自身按其规则计费。

模板已用已有原片验证本地编排、导出与降级，新增生成请求为 0。三点干货与演示种草动图使用「下班放松」原片，后者仅为布局示意；其余三套动图使用流程测试对白，不代表产品、情感题材已分别生成完整新样片。缺少对应题材的展示材料见 [demo 清单](../docs/DEMO_ASSETS.md)。

识别文本不匹配、置信度不足或模型缺失时，字幕按片段长度估算；三点干货的单段视频会同时按文案长度估算三个方法的切换，多段视频只保留标题。成功匹配的时间也是识别估计，均需播放复核。
