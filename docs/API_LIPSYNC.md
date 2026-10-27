# API_LIPSYNC：一期默认路线（API 先行，本地可扩展）

## 决策

- **默认：API 唇形**，首选 WaveSpeed OmniHuman 1.5（图片 + 音频输入，音频驱动）。
- **保留：本地扩展点**，`src/dhp/lipsync_local.py` + `registry.py` 的 `"local"`，接口与 API 路线相同，换路线只改配置。
- **不做**：不在仓库里写死价格、不自动重试提交、不把本地文件偷偷上传。

## 官方接口（2026-10-27 核对官方文档）

- 提交：`POST https://api.wavespeed.ai/api/v3/bytedance/avatar-omni-human-1.5`
- 认证：`Authorization: Bearer $WAVESPEED_API_KEY`
- 请求体：`{"image": "<image_url>", "audio": "<audio_url>"}`
- 查询：`GET https://api.wavespeed.ai/api/v3/predictions/{id}/result`
- 终态：`completed` 成功；`failed` / `cancelled` / `timeout` / `deleted` 失败
- 成功输出：`result.outputs[0]` 为视频链接
- 官方文档：https://wavespeed.ai/docs/docs-api/bytedance/bytedance-avatar-omni-human-1.5
- 模型页：https://wavespeed.ai/models/bytedance/avatar-omni-human-1.5

注意：官方文档的参数表在本轮抓取中是空的，所以本适配器只传已确认的 `image` + `audio` 两个字段，其他可选参数等你在 Playground 里确认后再以透传方式加，不要凭空编参数名。

## 两条硬规则（代码里已写死）

1. **提交绝不自动重试**。提交结果不明时，先去 History / predictions 查，盲目重提可能产生第二笔计费任务。
2. **价格绝不写死**。厂商页说最终价随尺寸、时长变化，以 Generate 旁边的实时价为准。本适配器在 `rate_per_sec` 为空、或调用方没传 `confirm_live_price=True` 时，直接拒绝提交。

## 使用流程

1. 复制 `config/lipsync.example.yaml` 为 `lipsync.yaml`（不要提交真实 key）。
2. `export WAVESPEED_API_KEY=...`（环境变量，不进仓库）。
3. 把定妆图和锁定音频传到你自己可公开访问的 URL（适配器不做上传，这一步故意显式）。
4. 先跑 `dry_run()`：只校验 + 出报价单，不花钱。
5. 在模型页确认本次输入的实时价，填进 `rate_per_sec`，再以 `confirm_live_price=True` 提交。
6. 轮询只重试 429 / 5xx，终态失败直接写进 `qa.json`，不静默重提。

## 切到本地路线时要做的事

1. 选模型（MuseTalk / SadTalker / Hallo 类），先核许可证和显存。
2. 在 `lipsync_local.py` 里实现 `drive()`，注册进 `registry.py`。
3. 同一份中文测试音频、同一套五维 QA、同一份 `qa.json` 格式跑 Benchmark，英文 demo 不算证据。
4. 保持缓存键语义不变：换模型 = 换缓存键，必须重新生成。

## 扩展成其他 API 厂商

继承 `ApiLipSyncProvider`，只改 `submit_url` / 结果解析，保留“不重试提交 + 价格确认”两条规则。不要为了接新厂商把这两条规则绕过去。
