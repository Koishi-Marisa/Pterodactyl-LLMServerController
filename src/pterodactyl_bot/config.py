"""
配置管理模块
从环境变量读取所有配置项
"""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """机器人配置"""

    # ── 翼龙面板配置 ──
    panel_url: str = ""
    api_key: str = ""
    server_identifier: str = ""  # 服务器短 UUID (identifier)

    # ── AI 配置 ──
    # 支持的 provider: openai / zhipu / deepseek / ollama / custom
    ai_provider: str = "zhipu"
    ai_api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    ai_api_key: str = ""
    ai_model: str = "glm-4-flash"
    ai_max_tokens: int = 300
    ai_temperature: float = 0.7

    # 内置 AI 提供商预设 {name: (api_url, default_model)}
    AI_PROVIDERS = {
        "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
        "zhipu": ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash"),
        "deepseek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
        "ollama": ("http://localhost:11434/v1/chat/completions", "llama3"),
    }

    # ── 机器人行为配置 ──
    bot_name: str = "AI助手"
    bot_prompt: str = (
        "你是一个友好的游戏服务器 AI 助手。"
        "你通过服务器控制台与玩家互动，回复需要简洁明了。"
        "每次回复控制在50字以内。不要使用特殊字符和代码块。"
    )
    game_type: str = "minecraft"  # minecraft / palworld / generic
    trigger_mode: str = "mention"  # mention / all / keyword
    trigger_keyword: str = "AI"
    cooldown_seconds: int = 10  # 同一玩家回复冷却时间
    command_prefix: str = "!"  # 管理员命令前缀

    # ── 连接配置 ──
    ws_reconnect_delay: int = 5  # 断线重连延迟(秒)
    ws_token_refresh_interval: int = 480  # token 刷新间隔(秒)，JWT 有效期 10 分钟
    ping_interval: int = 30  # WebSocket 心跳间隔(秒)

    # ── 日志配置 ──
    log_level: str = "INFO"

    # ── 运行时状态 ──
    player_cooldowns: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置，自动解析 AI 提供商"""
        provider = os.getenv("AI_PROVIDER", "zhipu").lower()

        # 根据 provider 自动填充 API URL 和默认模型
        if provider in cls.AI_PROVIDERS:
            default_url, default_model = cls.AI_PROVIDERS[provider]
        else:
            default_url = "https://api.openai.com/v1/chat/completions"
            default_model = "gpt-4o-mini"

        # 自定义 API URL 优先于预设
        custom_url = os.getenv("AI_API_URL", "")
        api_url = custom_url if custom_url else default_url
        model = os.getenv("AI_MODEL", default_model)

        return cls(
            panel_url=os.getenv("PTERODACTYL_PANEL_URL", ""),
            api_key=os.getenv("PTERODACTYL_API_KEY", ""),
            server_identifier=os.getenv("PTERODACTYL_SERVER_ID", ""),
            ai_provider=provider,
            ai_api_url=api_url,
            ai_api_key=os.getenv("AI_API_KEY", ""),
            ai_model=model,
            ai_max_tokens=int(os.getenv("AI_MAX_TOKENS", "300")),
            ai_temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
            bot_name=os.getenv("BOT_NAME", "AI助手"),
            bot_prompt=os.getenv("BOT_PROMPT", cls.bot_prompt),
            game_type=os.getenv("GAME_TYPE", "minecraft"),
            trigger_mode=os.getenv("TRIGGER_MODE", "mention"),
            trigger_keyword=os.getenv("TRIGGER_KEYWORD", "AI"),
            cooldown_seconds=int(os.getenv("COOLDOWN_SECONDS", "10")),
            command_prefix=os.getenv("COMMAND_PREFIX", "!"),
            ws_reconnect_delay=int(os.getenv("WS_RECONNECT_DELAY", "5")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> list[str]:
        """验证必填配置，返回错误列表"""
        errors = []
        if not self.panel_url:
            errors.append("PTERODACTYL_PANEL_URL 未设置")
        if not self.api_key:
            errors.append("PTERODACTYL_API_KEY 未设置")
        if not self.server_identifier:
            errors.append("PTERODACTYL_SERVER_ID 未设置")
        if not self.ai_api_key:
            errors.append("AI_API_KEY 未设置")
        return errors
