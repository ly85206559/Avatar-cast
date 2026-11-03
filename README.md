<div align="center">

# AvatarCast

### 给一张照片，说一句想法。让 AI 助手帮你做到口播成片。

从拟稿、生成到字幕与风格包装，由 Codex / Claude Code 串起整个流程。

[![CI](https://github.com/ly85206559/Avatar-cast/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/ly85206559/Avatar-cast/actions/workflows/test.yml)
[![MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](pyproject.toml)
[![Agent Skill](https://img.shields.io/badge/Agent_Skill-Codex_%2F_Claude_Code-orange.svg)](skills/avatarcast/SKILL.md)

[模板选择](#选一个模板开始) · [一句话开始](#一句话开始) · [组件图鉴](docs/COMPONENT_GALLERY.md) · [费用说明](#费用说明) · [使用文档](#使用文档) · [参考与致谢](#参考与致谢)

**免费开源 · 使用你自己的生成账号 · 生成前确认费用**

</div>

## 选一个模板开始

| [产品推荐](templates/product-intro/README.md) | [知识分享](templates/knowledge-share/README.md) | [情感共鸣](templates/empathy/README.md) |
| :---: | :---: | :---: |
| <a href="templates/product-intro/README.md"><img src="docs/demos/product-intro.gif" width="216" alt="产品推荐包装预览：复用测试对白，强调短句和调整景别"></a> | <a href="templates/knowledge-share/README.md"><img src="docs/demos/knowledge-share.gif" width="216" alt="知识分享包装预览：复用测试对白，逐项推进要点"></a> | <a href="templates/empathy/README.md"><img src="docs/demos/empathy.gif" width="216" alt="情感共鸣包装预览：复用测试对白，稀疏暖色关键句"></a> |
| **谁会需要 → 一个卖点 → 适用建议** | **问题 → 解释或例子 → 一句话带走** | **说中处境 → 温和回应 → 一个小行动** |
| 人像＋产品和真实特点 | 人像＋一个问题或方法 | 人像＋想回应的情境 |
| “用产品推荐模板介绍这款轻便水杯” | “用知识分享模板讲讲下班放松” | “用情感共鸣模板鼓励进步慢的人” |
| [使用这个模板 →](templates/product-intro/README.md) | [使用这个模板 →](templates/knowledge-share/README.md) | [使用这个模板 →](templates/empathy/README.md) |

每个模板包含可替换文案槽位、默认包装和可运行示例。助手负责填内容与安排时间，你无需改模板代码；也可以直接说想做什么，让助手替你选。

上面是**同一条测试口播的实际包装动图**，用于预览呈现方式，尚非三个题材各自的新成片。本轮新增生成请求为 **0**；GIF 无声，原对白与表演不变。[样例来源](docs/demos/README.md) · [还缺哪些完整 demo](docs/DEMO_ASSETS.md)

## 一句话开始

在能访问本地文件、执行终端命令的 **Codex 或 Claude Code** 中，附上一张本人或已授权的照片，发送：

```text
请安装 https://github.com/ly85206559/Avatar-cast，按 skills/avatarcast/SKILL.md 用这张照片做一条「分享三个下班放松方法」口播。
```

把「」里的内容换成你的想法。安装完成后，可以直接说：**“用这张照片，做一段介绍我的咖啡店的口播。”**

| 你来决定 | 助手来完成 |
| --- | --- |
| 给照片、说想法 | 准备环境，选择模板，按三段结构拟好台词与标题 |
| 登录自己的账号，确认方案与费用 | 生成片段，等待或恢复原任务，完成本地包装 |
| 看成片，提出修改 | 交付 MP4；复用原片修改标题、字幕呈现与风格 |

默认先做 **约 10 秒 · 普通话 · 9:16 · 720p** 的一段短片。生成前，你会看到实际台词、标题、风格、段数和费用条件；确认后才提交。

**首次需要你的 Grok Bot 账号与可用额度。** 助手会引导登录和连接；无法确认费用符合预算时，停在计划阶段。项目不附送生成账号或订阅。

<details>
<summary><strong>看一次实际的新用户流程</strong></summary>

输入想法：**分享三个下班放松方法**。

助手拟稿并经确认后生成：

> 下班后，先把工作消息放一放，再散步十分钟，最后听首喜欢的歌，给自己一点放松的时间。

<p align="center">
  <img src="docs/images/first-video.png" width="300" alt="新用户流程样片截图：虚拟主播讲述下班放松方法，画面含 AI 标识和短句字幕">
</p>

这条约 10 秒样片来自一个全新目录下的 Windows 实际运行。截图展示修复后的本地包装；该次语音匹配未通过，字幕降级为按短句估算时间，仍需播放复核。它证明了这一账号与环境下的流程产出，不代表所有账号、平台或口型质量均已验证。

</details>

## 为什么用 AvatarCast

- **从想法开始。** 助手负责拟稿和操作，你无需先写 JSON、选字体或填模型参数。
- **改包装，复用原片。** 说“换成知识讲解”或“标题改成……”，在本机另存一个版本，保留原声。
- **花费提前说清。** 默认只用已有订阅额度、不额外付费；核实账号条件后，再确认生成计划。
- **中断后接着做。** 保存已提交的任务记录，连接恢复后查询原任务，避免盲目重复生成。
- **本地完成后期。** FFmpeg 负责组装与包装，Vosk 尝试语音匹配；无需在本机部署视频生成大模型。

项目由 **Python 流水线 + 轻量 Skill** 组成。助手使用与命令行相同的一套工具，进阶用户也可以直接运行 `dhp`。

## 模板也能继续改

模板决定文案结构与默认配方，风格决定文字外观。普通自我介绍仍可使用简洁口播；你也可以对所选模板说“少点花字”“只突出最后一句”。

**已有成片后，继续说：**

```text
保留原片和原声，换成知识分享模板。
标题改成「给自己十分钟」。
```

这些调整在本机完成，不再次提交视频生成。包装可以改变信息呈现；修改对白、换形象或重新表演需要另行生成、重新确认费用。商品信息与价格由你提供，助手不会补造。

<details>
<summary><strong>想自己搭配？已有 8 个基础包装组件</strong></summary>

| 组件 | 用途 |
| --- | --- |
| 文字卡 · 关键词强调 | 开场命题、定义、强调一句重点 |
| 数字卡 · 文字证据聚焦 | 展示有来源的数字或原话摘录 |
| 文字对比 · 步骤推进 | 对照两种说法，逐步讲解一个方法 |
| 主播景别 · 复盘板 | 小幅调整画面，收束已讲过的要点 |

自动配方会尝试本地语音匹配；缺模型、文字不匹配或置信度不足时，使用简单标题与估算字幕，并提示复核。识别出的短句时间也不是逐词强制对齐。

先看[8 个组件的实际动图与用法](docs/COMPONENT_GALLERY.md)，再让助手添加需要的效果。参数、时间线和复现方法见[本地包装指南](docs/LOCAL_PACKAGING.md)。

</details>

## 费用说明

**开源免费，视频生成由你自己的服务账号计费。** 默认预算是只用已有订阅额度、不额外付费；这需要先核实账号设置，不是供应商账单保证。

| 环节 | 费用来自哪里 |
| --- | --- |
| 助手安装、拟稿与操作 | Codex / Claude 账号或 API 的计费规则 |
| 生成画面与声音 | Grok Bot 账号的订阅、额度及可能的超额费用；单条消耗不能预设为零 |
| 本地识别、字幕、风格包装 | 不调用付费生成服务；占用本机计算资源 |
| 另行生成图片、声音，或更换服务 | 需单独核实服务费用并确认，不会自动切换 |

生成前检查订阅、剩余额度、按需计费和自动充值；未知费用就明确标为未知。助手不会自动充值、升级或开启按需计费，CLI 本身不能核实账单或强制限制供应商扣费。

## 当前能跑到哪一步

| 范围 | 当前状态 |
| --- | --- |
| Windows + Grok Bot | 已在一个账号上实际跑通单段生成、任务恢复和本地包装 |
| macOS / Linux | 提供连接脚本与指南；Ubuntu、macOS 的离线连接测试已进 CI，真实账号出片仍待验证 |
| 内容模板与字幕 | 已接入 3 个内容模板、4 种外观、8 个组件；可填写文案槽位并自动包装，语音匹配不可靠时明确降级 |
| 替换生成模型、锁定录音 | 引导入口目前使用 Grok 原生路线；WaveSpeed 有独立单段适配，尚未完成真实端到端验证 |

Grok 原生路线同时生成画面与声音，不能锁定已有 WAV，也不保证跨段声音一致。Grok Bot 网关属于非公开接口，版本或远程电脑状态变化可能影响连接。精确口型评分、自动多模型路由和直播仍属后续方向。

## 使用文档

**想直接出片，用上面的一句话；想自己操作，从命令行指南开始。**

| 文档 | 解决什么问题 |
| --- | --- |
| [模板用法](templates/README.md) · [8 个组件图鉴](docs/COMPONENT_GALLERY.md) | 选成品结构、替换内容、组合具体效果 |
| [Demo 素材清单](docs/DEMO_ASSETS.md) | 已有 JPG／GIF、本地验证视频与待补的题材成片 |
| [命令行安装与使用](docs/CLI_GUIDE.md) | 安装、账号连接、计划确认、生成、恢复与交付 |
| [macOS / Linux 连接指南](docs/GROK_SETUP_UNIX.md) | Unix 环境与第三方 CLI 登录、网关配置 |
| [本地包装指南](docs/LOCAL_PACKAGING.md) | 自动配方、Vosk 模型、8 个组件与对照样例 |
| [Agent Skill](skills/avatarcast/SKILL.md) | 给助手执行的完整工作流程 |
| [音频驱动接口](docs/API_LIPSYNC.md) | WaveSpeed 独立适配与费用确认规则 |
| [研究记录](docs/PRESENTATION_PARADIGMS.md) · [风格调研](docs/STYLE_RESEARCH.md) | 包装组件从哪里来，哪些还需验证 |
| [架构设计](docs/ARCHITECTURE.md) · [路线图](docs/ROADMAP.md) | 模块与后续方向；规划不等于已实现 |

<details>
<summary><strong>没有生成账号？先跑一次离线流程</strong></summary>

在已克隆的仓库中准备 Python 3.10+、FFmpeg / ffprobe 与中文字体，使用虚拟环境运行：

```bash
python -m pip install -e .
python -m dhp.cli examples/demo-script.json --brief examples/demo-brief.json --dry-run --output-dir outputs/dry-run --cache-dir outputs/dry-run-cache
```

输出目录须不存在或为空，且与缓存目录分开。该演练只用测试卡与合成音调，验证组装、字幕和报告，不生成真实口播、不调用生成服务。完整环境步骤见[命令行指南](docs/CLI_GUIDE.md)。

</details>

## 参与改进

欢迎反馈安装卡点、字幕问题和包装建议。[提交 Issue](https://github.com/ly85206559/Avatar-cast/issues) 时附上系统、命令和脱敏报错；不要上传令牌、私有配置或未经授权的素材。

贡献代码前请看 [CONTRIBUTING.md](CONTRIBUTING.md)。代码采用 [MIT 许可证](LICENSE)；示例截图的素材说明见[这里](docs/images/README.md)。

## 参考与致谢

感谢 Berryxia（[@andyhuo520](https://github.com/andyhuo520)）开源的 [digital-human-koubo](https://github.com/andyhuo520/digital-human-koubo)。AvatarCast 在自然语言驱动口播制作、按内容选择包装风格，以及将成熟视频呈现方式沉淀为可组合组件的设计上，参考了该项目公开的工作流与组件方案。

AvatarCast 当前以 Grok Bot 原生生成、本地 FFmpeg 包装、保守的 Vosk 语音匹配、费用确认和原任务恢复为实现重点。具体参考点、源码对照与复用边界见[呈现范式与组件研究](docs/PRESENTATION_PARADIGMS.md)；能力与效果以本仓库的实现和实测记录为准。
