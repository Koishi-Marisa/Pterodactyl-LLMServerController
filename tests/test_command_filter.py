"""指令安全过滤器单元测试"""
import pytest
from pterodactyl_bot.command_filter import (
    extract_command,
    is_dangerous,
    filter_command,
)


class TestExtractCommand:
    def test_slash_command(self):
        assert extract_command("/say Hello") == "say"
        assert extract_command("/time set day") == "time"
        assert extract_command("/weather clear") == "weather"

    def test_exclamation_command(self):
        assert extract_command("!help") == "help"
        assert extract_command("!list players") == "list"

    def test_no_command(self):
        assert extract_command("Hello world") == ""
        assert extract_command("  ") == ""
        assert extract_command("") == ""

    def test_case_insensitive(self):
        assert extract_command("/SAY hello") == "say"
        assert extract_command("/Time set day") == "time"


class TestIsDangerous:
    def test_dangerous_commands(self):
        assert is_dangerous("op") is True
        assert is_dangerous("ban") is True
        assert is_dangerous("kick") is True
        assert is_dangerous("gamemode") is True
        assert is_dangerous("give") is True
        assert is_dangerous("kill") is True
        assert is_dangerous("tp") is True
        assert is_dangerous("stop") is True
        assert is_dangerous("//") is True

    def test_safe_commands(self):
        assert is_dangerous("say") is False
        assert is_dangerous("list") is False
        assert is_dangerous("help") is False
        assert is_dangerous("me") is False
        assert is_dangerous("msg") is False


class TestFilterCommand:
    def test_safe_chat(self):
        is_safe, reason = filter_command("Hello everyone!")
        assert is_safe is True
        assert reason == ""

    def test_safe_command(self):
        is_safe, reason = filter_command("/say Hello")
        assert is_safe is True
        assert reason == ""

    def test_blocked_op(self):
        is_safe, reason = filter_command("/op Steve")
        assert is_safe is False
        assert "op" in reason

    def test_blocked_ban(self):
        is_safe, reason = filter_command("/ban BadPlayer")
        assert is_safe is False
        assert "ban" in reason

    def test_blocked_gamemode(self):
        is_safe, reason = filter_command("/gamemode creative Steve")
        assert is_safe is False
        assert "gamemode" in reason

    def test_blocked_worldedit(self):
        is_safe, reason = filter_command("//set stone")
        assert is_safe is False
        assert "//" in reason
