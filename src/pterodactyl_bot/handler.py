"""
事件处理模块
处理 WebSocket 消息，管理聊天交互流程
"""
import asyncio
import json
import logging
import time

from .client import PterodactylClient
from .ai_chat import AIChat
from .parser import MessageParser, ChatMessage

logger = logging.getLogger(__name__)


class EventHandler:
    """事件处理器，协调 WebSocket 消息与 AI 回复"""

    def __init__(self, client: PterodactylClient, ai: AIChat, parser: MessageParser):
        self.client = client
        self.ai = ai
        self.parser = parser
        self.config = client.config
        self._stats_last_print = time.time()

    async def handle_ws_message(self, data: dict):
        """
        处理一条 WebSocket 消息

        Args:
            data: 解析后的 JSON 消息 {"event": "...", "args": [...]}
        """
        event = data.get("event", "")
        args = data.get("args", [])

        if event == "console output":
            await self._handle_console_output(args)
        elif event == "stats":
            self._handle_stats(args)
        elif event == "status":
            self._handle_status(args)
        elif event == "auth success":
            logger.info("WebSocket 认证成功")
        elif event == "jwt error":
            logger.error(f"JWT 认证错误: {args}")
        elif event == "throttled":
            logger.warning(f"消息频率超限: {args}")

    async def _handle_console_output(self, args: list):
        """处理控制台输出，检测玩家聊天"""
        if not args:
            return

        # 翼龙面板 console output 的 args[0] 是文本内容
        text = args[0] if isinstance(args[0], str) else str(args[0])
        logger.debug(f"控制台: {text}")

        # 解析聊天消息
        chat_msg = self.parser.parse(text)
        if chat_msg is None:
            return

        logger.info(f"[聊天] {chat_msg.player}: {chat_msg.message}")

        # 检查是否是管理员命令
        if chat_msg.is_command:
            await self._handle_admin_command(chat_msg)
            return

        # 检查触发条件
        if not self._should_trigger(chat_msg):
            return

        # 检查冷却时间
        if not self._check_cooldown(chat_msg.player):
            logger.debug(f"玩家 {chat_msg.player} 在冷却中")
            return

        # 调用 AI 获取回复
        try:
            reply = await self.ai.chat(chat_msg.player, chat_msg.message)
            if reply:
                # 清理回复内容（移除换行等控制台不友好的字符）
                clean_reply = reply.replace("\n", " ").replace("\r", "")
                # 游戏内通常有字符限制
                if len(clean_reply) > 200:
                    clean_reply = clean_reply[:200]
                await self.client.send_say(clean_reply)
                logger.info(f"[AI回复] -> {chat_msg.player}: {clean_reply}")
        except Exception as e:
            logger.error(f"AI 回复异常: {e}", exc_info=True)

    def _should_trigger(self, chat_msg: ChatMessage) -> bool:
        """判断是否应该触发 AI 回复"""
        mode = self.config.trigger_mode

        if mode == "all":
            return True
        elif mode == "mention":
            keyword = self.config.trigger_keyword.lower()
            return (
                keyword in chat_msg.message.lower()
                or keyword in chat_msg.player.lower()
            )
        elif mode == "keyword":
            return self.config.trigger_keyword.lower() in chat_msg.message.lower()
        return False

    def _check_cooldown(self, player: str) -> bool:
        """检查玩家冷却时间"""
        now = time.time()
        last_time = self.config.player_cooldowns.get(player, 0)
        if now - last_time < self.config.cooldown_seconds:
            return False
        self.config.player_cooldowns[player] = now
        return True

    async def _handle_admin_command(self, chat_msg: ChatMessage):
        """处理管理员命令（以 ! 开头）"""
        cmd = chat_msg.message.lower().split()[0] if chat_msg.message else ""
        prefix = self.config.command_prefix

        # 仅识别管理员命令前缀
        if not cmd.startswith(prefix):
            return

        command = cmd[len(prefix):]
        logger.info(f"[管理命令] {chat_msg.player}: {command}")

        if command == "ai-clear":
            # 清除该玩家的对话历史
            self.ai.clear_history(chat_msg.player)
            await self.client.send_say(
                f"[{self.config.bot_name}] 已清除与 {chat_msg.player} 的对话记录。"
            )
        elif command == "ai-status":
            await self.client.send_say(
                f"[{self.config.bot_name}] 运行中，"
                f"已记录 {len(self.ai._history)} 位玩家的对话。"
            )
        elif command == "ai-ignore":
            # TODO: 添加玩家到忽略列表
            pass
        elif command == "ai-help":
            await self.client.send_say(
                f"[{self.config.bot_name}] 可用命令: "
                f"!ai-clear(清除记录) !ai-status(查看状态) !ai-help(帮助)"
            )

    def _handle_stats(self, args: list):
        """处理服务器统计信息"""
        # 每 60 秒打印一次统计
        now = time.time()
        if now - self._stats_last_print < 60:
            return
        self._stats_last_print = now

        if not args:
            return
        try:
            stats = json.loads(args[0]) if isinstance(args[0], str) else args[0]
            memory_mb = stats.get("memory_bytes", 0) / (1024 * 1024)
            cpu = stats.get("cpu_absolute", 0)
            logger.info(f"[统计] CPU: {cpu:.1f}% | 内存: {memory_mb:.0f}MB")
        except (json.JSONDecodeError, TypeError):
            pass

    def _handle_status(self, args: list):
        """处理服务器状态变化"""
        if args:
            status = args[0] if isinstance(args[0], str) else str(args[0])
            logger.info(f"[状态] 服务器状态: {status}")
