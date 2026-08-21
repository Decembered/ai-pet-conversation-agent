# 当前架构

## 总览

```text
浏览器 UI / 麦克风 / 摄像头
          │ WebSocket + HTTP
          ▼
FastAPI / websocket_handler / pet_routes
          │
          ▼
BasicMemoryAgent ── StepFun step-1o-turbo-vision
          │                    │
          │ MCP 工具            └─ 文本 + 授权图片理解
          ▼
pet_mcp_server ── PetStateService ── PetStateRepository ── SQLite data/pet.db
          │                 │                                │
          │                 └─ ReactionPlan                  └─ pet_events
          │                                                       │
          ├─ Agent 文本 → 表情提取/隐藏 → 短句合并 → Edge TTS     │
          │                                                       ▼
          └────────────────────────────────────────── /api/pet/events WebSocket
                                                                  │
                                                                  ▼
                          状态卡 + 头顶气泡 + 粒子/高亮 + Live2D 动作桥 + 受控音效
```

## 主要层和文件

### 表现层

- `frontend/`：Open-LLM-VTuber Web 构建产物。
- `frontend/pet-status.js`：状态卡、事件 WebSocket、事件去重、动作反应编排、Live2D 动作桥（`window.getLAppAdapter()`）、受控音效、头顶气泡（动作 + 说话）、右侧抽屉骨架和摄像头画中画。
- `frontend/pet-status.css`：状态卡、头顶气泡、粒子、降级高亮、侧边栏抽屉和摄像头画中画样式（全部限定在自有类名内）。
- `frontend/index.html`：加载项目扩展资源。
- `live2d-models/mao_pro`、`model_dict.json`：当前形象和表情映射。

### 通信与服务层

- `run_server.py`：启动入口，默认 `localhost:12393`。
- `src/open_llm_vtuber/server.py`：FastAPI 应用与静态前端。
- `src/open_llm_vtuber/websocket_handler.py`：对话连接、历史记录和消息处理。
- `src/open_llm_vtuber/pet_routes.py`：宠物状态 HTTP API 和独立事件 WebSocket，读取 MCP/HTTP 共同写入的 SQLite 事件，并附加 Live2D 渲染方案。
- `src/open_llm_vtuber/pet_live2d.py`：只依赖标准库的 Live2D 资源盘点与反应解析，把 `ReactionPlan` 映射到模型真实存在的动作/表情，缺失时给出显式降级原因。
- `src/open_llm_vtuber/pet_speech.py`：进程内说话广播（有界队列、丢最旧、发布不抛异常），把对话管线已过滤的 `display_text` 投影到头顶气泡，并维护一个短期「最近对话」显示缓冲。

### Agent 与模型适配层

- `src/open_llm_vtuber/agent/agents/basic_memory_agent.py`：当前对话 Agent 和 MCP 工具循环。
- `src/open_llm_vtuber/agent/stateless_llm/openai_compatible_llm.py`：StepFun OpenAI 兼容流式接口与图片兼容处理。
- `src/open_llm_vtuber/agent/transformers.py`：分句、动作提取、显示文本过滤、TTS 过滤和短句合并。
- `characters/zh_小太阳.yaml`：小太阳人格、音色和形象绑定。

### 宠物领域层

- `src/open_llm_vtuber/pet_domain/models.py`：状态、动作结果和确定性的 `ReactionPlan` 表现提示。
- `src/open_llm_vtuber/pet_domain/state_service.py`：查询、离线衰减（含睡眠恢复）、喂食/玩耍/清洁/睡觉四种动作及其幂等规则；所有数值集中在此。
- `src/open_llm_vtuber/pet_domain/repository.py`：SQLite 持久化、事件原子写入和 `pet_world_events` 世界事件表。
- `src/open_llm_vtuber/pet_domain/world.py`：`WorldClock`、`RoutineScheduler`、`BehaviorPlanner`、`WorldEvent` 与 `WorldService`——宠物的时段、日程、行为优先级、重启恢复、离线摘要和背景选择。
- `scripts/pet_mcp_server.py`：将安全领域方法暴露为 MCP 工具（`get_pet_state`、`feed_pet`、`play_with_pet`、`clean_pet`、`put_pet_to_sleep`）。

### 音频与动作输出

- `src/open_llm_vtuber/conversations/tts_manager.py`：并行 TTS 生成和有序发送；在把载荷发给浏览器的同一时刻广播 `pet_speech`。
- `src/open_llm_vtuber/utils/stream_audio.py`：音频解码为 WAV、Base64 编码和口型音量切片。
- `src/open_llm_vtuber/live2d_model.py`：表情标签到 Live2D 动作映射，并清理可见标签。

## 核心数据流

### 语音和摄像头对话

1. 浏览器收集用户语音；ASR 转写为文本。
2. 摄像头开启且本轮附带画面时，文本和图片一起构造成 `BatchInput`。
3. BasicMemoryAgent 将消息流式发送给 StepFun 视觉模型。
4. 模型回复中的 `[joy]`、`[neutral]` 等标签被提取为 Live2D 动作。
5. 标签从显示文本和 TTS 文本中删除。
6. 相邻短句合并后提交给 Edge TTS；音频按原顺序发送浏览器播放。

