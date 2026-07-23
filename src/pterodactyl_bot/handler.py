"""
事件处理模块
处理 WebSocket 消息，管理聊天交互流程、定时活跃气氛、控制台调试
"""
import asyncio
import json
import logging
import time

from .client import PterodactylClient
from .ai_chat import AIChat
from .parser import MessageParser, ChatMessage, parse_console_ai

logger = logging.getLogger(__name__)


class EventHandler:
    """事件处理器，协调 WebSocket 消息与 AI 回复"""

    def __init__(self, client: PterodactylClient, ai: AIChat, parser: MessageParser):
        self.client = client
        self.ai = ai
        self.parser = parser
        self.config = client.config
        self._stats_last_print = time.time()
        self._auto_chat_task: asyncio.Task | None = None
        self._auto_chat_running = False

    # ── 公开方法 ──

    def start_auto_chat(self):
        """启动定时活跃气氛任务"""
        if not self.config.auto_chat_enabled:
            logger.info("定时活跃气氛已禁用")
            return
        if self._auto_chat_running:
            return
        self._auto_chat_running = True
        self._auto_chat_task = asyncio.create_task(self._auto_chat_loop())
        logger.info(
            f"定时活跃气氛已启动，间隔 {self.config.auto_chat_interval} 秒"
        )

    def stop_auto_chat(self):
        """停止定时活跃气氛任务"""
        self._auto_chat_running = False
        if self._auto_chat_task and not self._auto_chat_task.done():
            self._auto_chat_task.cancel()
        logger.info("定时活跃气氛已停止")

    async def _auto_chat_loop(self):
        """定时活跃气氛主循环"""
        await asyncio.sleep(self.config.auto_chat_interval)
        while self._auto_chat_running:
            try:
                reply = await self.ai.chat(
                    "_auto_chat", self.config.auto_chat_prompt
                )
                if reply:
                    clean = reply.replace("\n", " ").replace("\r", "")
                    if len(clean) > 100:
                        clean = clean[:100]
                    await self.client.send_say(clean)
                    logger.info(f"[定时活跃] {clean}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时活跃气氛异常: {e}", exc_info=True)
            await asyncio.sleep(self.config.auto_chat_interval)

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
            # 发送连接成功消息（如果配置了）
            msg = self.config.connect_success_message
            if msg:
                try:
                    await self.client.send_say(msg)
                    logger.info(f"连接成功消息已发送: {msg}")
                except Exception as e:
                    logger.error(f"发送连接成功消息失败: {e}")
            # 启动定时活跃气氛
            self.start_auto_chat()
        elif event == "jwt error":
            logger.error(f"JWT 认证错误: {args}")
        elif event == "throttled":
            logger.warning(f"消息频率超限: {args}")

    # ── 控制台输出处理 ──

    async def _handle_console_output(self, args: list):
        """处理控制台输出，检测玩家聊天和 @AI 调试指令"""
        if not args:
            return

        text = args[0] if isinstance(args[0], str) else str(args[0])
        logger.debug(f"控制台: {text}")

        # 优先检测 @AI 控制台调试指令
        console_ai_msg = parse_console_ai(text)
        if console_ai_msg is not None:
            await self._handle_console_ai(console_ai_msg)
            return

        # 解析玩家聊天消息
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
        await self._ai_reply(chat_msg.player, chat_msg.message)

    async def _handle_console_ai(self, message: str):
        """处理控制台 @AI 调试指令，直接将消息发送给 AI"""
        logger.info(f"[控制台调试] @AI: {message}")
        try:
            reply = await self.ai.chat("_console", message)
            if reply:
                clean_reply = reply.replace("\n", " ").replace("\r", "")
                if len(clean_reply) > 200:
                    clean_reply = clean_reply[:200]
                await self.client.send_say(clean_reply)
                logger.info(f"[控制台AI回复] {clean_reply}")
        except Exception as e:
            logger.error(f"控制台 AI 回复异常: {e}", exc_info=True)

    async def _ai_reply(self, player: str, message: str):
        """调用 AI 获取回复并发送"""
        try:
            reply = await self.ai.chat(player, message)
            if reply:
                clean_reply = reply.replace("\n", " ").replace("\r", "")
                if len(clean_reply) > 200:
                    clean_reply = clean_reply[:200]
                await self.client.send_say(clean_reply)
                logger.info(f"[AI回复] -> {player}: {clean_reply}")
        except Exception as e:
            logger.error(f"AI 回复异常: {e}", exc_info=True)

    # ── 触发条件与冷却 ──

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

    # ── 管理员命令 ──

    async def _handle_admin_command(self, chat_msg: ChatMessage):
        """处理管理员命令（以 ! 开头）"""
        cmd = chat_msg.message.lower().split()[0] if chat_msg.message else ""
        prefix = self.config.command_prefix

        if not cmd.startswith(prefix):
            return

        command = cmd[len(prefix):]
        logger.info(f"[管理命令] {chat_msg.player}: {command}")

        if command == "ai-clear":
            self.ai.clear_history(chat_msg.player)
            await self.client.send_say(
                f"已清除与 {chat_msg.player} 的对话记录。"
            )
        elif command == "ai-status":
            await self.client.send_say(
                f"运行中，已记录 {len(self.ai._history)} 位玩家的对话。"
            )
        elif command == "ai-ignore":
            pass
        elif command == "ai-help":
            await self.client.send_say(
                "可用命令: !ai-clear(清除记录) !ai-status(查看状态) !ai-help(帮助)"
            )

    # ── 服务器状态处理 ──

    def _handle_stats(self, args: list):
        """处理服务器统计信息"""
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