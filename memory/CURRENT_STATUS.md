# 当前状态

更新时间：2026-08-22（Asia/Shanghai）  
最后验证的代码状态：当前未提交工作树（基于 `4440d56 docs: add durable project memory`），
其中包含宠物事件协议实现与 Live2D 原生互动渲染（交接文档 Phase A）
分支：`main`  
产品基线标签：`v0.1.0`（位于较早提交 `1e8eae8`，后续修复尚未重新打标签）

## 仓库与运行状态

- 实际 Git 仓库：
  `D:\mineD\Projecttt\0821pet\Open-LLM-VTuber-main\Open-LLM-VTuber-main`
- 远端：`https://github.com/Decembered/ai-pet-conversation-agent.git`。
- 当前 `main` 没有配置远端跟踪分支；此前推送尝试因当前 GitHub 凭据没有仓库写权限而返回 403，尚未重新验证。
- 当前工作树包含待提交的交互补充说明、宠物事件协议和喂食反应实现。
- 本轮没有启动服务；最近一次只读端口检查未发现 `localhost:12393` 监听，运行状态仍需在启动验收时重查。

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
- 宠物事件 WebSocket：`/api/pet/events`；schema v1 包含
  `pet_state_changed`、`pet_reaction` 和重连基线 `pet_events_ready`。
- `ReactionPlan` 由领域服务根据已提交动作确定，包含动作提示、降级表情、气泡、粒子、音效标识和持续时间。
- 页面右侧已有状态卡：饥饿、精力、心情、健康、清洁、亲密、等级、经验和成长值。
- 页面重连时通过 HTTP 获取完整快照，运行中通过 WebSocket 接收 HTTP 或独立 MCP 进程写入的 SQLite 事件。
- 喂食成功会立即更新状态条，并显示头顶气泡、小鱼粒子、状态卡反馈和 Live2D 画布高亮；按 `event_id` 去重。

### 最小生活节奏与动态背景（交接文档 Phase E）

- `pet_domain/world.py` 新增四个部件：
  `WorldClock`（清晨/白天/傍晚/夜里四个时段）、`RoutineScheduler`（确定性日程，
  只用休息/学习/玩耍三种可恢复行为、全天无空档）、`BehaviorPlanner`
  （优先级链：用户即时互动 > 状态告警 > 日程 > 待机）、`WorldEvent` + `WorldService`。
- 新表 `pet_world_events`（`CREATE TABLE IF NOT EXISTS` 前向迁移，不动既有数据）。
  重启后如果事件仍在有效期且行为/原因未变，恢复同一个 `event_id` 与开始时间，
  不会把宠物的下午重新开始一遍。
- 离线超过 30 分钟只生成一句摘要（「你不在的大约 N 小时里，小光按日程学习、玩耍了一阵子」），
  不补播任何动画或事件队列。
- 背景随时段与行为变化：`background_for()` 只提供磁盘上真实存在的
  `backgrounds/*.jpeg`，缺失时降级为自绘渐变（`backgrounds/` 是 git-ignored，
  新克隆可能为空，所以可用性每次都检查）。
- 前端把背景层作为兄弟节点挂进应用自己的背景容器（按 `img[src*="/bg/"]` 定位，
  不接管它的 `<img>`），双层 1.4 秒交叉淡入，另加一层按时段变化的柔光色调。
- 状态卡新增生活条：时段 + 当前行为 + 原因说明 + 「约 N 分钟后换下一件事」，
  行为标签按原因变色（日程/互动/告警）。
- 刷新时机：启动、每 60 秒、每次照料动作之后、以及收到任何已提交状态变更事件时。
- HTTP：`GET /api/pet/world`。

### 摄像头画中画与隐私状态（交接文档 Phase D）

- 精确识别：只认「`srcObject` 是活跃摄像头轨道、无 `displaySurface`（排除屏幕共享）、
  不在 `#live2d` 内、且不覆盖整个舞台」的 video；不给页面上任意 `video`/`canvas` 加通用样式。
- 画中画是**我们自己创建的容器**，把同一个 `MediaStream` 镜像到自己的 `<video>`，
  不搬动也不改写应用自己的预览元素，避免和 React 渲染冲突。
- 支持圆角、轻阴影、径向渐隐遮罩、拖动（指针捕获 + 视口夹取）、缩放 0.6–2.0，
  以及 16:9 / 圆形 / 隐藏预览三种模式；位置、缩放和形状写入 localStorage。
- 「隐藏预览」只隐藏画面：红色呼吸指示灯、「正在提供画面」文案和停止入口始终可见。
- 停止入口为两步确认（无模态框），确认后直接 `track.stop()` 立即切断画面。
- 隐私边界：该模块只把流镜像到 video 元素，不做 canvas 绘制、不读像素、不上传、不落盘。
  后端侧 `openai_compatible_llm._message_summary` 已经是「不含提示词、图片和用户内容」的
  日志摘要，`pet_speech` 广播新增回归测试断言载荷中的图片字段不会进入消息或最近对话缓冲。

