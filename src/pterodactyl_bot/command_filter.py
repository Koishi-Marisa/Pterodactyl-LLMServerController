"""
指令安全过滤器
拦截可能破坏游戏平衡的敏感指令
"""
import logging

logger = logging.getLogger(__name__)

# ── 危险指令黑名单 ──
# 匹配命令第一个词即可，例如 "op" 匹配 "op Steve"
DANGEROUS_COMMANDS = frozenset(
    {
        # 权限管理
        "op",
        "deop",
        # 封禁
        "ban",
        "ban-ip",
        "banip",
        "pardon",
        "pardon-ip",
        "pardonip",
        # 踢出
        "kick",
        # 游戏模式
        "gamemode",
        "gm",
        "defaultgamemode",
        # 给予物品/经验
        "give",
        "enchant",
        "xp",
        "experience",
        # 杀死/传送
        "kill",
        "tp",
        "teleport",
        "tpa",
        "tpahere",
        "tpaccept",
        "tpdeny",
        "tphere",
        # 世界控制（环境指令，不算破坏平衡，放行）
        # "time",
        # "weather",
        # "difficulty",
        # "gamerule",
        # 服务器控制
        "stop",
        "restart",
        "reload",
        # 白名单
        "whitelist",
        # 世界编辑 (常见 WorldEdit 前缀)
        "//",
        "/brush",
        "/tool",
        # 其他敏感
        "effect",
        "clear",
        "seed",
        "save-off",
        "save-on",
        "save-all",
        "debug",
        "publish",
        "setidletimeout",
        "spreadplayers",
        "worldborder",
    }
)


def extract_command(raw: str) -> str:
    """
    从 AI 回复中提取指令名

    控制台指令不需要 '/' 前缀，直接取第一个词即可。
    例如 "say Hello" → "say", "time set day" → "time"
    """
    raw = raw.strip()
    if not raw:
        return ""
    # WorldEdit 双斜杠指令
    if raw.startswith("//"):
        return "//"
    parts = raw.split(None, 1)
    return parts[0].lower() if parts else ""


def is_dangerous(command: str) -> bool:
    """判断指令是否在黑名单中"""
    return command in DANGEROUS_COMMANDS


def filter_command(ai_reply: str) -> tuple[bool, str]:
    """
    过滤 AI 回复中的指令

    Returns:
        (is_safe, reason)
        - is_safe: True 表示可以执行，False 表示被拦截
        - reason: 拦截原因（安全时为空字符串）
    """
    cmd = extract_command(ai_reply)
    if not cmd:
        # 空内容，安全
        return True, ""

    if is_dangerous(cmd):
        reason = f"危险指令 '{cmd}' 已被拦截，禁止执行"
        logger.warning(f"[指令拦截] {reason}")
        return False, reason

    logger.info(f"[指令放行] {cmd}")
    return True, ""
