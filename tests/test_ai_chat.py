"""AI 聊天模块单元测试"""
import pytest
from unittest.mock import AsyncMock, patch
from pterodactyl_bot.ai_chat import AIChat
from pterodactyl_bot.config import Config


@pytest.fixture
def config():
    return Config(
        ai_api_url="https://api.example.com/v1/chat/completions",
        ai_api_key="test-key",
        ai_model="gpt-4o-mini",
        ai_max_tokens=100,
        ai_temperature=0.7,
        bot_name="TestBot",
        bot_prompt="You are a test bot.",
    )


@pytest.fixture
def ai(config):
    return AIChat(config)


class TestAIChat:
    @pytest.mark.asyncio
    async def test_chat_success(self, ai):
        """测试正常聊天流程"""
        mock_response = {
            "choices": [
                {"message": {"content": "你好！我是 AI 助手。"}}
            ]
        }

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await ai.chat("Steve", "你好")

        assert result == "你好！我是 AI 助手。"
        assert "Steve" in ai._history

    @pytest.mark.asyncio
    async def test_chat_api_error(self, ai):
        """测试 API 错误处理"""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_resp.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await ai.chat("Steve", "测试")

        assert "[TestBot]" in result

    @pytest.mark.asyncio
    async def test_history_management(self, ai):
        """测试对话历史管理"""
        mock_response = {
            "choices": [{"message": {"content": "回复1"}}]
        }

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=False)

            for i in range(5):
                await ai.chat("Player", f"消息{i}")

        history = ai._history["Player"]
        assert len(history) == 10  # 5 轮对话，每轮 user + assistant

    def test_clear_history(self, ai):
        """测试清除对话历史"""
        ai._history["Player1"] = [{"role": "user", "content": "test"}]
        ai._history["Player2"] = [{"role": "user", "content": "test"}]

        ai.clear_history("Player1")
        assert "Player1" not in ai._history
        assert "Player2" in ai._history

        ai.clear_history()
        assert len(ai._history) == 0
