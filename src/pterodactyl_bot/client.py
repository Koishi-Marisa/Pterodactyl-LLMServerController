"""
翼龙面板 API 客户端
处理 REST API 请求和 WebSocket 连接管理
"""
import logging
import time
import asyncio
import aiohttp
import json

logger = logging.getLogger(__name__)

# 翼龙面板 API 请求头
API_HEADERS = {
    "Accept": "Application/vnd.pterodactyl.v1+json",
    "Content-Type": "application/json",
}


class PterodactylClient:
    """翼龙面板客户端，管理 REST API 和 WebSocket 连接"""

    def __init__(self, config):
        self.config = config
        self.panel_url = config.panel_url.rstrip("/")
        self.api_key = config.api_key
        self.server_id = config.server_identifier

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_session: aiohttp.ClientSession | None = None
        self._session: aiohttp.ClientSession | None = None
        self._ws_token: str = ""
        self._ws_url: str = ""
        self._token_refresh_task: asyncio.Task | None = None
        self._last_token_refresh: float = 0

    @property
    def _headers(self) -> dict:
        """带 API Key 的请求头"""
        return {**API_HEADERS, "Authorization": f"Bearer {self.api_key}"}

    async def start_session(self):
        """启动 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)

    async def close(self):
        """关闭所有连接"""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._ws_session and not self._ws_session.closed:
            await self._ws_session.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("翼龙面板客户端已关闭")

    # ── REST API 方法 ──

    async def get_servers(self) -> list[dict]:
        """获取服务器列表"""
        await self.start_session()
        async with self._session.get(f"{self.panel_url}/api/client") as resp:
            resp.raise_for_status()
            data = await resp.json()
            servers = data.get("data", [])
            logger.info(f"获取到 {len(servers)} 个服务器")
            return servers

    async def get_server_resources(self) -> dict:
        """获取服务器资源使用情况"""
        await self.start_session()
        url = f"{self.panel_url}/api/client/servers/{self.server_id}/resources"
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
            attrs = data.get("attributes", {})
            logger.debug(f"服务器资源: CPU={attrs.get('cpu_absolute')}%, "
                         f"内存={attrs.get('memory_current')}/{attrs.get('memory_limit')}MB")
            return attrs

    async def send_power_signal(self, signal: str):
        """发送电源控制信号: start / stop / restart / kill"""
        await self.start_session()
        url = f"{self.panel_url}/api/client/servers/{self.server_id}/power"
        async with self._session.post(url, json={"signal": signal}) as resp:
            resp.raise_for_status()
            logger.info(f"电源信号已发送: {signal}")

    async def send_command(self, command: str):
        """通过 WebSocket 发送控制台命令"""
        if self._ws and not self._ws.closed:
            msg = json.dumps({"event": "send command", "args": [command]})
            await self._ws.send_str(msg)
            logger.debug(f"发送命令: {command}")
        else:
            logger.warning("WebSocket 未连接，无法发送命令")

    async def send_say(self, message: str):
        """发送 say 命令"""
        await self.send_command(f"say {message}")

    # ── WebSocket 方法 ──

    async def _fetch_ws_credentials(self):
        """获取 WebSocket 连接凭据（token + socket URL）"""
        await self.start_session()
        url = f"{self.panel_url}/api/client/servers/{self.server_id}/websocket"
        async with self._session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ConnectionError(
                    f"获取 WebSocket 凭据失败 (HTTP {resp.status}): {text}"
                )
            data = await resp.json()
            ws_data = data.get("data", {})
            self._ws_token = ws_data.get("token", "")
            self._ws_url = ws_data.get("socket", "")
            self._last_token_refresh = time.time()
            logger.info("WebSocket 凭据已获取")

    async def connect_websocket(self):
        """建立 WebSocket 连接并进行认证"""
        await self._fetch_ws_credentials()

        if not self._ws_url or not self._ws_token:
            raise ConnectionError("WebSocket URL 或 Token 为空")

        # 关闭旧连接
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._ws_session and not self._ws_session.closed:
            await self._ws_session.close()

        # Wings 节点需要:
        # 1. Origin 头匹配面板地址（CORS 校验）
        # 2. Authorization 头携带 JWT token（不是面板 API Key）
        # 不能用 _session 的默认头，因为里面有面板 API Key 会触发 403
        ws_headers = {
            "Origin": self.panel_url,
            "Authorization": f"Bearer {self._ws_token}",
        }

        logger.info(f"正在连接 WebSocket: {self._ws_url}")
        # 使用独立会话，避免面板 API Key 污染请求头
        self._ws_session = aiohttp.ClientSession()
        try:
            self._ws = await self._ws_session.ws_connect(
                self._ws_url,
                headers=ws_headers,
                heartbeat=self.config.ping_interval,
            )
        except aiohttp.WSServerHandshakeError as e:
            # 如果带 Origin 仍然 403，尝试不带 Origin（某些 Wings 配置不校验）
            if e.status == 403 and "Origin" in ws_headers:
                logger.warning(
                    "首次连接被拒 (403)，尝试不带 Origin 头重连..."
                )
                del ws_headers["Origin"]
                try:
                    self._ws = await self._ws_session.ws_connect(
                        self._ws_url,
                        headers=ws_headers,
                        heartbeat=self.config.ping_interval,
                    )
                except Exception:
                    await self._ws_session.close()
                    raise
            else:
                await self._ws_session.close()
                raise

        # 发送认证消息
        auth_msg = json.dumps({"event": "auth", "args": [self._ws_token]})
        await self._ws.send_str(auth_msg)
        logger.info("WebSocket 认证消息已发送")

        # 启动 token 定时刷新任务
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
        self._token_refresh_task = asyncio.create_task(
            self._refresh_token_loop()
        )

    async def _refresh_token_loop(self):
        """定时刷新 WebSocket JWT token（10分钟有效期）"""
        while True:
            await asyncio.sleep(self.config.ws_token_refresh_interval)
            try:
                await self._fetch_ws_credentials()
                # 发送新的 auth 消息
                if self._ws and not self._ws.closed:
                    auth_msg = json.dumps(
                        {"event": "auth", "args": [self._ws_token]}
                    )
                    await self._ws.send_str(auth_msg)
                    logger.info("WebSocket Token 已刷新")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Token 刷新失败: {e}")

    async def reconnect(self):
        """断线重连"""
        logger.warning("正在重连 WebSocket...")
        try:
            await self.connect_websocket()
            logger.info("WebSocket 重连成功")
            return True
        except Exception as e:
            logger.error(f"重连失败: {e}")
            return False

    async def recv_message(self) -> dict | None:
        """接收一条 WebSocket 消息"""
        if self._ws is None or self._ws.closed:
            return None
        try:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                return json.loads(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket 错误: {self._ws.exception()}")
                return None
            elif msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
            ):
                logger.warning("WebSocket 连接已关闭")
                return None
        except Exception as e:
            logger.error(f"接收消息异常: {e}")
            return None
        return None
