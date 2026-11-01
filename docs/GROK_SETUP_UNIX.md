# 在 macOS 或 Linux 上连接 Grok Bot

这条路线使用你自己的 Grok Bot 账号和已唤醒的云电脑。连接脚本只读取运行状态和网关信息，不生成视频，也不会替你修改按需计费或充值设置。首次生成之前仍需检查实际账号的额度、超额和自动充值设置，确认费用后再提交。Grok Bot 的网关属于非公开接口，可能随版本变化。

此处的 Unix 导入器已在 Linux 子系统上用模拟网关测试；macOS 及其他账号的真实登录和网关连接尚未实测。Windows 用户使用仓库中的 `scripts/setup_grok_bot_windows.ps1`。

## 1. 准备环境

安装并登录 [Grok Bot 桌面应用](https://docs.x.ai/grok-bot/overview)，在 Bot 的“电脑”面板唤醒电脑。还需要 Python 3.10+、Git、Node.js 18+ 和支持 `subtitles`、`libx264` 的 FFmpeg。

macOS 用户如果已经安装 Homebrew，可以运行：

```bash
brew install python node ffmpeg-full
```

`ffmpeg-full` 是 keg-only 版本，需在当前终端将其放在 PATH 前面；普通 `ffmpeg` 包不一定带字幕滤镜。根据 [Homebrew 的 ffmpeg-full 说明](https://formulae.brew.sh/formula/ffmpeg-full)，它包含 libass 和 x264。系统一般自带中文字体。

Ubuntu / Debian 用户可以运行：

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip nodejs ffmpeg fontconfig fonts-noto-cjk
```

如果 `node --version` 小于 18，请按 [Node.js 官方说明](https://nodejs.org/en/download)安装受支持的版本。其他 Linux 发行版使用对应包管理器安装这些工具及中文字体。

## 2. 安装项目

```bash
git clone https://github.com/ly85206559/Avatar-cast.git
cd Avatar-cast
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[native]'
# 仅 macOS + Homebrew ffmpeg-full 需要：
export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"
dhp make doctor
```

Linux 用户跳过 `brew` 和 `export` 行。如果 `subtitles`、`libx264` 或中文字体不符合要求，先修复并重新运行 `doctor`。`unknown` 字体状态需要手动检查。

## 3. 登录并导入网关

Unix 导入器不读取桌面应用的钥匙串或密码。它通过第三方开源 [grok-bot CLI](https://github.com/Kargatharaakash/grok-bot-mcp) 已登录的本地配置获取访问令牌。该工具与 Grok Bot 官方无关，版本变化可能影响兼容性；浏览器登录会让它保存该账号的访问和刷新凭据。请先确认你愿意使用该工具，使用与桌面应用**同一个账号**，不要把令牌贴到聊天或提交到仓库。

如尚未安装 CLI，可先单独克隆并检查其源码，然后执行：

```bash
git clone https://github.com/Kargatharaakash/grok-bot-mcp.git "$HOME/grok-bot-mcp"
node "$HOME/grok-bot-mcp/server.mjs" login
```

在浏览器完成登录。若目标目录已存在，请检查原目录而不是覆盖。若 CLI 中保存了多个账号，确认当前活跃账号与桌面应用相同；该 CLI 在 macOS 切换账号时可能同步更改桌面账号，请先阅读其说明。CLI 将凭据保存在 `~/.gbm/accounts.json` 与 `~/.gbm/config.json`；它们包含敏感信息，应仅允许当前用户读取。

回到 AvatarCast 项目目录、确保虚拟环境已激活并且电脑已唤醒，然后运行：

```bash
python scripts/setup_grok_bot_unix.py
dhp make doctor --online
```

导入器默认只读轮询就绪状态 30 秒，适合刚在桌面点了唤醒的电脑；可用 `--wait-seconds 0` 立即检查，或设置 0–120 秒的等待窗口。等待超时不修改原配置，也不调用唤醒或创建电脑。Windows 导入器对应参数为 `-WaitSeconds`。网络请求自身仍受超时限制。

脚本从 `~/.gbm/config.json` 读取 CLI 的 `accessToken`，只接受当前用户拥有且权限为 `600` 的普通文件；它会保留其他配置，在同一个文件中写入网关信息。文件含敏感令牌，不要打印或分享。若提示权限不安全，确认文件归属后可由用户执行 `chmod 600 ~/.gbm/config.json`。若配置在脚本运行中被其他程序修改，脚本会停止，避免覆盖。

如果电脑休眠、登录过期或网关变化，先在桌面应用唤醒电脑，必要时重新登录 CLI，再运行导入脚本和在线检查。`doctor --online` 查询连接状态，不验证账单，也不生成视频。

## 4. 制作视频

回到 [README 的引导流程](../README.md#让-codex-或-claude-code-帮你安装并做视频)：先准备授权图片和 UTF-8 文案，通过 `dhp make plan` / `show` 核对全部分段；确认实际费用后才运行 `dhp make run`。如任务中断，使用 `dhp make resume` 查询已有任务，勿删除回执或重复提交。
