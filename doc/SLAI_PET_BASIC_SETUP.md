# SLAI Pet 基础功能说明

当前 SLAI Pet 产品版本为 `0.1.0`，上游代码基于 Open-LLM-VTuber `1.2.1`。

本版本先实现需求文档要求的第一条基础纵向闭环：

```text
安全小太阳人格
  -> LLM 识别状态或喂食意图
  -> MCP 调用真实宠物状态工具
  -> SQLite 持久化状态与事件
  -> LLM 根据工具结果进行人格化回复
```

## 已实现

- 安全默认中英文 Prompt，移除原模板的攻击性默认人格；
- `characters/zh_小太阳.yaml` 完整角色配置；
- 小太阳 System Prompt、Edge TTS 音色和 Live2D 模型绑定；
- `PetState`：饥饿、精力、健康、心情、清洁、亲密度、位置、活动、等级、经验和成熟度；
- 基于时间差的状态衰减；
- SQLite 自动初始化与持久化；
- `PetFed` 审计事件；
- 带 `request_id` 的幂等喂食，避免重试重复执行；
- MCP 工具 `get_pet_state` 和 `feed_pet`；
- 基础回归测试。

## 本地配置

1. 从默认模板生成配置：

   ```powershell
   Copy-Item config_templates/conf.ZH.default.yaml conf.yaml
   ```

2. 从 MCP 模板生成本地配置：

   ```powershell
   Copy-Item mcp_servers.example.json mcp_servers.json
   ```

3. 根据本机实际情况配置一个支持原生工具调用的 OpenAI Compatible 或 Claude LLM。

4. 启动服务：

   ```powershell
   uv sync
   uv run run_server.py
   ```

5. 在角色选择中切换到 `SLAI Pet · 小太阳`。

角色配置会启用 `pet-state` MCP Server。询问“你现在怎么样”时应调用 `get_pet_state`；发送“给你吃一条鱼”时应调用 `feed_pet`。

## 直接验证领域服务

不启动 LLM 也可以运行基础状态测试：

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

## 本版本边界

- `frontend/` 已纳管 Open-LLM-VTuber-Web `build` 分支的静态页面，来源提交记录在 `frontend/UPSTREAM_SOURCE.md`；当前页面尚未增加宠物状态面板；
- 当前只完成状态查询和喂食，洗澡、治疗、学习、打工和冒险将在后续版本扩展；
- 长期记忆、成长阶段变化、绘画、写信和摄像头主动交互尚未实现；
- MCP 原生工具调用当前只由上游明确适配的 OpenAI Compatible 和 Claude Agent 路径保证。

不得把上述未完成功能标记为已完成。
