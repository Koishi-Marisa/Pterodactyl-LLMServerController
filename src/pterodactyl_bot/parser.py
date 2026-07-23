"""
消息解析模块
解析不同游戏服务器的聊天日志格式，提取玩家名称和消息内容

支持的格式:
- Minecraft: [HH:MM:SS] [Player]: message  或  <Player> message
- Palworld: [YYYY/MM/DD HH:MM:SS] chat message
- Rust: Chat message format
- 通用: 通过正则表达式自定义匹配
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """解析后的聊天消息"""
    player: str
    message: str
    raw: str
    is_command: bool = False


# ── Minecraft 日志格式 ──
# 格式1: [10:30:45] [Server thread/INFO]: <Steve> Hello!
# 格式2: [10:30:45] [Server thread/INFO]: [Steve] -> Hello!
# 格式3: [10:30:45] [Server thread/INFO]: Steve: Hello!
MINECRAFT_PATTERNS = [
    re.compile(
        r"\[\d{2}:\d{2}:\d{2}\]\s+\[.+?\]:\s+<(\S+?)>\s+(.*)"
    ),
    re.compile(
        r"\[\d{2}:\d{2}:\d{2}\]\s+\[.+?\]:\s+\[(\S+?)\]\s+->\s+(.*)"
    ),
    re.compile(
        r"\[\d{2}:\d{2}:\d{2}\]\s+\[.+?\]:\s+(\S+?):\s+(.*)"
    ),
    # 简化格式
    re.compile(r"<(\S+?)>\s+(.*)"),
]

# ── Palworld 日志格式 ──
# [2024/01/15 10:30:45] Chat: [SteamID] PlayerName: message
PALWORLD_PATTERNS = [
    re.compile(
        r"\[\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\]\s+Chat:\s+\[\S+?\]\s+(\S+?):\s+(.*)"
    ),
    re.compile(
        r"\[\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\]\s+(\S+?):\s+(.*)"
    ),
]

# ── 通用聊天格式 ──
# PlayerName: message
GENERIC_PATTERNS = [
    re.compile(r"^(\S+?):\s+(.*)"),
]


class MessageParser:
    """聊天消息解析器"""

    def __init__(self, game_type: str = "minecraft"):
        """
        Args:
            game_type: 游戏类型 (minecraft / palworld / rust / generic)
        """
        self.game_type = game_type.lower()
        self._patterns = self._load_patterns()
        self._server_patterns: list[re.Pattern] = []
        # 服务器内部消息关键字（忽略这些消息）
        self._ignore_keywords = [
            "Server thread",
            "INFO",
            "WARN",
            "ERROR",
            "FATAL",
            "joined the game",
            "left the game",
            "lost connection",
            "was slain",
            "died",
            "earned the advancement",
            "[main/",
            "Preparing spawn",
            "Done (",
            "Starting minecraft",
            "Stopping",
            "Saving chunks",
            "There are",
            "Thread dump",
            "Can't keep up",
        ]

    def _load_patterns(self) -> list[re.Pattern]:
        """根据游戏类型加载正则表达式"""
        if self.game_type == "minecraft":
            return MINECRAFT_PATTERNS
        elif self.game_type == "palworld":
            return PALWORLD_PATTERNS
        else:
            return GENERIC_PATTERNS

    def add_custom_pattern(self, pattern: str):
        """添加自定义正则表达式，第一个捕获组为玩家名，第二个为消息"""
        self._server_patterns.append(re.compile(pattern))

    def add_ignore_keyword(self, keyword: str):
        """添加忽略关键字"""
        self._ignore_keywords.append(keyword)

    def parse(self, raw_line: str) -> ChatMessage | None:
        """
        解析一行控制台输出

        Args:
            raw_line: 控制台原始输出

        Returns:
            ChatMessage 或 None（非聊天消息）
        """
        raw_line = raw_line.strip()
        if not raw_line:
            return None

        # 如果消息太短，大概率不是聊天
        if len(raw_line) < 3:
            return None

        # 优先尝试正则匹配（聊天消息也包含 "INFO" 等字样，需先匹配）
        all_patterns = self._patterns + self._server_patterns
        for pattern in all_patterns:
            match = pattern.search(raw_line)
            if match:
                player = match.group(1).strip()
                message = match.group(2).strip()
                if player and message:
                    return ChatMessage(
                        player=player,
                        message=message,
                        raw=raw_line,
                        is_command=message.startswith("!"),
                    )

        # 正则未命中，检查是否为服务器日志（应忽略）
        for kw in self._ignore_keywords:
            if kw.lower() in raw_line.lower():
                return None

        return None
