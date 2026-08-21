# SLAI Pet 仓库工作约定

## 每个任务开始时

1. 先读取 `memory/README.md` 和 `memory/CURRENT_STATUS.md`。
2. 根据任务范围读取 `memory/PROJECT_CONTEXT.md`、`memory/ARCHITECTURE.md`、
   `memory/DECISIONS.md` 或 `memory/RUNBOOK.md`。
3. 执行 `git status --short` 和 `git log -1 --oneline`，确认实际代码状态。
4. 代码与测试是“已经实现了什么”的最终证据；需求文档描述“应该实现什么”。

## 仓库范围

- 本仓库基于 Open-LLM-VTuber 1.2.1，产品名称为 SLAI Pet。
- 当前优先完成可演示的宠物状态纵向闭环，再扩展长期记忆、成长、作品和主动感知。
- 本地 `conf.yaml`、`mcp_servers.json`、`data/`、日志和缓存不得提交。
- 不要在命令输出、测试日志、文档或回答中显示 API Key。

## 基本验证

- Python：`>=3.10,<3.13`。
- 安装：`uv sync`。
- 启动：`uv run python run_server.py`。
- 测试：`uv run python -m unittest discover -s tests -p "test_*.py" -v`。
- 修改 Python 后运行 Ruff 和相关测试；高风险链路再运行全部测试。

## 项目记忆维护

- 完成功能、修复缺陷或改变当前优先级后，更新 `memory/CURRENT_STATUS.md`。
- 做出架构、数据、供应商、安全或兼容性选择后，追加到 `memory/DECISIONS.md`。
- 启动、安装或排障方式变化后，更新 `memory/RUNBOOK.md`。
- 架构边界或数据流变化后，更新 `memory/ARCHITECTURE.md`。
- 只记录已验证事实、关键原因、已知限制和下一步；不要复制完整聊天记录。
- 尽量让代码和对应 memory 更新进入同一个 Git commit。
