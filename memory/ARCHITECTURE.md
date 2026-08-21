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
          │
          └─ Agent 文本 → 表情提取/隐藏 → 短句合并 → Edge TTS → 浏览器播放/Live2D
```

## 主要层和文件

### 表现层

- `frontend/`：Open-LLM-VTuber Web 构建产物。
- `frontend/pet-status.js`：状态卡加载、喂食和刷新。
- `frontend/pet-status.css`：状态卡样式。
- `frontend/index.html`：加载项目扩展资源。
- `live2d-models/mao_pro`、`model_dict.json`：当前形象和表情映射。

### 通信与服务层

- `run_server.py`：启动入口，默认 `localhost:12393`。
- `src/open_llm_vtuber/server.py`：FastAPI 应用与静态前端。
- `src/open_llm_vtuber/websocket_handler.py`：对话连接、历史记录和消息处理。
- `src/open_llm_vtuber/pet_routes.py`：宠物状态 HTTP API。

### Agent 与模型适配层

- `src/open_llm_vtuber/agent/agents/basic_memory_agent.py`：当前对话 Agent 和 MCP 工具循环。
- `src/open_llm_vtuber/agent/stateless_llm/openai_compatible_llm.py`：StepFun OpenAI 兼容流式接口与图片兼容处理。
- `src/open_llm_vtuber/agent/transformers.py`：分句、动作提取、显示文本过滤、TTS 过滤和短句合并。
- `characters/zh_小太阳.yaml`：小太阳人格、音色和形象绑定。

### 宠物领域层

- `src/open_llm_vtuber/pet_domain/models.py`：状态和动作结果数据模型。
- `src/open_llm_vtuber/pet_domain/state_service.py`：查询、离线衰减、喂食和幂等业务规则。
- `src/open_llm_vtuber/pet_domain/repository.py`：SQLite 持久化和事件原子写入。
- `scripts/pet_mcp_server.py`：将安全领域方法暴露为 MCP 工具。

### 音频与动作输出

- `src/open_llm_vtuber/conversations/tts_manager.py`：并行 TTS 生成和有序发送。
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
4. 工具结果回到 Agent 形成自然语言、动作和语音回复。
5. 当前状态卡通过 HTTP API 获取最新状态；未来应增加 WebSocket 状态变更事件。

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
