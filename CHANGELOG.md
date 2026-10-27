# CHANGELOG

## v0.3.0 — 2026-10-28：真实评分器接入（标签不混）

- **ASR 真接入**：Vosk 离线中文小模型，s1 实测字符准确率 0.9455（16 词错 1 个），带逐字时间，可直接进时间轴。模型不进仓库。
- **TTS 缝**：`CommandTTSProvider`，默认沙箱 tts 命令中文实测出音，仅本地验证；产品 TTS 按 `config/tts.example.yaml` 换命令。
- **唇音启发式（不是 SyncNet）**：嘴部亮度水平 vs 音频 RMS 相关，合成素材同步 0.9985 / 未同步 -0.2785。真 SyncNet 需 torch + 权重 + 算力，本机不装、不冒充。
- **画面一致性代理（不是人脸 embedding）**：aHash 帧相似度。真 embedding 只走 `FaceEmbeddingProvider`（人脸裁图 + 调用方 ONNX 模型 + onnxruntime），缺一样就报错。
- **本地唇形**：`check_environment()` 实测本机不可行（无 GPU、无 torch、内存紧张），`drive()` 仍显式拒绝，绝不用通用视频冒充唇形。
- **API 真跑**：`scripts/api_lipsync_run.py`，缺 key / 公开 URL / 实时价 / `--confirm` 任一样都不花钱；本次未花钱，仍缺用户提供的三样。
- **直播**：只做了 `live.py` 状态机与延迟预算（接口），无 RTMP、无流式模型，三期仍未实现。
- 测试：23 通过、1 跳过（系统 Python 无 vosk，Vosk 转写已在独立 venv 中手工实测通过，见上）。

## v0.2.0 — 2026-10-28：去旧影子 + 全面升级

这次升级的目标只有一个：AvatarCast 从第一行起就是它自己，不带之前仓库的影子。

### 删掉的旧影子

- 删掉上一版仓库名的残留称呼（内部唇形标准不再用旧名）。
- 删掉从别处带过来的包装组件名和示例，换成 AvatarCast 自带的 `PriceTag` / `FactCard` / `MapRoute` / `QuoteCard`。
- 删掉对照旧工具的写法，改写成 AvatarCast 自己要解决的六个问题。
- 修正旧包名残留，README 里的模块表改成与 `src/dhp/` 实际文件一致，不再列不存在的目录。

### 新增的实装（不再只是骨架）

- `src/dhp/pipeline.py`：报价门（段数、总时长、预估总价、缓存省多少钱、超预算标记、首段门禁）+ 固定重拍顺序（同模型换提示词 → 换同类模型 → 降规格 → 人工介入，最多 3 次）。
- `src/dhp/components.py`：声明式组件与校验，缺数据直接丢弃并上报，绝不编数据渲染。
- `src/dhp/render.py`：ffmpeg 组装（说完 +0.25 秒截段、30fps / 48k / -16 LUFS 归一、SRT 生成、拼接）。
- `scripts/benchmark.py`：四数 Benchmark（重拍率、唇音/人脸均分、每分钟成本、首次通过率），单数变好不算优化。
- `docker/docker-compose.yml`：一键起本地服务。
- 测试：pipeline / components / benchmark / render 新增 8 个测试（含 ffmpeg 本地合成素材组装）。

### 仍未实装（诚实清单，不许对外说成已验证）

- 真实 TTS、真实 ASR 转写、SyncNet 唇音分、人脸 embedding：阈值和接口在，模型未接入。
- 本地唇形模型：仍是显式扩展点，未实现。
- API 唇形：只做到 dry_run + 价格确认提交，尚未花钱真跑过一次。
- 直播链路：三期目标，v0.2 不含。

## v0.1.0 — 2026-10-27：首版骨架

- JSON 契约（brief / script / qa）、缓存键、QA 阈值、API 唇形适配器（不自动重试、不猜价格）、8 个测试。
- 推送到 GitHub：`ly85206559/avatarcast`，main 分支。
