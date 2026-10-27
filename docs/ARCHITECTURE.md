# ARCHITECTURE：模块边界与数据流

## 原则

- 上层只依赖接口，不依赖具体模型。换模型 = 换 adapter + 改配置。
- 数据只向下游流动：brief → script → audio → video → timeline → edit → render。
- 任何环节失败，都只重跑该环节，不许整片重跑。

## 数据流

```
brief.json + persona.json
  → script.json（分段稿子，含情绪/语速/停顿）
  → audio/（每段锁定音频 + 哈希）
  → tasks.json（生成任务，含报价单与缓存键）
  → clips/（每段画面，含模型与参数版本）
  → tl.json（逐字绝对时间轴）
  → qa.json（五维分数 + 重拍记录）
  → edit.json（包装决策，可人工改）
  → final.mp4 + final.srt + cover.jpg + qa.json
```

## 接口清单（先定接口，再写实现）

| 接口 | 职责 | 关键方法 |
|---|---|---|
| `VideoProvider` | 按镜头类型生成画面 | `estimate(task) -> Quote`、`generate(task) -> Clip` |
| `TTSProvider` | 生成锁定音频 | `synthesize(segment) -> Audio` |
| `LipSyncProvider` | 音频驱动唇形 | `drive(image, audio) -> Clip` |
| `MattingProvider` | 跨平台抠像 | `matte(frame) -> Alpha` |
| `ASRProvider` | 回听转写 | `transcribe(audio) -> Words` |
| `QAScorer` | 五维评分 | `score(clip, script, audio) -> QAResult` |
| `Renderer` | 按 tl + edit 渲染 | `render(timeline, edit) -> Video` |

每个 adapter 必须在返回结果里写清：模型名、模型版本、关键参数、耗时、成本。缺这五项，视为未完成实现。

## 失败处理

1. 同模型换提示词重拍
2. 换同类模型重拍
3. 降分辨率 / 降时长重拍
4. 停下来，写进 qa.json，人工介入

默认最多重拍 3 次。重拍原因必须进日志，不许静默重试。
