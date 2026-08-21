# AI 宠物对话 Agent：拉取与运行说明

本仓库是在 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 基础上开发的 AI 宠物项目，包含：

- 宠物世界状态：饥饿、精力、健康、心情、亲密度和等级成长
- 四套人格配置，以及由 system prompt 注入的宠物身份和安全约束
- SQLite 短期/长期记忆数据
- 喂食、摸摸、洗澡、休息、学习、打工、冒险等动作
- 写信和 SVG 画作技能，作品保存在本地 `data/artifacts/`
- 主动回应事件接口（当前 Demo 使用隐私友好的事件信号，不保存摄像头画面）
- 原版 Live2D/语音/LLM/ASR/TTS 能力

## 1. 环境要求

- Python 3.10–3.12
- Git
- [uv](https://docs.astral.sh/uv/)
- 如果要进行自由聊天：Ollama 或其他兼容的 LLM 服务

## 2. 拉取代码

推荐使用递归子模块方式，这样会同时拉取原版 Web 前端：

```bash
git clone --recurse-submodules https://github.com/Decembered/ai-pet-conversation-agent.git
cd ai-pet-conversation-agent
```

如果已经普通拉取过仓库，再执行：

```bash
git submodule update --init --recursive
```

## 3. 安装依赖

```bash
uv sync
```

首次使用可以从中文模板生成配置：

```bash
cp config_templates/conf.ZH.default.yaml conf.yaml
```

然后打开 `conf.yaml`，至少确认以下内容：

- `system_config.host`：本机使用 `localhost`；局域网访问可改成 `0.0.0.0`
- `character_config.agent_config...llm_provider`：选择你实际使用的 LLM
- 如果使用 Ollama，先安装并启动 Ollama，再准备配置中的模型，例如 `qwen2.5:latest`

不要把真实 API Key 写入 Git。`conf.yaml` 已经被 `.gitignore` 忽略；分享代码时只提交模板文件。

## 4. 启动服务

```bash
uv run run_server.py
```

打开：

- AI 宠物世界 Demo：<http://localhost:12393/pet-demo/>
- 原版完整前端：<http://localhost:12393/>

宠物动作、状态、记忆和作品接口都挂在 `/api/pet/*` 下。第一次访问时会自动创建本地 `data/pet.sqlite3`，不要把这个文件提交到仓库。

## 5. 只体验静态 Demo

不想安装 Python 或 LLM 时，可以使用 `pet_demo` 的浏览器静态模式。用任意静态文件服务器托管仓库目录后访问：

```bash
python -m http.server 8000
```

然后打开 <http://localhost:8000/pet_demo/?static=1>。静态模式的成长状态保存在当前浏览器的 localStorage 中，不能代替完整后端。

## 6. 运行测试

```bash
uv run --with pytest --with httpx pytest -q
```

## 7. 远程访问提醒

远程访问需要 HTTPS，麦克风和摄像头才会被浏览器允许。可以使用 ngrok 或 Cloudflare Tunnel 将本机的 `12393` 端口映射出去，但本机服务和模型必须持续运行。公开 Demo 前请补充登录、限流和每个用户独立的 `pet_id`，当前示例默认使用共享的 `demo` 宠物。

## 8. 许可证提醒

本项目继承上游项目的许可证和第三方素材说明。仓库中的 Live2D 示例模型遵循 Live2D 单独的素材许可，不等同于项目代码许可证；商业使用前请单独确认授权。
