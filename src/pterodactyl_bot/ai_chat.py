"""
AI 聊天模块
支持 OpenAI 兼容 API（OpenAI / DeepSeek / Ollama / 自定义端点）
可选集成联网搜索，在调用 AI 前先检索最新信息
"""
import asyncio
import logging
import aiohttp
import json

from .search import web_search

logger = logging.getLogger(__name__)

# 每个玩家的对话历史最大条数
MAX_HISTORY_PER_PLAYER = 20


class AIChat:
    """AI 聊天处理器"""

    def __init__(self, config):
        self.config = config
        self.api_url = config.ai_api_url
        self.api_key = config.ai_api_key
        self.model = config.ai_model
        self.max_tokens = config.ai_max_tokens
        self.temperature = config.ai_temperature
        self.system_prompt = config.bot_prompt

        # 搜索配置
        self.search_enabled = config.search_enabled
        self.search_provider = config.search_provider
        self.search_api_key = config.search_api_key
        self.search_max_results = config.search_max_results

        # 玩家对话历史 {player_name: [{"role": "user/assistant", "content": "..."}]}
        self._history: dict[str, list[dict]] = {}

    def _get_history(self, player: str) -> list[dict]:
        """获取玩家对话历史"""
        return self._history.setdefault(player, [])

    def _trim_history(self, player: str):
        """裁剪过长的对话历史"""
        history = self._history.get(player, [])
        if len(history) > MAX_HISTORY_PER_PLAYER * 2:
            self._history[player] = history[-(MAX_HISTORY_PER_PLAYER * 2) :]

    async def _do_search(self, message: str) -> str:
        """
        根据玩家消息进行联网搜索

        Returns:
            搜索结果摘要文本，失败返回空字符串
        """
        if not self.search_enabled:
            return ""

        try:
            result = await web_search(
                query=message,
                provider=self.search_provider,
                api_key=self.search_api_key,
                max_results=self.search_max_results,
            )
            if result:
                logger.info(f"[搜索] 获取到结果: {len(result)} 字符")
            return result
        except Exception as e:
            logger.warning(f"联网搜索异常: {e}")
            return ""

    async def chat(self, player: str, message: str) -> str:
        """
        向 AI 发送玩家消息并获取回复

        Args:
            player: 玩家名称
            message: 玩家消息内容

        Returns:
            AI 回复文本
        """
        history = self._get_history(player)

        # 构建消息列表
        messages = [
            {"role": "system", "content": self.system_prompt},
            *history,
        ]

        # 联网搜索增强
        search_context = await self._do_search(message)
        if search_context:
            user_content = (
                f"[参考信息]\n{search_context}\n"
                f"[参考信息结束]\n"
                f"[{player}] 说: {message}"
            )
        else:
            user_content = f"[{player}] 说: {message}"

        messages.append({"role": "user", "content": user_content})

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(
                            f"AI API 请求失败 (HTTP {resp.status}): {error_text}"
                        )
                        return ""

                    data = await resp.json()
                    reply = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )

                    if not reply:
                        return ""

                    # 更新对话历史（只记录原始玩家消息，不含搜索结果）
                    history.append({"role": "user", "content": message})
                    history.append({"role": "assistant", "content": reply})
                    self._trim_history(player)

                    return reply

        except asyncio.TimeoutError:
            logger.error("AI API 请求超时")
            return ""
        except Exception as e:
            logger.error(f"AI 聊天异常: {e}")
            return ""

    def clear_history(self, player: str = None):
        """清除对话历史"""
        if player:
            self._history.pop(player, None)
        else:
            self._history.clear()
