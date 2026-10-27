# CONTRACTS：JSON 契约详解

契约是本项目的“法律”。环节之间只传 JSON，不传口头约定、不传临时字段。

## brief.json：一次问完，写死再开工

```json
{
  "topic": "主题",
  "style": "口播 / 解说 / 教程",
  "ratio": "16:9",
  "duration_target_sec": 60,
  "persona_id": "presenter-v1",
  "caption_style": "花字强度：低 / 中 / 高"
}
```

## persona.json：主播的唯一正典

- `face_image_hash`：定妆照哈希，换图必须换版本
- `voice_id`：音色 ID，不写“像谁”
- `outfit`、`background`：衣服与背景描述
- `version`：persona 改了任何一项，版本必须 +1

## script.json：每段一句，情绪结构化

```json
{
  "id": "s1",
  "shot": "talking_head",
  "text": "这是一句台词。",
  "emotion": {"label": "calm", "intensity": 0.6},
  "rate": 1.0,
  "pause_after_ms": 300
}
```

- `shot` 只能取路由表里的值：`talking_head` / `b_roll` / `demo` / `scene`
- 情绪、语速、停顿是字段，不是提示词里的形容词
- 中文语速估算先按约 5 字/秒做预算，实测后以音频实际时长为准

## tl.json：逐字绝对时间

每个字一条记录：`{segment_id, text, start, end}`。包装组件的 `at` 字段必须指向这里，不许写死秒数。

## qa.json：没有它，成片视为未质检

```json
{
  "segment_id": "s1",
  "wer_accuracy": 0.92,
  "lipsync_score": 0.81,
  "face_cosine": 0.94,
  "burned_subtitle": false,
  "voice_drift": 0.12,
  "retries": 1,
  "retry_reasons": ["lipsync_score below threshold"],
  "cost": 0.0,
  "cache_hit": false,
  "verdict": "pass"
}
```

阈值见 README §5，先定默认值，跑 Benchmark 后再调，不要凭感觉改阈值。