### 宠物状态工具调用

1. Persona Prompt 要求涉及真实状态或喂食时调用 MCP 工具。
2. Agent 通过 `pet-state` MCP Server 调用 `get_pet_state` 或 `feed_pet`。
3. PetStateService 执行业务规则；Repository 在 `data/pet.db` 持久化。
4. 状态与 `PetFed` 事件原子提交；事件载荷包含状态差量和 `ReactionPlan`。
5. 工具结果回到 Agent 形成自然语言、动作和语音回复。
6. 独立 `/api/pet/events` WebSocket 通过 SQLite 事件序列发现 HTTP 或 MCP 进程提交的事件，发送 `pet_state_changed` 与 `pet_reaction` v1。
7. `pet_routes` 用 `Live2dReactionResolver` 把 `ReactionPlan` 解析为 `render`（真实动作或降级表情），附加在 HTTP 响应与 `pet_reaction` 消息上（schema v1 可选字段）。
8. 页面以 `event_id` 去重；先按 `render` 调用 `startMotion` 或 `setExpression`，再播放气泡、粒子、状态卡、画布高亮和受控音效；重连时通过 HTTP 获取完整快照，不重放旧反应。

### 说话投影

1. Agent 文本经 transformers 过滤后形成 `SentenceOutput`，`TTSTaskManager` 生成音频并按序发送。
2. 发送的同一时刻广播 `pet_speech`：文本与字幕/历史完全一致，控制标签再清洗一次。
3. `/api/pet/events` 把 `pet_speech` 与状态/反应事件混在同一条有序通道里发给页面。
4. 页面用同一个气泡渲染：动作反应优先，说话不覆盖进行中的反应；长文本可展开。
5. 侧边栏「最近对话」来自 `GET /api/pet/speech/recent` 与实时 `pet_speech`，
   明确标注为短期显示缓冲；「共同记忆」保持空状态，等待真正的 `MemoryRecord`。

### 生活节奏与背景

1. `WorldClock` 把本地时间映射为清晨/白天/傍晚/夜里四个时段。
2. `RoutineScheduler` 给出确定性日程槽，只使用休息/学习/玩耍三种可恢复行为。
3. `BehaviorPlanner` 按「用户即时互动 > 状态告警 > 日程 > 待机」选择当前行为，
   决策来自真实状态与时间，不由 LLM 自由发挥。
4. `WorldService` 持久化 `WorldEvent`；重启时若事件仍有效且行为/原因未变则恢复，
   离线超过 30 分钟只产出一句摘要，不补播。
5. `background_for()` 只返回磁盘上真实存在的背景文件，缺失时给出自绘渐变与时段色调。
6. 前端按 `img[src*="/bg/"]` 找到应用背景容器，挂一个自有的交叉淡入层，
   不接管应用自己的背景元素。

### 摄像头预览与隐私

- 识别条件：活跃摄像头轨道、无 `displaySurface`、不在 `#live2d` 内、不覆盖整个舞台。
- 画中画镜像同一个 `MediaStream` 到自建 video，不接管应用原生预览元素。
- 该模块不做 canvas 绘制、不读像素、不上传、不落盘；原始帧不进入日志、数据库和 memory。
- 摄像头开启期间指示灯与停止入口常驻，「隐藏预览」只隐藏画面本身。

### Live2D 表现解析

- 资源真值：`live2d-models/<model>/runtime/<model>.model3.json` 的 `Motions` 与 `Expressions`，加上 `model_dict.json` 的 `emotionMap`。
- 服务端解析，不在前端猜测：动作按语义关键词匹配组名与动作文件名；找不到时回落到 `fallback_expression` 对应的真实表情。
- 当前 `mao_pro` 在原有 `Idle` 和 6 个通用动作之外，注册 `Eat`、`Play`、`Clean`、
  `Sleep`、`SleepIdle`、`Wake` 六个动作组；四类交互的 `missing_motion_assets` 为空。
- 睡眠是持久活动：反应事件启动 `Sleep`，页面观察状态后接续循环 `SleepIdle`，
  服务端离线恢复将活动改回 `resting` 时页面播放 `Wake`。
- 浏览器侧动作桥使用前端 bundle 已暴露的 `window.getLAppAdapter()`（`startMotion` / `setExpression` / `getExpressionName`），不修改压缩产物，也不伪造静音 TTS。

## 状态真值与配置真值

- 宠物状态真值：后端 SQLite，而不是前端显示值或模型口述。
- 人格真值：角色配置中的 System Prompt/PersonaPack。
- 本地运行配置：`conf.yaml`，包含敏感配置且不提交。
- 可共享配置：`config_templates/`，必须保持无密钥。
- MCP 本地启用配置：`mcp_servers.json`，不提交；共享示例为 `mcp_servers.example.json`。

## 下一阶段架构约束

- 先冻结领域对象和事件协议，再并行实现世界、记忆、成长和作品。
- 主动感知必须产生结构化 `PerceptionEvent`，不能让摄像头逻辑直接驱动自由文本。
- 绘画、写信等生成能力必须经过安全工具层，并写入受控作品目录和索引。
- 长期记忆应与聊天历史分开，记录来源、置信度、隐私级别和召回时间。
