# 命令行安装与使用

[返回首页](../README.md) · [让助手代为操作](../skills/avatarcast/SKILL.md) · [本地包装](LOCAL_PACKAGING.md)

本指南使用当前的 Grok 原生路线：形象与台词一起生成画面和声音，再在本机包装。需要自己的 Grok Bot 账号与可用额度；不支持锁定已有 WAV。安装、检查和计划不提交生成，真实生成需要先确认完整方案与费用。

## 1. 准备本机环境

需要 Git、Python 3.10+、带 `subtitles` 滤镜和 `libx264` 编码器的 FFmpeg，以及中文字体。离线流程演练另需 ffprobe。`.[native]` 提供备用 FFmpeg，但其构建不一定支持字幕滤镜。

先克隆到新目录，已有项目可直接使用，不要覆盖其他文件：

```bash
git clone https://github.com/ly85206559/Avatar-cast.git
cd Avatar-cast
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = '1'
python -m pip install -e ".[native,asr]"
dhp make doctor
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[native,asr]'
dhp make doctor
```

若终端不允许激活虚拟环境，可直接使用 `.venv` 内的 Python，通过 `python -m dhp.cli` 替代 `dhp`。安装系统依赖的 Unix 示例见[连接指南](GROK_SETUP_UNIX.md)。

`doctor` 只检查环境。若 `subtitles` 或 `libx264` 为 `false`，先安装符合要求的 FFmpeg 并加入 PATH；中文字体为 `missing` 时先安装，为 `unknown` 时自行确认字幕可读。Linux 可安装 Noto CJK 字体。

本地语音匹配还需单独下载 Vosk 中文模型，设置 `VOSK_MODEL_PATH` 或在包装时传入 `--asr-model`；步骤见[本地包装指南](LOCAL_PACKAGING.md)。没有模型或识别不可靠时，会降级为估算字幕，不自动调用付费识别。

## 2. 连接自己的 Grok Bot

项目内置 Python 网关客户端与 `dhp` 命令，不包含 Grok Bot 桌面应用、账号或第三方 CLI/MCP，也不要求运行 MCP 服务。

Windows：在 Grok Bot 桌面应用登录并唤醒已有远程电脑，然后从仓库根目录运行（需要 PowerShell 7）：

```powershell
pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1
dhp make doctor --online
```

脚本读取本机已登录应用的数据，将网关写入当前用户的 `~/.gbm/config.json`。文件含明文令牌，只供当前用户读取，不要共享或提交。脚本默认等待 30 秒就绪，不会自动唤醒、创建电脑或更改计费。

macOS / Linux：按[专门指南](GROK_SETUP_UNIX.md)登录第三方 `grok-bot` CLI，再运行 `python scripts/setup_grok_bot_unix.py`。已有可用网关配置时可直接使用。Unix 连接逻辑有 Ubuntu / macOS 离线测试，真实账号连接与出片仍待验证。

`doctor --online` 只读取网关状态和 Bot 列表。网关为非公开接口，可能随版本变化；连接成功不代表费用已核实。

## 3. 写稿并查看计划

准备授权图片 `presenter.png` 与 UTF-8 台词文件 `script.txt`，选择一个新的输出目录：

