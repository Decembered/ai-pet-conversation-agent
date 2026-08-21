# SLAI Pet 项目记忆

此目录保存的是**开发项目上下文**，用于让新的 Codex 窗口、团队成员或后续会话
快速恢复工作状态。它不是产品未来的“宠物长期记忆”运行时模块。

## 新会话读取顺序

1. `CURRENT_STATUS.md`：现在做到哪里、最后验证结果、已知问题和下一步。
2. `PROJECT_CONTEXT.md`：产品目标、需求优先级和范围。
3. `ARCHITECTURE.md`：当前真实架构、主要文件和数据流。
4. `DECISIONS.md`：已经做出的关键决策及原因。
5. `RUNBOOK.md`：安装、启动、测试和排障命令。
6. `NEXT_TASKS.md`：推荐实施顺序和验收条件。

## 新窗口推荐提示词

```text
请先读取 AGENTS.md、memory/README.md 和 memory/CURRENT_STATUS.md，
再检查 git status 与最近提交。基于 memory/NEXT_TASKS.md 继续项目，
不要泄露 conf.yaml 或其他本地密钥；完成修改后同步更新 memory。
```

## 维护规则

- `CURRENT_STATUS.md` 只写当前有效状态，不累积完整流水账。
- `DECISIONS.md` 采用追加方式，已接受的决策不能静默删除；变更时新增“取代”记录。
- 所有状态描述都应附带可验证证据：提交、测试、文件或可复现命令。
- 本目录可以提交 Git，但不得包含 API Key、访问令牌、用户隐私图片或摄像头内容。
- 聊天记录不是最终事实来源；当前代码、测试结果和这些文件共同构成项目事实来源。

最后整理日期：2026-08-22（Asia/Shanghai）。