### 统一头顶气泡与侧边栏骨架（交接文档 Phase C）

- 普通助手回复也会投影到头顶气泡：`TTSTaskManager._process_payload_queue` 在把
  音频/字幕载荷发给浏览器的同一时刻，调用 `pet_speech_broadcaster` 广播同一份
  已过滤的 `display_text`，因此气泡、字幕和聊天历史三者内容一致。
- 气泡文本再做一次 `[joy]` 类控制标签兜底清洗；中文书名号/引号不受影响。
- 新消息类型 `pet_speech`（schema v1）与 `pet_state_changed`/`pet_reaction`
  共用 `/api/pet/events`；新增 `GET /api/pet/speech/recent` 供侧边栏冷启动。
- 广播是进程内 fan-out：订阅队列有界，订阅者迟滞时丢最旧一条，
  绝不阻塞或中断对话；发布失败一律吞掉。
- 气泡定位改用 `#live2d` 容器内的画布，并用模型矩阵偏移作为头部提示
  （夹在 ±35% 以内），同时做视口夹取、`resize` 与 `ResizeObserver` 跟随。
- 长文本三行截断 + 「展开/收起」按钮；动作反应与说话共用同一个气泡，
  动作反应优先，不会被说话覆盖。
- 右侧抽屉骨架：「最近对话」显示短期显示缓冲并标注它不是长期记忆；
  「共同记忆」显示明确空状态，不用聊天记录冒充记忆。

### 三种真实宠物行为（交接文档 Phase B）

- `PetStateService` 新增 `play_with_pet`、`clean_pet`、`put_pet_to_sleep`，
  与 `feed_pet` 共用同一条 `_commit_action` 流水线：幂等、状态差量、原子事件。
- 事件类型：`PetPlayed`、`PetCleaned`、`PetSlept`（与 `PetFed` 并列）。
- 数值规则集中在领域服务，前端和 Prompt 不得自行计算：
  玩耍 `energy-12 / mood+12 / intimacy+5 / exp+3`，
  清洁 `cleanliness+35 / mood+4 / intimacy+1 / energy-3 / exp+1`，
  睡觉 `energy+10 / health+2 / mood+2 / exp+1` 并把 `activity` 置为 `sleeping`。
- 睡眠是持久行为而不是一次动画：`activity == "sleeping"` 时离线时间按
  `energy +6/h`、`health +0.5/h`、`mood +1/h`、`hunger +1/h` 恢复，精力满后自动醒来。
- MCP 工具：`play_with_pet`、`clean_pet`、`put_pet_to_sleep`（均支持 `request_id`）。
- HTTP：`POST /api/pet/play`、`/api/pet/clean`、`/api/pet/sleep`，参数经 Pydantic 校验。
- 状态卡新增「陪玩 / 洗澡 / 睡觉」按钮，粒子按动作切换（🐟 / ✨ / 🫧 / 💤）。
- Persona Prompt 已写明这三个动作必须调用工具，不能只用文字宣称完成。

### Live2D 原生互动渲染（交接文档 Phase A）

- `src/open_llm_vtuber/pet_live2d.py` 按 `model3.json` 与 `model_dict.json` 盘点真实资源；
  `mao_pro` 保留 `Idle`、6 个通用动作和 8 个表情，并新增 `Eat`、`Play`、`Clean`、
  `Sleep`、`SleepIdle`、`Wake` 六个交互动作组。
- 六个新增 `.motion3.json` 只使用 `mao_pro.cdi3.json` 已公开的真实参数；
  吃、玩、清洁、睡眠四种反应均解析为 `reason="native_motion"`，
  `missing_motion_assets=[]`，同时保留 `exp_04` 开心表情和气泡/粒子/高亮。
- 睡眠反应先播放一次 `Sleep`，随后由页面按持久 `activity=sleeping` 切到循环
  `SleepIdle`；离线恢复自动醒来时播放一次 `Wake`。
- `render` 作为 schema v1 可选字段附加在 `POST /api/pet/feed` 响应和 `pet_reaction` 事件上；
  `GET /api/pet/state` 增加 `live2d` 能力清单。忽略这些字段的旧客户端行为不变。
- 前端通过 bundle 已暴露的 `window.getLAppAdapter()` 调用 `startMotion` / `setExpression`，
  不修改压缩产物、不伪造静音 TTS；表情在 `duration_ms` 后回到 `neutral`。
- 反应音效由 WebAudio 实时合成（无第三方素材），面板提供静音开关，
  自动播放被拦截时静默降级，不影响状态、气泡和 TTS。

## 测试状态

新增 `tests/test_pet_live2d.py`（13 项）、`tests/test_pet_actions.py`（11 项）
、`tests/test_pet_speech.py`（14 项）与 `tests/test_pet_world.py`（19 项）。
Windows 环境在 Phase E 之前的全量 54 项已通过；加入世界规则测试后应为 73 项。

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

