# 本地运行与验证手册

## 工作目录

```powershell
Set-Location "D:\mineD\Projecttt\0821pet\Open-LLM-VTuber-main\Open-LLM-VTuber-main"
```

Python 要求：`>=3.10,<3.13`。依赖管理统一使用 `uv`。

如果 `uv` 不在 PATH，可使用当前机器上的完整路径：

```powershell
& "D:\mineD\Softwareee\anacondaaa20250707\Scripts\uv.exe" --version
```

## 首次安装

```powershell
uv sync
```

只有在文件不存在时才从模板创建本地配置；不要覆盖已经配置好 StepFun Key 的文件：

```powershell
Copy-Item "config_templates\conf.ZH.default.yaml" "conf.yaml"
Copy-Item "mcp_servers.example.json" "mcp_servers.json"
```

然后只在本地 `conf.yaml` 填写凭据。不要把凭据发到聊天、日志、截图或 Git。

## 启动

```powershell
uv run python run_server.py
```

打开：`http://localhost:12393`

停止服务：在运行服务器的终端按 `Ctrl+C`。

已知环境差异：直接执行 `.venv\Scripts\python.exe run_server.py` 曾导致 SenseVoice
ONNX 报 `No graph was found in the protobuf`，优先坚持使用 `uv run`。

## 完整测试

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

最近基线：14 项通过。

## 代码质量

```powershell
uvx ruff format src tests scripts
uvx ruff check src tests scripts
```

如果全目录检查暴露大量上游历史问题，至少检查本次修改涉及的文件，并在交付说明中写明范围。

## 验证 StepFun 文本和视觉连接

```powershell
uv run python scripts/verify_stepfun.py
```

脚本只输出成功标志、视觉开关和回复字符数，不应打印凭据或完整模型回复。

## 常用只读检查

```powershell
git status --short
git log -5 --oneline
Test-NetConnection -ComputerName localhost -Port 12393 -InformationLevel Quiet
```

## 页面问题

- 后端已重启但前端仍显示旧内容：浏览器按 `Ctrl+F5` 强制刷新。
- 显示“已连接”只代表 WebSocket 已连接，不代表 StepFun API 一定成功；同时查看服务器日志。
- 摄像头开启后视觉轮次会更慢；先分别测试纯文本、语音、语音+图片来定位瓶颈。
- 表情标签如果再次泄露，检查 `display_processor`、历史消息清理和 `model_dict.json`。

## Git 和远端

```powershell
git remote -v
git branch -vv
```

当前 `origin` 指向团队 GitHub 仓库，但之前使用的凭据返回 403。推送前先确认当前 GitHub
账号是仓库协作者或拥有写权限；不要在 memory 中保存访问令牌。
