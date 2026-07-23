"""消息解析器单元测试"""
import pytest
from pterodactyl_bot.parser import MessageParser, ChatMessage


class TestMessageParser:
    """测试 Minecraft 格式解析"""

    def setup_method(self):
        self.parser = MessageParser(game_type="minecraft")

    def test_minecraft_format_angle_brackets(self):
        """测试 Minecraft 尖括号格式: <Player> message"""
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: <Steve> Hello World!"
        )
        assert result is not None
        assert result.player == "Steve"
        assert result.message == "Hello World!"
        assert result.is_command is False

    def test_minecraft_format_arrow(self):
        """测试 Minecraft 箭头格式: [Player] -> message"""
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: [Alex] -> How are you?"
        )
        assert result is not None
        assert result.player == "Alex"
        assert result.message == "How are you?"

    def test_minecraft_format_colon(self):
        """测试 Minecraft 冒号格式: Player: message"""
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: Notch: Testing!"
        )
        assert result is not None
        assert result.player == "Notch"
        assert result.message == "Testing!"

    def test_simple_bracket_format(self):
        """测试简化尖括号格式"""
        result = self.parser.parse("<Player123> hello there")
        assert result is not None
        assert result.player == "Player123"
        assert result.message == "hello there"

    def test_command_detection(self):
        """测试命令检测"""
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: <Admin> !ai-help"
        )
        assert result is not None
        assert result.is_command is True

    def test_ignore_server_logs(self):
        """测试忽略服务器日志"""
        # 玩家加入
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: Steve joined the game"
        )
        assert result is None

        # 玩家退出
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: Steve left the game"
        )
        assert result is None

        # 服务器启动
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: Starting minecraft server version 1.20.4"
        )
        assert result is None

    def test_empty_message(self):
        """测试空消息"""
        assert self.parser.parse("") is None
        assert self.parser.parse("  ") is None

    def test_non_chat_message(self):
        """测试非聊天消息"""
        result = self.parser.parse(
            "[10:30:45] [Server thread/INFO]: Preparing spawn area: 100%"
        )
        assert result is None


class TestPalworldParser:
    """测试 Palworld 格式解析"""

    def setup_method(self):
        self.parser = MessageParser(game_type="palworld")

    def test_palworld_chat_format(self):
        """测试 Palworld 聊天格式"""
        result = self.parser.parse(
            "[2024/01/15 10:30:45] Chat: [76561198xxxxx] PlayerName: Hello!"
        )
        assert result is not None
        assert result.player == "PlayerName"
        assert result.message == "Hello!"

    def test_palworld_simple_format(self):
        """测试 Palworld 简化格式"""
        result = self.parser.parse(
            "[2024/01/15 10:30:45] PlayerName: Hello!"
        )
        assert result is not None
        assert result.player == "PlayerName"


class TestGenericParser:
    """测试通用格式解析"""

    def setup_method(self):
        self.parser = MessageParser(game_type="generic")

    def test_generic_colon_format(self):
        """测试通用冒号格式"""
        result = self.parser.parse("PlayerOne: This is a message")
        assert result is not None
        assert result.player == "PlayerOne"
        assert result.message == "This is a message"

    def test_custom_pattern(self):
        """测试自定义正则"""
        self.parser.add_custom_pattern(r"CHAT\|(\S+)\|(.+)")
        result = self.parser.parse("CHAT|Admin|Hello World")
        assert result is not None
        assert result.player == "Admin"
        assert result.message == "Hello World"