已验证范围与限制：

- 在无 FastAPI 的隔离环境中实测通过：`test_pet_state.py`、`test_pet_live2d.py`、
  `test_pet_actions.py`、`test_pet_speech.py`、`test_pet_world.py` 的领域、
  资源解析、广播与世界规则部分（61 项中 51 项通过，10 项路由/WebSocket 用例按
  `skipUnless(FastAPI)` 跳过；该环境的 `pet_live2d` 测试为 Phase A 版本）。
- Ruff `format --check` 与 `check` 对本次改动文件全部通过。
- `node --check frontend/pet-status.js` 通过。
- Windows 真机已执行完整 54 项测试（FastAPI/loguru/openai 依赖），全部通过；
  `node --check frontend/pet-status.js` 与 Live2D 相关 Ruff 检查通过。
- 仍需执行全目录 Ruff 检查和浏览器视觉实测。
- **Phase E 仍需在 Windows 真机跑一次全量**（新增 `test_pet_world.py` 19 项）。

覆盖范围：

- 宠物状态创建、时间变化、幂等喂食、持久化和边界裁剪。
- 宠物 HTTP 路由。
- 宠物事件 WebSocket、schema v1，以及来自独立 SQLite 连接的事件读取。
- StepFun 文本/视觉兼容转换。
- 音频 WAV 载荷和音量切片。
- Live2D 表情标签隐藏与动作保留。
- 短 TTS 片段平滑合并。
- Live2D 资源盘点、动作语义匹配、缺失动作降级、缺失表情降级、模型不可用不抛异常。
- 玩耍/清洁/睡觉的状态变化、事件类型、幂等重试、边界裁剪和睡眠期间的时间恢复。
- 气泡文本过滤、空句丢弃、超长截断、订阅/退订、慢订阅者丢最旧一条和最近对话缓冲上限。
- 隐私回归：载荷里的图片/base64 字段不会进入 `pet_speech` 消息或最近对话缓冲。
- 时段划分、日程全天覆盖、行为优先级链、重启恢复同一事件、长时间离线只出摘要、
  背景可用性与缺失降级。
- `render` 只附加在 `pet_reaction` 消息、且不改写原 `reaction`（schema v1 兼容）。

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
5. 宠物事件 WebSocket 当前按连接轮询 SQLite 事件表，适合单机桌面阶段；扩展多用户或高事件量前需要改为共享事件分发器。
6. 尚缺“用户自然语言喂食 → LLM 实际工具调用 → SQLite → 页面反应 → Live2D/TTS”完整自动端到端测试；目前已覆盖 HTTP 和独立数据库写入到 WebSocket 的后半段。
7. `mao_pro` 的吃/玩/清洁/睡眠动作已生成并接入，但属于基于现有参数的程序化首版；
   手持鱼干、毛巾、被子等真正模型内道具仍需 `.cmo3` 源文件和 Cubism Editor 绑定。
   新动作幅度、穿模、睡眠循环衔接及表情回归仍需在真机浏览器逐项验收。
8. 目前只有小太阳一套正式 PersonaPack；长期记忆、完整成长、绘画/写信、主动感知调度仍未实现。
   玩耍/清洁/睡觉三种行为的真机浏览器与 MCP 端到端验收也尚未进行。
9. 摄像头画中画的识别依赖运行时轨道属性，只能在真机开启摄像头后验证；
   自动化测试无法覆盖浏览器媒体流，这部分目前没有单元测试保护。
10. 头顶气泡的定位使用「画布 + 模型矩阵偏移」启发式，尚未按 Live2D 实际可见包围盒计算；
   不同缩放/拖动位置下的效果需要真机确认。侧边栏目前只有骨架与最近对话，
   共同记忆仍是空状态。
9. 日志中曾观察到一次 `/undefined/undefined.model3.json` 404，需要确认是否只是初始化瞬态请求。
10. 如果 StepFun Key 在历史终端或截图中暴露过，应在控制台轮换；项目文件不得记录具体 Key。

## 下一步建议

按顺序执行：

1. 修复 GitHub 凭据/协作者写权限并推送当前本地历史。
2. 添加真实 LLM/MCP 自然语言喂食端到端验收，确认 P0 闭环完整完成。
3. 在真实浏览器验收 Live2D 动作桥、表情回归、音效开关和降级路径（代码已完成，见 `NEXT_TASKS.md` P0-C2）。
4. 为视觉、LLM 首字、TTS 生成和前端播放分别增加耗时指标，再继续优化延迟。
5. 按交互补充说明进入气泡布局、摄像头画中画和最小生活节奏切片。
6. 完成 `0.1.x` 发布验收后，再进入四人格原子切换或长期记忆。

具体任务和验收条件见 `NEXT_TASKS.md`。
