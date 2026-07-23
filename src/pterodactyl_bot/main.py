"""
Pterodactyl AI Chat Bot - 翼龙面板 AI 聊天机器人
主入口：启动 WebSocket 连接，监听控制台，与玩家互动
"""
import asyncio
import logging
import signal
import sys

from .config import Config
from .client import PterodactylClient
from .ai_chat import AIChat
from .parser import MessageParser
from .handler import EventHandler

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """配置日志"""
    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


class PterodactylBot:
    """翼龙面板 AI 聊天机器人"""

    def __init__(self, config: Config):
        self.config = config
        self.client = PterodactylClient(config)
        self.ai = AIChat(config)
        self.parser = MessageParser()
        self.handler = EventHandler(self.client, self.ai, self.parser)
        self._running = False

    async def start(self):
        """启动机器人"""
        logger.info("=" * 50)
        logger.info("  翼龙面板 AI 聊天机器人")
        logger.info("=" * 50)
        logger.info(f"面板地址: {self.config.panel_url}")
        logger.info(f"服务器 ID: {self.config.server_identifier}")
        logger.info(f"AI 模型: {self.config.ai_model}")
        logger.info(f"触发模式: {self.config.trigger_mode}")
        logger.info(f"机器人名称: {self.config.bot_name}")
        logger.info("=" * 50)

        self._running = True

        while self._running:
            try:
                logger.info("正在连接翼龙面板 WebSocket...")
                await self.client.connect_websocket()
                logger.info("连接成功，开始监听控制台...")

                await self._listen_loop()

            except ConnectionError as e:
                logger.error(f"连接错误: {e}")
            except Exception as e:
                logger.error(f"运行异常: {e}", exc_info=True)

            if self._running:
                delay = self.config.ws_reconnect_delay
                logger.info(f"{delay} 秒后重连...")
                await asyncio.sleep(delay)

    async def _listen_loop(self):
        """WebSocket 消息监听主循环"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self.client.recv_message(),
                    timeout=1.0,
                )
                if message is not None:
                    await self.handler.handle_ws_message(message)
                elif self.client._ws is None or self.client._ws.closed:
                    logger.warning("WebSocket 连接已断开")
                    break
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"消息处理异常: {e}")
                await asyncio.sleep(0.5)

    async def stop(self):
        """停止机器人"""
        logger.info("正在停止机器人...")
        self._running = False
        await self.client.close()
        logger.info("机器人已停止")

    async def _shutdown(self, signum=None):
        """优雅关闭"""
        await self.stop()


def main():
    """主函数入口"""
    config = Config.from_env()

    # 验证配置
    errors = config.validate()
    if errors:
        print("配置错误:")
        for err in errors:
            print(f"  - {err}")
        print("\n请设置环境变量后重试。参考 .env.example 文件。")
        sys.exit(1)

    # 配置日志
    setup_logging(config.log_level)

    # 创建并启动机器人
    bot = PterodactylBot(config)

    # 注册信号处理
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(bot.stop()))
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        loop.run_until_complete(bot.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
