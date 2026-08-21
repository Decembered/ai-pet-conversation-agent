# AI 宠物对话 Agent：拉取与运行说明

本仓库是在 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 基础上开发的 AI 宠物项目，包含：

- 宠物世界状态：饥饿、精力、健康、心情、亲密度和等级成长
- 四套人格配置，以及由 system prompt 注入的宠物身份和安全约束
- SQLite 短期/长期记忆数据
- 喂食、摸摸、洗澡、休息、学习、打工、冒险、梳毛、唱歌、跳舞、探索、社交等动作
- 写信和 SVG 画作技能，作品保存在本地 `data/artifacts/`
- 主动回应事件接口（当前 Demo 使用隐私友好的事件信号，不保存摄像头画面）
- 原版 Live2D/语音/LLM/ASR/TTS 能力

## 1. 环境要求

- Python 3.10–3.12
- Git
- [uv](https://docs.astral.sh/uv/)
- Chrome 或 Edge（麦克风、摄像头和 Live2D 网页渲染）
- `ffmpeg`（语音音频转换；macOS 可用 `brew install ffmpeg`，Ubuntu 可用 `sudo apt install ffmpeg`）
- 如果要进行自由聊天：MiMo API Key 或其他兼容的 LLM 服务

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

`uv sync` 会按 `pyproject.toml` 和 `uv.lock` 安装包括 `silero-vad`、`sherpa-onnx`、PyTorch 在内的运行依赖；不需要再单独执行 `pip install`。

首次使用可以从中文模板生成配置：

```bash
cp config_templates/conf.ZH.default.yaml conf.yaml
```

然后打开 `conf.yaml`，至少确认以下内容：

- `system_config.host`：本机使用 `localhost`；局域网访问可改成 `0.0.0.0`
- `character_config.agent_config...llm_provider`：中文模板已经设置为 `openai_compatible_llm`
- `character_config.agent_config...llm_configs.openai_compatible_llm.model`：已经设置为 `mimo-v2.5`
- `character_config.asr_config.asr_model`：使用本地 `sherpa_onnx_asr`
- `character_config.vad_config.vad_model`：使用浏览器/服务端已有的 `silero_vad`
- `character_config.tts_config.tts_model`：默认使用 `edge_tts`，它和 MiMo 文本接口是两条独立链路

Sherpa 的 SenseVoice 模型不随 Git 仓库提交。第一次启动且本地没有模型时，服务会自动下载约 1GB；如果只想先看网页，可以使用下面的静态 Demo，不会触发模型初始化。

### MiMo 文本接口

先在当前终端设置密钥，再启动服务：

```bash
export MIMO_API_KEY='你的 MiMo API Key'
```

检查密钥是否已经注入当前终端：

```bash
test -n "$MIMO_API_KEY" && echo 'MIMO_API_KEY 已设置' || echo 'MIMO_API_KEY 未设置'
```

没有设置密钥时，网页和本地宠物动作仍然可以打开，但自由文本对话会在调用 MiMo 时失败；这不是模型加载失败。密钥只通过环境变量传入，不会写入仓库。

默认地址是 `https://api.xiaomimimo.com/v1`。如果你使用 Token Plan，把 `conf.yaml` 中的 `base_url` 改为 `https://token-plan-cn.xiaomimimo.com/v1`，模型仍然使用 `mimo-v2.5`。可参考 [MiMo 官方 API 文档](https://mimo.mi.com/docs/) 和 [官方 Codex 接入说明](https://github.com/XiaomiMiMo/awesome-mimo-agent/blob/main/docs/codex.zh-CN.md)。

不要把真实 API Key 写进 Git。`conf.yaml` 已经被 `.gitignore` 忽略；分享代码时只提交模板文件。

当前项目先把 MiMo 用在文本对话上。MiMo 的 ASR/TTS 模型虽然存在，但本项目的 ASR/TTS 适配器不是 MiMo 专用 REST 适配器，不能只改一个模型名就接通；要接 MiMo 语音，需要再单独实现对应的音频请求和流式播放适配器。

### 主动交互

Demo 页面默认打开“自动陪伴”。页面每 30 秒询问一次 `/api/pet/proactive/tick`，服务端按 90 秒冷却并结合饥饿、精力、心情决定是否主动说话；可以在右侧控制抽屉关闭。摄像头事件仍然只传入 `entered`、`smile` 等信号，不上传或保存画面。

### 首次启动的模型下载

SenseVoice ASR 模型约 1GB，首次启动会下载到 `models/`，不提交到 Git。下载过程中不要关闭终端。现在启动逻辑会验证模型图；如果上次下载中断导致 `No graph was found in the protobuf`，会自动清理损坏目录并重新下载。`silero-vad` 的 VAD 模型由依赖包首次加载时准备，已由 `uv sync` 安装。

Live2D 模型已经随仓库的 `live2d-models/` 目录提供，服务启动成功后由原版前端从 `/live2d-models/` 加载。若只看到“宠物世界暂时没有加载”，先检查服务端是否真的保持在 `12393` 端口监听，而不是只打开了静态网页。

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

启动后可以用下面两条命令快速确认网站和模型相关静态资源：

```bash
curl -I http://localhost:12393/pet-demo/
curl -I http://localhost:12393/live2d-models/mao_pro/runtime/mao_pro.model3.json
```

两条命令都应返回 `200 OK`。如果第一条失败，说明服务没有启动完成；如果第二条失败，说明 Live2D 资源目录或前端服务路径不完整。

## 7. 远程访问提醒

远程访问需要 HTTPS，麦克风和摄像头才会被浏览器允许。可以使用 ngrok 或 Cloudflare Tunnel 将本机的 `12393` 端口映射出去，但本机服务和模型必须持续运行。公开 Demo 前请补充登录、限流和每个用户独立的 `pet_id`，当前示例默认使用共享的 `demo` 宠物。

## 8. 许可证提醒

本项目继承上游项目的许可证和第三方素材说明。仓库中的 Live2D 示例模型遵循 Live2D 单独的素材许可，不等同于项目代码许可证；商业使用前请单独确认授权。
