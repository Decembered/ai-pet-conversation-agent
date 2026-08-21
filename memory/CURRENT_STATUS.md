# 当前状态

更新时间：2026-08-22（Asia/Shanghai）  
最后验证的代码提交：`9ae4276 perf: smooth short TTS response segments`  
分支：`main`  
产品基线标签：`v0.1.0`（位于较早提交 `1e8eae8`，后续修复尚未重新打标签）

## 仓库与运行状态

- 实际 Git 仓库：
  `D:\mineD\Projecttt\0821pet\Open-LLM-VTuber-main\Open-LLM-VTuber-main`
- 远端：`https://github.com/Decembered/ai-pet-conversation-agent.git`。
- 当前 `main` 没有配置远端跟踪分支；此前推送尝试因当前 GitHub 凭据没有仓库写权限而返回 403，尚未重新验证。
- 整理此 memory 前工作树干净。
- 2026-08-22 整理时，本地服务正在 `http://localhost:12393` 运行；进程状态是临时信息，新会话必须重新检查端口。

## 已完成且已验证

### 工程基线

- 基于 Open-LLM-VTuber 1.2.1。
- 后端和 `frontend/` 已纳入同一 Git 仓库，不再依赖缺失的前端子模块。
- 已配置团队 GitHub `origin`，本地已有清晰提交历史。
- `conf.yaml`、`mcp_servers.json`、`data/`、日志、缓存和模型文件已忽略。

### 小太阳人格与表现

- 人格文件：`characters/zh_小太阳.yaml`。
- 角色名：小光；Live2D：`mao_pro`；音色：`zh-CN-XiaoxiaoNeural`。
- Persona System Prompt 包含人格、安全、真实状态工具和视觉感知边界。
- `[joy]`、`[neutral]` 等表情标签仍驱动 Live2D，但不会显示在聊天气泡/字幕中，也不会被 TTS 朗读。
- 历史消息重新加载时也会隐藏旧的表情标签。

### LLM、语音和视觉

- LLM 使用 StepFun OpenAI 兼容接口，当前模型为 `step-1o-turbo-vision`，视觉输入已启用。
- 用户已实际确认麦克风语音输入和摄像头图像输入可工作。
- ASR 使用 Sherpa-ONNX SenseVoice，当前为 CPU 推理。
- TTS 使用 Edge TTS。
- 已增加短句合并：少于约 12 个有效字符的相邻句子会合并，减少多个小音频文件造成的播放间隙。

### 宠物状态纵向切片

- `PetState`、成长基础字段、归一化规则和离线时间衰减已实现。
- SQLite 数据库：`data/pet.db`（本地运行数据，不提交）。
- `get_pet_state` 和 `feed_pet` 已通过 MCP 服务暴露。
- `feed_pet` 支持 `request_id` 幂等，并原子保存状态和事件。
- HTTP API：`GET /api/pet/state`、`POST /api/pet/feed`。
- 页面右侧已有状态卡：饥饿、精力、心情、健康、清洁、亲密、等级、经验和成长值。
- 前端当前通过 HTTP 获取/刷新状态；完整 WebSocket `pet_state_changed` 契约尚未冻结。

## 测试状态

最近一次完整测试结果：14 项全部通过。

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

覆盖范围：

- 宠物状态创建、时间变化、幂等喂食、持久化和边界裁剪。
- 宠物 HTTP 路由。
- StepFun 文本/视觉兼容转换。
- 音频 WAV 载荷和音量切片。
- Live2D 表情标签隐藏与动作保留。
- 短 TTS 片段平滑合并。

## 最近关键提交

- `9ae4276`：合并过短 TTS 句子，降低语音片段卡顿。
- `b5b6a0d`：隐藏对话中的 Live2D 表情标签，同时保留动作。
- `ef4e3db`：启用视觉宠物交互并增强无 FFmpeg 音频转换。
- `48d1398`：状态 UI、StepFun 文本模型兼容和配置支持。
- `1e8eae8`：SLAI Pet `v0.1.0` 基础状态纵向切片。

## 已知问题与限制

1. GitHub 推送权限尚未解决，本地提交可能尚未上传远端。
2. `v0.1.0` 标签早于最近三次视觉/表情/TTS 修复，发布版本需要重新评估。
3. 直接运行 `.venv\Scripts\python.exe run_server.py` 曾出现 SenseVoice ONNX
   `No graph was found in the protobuf`；使用 `uv run python run_server.py` 可以正常启动。
4. StepFun 视觉轮次比纯文本/语音轮次更慢。实测日志中普通轮次约 9–13 秒，带一张摄像头图片约 16 秒；需继续做分段性能观测。
5. 前端状态主要通过 HTTP 轮询/刷新同步，需求中的 WebSocket 状态事件尚未正式实现和冻结。
6. 尚缺“用户自然语言喂食 → LLM 工具调用 → SQLite → 页面更新 → 动作/TTS”自动端到端测试。
7. 目前只有小太阳一套正式 PersonaPack；长期记忆、完整成长、绘画/写信、主动感知调度仍未实现。
8. 日志中曾观察到一次 `/undefined/undefined.model3.json` 404，需要确认是否只是初始化瞬态请求。
9. 如果 StepFun Key 在历史终端或截图中暴露过，应在控制台轮换；项目文件不得记录具体 Key。

## 下一步建议

按顺序执行：

1. 修复 GitHub 凭据/协作者写权限并推送当前本地历史。
2. 添加自然语言喂食端到端验收，确认 P0 闭环真实完成。
3. 冻结 `PetState` 与 `pet_state_changed` WebSocket schema v1，并让 UI 事件驱动更新。
4. 为视觉、LLM 首字、TTS 生成和前端播放分别增加耗时指标，再继续优化延迟。
5. 完成 `0.1.x` 发布验收后，再进入四人格原子切换或长期记忆。

具体任务和验收条件见 `NEXT_TASKS.md`。
