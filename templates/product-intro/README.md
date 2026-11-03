# 产品推荐模板

把已确认的产品特点讲清楚，适合单个卖点的短口播。

[返回模板选择](../../README.md#选一个模板开始) · [模板用法](../README.md) · [组件图鉴](../../docs/COMPONENT_GALLERY.md)

![产品推荐包装动图：复用测试原片](../../docs/demos/product-intro.gif)

上图仅展示模板在既有测试口播上的包装，不是按下方示例文案新生成的视频。普通话、竖屏 720p，默认先做一段约 10 秒。语音匹配失败时使用简单标题与估算字幕。

## 直接告诉助手

```text
用产品推荐模板，介绍这款轻便保温杯，强调通勤携带方便。
```

同时附上一张本人或已授权的人像。请说明产品及真实特点；本版只做口播与文字卡，不展示商品实物或自动制作商品画中画。首次使用需准备自己的 Grok Bot 账号与额度，生成前确认完整方案与费用。

## 模板替你安排什么

- **谁会需要**：用一个具体使用情境开场，不虚构痛点。
- **一个卖点**：只讲用户提供的特点；没有商品图时不声称展示了实物。
- **适用建议**：说明适合谁或怎样选择；不编造优惠、销量或效果。

这些是助手的写稿槽位，不是必须由用户填写的表单。缺少必要事实时助手会补问；不会为了填模板编造事实。

## 可运行的示例

让助手根据你的内容改写 [example.json](example.json)，然后：

```text
dhp make plan --image presenter.png --brief-file templates/product-intro/example.json --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

这两步只在本机准备计划。核实全部台词、片段与计费条件后，才按[命令行指南](../../docs/CLI_GUIDE.md#4-确认后生成等待时恢复原任务)确认生成。`run` / `resume` 会按已选模板进行本地包装；没有 Vosk 模型或匹配不可靠时会提示降级。

已有完成的项目也可以直接换模板：

```text
dhp make restyle --project outputs/my-video --template product-intro --title "你的标题"
```

换模板只调整已有画面上的呈现，不改对白或表演；若要讲新的内容，需要另行生成并确认费用。源文件保留，结果另存。


模板定义见[可安装的配置](../../src/dhp/template_data/product-intro.json)；CLI 查看：`dhp make templates product-intro`。
