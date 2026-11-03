# 情感共鸣模板

说中一种具体处境，温和回应，并给一个小行动。

[返回模板选择](../../README.md#选一个模板开始) · [模板用法](../README.md) · [组件图鉴](../../docs/COMPONENT_GALLERY.md)

![情感共鸣包装动图：复用测试原片](../../docs/demos/empathy.gif)

上图仅展示模板在既有测试口播上的包装，不是按下方示例文案新生成的视频。普通话、竖屏 720p，默认先做一段约 10 秒。语音匹配失败时使用简单标题与估算字幕。

## 直接告诉助手

```text
用情感共鸣模板，鼓励一下觉得自己进步太慢的人。
```

同时附上一张本人或已授权的人像。首次使用需准备自己的 Grok Bot 账号与额度，生成前确认完整方案与费用。

## 模板替你安排什么

- **说中处境**：描述用户指定的感受，不假装知道观众的个人经历。
- **温和回应**：用克制的安慰或新视角，不承诺治疗或保证效果。
- **一个小行动**：给一个容易做到的建议，留一句温和收束。

这些是助手的写稿槽位，不是必须由用户填写的表单。缺少必要事实时助手会补问；不会为了填模板编造事实。

## 可运行的示例

让助手根据你的内容改写 [example.json](example.json)，然后：

```text
dhp make plan --image presenter.png --brief-file templates/empathy/example.json --output-dir outputs/my-video
dhp make show --project outputs/my-video
```

这两步只在本机准备计划。核实全部台词、片段与计费条件后，才按[命令行指南](../../docs/CLI_GUIDE.md#4-确认后生成等待时恢复原任务)确认生成。`run` / `resume` 会按已选模板进行本地包装；没有 Vosk 模型或匹配不可靠时会提示降级。

已有完成的项目也可以直接换模板：

```text
dhp make restyle --project outputs/my-video --template empathy --title "你的标题"
```

换模板只调整已有画面上的呈现，不改对白或表演；若要讲新的内容，需要另行生成并确认费用。源文件保留，结果另存。


模板定义见[可安装的配置](../../src/dhp/template_data/empathy.json)；CLI 查看：`dhp make templates empathy`。
