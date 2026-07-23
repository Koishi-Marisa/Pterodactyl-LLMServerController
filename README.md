# Pterodactyl AI Chat Bot

翼龙面板 AI 聊天机器人。通过 WebSocket 监听游戏服务器控制台，使用 AI 自动与玩家互动。

## 功能特性

- WebSocket 实时监听翼龙面板控制台输出
- 智能识别玩家聊天消息（支持 Minecraft / Palworld / 通用格式）
- AI 自动回复（支持 OpenAI / DeepSeek / Ollama 等兼容接口）
- 多种触发模式：@提及 / 所有人 / 关键词
- 玩家冷却时间，防止刷屏
- 管理员命令（清除记录 / 查看状态）
- 对话历史记忆，上下文连贯
- JWT Token 自动刷新，永不断线
- 断线自动重连
- GitHub Actions 云端运行
- Docker 一键部署

## 项目结构

```
src/pterodactyl_bot/
  main.py          # 主入口
  config.py        # 配置管理（环境变量）
  client.py        # 翼龙面板 API/WebSocket 客户端
  ai_chat.py       # AI 聊天模块
  parser.py        # 聊天消息解析器
  handler.py       # 事件处理器
```

## 快速开始

### 方式一：GitHub Actions 云端运行（免费）

1. Fork 本仓库
2. 进入仓库 **Settings -> Secrets and variables -> Actions**
3. 添加以下 Secrets：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `PTERODACTYL_PANEL_URL` | 翼龙面板地址 | `https://panel.example.com` |
| `PTERODACTYL_API_KEY` | Client API Key（`ptlc_` 开头） | `ptlc_xxxx...` |
| `PTERODACTYL_SERVER_ID` | 服务器标识符（短 UUID） | `d3aac109` |
| `AI_API_KEY` | AI API Key | `sk-xxxx...` |

4. 可选 Secrets：

| Secret 名称 | 默认值 | 说明 |
|---|---|---|
| `AI_PROVIDER` | `zhipu` | AI 提供商 |
| `AI_API_URL` | 自动填充 | 自定义 AI 端点（覆盖预设） |
| `AI_MODEL` | `glm-4-flash` | 模型名称 |
| `GAME_TYPE` | `minecraft` | `minecraft` / `palworld` / `generic` |
| `TRIGGER_MODE` | `mention` | `mention` / `all` / `keyword` |
| `TRIGGER_KEYWORD` | `AI` | 触发关键词 |
| `BOT_NAME` | `AI助手` | 机器人名称 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

5. 进入 **Actions** 标签页，选择 `Run Pterodactyl AI Bot`，点击 **Run workflow**

> **注意**：GitHub Actions 单次运行最长 6 小时，到期会自动停止。可配合 `keep-alive.yml` 定时重启。

### 方式二：Docker 部署

```bash
# 复制配置文件
cp .env.example .env
# 编辑 .env 填写配置
nano .env

# 启动
docker compose up -d

# 查看日志
docker compose logs -f
```

### 方式三：本地运行

```bash
# 安装依赖
pip install aiohttp>=3.9.0 --break-system-packages

# 设置环境变量
export PTERODACTYL_PANEL_URL=https://panel.example.com
export PTERODACTYL_API_KEY=ptlc_xxxxx
export PTERODACTYL_SERVER_ID=d3aac109
export AI_API_KEY=sk-xxxxx

# 启动
PYTHONPATH=src python -m pterodactyl_bot.main
```

## 翼龙面板配置说明

### 获取 API Key

1. 登录翼龙面板
2. 进入 **Profile -> API Credentials**
3. 点击 **Create New Token**
4. 权限选择：至少需要 `Read Servers`、`Send Console Command`、`Read Server Resources`
5. 复制生成的 Key（`ptlc_` 开头）

### 获取服务器 ID

1. 进入服务器列表
2. 点击服务器名称
3. URL 中 `servers/` 后面的短 UUID 就是服务器标识符，例如 `d3aac109`

### 获取 AI API Key

内置支持以下 AI 提供商（设置 `AI_PROVIDER` 即可自动配置）：

| 提供商 | AI_PROVIDER 值 | 默认模型 | 获取 Key |
|---|---|---|---|
| **智谱AI（推荐）** | `zhipu` | `glm-4-flash`（免费） | [bigmodel.cn](https://bigmodel.cn) |
| OpenAI | `openai` | `gpt-4o-mini` | platform.openai.com |
| DeepSeek | `deepseek` | `deepseek-chat` | platform.deepseek.com |
| Ollama (本地) | `ollama` | `llama3` | 无需 Key |

智谱平台免费模型推荐：`glm-4-flash`（文本）、`GLM-4-Air`（增强）、`GLM-4V-Flash`（多模态）

使用自定义接口时，设置 `AI_PROVIDER=custom` 并填写 `AI_API_URL`。

## 触发模式说明

| 模式 | 说明 | 示例 |
|---|---|---|
| `mention` | 玩家消息包含关键词（默认 "AI"） | `AI 你好` 会触发回复 |
| `all` | 所有玩家聊天都会触发 | 任何消息都会回复 |
| `keyword` | 玩家消息包含指定关键词 | 自定义关键词匹配 |

## 管理员命令

在游戏内通过聊天发送：

| 命令 | 说明 |
|---|---|
| `!ai-help` | 查看帮助 |
| `!ai-status` | 查看机器人状态 |
| `!ai-clear` | 清除与你的对话记录 |

## 自定义 AI 提示词

通过 `BOT_PROMPT` 环境变量自定义 AI 的性格和行为，例如：

```
BOT_PROMPT=你是一个 Minecraft 服务器的小助手，名叫小明。你擅长回答游戏问题，语气活泼可爱。每次回复不超过30字。
```

## License

MIT