```text
dhp make plan --image presenter.png --script-file script.txt --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

也可用 [quick-brief.json](../examples/quick-brief.json) 的格式，传入 `--brief-file brief.json` 替代 `--script-file`。其中 `request` 是制作意图，`script` 是实际台词，`title` 是标题，`style` 支持 `auto/clean/promo/explainer/warm`。CLI 不会额外调用语言模型写稿；使用 Skill 时由当前助手拟稿。

计划按标点和长度分段，时长只是估计；当前请求普通话、竖屏 720p。首次建议约 10 秒、30–45 个中文字。省略输出路径会在 `outputs/` 下创建新项目。

**真实生成前，核对整份计划中的台词、标题、全部片段及账号计费条件。** 检查订阅、剩余额度、超额费用和自动充值，记录未知值。已有订阅不等于没有额外费用；CLI 无法查询账单或强制执行消费上限。费用不符合预算或无法核实，就先停在这里。

## 4. 确认后生成，等待时恢复原任务

从刚查看并确认的计划中复制 `plan_sha256`，替换下面的 `REVIEWED_PLAN_HASH`：

```text
dhp make run --project outputs/my-video --plan-sha256 REVIEWED_PLAN_HASH --confirm-allowance
```

`--confirm-allowance` 代表同意**这份完整计划的所有片段**与账号计费条件，不是供应商免收费保证。计划变更后需要重新查看和确认；生成后要换台词或图片，应创建新项目。

只有一个 Bot 时自动选择；有多个时用 `dhp native bots` 查询，在运行命令加 `--agent-id BOT_ID`。同一项目不能并发运行。

等待、连接或下载中断后：

```text
dhp make resume --project outputs/my-video
```

`resume` 查询已有请求，不重发状态不明的任务；也可能继续提交同一份已批准计划中尚未开始的片段。不要删除任务目录后重新提交。

| 状态 | 怎么处理 |
| --- | --- |
| `waiting` / `awaiting_result` | 等待原任务最终文件；退出码 2 也可能仅表示尚未完成 |
| `awaiting_approval` | 查看原任务的明确审批或用户输入要求，不能绕过 |
| `needs_attention` | 检查原回复；不是重新生成的授权 |
| 连接失败 / HTTP 417 | 按 `recovery` 指引检查已有电脑、刷新连接，再恢复原项目 |

提交后的前 120 秒，仅有开场回复、Bot 暂时空闲时会继续等待；明确的审批或用户输入要求仍立即停止。HTTP 417 可能与休眠或旧网关有关，不代表已确定原因。先在 Grok Bot 唤醒已有电脑，重新运行对应系统的连接导入脚本，再执行 `doctor --online` 和 `resume`。

## 5. 本地包装与交付

生成完成后，使用实际制作意图选择配方，例如：

```text
dhp make restyle --project outputs/my-video --request "把这条做成知识分享" --title "你的标题"
```

本地重新包装只读取已完成原片，保留完整规范化时长，不提交生成请求。缺模型、台词不匹配或低置信度时会给出简单包装和复核提示。需要特定风格可加 `--style promo` 等参数；自定义 8 个组件用 `--pack-file`，不能与 `--request` 同时使用。

修改标题时显式传入最新标题；省略 `--title` 会使用原计划标题。旧版单段任务可用 `--job-dir` 代替 `--project`。

交付 `restyle` 返回的新目录中的 `final.mp4`，同时保留原片、SRT 与 QA 记录。之前 `make run` 产出的 `result/final.mp4` 是较早版本，字幕按段长估算。检查实际对白、字幕时间、口型和结尾；机器检查不等于人工验收。成片保留 AI 标识，发布时描述栏也需标识，发布本身需另外决定。

## 低层单段入口

通常使用上面的 `make` 流程即可。要单独调试一段原生视频，先用不带 `--confirm` 的命令查看计划：

```text
dhp native bots
dhp native start --image presenter.png --text "你好，这是数字人口播测试。" --agent-id BOT_ID --output-dir outputs/first-clip --duration 10 --billing allowance
```

确认形象、台词与费用后，在同一命令末尾加 `--confirm` 才上传素材并提交一次请求。默认最多等 120 秒；尚未完成时只恢复同一个目录：

```text
dhp native resume --output-dir outputs/first-clip --wait-seconds 60
```

完成后保留 `original.mp4`、`job.json` 与 `qa.json`。如果太晚首次查询、原始请求被大量新消息挤出，可能无法自动关联结果；此时在 Grok Bot 查看原任务，不要直接重发。

看过和听过后才记录人工结论：

```text
dhp native review --output-dir outputs/first-clip --decision accept --note "画面和声音已人工检查"
```

多个已完成片段可本地拼接：

```text
dhp native assemble --job-dir outputs/first-clip --job-dir outputs/second-clip --output-dir outputs/assembled
```

拼接会重新编码原生音轨；字幕时间按段长和文字估算，声音及人物跨段一致性仍需检查。音频驱动的独立适配见 [API 唇形指南](API_LIPSYNC.md)，不能通过改示例 YAML 就切换 `make` 的生成服务。

## 项目内 Skill 与开发入口

在助手中打开仓库时，Codex 入口为 `.agents/skills/avatarcast`，Claude Code 入口为 `.claude/skills/avatarcast`，均读取同一份 [Skill](../skills/avatarcast/SKILL.md)。若未发现，直接让助手读取该文件或在项目内开启新会话。Skill 只描述工作流程，Python 内核、账号与服务仍需准备。

离线演练见 [README](../README.md#使用文档)。开发者可安装 `.[test]` 后运行 `python -m pytest -q` 与 `dhp demo --out outputs/demo`；后者是测试卡与合成音调，不是真实数字人。测试与 CI 不应提交付费生成，详见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
