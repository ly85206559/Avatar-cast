# ARCHITECTURE：模块边界与数据流

## 原则

- 上层只依赖接口，不依赖具体模型。换模型 = 换 adapter + 改配置。
- 音频驱动路线：brief → script → 锁定 audio → video → timeline → edit → render。
- 原生视音频路线：brief + script + 形象 → 同时生成 video 和 audio → 检查、时间轴与剪辑；不声称音轨可事先锁定。
- 失败优先恢复已有环节；生成请求结果不明时先查询，不盲目重发。

## 数据流

```
音频驱动路线：
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

原生路线输入为形象、台词和生成参数；输出包含原片及其原生音轨，再进入检查和剪辑。当前仅实施单段入口；多段串联和跨段声音一致性需要实测。

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

每个 adapter 应记录已知的模型名、版本、参数、耗时与费用来源；未知值显式标记未知，不能填零或猜测。

## 失败处理

1. 提交结果不明确时，保存请求记录并查询已有任务；查询、下载与生成分开。
2. 失败已确认后，根据人工批准的费用条件选择是否重拍。
3. 重拍计划可考虑同模型调整提示词、同类模型替换或降低规格。
4. 无法恢复或未批准新消费时停止，保留记录并交人工介入。

规划策略默认最多重拍 3 次；它不授权执行付费重拍。原因和批准条件必须进日志，不许静默重试。
